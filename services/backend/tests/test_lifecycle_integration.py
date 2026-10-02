from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from local_environment import ADMIN_DSN
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from test_activation_integration import (
    activation_command,
    capacity_command,
    prepared,
)
from test_identity_integration import settings
from test_review_integration import FixtureModeration, headers

from cce.api_entrypoint import create_app
from cce.infrastructure.database import create_database
from cce.modules.identity.authentication import TokenVerifier
from cce.modules.identity.repository import actor_transaction

pytestmark = pytest.mark.integration


def command(version, prior=None):
    return {
        "expected_version": version,
        "reason": "Isolated character lifecycle decision",
        "request_id": str(uuid4()),
        "reviewed_prior_reason": prior,
    }


def active_fixture(api, owner, contributor):
    item, definition = prepared(api, owner, contributor)
    base = f"/reviews/{item['id']}"
    response = api.post(
        f"{base}/activation", headers=headers(owner), json=activation_command(item, definition)
    )
    assert response.status_code == 200
    return base, response.json()


def test_suspend_archive_restore_reactivate_preserve_identity_and_history(activation_accounts):
    (owner, contributor), _ = activation_accounts
    with TestClient(create_app(settings(), moderation=FixtureModeration())) as api:
        base, original = active_fixture(api, owner, contributor)
        character_id = original["id"]
        person_id = original["person_id"]
        initial_state = original["initial_state"]
        assert original["lifecycle_version"] == 1
        first = command(1)
        with ThreadPoolExecutor(max_workers=2) as pool:
            duplicate = list(
                pool.map(
                    lambda _: api.post(
                        f"{base}/lifecycle/SUSPEND", headers=headers(owner), json=first
                    ),
                    range(2),
                )
            )
        assert [result.status_code for result in duplicate] == [200, 200]
        assert duplicate[0].json() == duplicate[1].json()
        assert duplicate[0].json()["new_status"] == "SUSPENDED"
        assert (
            api.get(f"{base}/activation", headers=headers(owner)).json()["lifecycle_version"] == 2
        )
        assert (
            api.post(
                f"{base}/lifecycle/SUSPEND", headers=headers(owner), json=command(1)
            ).status_code
            == 409
        )
        assert (
            api.post(
                f"{base}/lifecycle/REACTIVATE",
                headers=headers(owner),
                json=command(2, "Wrong suspension reason"),
            ).status_code
            == 409
        )
        second = api.post(
            f"{base}/lifecycle/REACTIVATE", headers=headers(owner), json=command(2, first["reason"])
        )
        assert second.status_code == 200
        assert second.json()["new_status"] == "ACTIVE"
        archive = command(3)
        assert (
            api.post(f"{base}/lifecycle/ARCHIVE", headers=headers(owner), json=archive).status_code
            == 200
        )
        assert (
            api.post(
                f"{base}/lifecycle/REACTIVATE",
                headers=headers(owner),
                json=command(4, first["reason"]),
            ).status_code
            == 409
        )
        assert (
            api.post(
                f"{base}/lifecycle/RESTORE",
                headers=headers(owner),
                json=command(4, "Wrong archive reason"),
            ).status_code
            == 409
        )
        restore = command(4, archive["reason"])
        restored = api.post(f"{base}/lifecycle/RESTORE", headers=headers(owner), json=restore)
        assert restored.status_code == 200
        assert restored.json()["new_status"] == "SUSPENDED"
        assert (
            restored.json()
            == api.post(f"{base}/lifecycle/RESTORE", headers=headers(owner), json=restore).json()
        )
        assert (
            api.post(
                f"{base}/lifecycle/REACTIVATE",
                headers=headers(owner),
                json=command(5, restore["reason"]),
            ).status_code
            == 200
        )
        current = api.get(f"{base}/activation", headers=headers(owner)).json()
        assert (current["id"], current["person_id"], current["initial_state"]) == (
            character_id,
            person_id,
            initial_state,
        )
        assert current["lifecycle_version"] == 6
        history = api.get(f"{base}/lifecycle", headers=headers(owner)).json()
        assert [row["action"] for row in history] == [
            "REACTIVATE",
            "RESTORE",
            "ARCHIVE",
            "REACTIVATE",
            "SUSPEND",
        ]
        assert all(row["character_id"] == character_id for row in history)
        with psycopg.connect(ADMIN_DSN) as db:
            assert db.execute("select count(*) from world_private.people").fetchone() == (2,)
            assert db.execute(
                "select count(*) from world_private.character_initial_state"
            ).fetchone() == (1,)
            assert db.execute(
                "select count(*) from ops_private.character_lifecycle_events"
            ).fetchone() == (5,)


