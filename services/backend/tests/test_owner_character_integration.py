"""M3.6: the World Owner authors characters through the contributor line, and
lifecycle commands never resurrect work that was deliberately finished."""

from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from local_environment import ADMIN_DSN
from test_activation_integration import prepared
from test_identity_integration import settings
from test_review_integration import FixtureModeration, decision, headers, start, submitted

from cce.api_entrypoint import create_app

pytestmark = pytest.mark.integration


def moderation_job_count(submission_id: str) -> int:
    with psycopg.connect(ADMIN_DSN) as db:
        return db.execute(
            "select count(*) from ops_private.moderation_jobs where revision_id="
            "(select revision_id from public.character_submissions where id=%s)",
            (submission_id,),
        ).fetchone()[0]


def test_owner_authors_through_the_contributor_line_and_audits_the_real_actor(
    activation_accounts,
) -> None:
    """WADR-003: an Owner-created character takes the same structured form and
    the same validation line. The Owner's own approval is still an approval:
    it runs moderation again and records the real actor rather than skipping
    either."""
    (owner, _contributor), _ = activation_accounts
    with TestClient(create_app(settings(), moderation=FixtureModeration())) as api:
        item = submitted(api, owner)
        assert item["user_id"] == owner["id"], "Owner authored their own submission"
        assert item["status"] == "SUBMITTED"

        started = start(api, item, owner)
        assert started["submission"]["status"] == "UNDER_REVIEW"
        assert started["moderation"]["is_fixture"] is True

        approved = api.post(
            f"/reviews/{item['id']}/decision",
            headers=headers(owner),
            json=decision(started["submission"]),
        )
        assert approved.status_code == 200, approved.text

        detail = api.get(f"/reviews/{item['id']}", headers=headers(owner)).json()
        assert detail["submission"]["status"] == "APPROVED"
        assert any(feedback["decision"] == "APPROVED" for feedback in detail["history"]["feedback"])

        with psycopg.connect(ADMIN_DSN) as db:
            # psycopg returns uuid columns as UUID objects; the account fixture
            # carries strings, so compare on the textual form.
            actors = [
                str(row[0])
                for row in db.execute(
                    "select distinct actor_user_id from ops_private.contribution_events "
                    "where submission_id=%s",
                    (item["id"],),
                ).fetchall()
            ]
        assert actors == [owner["id"]], "every audit row names the real World Owner"


def test_block_verdict_still_binds_an_owner_created_character(activation_accounts) -> None:
    """WADR-010: a BLOCK result cannot be overridden, including on a character
    the Owner wrote themselves."""
    (owner, _contributor), _ = activation_accounts
    with TestClient(create_app(settings(), moderation=FixtureModeration("BLOCK"))) as api:
        item = submitted(api, owner)
        started = start(api, item, owner)
        assert started["moderation"]["result"] == "BLOCK"

        refused = api.post(
            f"/reviews/{item['id']}/decision",
            headers=headers(owner),
            json=decision(started["submission"], "APPROVED"),
        )
        assert refused.status_code == 409, refused.text

        after = api.get(f"/reviews/{item['id']}", headers=headers(owner)).json()
        assert after["submission"]["status"] == "UNDER_REVIEW"


def test_restore_and_reactivate_do_not_resurrect_finished_work(activation_accounts) -> None:
    """M3.6 negative requirement: restoring or reactivating a character must
    not re-open moderation for a revision that already has a verdict, and must
    not schedule any follow-up job. Restore is a state transition only."""
    (owner, contributor), _ = activation_accounts
    with TestClient(create_app(settings(), moderation=FixtureModeration())) as api:
        item, definition = prepared(api, owner, contributor)
        base = f"/reviews/{item['id']}"
        assert (
            api.post(
                f"{base}/activation",
                headers=headers(owner),
                json={
                    "expected_version": item["version"],
                    "revision_id": item["revision_id"],
                    "definition_id": definition["id"],
                    "artifact_sha256": definition["artifact_sha256"],
                    "reason": "Isolated activation for the restore invariant",
                },
            ).status_code
            == 200
        )

        settled = moderation_job_count(item["id"])
        # start_review writes the fixture verdict inline rather than queueing a
        # job, so the baseline is zero. What matters is that it never moves.
        assert settled == 0, "the inline fixture provider must not create a moderation job"

        def lifecycle(action, version, prior=None):
            response = api.post(
                f"{base}/lifecycle/{action}",
                headers=headers(owner),
                json={
                    "expected_version": version,
                    "reason": f"Isolated {action} for the restore invariant",
                    "request_id": str(uuid4()),
                    "reviewed_prior_reason": prior,
                },
            )
            assert response.status_code == 200, response.text
            return response.json()

        def verdict_count():
            with psycopg.connect(ADMIN_DSN) as db:
                return db.execute(
                    "select count(*) from ops_private.submission_moderation where revision_id=%s",
                    (item["revision_id"],),
                ).fetchone()[0]

        assert verdict_count() == 1

        suspended = lifecycle("SUSPEND", 1)
        assert moderation_job_count(item["id"]) == settled
        archived = lifecycle("ARCHIVE", suspended["new_version"])
        assert moderation_job_count(item["id"]) == settled
        restored = lifecycle("RESTORE", archived["new_version"], archived["reason"])
        assert restored["new_status"] == "SUSPENDED"
        assert moderation_job_count(item["id"]) == settled
        reactivated = lifecycle("REACTIVATE", restored["new_version"], restored["reason"])
        assert reactivated["new_status"] == "ACTIVE"

        # Restore and reactivation are pure transitions: no job was queued and
        # the single immutable verdict for the revision is still the only one.
        assert moderation_job_count(item["id"]) == settled
        assert verdict_count() == 1, "restore must not create a second moderation verdict"
