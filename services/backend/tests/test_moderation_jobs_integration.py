"""Real DB protocol tests, not evidence of a real model's content-safety quality."""

import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import UUID, uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from local_environment import ADMIN_DSN, DB_PORT
from local_tools import pnpm_command
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError
from test_identity_integration import settings
from test_moderation_process import fixture_context
from test_review_integration import FixtureModeration, decision, headers, start, submitted

from cce.api_entrypoint import create_app
from cce.infrastructure.database import create_database
from cce.modules.contributions import review as review_module
from cce.modules.contributions.moderation_process import ProcessLocalScanner
from cce.modules.contributions.moderation_worker import ScanEvaluation, run_once
from cce.modules.identity.authentication import TokenVerifier
from cce.modules.identity.repository import actor_transaction

pytestmark = pytest.mark.integration


def worker():
    return psycopg.connect(
        host="127.0.0.1",
        port=DB_PORT,
        dbname="postgres",
        user="cce_worker_cpu",
        password="cce-local-worker-only",
        connect_timeout=3,
    )


def claim(auth_user_id=None):
    with worker() as db:
        if auth_user_id is None:
            return db.execute("select ops_private.claim_moderation()").fetchone()[0]
        return db.execute(
            "select ops_private.claim_moderation_for_worker(%s)", (auth_user_id,)
        ).fetchone()[0]


def finish(work, verdict="PASS", error=None, **changes):
    args = {
        "job": work["job_id"],
        "attempt": work["attempt_id"],
        "source": work["source_sha256"],
        "avatar": work["avatar_sha256"],
        "verdict": verdict,
        "error": error,
    } | changes
    with worker() as db:
        return db.execute(
            "select ops_private.finish_moderation(%(job)s,%(attempt)s,%(source)s,%(avatar)s,"
            "%(verdict)s,'protocol-test-only','protocol-test-v1','DB protocol test',%(error)s)",
            args,
        ).fetchone()[0]


def retry(api, item, owner):
    return api.post(
        f"/reviews/{item['id']}/moderation/retry",
        headers=headers(owner),
        json={"expected_version": item["version"], "revision_id": item["revision_id"]},
    )


def detail(api, item, owner):
    response = api.get(f"/reviews/{item['id']}", headers=headers(owner))
    assert response.status_code == 200
    return response.json()


@pytest.mark.skipif(os.environ.get("CCE_E2E_REVIEW") != "1", reason="Requires running test web/API")
def test_moderation_retry_browser_flow(review_accounts):
    (owner, contributor), _ = review_accounts
    with TestClient(create_app(settings())) as api:
        report = start(api, submitted(api, contributor), owner)
        assert report["moderation_job"]["state"] == "PENDING"
        work = claim()
        assert work["job_id"] == report["moderation_job"]["id"]
        assert finish(work, "ERROR", "MODEL_UNAVAILABLE") is True
        item = detail(api, report["submission"], owner)
        assert item["moderation_job"]["state"] == "ERROR"
    subprocess.run(
        [*pnpm_command(), "--filter", "@cce/web", "test:e2e", "moderation-retry.spec.ts"],
        cwd=Path(__file__).resolve().parents[3],
        env={
            **os.environ,
            "CCE_E2E_OWNER_EMAIL": owner["email"],
            "CCE_E2E_OWNER_PASSWORD": owner["password"],
            "CCE_E2E_MODERATION_SUBMISSION": report["submission"]["id"],
        },
        check=True,
        timeout=120,
    )


