"""Real DB protocol tests, not evidence of a real model's content-safety quality."""

from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from local_environment import ADMIN_DSN, DB_PORT
from sqlalchemy import create_engine
from test_identity_integration import settings
from test_review_integration import FixtureModeration, decision, headers, start, submitted

from cce.api_entrypoint import create_app
from cce.modules.contributions.moderation_worker import ScanEvaluation, run_once

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
