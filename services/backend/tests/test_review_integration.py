import os
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import UUID, uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from local_environment import ADMIN_DSN
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from test_contributions_integration import proposal
from test_identity_integration import settings

from cce.api_entrypoint import create_app
from cce.infrastructure.database import create_database
from cce.modules.contributions.moderation import ModerationOutcome
from cce.modules.contributions.schemas import CharacterProposal
from cce.modules.identity.authentication import TokenVerifier
from cce.modules.identity.repository import actor_transaction

pytestmark = pytest.mark.integration


class FixtureModeration:
    def __init__(self, verdict: str = "PASS") -> None:
        self.verdict = verdict

    def scan(self, definition: CharacterProposal) -> ModerationOutcome:
        assert self.verdict in {"PASS", "REVIEW", "BLOCK", "ERROR"}
        return ModerationOutcome(
            self.verdict,
            "test-fixture",
            "fixture-v1",
            True,
            "Deterministic test result; not a content safety scan.",
        )  # type: ignore[arg-type]


def headers(user: dict[str, str]) -> dict[str, str]:
    return {"Authorization": f"Bearer {user['token']}"}


def submitted(api: TestClient, contributor: dict[str, str]) -> dict:
    response = api.post(
        "/contributions",
        headers=headers(contributor),
        json={"creation_key": str(uuid4()), "definition": proposal()},
    )
    assert response.status_code == 200, response.text
    item = response.json()
    result = api.post(
        f"/contributions/{item['id']}/submit",
        headers=headers(contributor),
        json={"expected_version": item["version"]},
    )
    assert result.status_code == 200, result.text
    return result.json()


def start(api: TestClient, item: dict, owner: dict[str, str]) -> dict:
    response = api.post(
        f"/reviews/{item['id']}/start",
        headers=headers(owner),
        json={"expected_version": item["version"], "revision_id": item["revision_id"]},
    )
    assert response.status_code == 200, response.text
    return response.json()


def decision(item: dict, result: str = "APPROVED", **kwargs) -> dict:
    return {
        "expected_version": item["version"],
        "revision_id": item["revision_id"],
        "decision": result,
        "reason": "Integration review reason",
        **kwargs,
    }


def test_fixture_approval_requires_explicit_test_database_policy(review_accounts) -> None:
    (owner, contributor), _ = review_accounts
    config = settings()
    with TestClient(create_app(config, moderation=FixtureModeration())) as api:
        item = start(api, submitted(api, contributor), owner)["submission"]
        actor = TokenVerifier(config).verify(owner["token"])
        # Test the disabled policy in the same transaction as the raw Owner
        # command. No committed global switch can race other fixture approvals;
        # the rejected command rolls the local policy change back as well.
        with (
            pytest.raises(
                psycopg.errors.CheckViolation,
                match="Fixture moderation cannot approve a real submission",
            ),
            psycopg.connect(ADMIN_DSN) as admin,
        ):
            admin.execute(
                "update ops_private.fixture_approval_policy set enabled=false where singleton"
            )
            with psycopg.connect(ADMIN_DSN) as observer:
                assert observer.execute(
                    "select enabled from ops_private.fixture_approval_policy where singleton"
                ).fetchone() == (True,)
            admin.execute(
                "select set_config('cce.actor_id',%s,true),set_config('cce.session_id',%s,true)",
                (str(actor.user_id), str(actor.session_id)),
            )
            admin.execute("set local role cce_engine")
            assert admin.execute("select current_user").fetchone() == ("cce_engine",)
            admin.execute(
                "update public.character_submissions set status='APPROVED', "
                "version=version+1 where id=%s",
                (item["id"],),
            )
        assert (
            api.get(f"/reviews/{item['id']}", headers=headers(owner)).json()["submission"]["status"]
            == "UNDER_REVIEW"
        )
        assert (
            api.post(
                f"/reviews/{item['id']}/decision", headers=headers(owner), json=decision(item)
            ).status_code
            == 200
        )