def test_pending_claim_once_retry_and_late_result(review_accounts):
    (owner, contributor), _ = review_accounts
    with TestClient(create_app(settings())) as api:
        report = start(api, submitted(api, contributor), owner)
        item = report["submission"]
        assert report["moderation_job"]["state"] == "PENDING"
        assert retry(api, item, contributor).status_code == 403
        assert (
            retry(api, item, owner).json()["moderation_job"]["id"] == report["moderation_job"]["id"]
        )
        with ThreadPoolExecutor(max_workers=2) as pool:
            claims = list(pool.map(lambda _: claim(), range(2)))
        assert sum(work is not None for work in claims) == 1
        work = next(work for work in claims if work)
        assert work["revision_id"] == item["revision_id"]
        assert finish(work, "ERROR", "MODEL_UNAVAILABLE") is True
        assert finish(work) is False
        failed = detail(api, item, owner)
        assert failed["moderation"] is None
        assert failed["moderation_job"]["attempts"][0]["error_code"] == "MODEL_UNAVAILABLE"
        assert (
            api.post(
                f"/reviews/{item['id']}/decision", headers=headers(owner), json=decision(item)
            ).status_code
            == 409
        )
        assert retry(api, item, owner).status_code == 200
        with psycopg.connect(ADMIN_DSN) as db:
            events = db.execute(
                "select actor_user_id,previous_state,previous_attempt_number "
                "from ops_private.moderation_retry_events where job_id=%s "
                "order by requested_at,id",
                (work["job_id"],),
            ).fetchall()
        assert len(events) == 2
        assert {row[1] for row in events} == {"PENDING", "ERROR"}
        assert all(row[0] == UUID(owner["id"]) for row in events)
        second = claim()
        assert second["attempt_id"] != work["attempt_id"]
        assert second["source_sha256"] == work["source_sha256"]
        assert finish(work) is False
        assert finish(second, "BLOCK") is True
        assert retry(api, item, owner).status_code == 409
        assert (
            api.post(
                f"/reviews/{item['id']}/decision",
                headers=headers(owner),
                json=decision(item, review_accepted=True),
            ).status_code
            == 409
        )
        final = detail(api, item, owner)
        assert final["moderation"]["result"] == "BLOCK"
        assert [a["state"] for a in final["moderation_job"]["attempts"]] == ["SUCCEEDED", "ERROR"]


@pytest.mark.parametrize(
    ("orphan_state", "job_counter"), [("RUNNING", 0), ("RUNNING", 1), ("ERROR", 0)]
)
def test_inconsistent_pending_job_does_not_block_queue(review_accounts, orphan_state, job_counter):
    (owner, contributor), _ = review_accounts
    with TestClient(create_app(settings())) as api:
        broken = start(api, submitted(api, contributor), owner)
        healthy = start(api, submitted(api, contributor), owner)
        job_id = broken["moderation_job"]["id"]
        with psycopg.connect(ADMIN_DSN) as db:
            orphan_id = db.execute(
                "insert into ops_private.moderation_attempts "
                "(job_id,attempt_number,state,finished_at) "
                "values (%s,1,%s,case when %s='ERROR' then now() else null end) returning id",
                (job_id, orphan_state, orphan_state),
            ).fetchone()[0]
            source_sha256, avatar_sha256 = db.execute(
                "update ops_private.moderation_jobs set attempt_number=%s, "
                "requested_at=now()-interval '1 minute' where id=%s "
                "returning source_sha256,avatar_sha256",
                (job_counter, job_id),
            ).fetchone()
        orphan_work = {
            "job_id": job_id,
            "attempt_id": str(orphan_id),
            "source_sha256": source_sha256,
            "avatar_sha256": avatar_sha256,
        }
        work = claim()
        assert work["job_id"] == healthy["moderation_job"]["id"]
        failed = detail(api, broken["submission"], owner)["moderation_job"]
        assert failed["state"] == "ERROR"
        assert failed["error_code"] == "JOB_INCONSISTENT"
        assert failed["attempt_number"] == 1
        assert failed["attempts"][0]["state"] == "ERROR"
        if orphan_state == "RUNNING":
            assert failed["attempts"][0]["error_code"] == "JOB_INCONSISTENT"
        assert finish(orphan_work) is False
        assert finish(work) is True
        assert retry(api, broken["submission"], owner).status_code == 200
        recovered = claim()
        assert recovered["job_id"] == job_id
        assert recovered["attempt_id"] != str(orphan_id)
        assert finish(orphan_work) is False
        assert finish(recovered) is True
        assert detail(api, broken["submission"], owner)["moderation_job"]["attempt_number"] == 2


