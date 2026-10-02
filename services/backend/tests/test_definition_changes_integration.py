from uuid import UUID, uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from local_environment import ADMIN_DSN
from test_activation_integration import activation_command, prepared
from test_definition_integration import command
from test_identity_integration import settings
from test_review_integration import FixtureModeration, decision, headers, start

from cce.api_entrypoint import create_app

pytestmark = pytest.mark.integration


def test_ordinary_revision_keeps_history_and_requires_separate_owner_adoption(
    activation_accounts,
) -> None:
    (owner, contributor), _ = activation_accounts
    with TestClient(create_app(settings(), moderation=FixtureModeration("REVIEW"))) as api:
        item, original = prepared(api, owner, contributor)
        base = f"/reviews/{item['id']}"
        activation = api.post(
            f"{base}/activation",
            headers=headers(owner),
            json=activation_command(item, original),
        )
        assert activation.status_code == 200, activation.text
        initial = activation.json()
        revise = api.post(
            f"/contributions/{item['id']}/revise",
            headers=headers(contributor),
            json={"expected_version": item["version"]},
        )
        assert revise.status_code == 200, revise.text
        draft = revise.json()
        assert draft["status"] == "DRAFT"
        assert draft["revision_id"] == item["revision_id"]

        invalid = {
            **draft["definition"],
            "personality": {**draft["definition"]["personality"], "warmth": 1},
        }
        saved = api.put(
            f"/contributions/{item['id']}",
            headers=headers(contributor),
            json={"expected_version": draft["version"], "definition": invalid},
        )
        assert saved.status_code == 200, saved.text
        assert (
            api.post(
                f"/contributions/{item['id']}/submit",
                headers=headers(contributor),
                json={"expected_version": saved.json()["version"]},
            ).status_code
            == 422
        )
        assert api.get(f"{base}/activation", headers=headers(owner)).json() == initial

        valid = {
            **draft["definition"],
            "introduction": "A revised introduction for the same character.",
        }
        saved = api.put(
            f"/contributions/{item['id']}",
            headers=headers(contributor),
            json={"expected_version": saved.json()["version"], "definition": valid},
        )
        assert saved.status_code == 200, saved.text
        submitted = api.post(
            f"/contributions/{item['id']}/submit",
            headers=headers(contributor),
            json={"expected_version": saved.json()["version"]},
        )
        assert submitted.status_code == 200, submitted.text
        candidate = submitted.json()
        assert candidate["revision_id"] != item["revision_id"]
        assert api.get(f"{base}/activation", headers=headers(owner)).json() == initial
        assert api.get(f"{base}/definition", headers=headers(owner)).json()["id"] == original["id"]

        in_review = start(api, candidate, owner)["submission"]
        approved = api.post(
            f"{base}/decision",
            headers=headers(owner),
            json=decision(in_review, review_accepted=True),
        )
        assert approved.status_code == 200, approved.text
        accepted = approved.json()
        compiled = api.post(
            f"{base}/definition",
            headers=headers(owner),
            json=command(accepted),
        )
        assert compiled.status_code == 200, compiled.text
        updated_definition = compiled.json()
        assert updated_definition["id"] != original["id"]
        assert api.get(f"{base}/activation", headers=headers(owner)).json() == initial

        payload = {
            "definition_id": updated_definition["id"],
            "expected_version": initial["lifecycle_version"],
            "request_id": str(uuid4()),
            "reason": "Approved ordinary introduction revision",
        }
        assert (
            api.post(
                f"{base}/definition-changes", headers=headers(contributor), json=payload
            ).status_code
            == 403
        )
        adopted = api.post(f"{base}/definition-changes", headers=headers(owner), json=payload)
        assert adopted.status_code == 200, adopted.text
        event = adopted.json()
        assert event["previous_definition_id"] == original["id"]
        assert event["definition_id"] == updated_definition["id"]
        assert event["actor_user_id"] == owner["id"]
        assert (
            api.post(f"{base}/definition-changes", headers=headers(owner), json=payload).json()
            == event
        )
        assert (
            api.post(
                f"{base}/definition-changes",
                headers=headers(owner),
                json={**payload, "request_id": str(uuid4())},
            ).status_code
            == 409
        )
        current = api.get(f"{base}/activation", headers=headers(owner)).json()
        assert current["id"] == initial["id"]
        assert current["person_id"] == initial["person_id"]
        assert current["active_definition_id"] == updated_definition["id"]
        assert current["lifecycle_version"] == initial["lifecycle_version"] + 1
        assert current["initial_state"] == initial["initial_state"]
        assert api.get(f"{base}/definition-changes", headers=headers(owner)).json() == [event]
        with psycopg.connect(ADMIN_DSN) as db:
            assert db.execute(
                "select count(*) from public.submission_feedback "
                "where submission_id=%s and decision='APPROVED'",
                (UUID(item["id"]),),
            ).fetchone() == (2,)


def test_pending_revision_does_not_prevent_safe_reactivation(activation_accounts) -> None:
    (owner, contributor), _ = activation_accounts
    with TestClient(create_app(settings(), moderation=FixtureModeration("PASS"))) as api:
        item, original = prepared(api, owner, contributor)
        base = f"/reviews/{item['id']}"
        active = api.post(
            f"{base}/activation",
            headers=headers(owner),
            json=activation_command(item, original),
        ).json()
        suspended = api.post(
            f"{base}/lifecycle/SUSPEND",
            headers=headers(owner),
            json={
                "expected_version": active["lifecycle_version"],
                "request_id": str(uuid4()),
                "reason": "Temporary review of revision",
            },
        )
        assert suspended.status_code == 200, suspended.text
        revised = api.post(
            f"/contributions/{item['id']}/revise",
            headers=headers(contributor),
            json={"expected_version": item["version"]},
        )
        assert revised.status_code == 200, revised.text
        result = api.post(
            f"{base}/lifecycle/REACTIVATE",
            headers=headers(owner),
            json={
                "expected_version": suspended.json()["new_version"],
                "request_id": str(uuid4()),
                "reason": "Prior approved source remains valid",
                "reviewed_prior_reason": "Temporary review of revision",
            },
        )
        assert result.status_code == 200, result.text
        assert result.json()["new_status"] == "ACTIVE"
        assert (
            api.get(f"{base}/activation", headers=headers(owner)).json()["active_definition_id"]
            == original["id"]
        )