def test_owner_decision_cannot_commit_without_feedback_and_event(review_accounts) -> None:
    (owner, contributor), _ = review_accounts
    config = settings()
    with TestClient(create_app(config, moderation=FixtureModeration())) as api:
        item = start(api, submitted(api, contributor), owner)["submission"]
        engine = create_database(config, owner_commands=True)
        actor = TokenVerifier(config).verify(owner["token"])
        try:
            with pytest.raises(DBAPIError) as rejected, actor_transaction(engine, actor) as db:
                db.execute(
                    text(
                        "update public.character_submissions set status='APPROVED', "
                        "version=version+1 where id=:id"
                    ),
                    {"id": UUID(item["id"])},
                )
            assert rejected.value.orig.sqlstate == "23514"
        finally:
            engine.dispose()
        assert (
            api.get(f"/reviews/{item['id']}", headers=headers(owner)).json()["submission"]["status"]
            == "UNDER_REVIEW"
        )


def test_review_revision_history_and_authorization(review_accounts) -> None:
    (owner, contributor), auth = review_accounts
    with TestClient(create_app(settings(), moderation=FixtureModeration())) as api:
        assert api.get("/reviews").status_code == 401
        assert api.get("/reviews", headers=headers(contributor)).status_code == 403
        item = submitted(api, contributor)
        contributor_path = f"/contributions/{item['id']}"
        owner_path = f"/reviews/{item['id']}"
        assert api.get(contributor_path, headers=headers(owner)).status_code == 404
        first_revision = item["revision_id"]
        report = start(api, item, owner)
        assert report["moderation"]["is_fixture"] is True
        item = report["submission"]
        assert (
            api.post(
                owner_path + "/decision", headers=headers(contributor), json=decision(item)
            ).status_code
            == 403
        )
        assert (
            api.post(
                owner_path + "/decision",
                headers=headers(owner),
                json=decision(item, "CHANGES_REQUESTED", reason="  "),
            ).status_code
            == 422
        )
        response = api.post(
            owner_path + "/decision",
            headers=headers(owner),
            json=decision(item, "CHANGES_REQUESTED"),
        )
        assert response.status_code == 200, response.text
        item = response.json()
        assert (
            api.get(contributor_path + "/history", headers=headers(contributor)).json()["feedback"][
                0
            ]["decision"]
            == "CHANGES_REQUESTED"
        )
        item = api.post(
            contributor_path + "/revise",
            headers=headers(contributor),
            json={"expected_version": item["version"]},
        ).json()
        item = api.put(
            contributor_path,
            headers=headers(contributor),
            json={
                "expected_version": item["version"],
                "definition": {**proposal(), "name": "Revised Deniz"},
            },
        ).json()
        item = api.post(
            contributor_path + "/submit",
            headers=headers(contributor),
            json={"expected_version": item["version"]},
        ).json()
        assert item["revision_id"] != first_revision
        item = start(api, item, owner)["submission"]
        assert (
            api.post(
                owner_path + "/decision",
                headers=headers(owner),
                json=decision(item, revision_id=first_revision),
            ).status_code
            == 409
        )
        response = api.post(owner_path + "/decision", headers=headers(owner), json=decision(item))
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "APPROVED"
        assert (
            api.post(
                owner_path + "/decision", headers=headers(owner), json=decision(item)
            ).status_code
            == 409
        )
        history = api.get(contributor_path + "/history", headers=headers(contributor)).json()
        assert [r["revision_number"] for r in history["revisions"]] == [1, 2]
        assert history["revisions"][0]["definition"]["name"] == "Deniz"
        assert history["revisions"][1]["definition"]["name"] == "Revised Deniz"
        assert len(history["feedback"]) == 2
        direct = auth.post("/rest/v1/submission_feedback", headers=headers(contributor), json={})
        assert direct.status_code in {401, 403}
        with psycopg.connect(ADMIN_DSN) as db:
            assert db.execute(
                "select actor_user_id from ops_private.contribution_events "
                "where submission_id=%s and action='APPROVED'",
                (UUID(item["id"]),),
            ).fetchone() == (UUID(owner["id"]),)