def test_retry_audit_uses_locked_state_not_api_snapshot(review_accounts, monkeypatch):
    (owner, contributor), _ = review_accounts
    config = settings()
    with TestClient(create_app(config)) as api:
        report = start(api, submitted(api, contributor), owner)
        original = review_module.read_review
        claimed = []

        def read_then_claim(connection, submission_id):
            snapshot = original(connection, submission_id)
            if not claimed:
                assert snapshot.moderation_job.state == "PENDING"
                claimed.append(claim())
            return snapshot

        monkeypatch.setattr(review_module, "read_review", read_then_claim)
        response = retry(api, report["submission"], owner)
        assert response.status_code == 200
        assert response.json()["moderation_job"]["state"] == "RUNNING"
        engine = create_database(config, owner_commands=True)
        try:
            with actor_transaction(engine, TokenVerifier(config).verify(owner["token"])) as db:
                assert db.execute(
                    text(
                        "select actor_user_id,previous_state,previous_attempt_number "
                        "from ops_private.moderation_retry_events where job_id=:job"
                    ),
                    {"job": report["moderation_job"]["id"]},
                ).fetchall() == [(UUID(owner["id"]), "RUNNING", 1)]
            with (
                pytest.raises(DBAPIError) as rejected,
                actor_transaction(engine, TokenVerifier(config).verify(owner["token"])) as db,
            ):
                db.execute(
                    text(
                        "insert into ops_private.moderation_retry_events "
                        "(job_id,actor_user_id,previous_state,previous_attempt_number) "
                        "values (:job,:actor,'ERROR',999)"
                    ),
                    {"job": report["moderation_job"]["id"], "actor": UUID(owner["id"])},
                )
            assert rejected.value.orig.sqlstate == "42501"
        finally:
            engine.dispose()
        assert finish(claimed[0]) is True


def test_withdraw_during_scan_cannot_publish_result(review_accounts):
    (owner, contributor), _ = review_accounts
    with TestClient(create_app(settings())) as api:
        item = start(api, submitted(api, contributor), owner)["submission"]
        work = claim()
        response = api.post(
            f"/contributions/{item['id']}/withdraw",
            headers=headers(contributor),
            json={"expected_version": item["version"]},
        )
        assert response.status_code == 200
        assert finish(work) is False
        report = detail(api, item, owner)
        assert report["moderation"] is None
        assert report["moderation_job"]["state"] == "CANCELLED"
        assert retry(api, item, owner).status_code == 409


def test_expired_lease_and_source_mismatch_fail_closed(review_accounts):
    (owner, contributor), _ = review_accounts
    with TestClient(create_app(settings())) as api:
        item = start(api, submitted(api, contributor), owner)["submission"]
        work = claim()
        with pytest.raises(psycopg.errors.CheckViolation):
            finish(work, source="0" * 64)
        with pytest.raises(psycopg.errors.CheckViolation):
            finish(work, avatar="0" * 64)
        assert finish(work, attempt=str(uuid4())) is False
        with psycopg.connect(ADMIN_DSN) as db:
            db.execute(
                "update ops_private.moderation_jobs set lease_until=now()-interval '1 second' "
                "where id=%s",
                (work["job_id"],),
            )
        assert finish(work) is False
        assert claim() is None
        report = detail(api, item, owner)
        assert report["moderation_job"]["error_code"] == "LEASE_EXPIRED"
        assert retry(api, item, owner).status_code == 200
        replacement = claim()
        assert finish(replacement, "REVIEW") is True
        assert (
            api.post(
                f"/reviews/{item['id']}/decision", headers=headers(owner), json=decision(item)
            ).status_code
            == 409
        )
        assert (
            api.post(
                f"/reviews/{item['id']}/decision",
                headers=headers(owner),
                json=decision(item, review_accepted=True),
            ).status_code
            == 200
        )


def test_legacy_error_is_preserved_and_retryable(review_accounts):
    (owner, contributor), _ = review_accounts
    with TestClient(create_app(settings(), moderation=FixtureModeration("ERROR"))) as api:
        item = start(api, submitted(api, contributor), owner)["submission"]
    with TestClient(create_app(settings())) as api:
        report = retry(api, item, owner).json()
        assert report["moderation_job"]["attempts"][0]["error_code"] == "LEGACY_ERROR"
        with psycopg.connect(ADMIN_DSN) as db:
            assert db.execute(
                "select previous_state,previous_attempt_number "
                "from ops_private.moderation_retry_events where job_id=%s",
                (report["moderation_job"]["id"],),
            ).fetchall() == [("LEGACY_ERROR", 0)]
        work = claim()
        assert finish(work) is True
        assert detail(api, item, owner)["moderation"]["result"] == "PASS"
        assert len(detail(api, item, owner)["moderation_job"]["attempts"]) == 2