def test_reactivation_obeys_same_last_slot_capacity_as_first_activation(activation_accounts):
    (owner, contributor), _ = activation_accounts
    with TestClient(create_app(settings(), moderation=FixtureModeration())) as api:
        limit = api.get("/reviews/capacity", headers=headers(owner)).json()["active_limit"]
        assert (
            api.post(
                "/reviews/capacity", headers=headers(owner), json=capacity_command(limit, 1)
            ).status_code
            == 200
        )
        base1, _ = active_fixture(api, owner, contributor)
        suspend = command(1)
        assert (
            api.post(f"{base1}/lifecycle/SUSPEND", headers=headers(owner), json=suspend).status_code
            == 200
        )
        base2, _ = active_fixture(api, owner, contributor)
        failed = api.post(
            f"{base1}/lifecycle/REACTIVATE",
            headers=headers(owner),
            json=command(2, suspend["reason"]),
        )
        assert failed.status_code == 409
        assert "kapasitesi" in failed.json()["detail"]
        assert (
            api.get(f"{base1}/activation", headers=headers(owner)).json()["status"] == "SUSPENDED"
        )
        assert api.get(f"{base2}/activation", headers=headers(owner)).json()["status"] == "ACTIVE"
        assert len(api.get(f"{base1}/lifecycle", headers=headers(owner)).json()) == 1


def test_lifecycle_rejects_contributor_stale_requests_and_untrusted_role(activation_accounts):
    (owner, contributor), _ = activation_accounts
    config = settings()
    with TestClient(create_app(config, moderation=FixtureModeration())) as api:
        base, item = active_fixture(api, owner, contributor)
        first = command(1)
        assert (
            api.post(
                f"{base}/lifecycle/SUSPEND", headers=headers(contributor), json=first
            ).status_code
            == 403
        )
        assert api.post(f"{base}/lifecycle/SUSPEND", json=first).status_code == 401
        assert (
            api.post(
                f"{base}/lifecycle/SUSPEND",
                headers=headers(owner),
                json=first | {"status": "ACTIVE"},
            ).status_code
            == 422
        )
        assert (
            api.post(
                f"{base}/lifecycle/SUSPEND",
                headers=headers(owner),
                json=first | {"expected_version": 99},
            ).status_code
            == 409
        )
        assert (
            api.post(f"{base}/lifecycle/SUSPEND", headers=headers(owner), json=first).status_code
            == 200
        )
        assert (
            api.post(
                f"{base}/lifecycle/SUSPEND",
                headers=headers(owner),
                json=first | {"reason": "Different lifecycle command reason"},
            ).status_code
            == 409
        )
        assert (
            api.post(
                f"{base}/lifecycle/RESTORE",
                headers=headers(owner),
                json=command(2, first["reason"]),
            ).status_code
            == 409
        )
        assert len(api.get(f"{base}/lifecycle", headers=headers(owner)).json()) == 1
    engine = create_database(config, owner_commands=True)
    try:
        actor = TokenVerifier(config).verify(contributor["token"])
        with pytest.raises(DBAPIError) as caught, actor_transaction(engine, actor) as db:
            db.execute(
                text(
                    "select ops_private.apply_fixture_character_lifecycle"
                    "(:character,'ARCHIVE',2,'Unauthorized fixture decision',:request,null)"
                ),
                {"character": item["id"], "request": uuid4()},
            )
        assert caught.value.orig.sqlstate == "42501"
    finally:
        engine.dispose()


def test_non_test_api_rejects_fixture_lifecycle_commands(activation_accounts):
    (owner, contributor), _ = activation_accounts
    config = settings()
    with TestClient(create_app(config, moderation=FixtureModeration())) as api:
        base, _ = active_fixture(api, owner, contributor)
    with TestClient(create_app(config.model_copy(update={"environment": "local"}))) as api:
        assert (
            api.post(
                f"{base}/lifecycle/SUSPEND", headers=headers(owner), json=command(1)
            ).status_code
            == 409
        )
    with psycopg.connect(ADMIN_DSN) as db:
        assert db.execute(
            "select count(*) from ops_private.character_lifecycle_events"
        ).fetchone() == (0,)