@pytest.mark.parametrize("verdict", ["BLOCK", "ERROR", "REVIEW"])
def test_moderation_gates_and_reasoned_rejection(review_accounts, verdict: str) -> None:
    (owner, contributor), _ = review_accounts
    with TestClient(create_app(settings(), moderation=FixtureModeration(verdict))) as api:
        item = start(api, submitted(api, contributor), owner)["submission"]
        path = f"/reviews/{item['id']}/decision"
        assert api.post(path, headers=headers(owner), json=decision(item)).status_code == 409
        if verdict == "REVIEW":
            assert (
                api.post(
                    path, headers=headers(owner), json=decision(item, review_accepted=True)
                ).status_code
                == 200
            )
        else:
            assert (
                api.post(
                    path, headers=headers(owner), json=decision(item, review_accepted=True)
                ).status_code
                == 409
            )
            assert (
                api.post(path, headers=headers(owner), json=decision(item, "REJECTED")).status_code
                == 200
            )


def test_unconfigured_moderation_fails_closed(review_accounts) -> None:
    (owner, contributor), _ = review_accounts
    with TestClient(create_app(settings())) as api:
        report = start(api, submitted(api, contributor), owner)
        assert report["moderation"] is None
        assert report["moderation_job"]["state"] == "PENDING"
        item = report["submission"]
        assert (
            api.post(
                f"/reviews/{item['id']}/decision", headers=headers(owner), json=decision(item)
            ).status_code
            == 409
        )


def test_withdraw_approval_race_and_engine_rls(review_accounts) -> None:
    (owner, contributor), auth = review_accounts
    config = settings()
    with TestClient(create_app(config, moderation=FixtureModeration())) as api:
        item = start(api, submitted(api, contributor), owner)["submission"]
        with ThreadPoolExecutor(max_workers=2) as pool:
            approve = pool.submit(
                api.post,
                f"/reviews/{item['id']}/decision",
                headers=headers(owner),
                json=decision(item),
            )
            withdraw = pool.submit(
                api.post,
                f"/contributions/{item['id']}/withdraw",
                headers=headers(contributor),
                json={"expected_version": item["version"]},
            )
        assert sorted([approve.result().status_code, withdraw.result().status_code]) == [200, 409]
        engine = create_database(config, owner_commands=True)
        api_engine = create_database(config)
        verifier = TokenVerifier(config)
        try:
            # Even the privileged command connection requires a currently authorized Owner.
            with actor_transaction(engine, verifier.verify(contributor["token"])) as connection:
                assert (
                    connection.execute(text("select * from public.character_submissions")).all()
                    == []
                )
            with actor_transaction(api_engine, verifier.verify(contributor["token"])) as connection:
                with pytest.raises(DBAPIError):
                    connection.execute(text("set role cce_engine"))
            with engine.begin() as connection:
                assert (
                    connection.execute(text("select * from public.character_submissions")).all()
                    == []
                )
            assert (
                auth.post("/auth/v1/logout?scope=local", headers=headers(owner)).status_code == 204
            )
            assert api.get("/reviews", headers=headers(owner)).status_code == 401
        finally:
            engine.dispose()
            api_engine.dispose()


@pytest.mark.skipif(os.environ.get("CCE_E2E_REVIEW") != "1", reason="Requires running test web/API")
def test_review_browser_flow(review_accounts) -> None:
    (owner, contributor), _ = review_accounts
    # Only this isolated Python fixture can inject PASS. The running HTTP API cannot.
    with TestClient(create_app(settings(), moderation=FixtureModeration())) as seed:
        item = start(seed, submitted(seed, contributor), owner)["submission"]
        approved = seed.post(
            f"/reviews/{item['id']}/decision", headers=headers(owner), json=decision(item)
        )
        assert approved.status_code == 200
    env = {
        **os.environ,
        "CCE_E2E_OWNER_EMAIL": owner["email"],
        "CCE_E2E_OWNER_PASSWORD": owner["password"],
        "CCE_E2E_CONTRIBUTOR_EMAIL": contributor["email"],
        "CCE_E2E_CONTRIBUTOR_PASSWORD": contributor["password"],
        "CCE_E2E_DEFINITION_SUBMISSION": item["id"],
    }
    pnpm = shutil.which("pnpm.cmd" if os.name == "nt" else "pnpm")
    assert pnpm
    subprocess.run(
        [pnpm, "--filter", "@cce/web", "test:e2e", "review.spec.ts", "definition.spec.ts"],
        cwd=Path(__file__).resolve().parents[3],
        env=env,
        check=True,
        timeout=120,
    )