def test_worker_cannot_read_tables_or_enqueue():
    for statement in (
        "select * from ops_private.moderation_jobs",
        "select * from ops_private.submission_moderation",
        "select ops_private.enqueue_moderation(gen_random_uuid(),gen_random_uuid())",
    ):
        with worker() as db, pytest.raises(psycopg.errors.InsufficientPrivilege):
            db.execute(statement)


def test_worker_releases_database_connection_before_scanning(review_accounts):
    (owner, contributor), _ = review_accounts
    engine = create_engine(
        f"postgresql+psycopg://cce_worker_cpu:cce-local-worker-only@127.0.0.1:{DB_PORT}/postgres"
    )

    class Scanner:
        def evaluate(self, work):
            assert engine.pool.checkedout() == 0
            return ScanEvaluation(
                result="REVIEW",
                provider="protocol-test-only",
                policy_version="protocol-test-v1",
                text_checked=True,
            )

    try:
        with TestClient(create_app(settings())) as api:
            item = start(api, submitted(api, contributor), owner)["submission"]
            assert run_once(engine, Scanner()) is True
            assert run_once(engine, Scanner()) is False
            report = detail(api, item, owner)
            assert report["moderation"]["result"] == "REVIEW"
            assert report["moderation_job"]["state"] == "SUCCEEDED"
    finally:
        engine.dispose()


def test_process_timeout_persists_error_and_owner_retry_keeps_attempt_history(review_accounts):
    (owner, contributor), _ = review_accounts
    engine = create_engine(
        f"postgresql+psycopg://cce_worker_cpu:cce-local-worker-only@127.0.0.1:{DB_PORT}/postgres",
        pool_size=1,
        max_overflow=0,
    )
    scanner = ProcessLocalScanner(fixture_context, ("hang",), timeout_seconds=0.15)
    try:
        scanner.prepare()
        with TestClient(create_app(settings())) as api:
            item = start(api, submitted(api, contributor), owner)["submission"]
            assert run_once(engine, scanner) is True
            failed = detail(api, item, owner)
            job = failed["moderation_job"]
            assert job["state"] == "ERROR"
            assert job["error_code"] == "MODEL_TIMEOUT"
            assert job["attempts"][0]["error_code"] == "MODEL_TIMEOUT"
            assert failed["moderation"] is None
            assert scanner._process is None
            assert engine.pool.checkedout() == 0
            assert (
                api.post(
                    f"/reviews/{item['id']}/decision", headers=headers(owner), json=decision(item)
                ).status_code
                == 409
            )
            assert retry(api, item, owner).status_code == 200
            scanner.args = ("ok",)
            scanner.timeout_seconds = 5
            scanner.prepare()
            assert run_once(engine, scanner) is True
            recovered = detail(api, item, owner)
            assert recovered["moderation_job"]["state"] == "SUCCEEDED"
            assert recovered["moderation"]["result"] == "REVIEW"
            attempts = recovered["moderation_job"]["attempts"]
            assert [attempt["state"] for attempt in attempts] == ["SUCCEEDED", "ERROR"]
            assert attempts[1]["error_code"] == "MODEL_TIMEOUT"
    finally:
        try:
            scanner.close()
        finally:
            engine.dispose()


def test_withdraw_before_claim_cancels_pending_job(review_accounts):
    (owner, contributor), _ = review_accounts
    with TestClient(create_app(settings())) as api:
        item = start(api, submitted(api, contributor), owner)["submission"]
        response = api.post(
            f"/contributions/{item['id']}/withdraw",
            headers=headers(contributor),
            json={"expected_version": item["version"]},
        )
        assert response.status_code == 200
        assert claim() is None
        assert detail(api, item, owner)["moderation_job"]["state"] == "CANCELLED"
