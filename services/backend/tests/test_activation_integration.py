from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from local_environment import ADMIN_DSN
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from test_definition_integration import approve, command
from test_identity_integration import settings
from test_moderation_jobs_integration import claim, finish
from test_review_integration import FixtureModeration, decision, headers, start, submitted

from cce.api_entrypoint import create_app
from cce.infrastructure.database import create_database
from cce.modules.identity.authentication import TokenVerifier
from cce.modules.identity.repository import actor_transaction

pytestmark = pytest.mark.integration


def prepared(api, owner, contributor):
    item = approve(api, owner, contributor)
    response = api.post(
        f"/reviews/{item['id']}/definition", headers=headers(owner), json=command(item)
    )
    assert response.status_code == 200
    return item, response.json()


def activation_command(item, definition):
    return {
        **command(item),
        "definition_id": definition["id"],
        "artifact_sha256": definition["artifact_sha256"],
        "reason": "Isolated activation fixture approval",
    }


def capacity_command(expected, value):
    return {
        "expected_limit": expected,
        "active_limit": value,
        "request_id": str(uuid4()),
        "reason": "Isolated capacity fixture change",
    }


def test_activation_is_atomic_idempotent_and_private(activation_accounts):
    (owner, contributor), auth = activation_accounts
    with TestClient(create_app(settings(), moderation=FixtureModeration("REVIEW"))) as api:
        item, definition = prepared(api, owner, contributor)
        path = f"/reviews/{item['id']}/activation"
        body = activation_command(item, definition)
        assert api.get(path, headers=headers(owner)).json() is None
        assert api.post(path, headers=headers(contributor), json=body).status_code == 403
        assert api.post(path, json=body).status_code == 401
        assert (
            api.post(path, headers=headers(owner), json={**body, "status": "ACTIVE"}).status_code
            == 422
        )
        for change in (
            {"revision_id": str(uuid4())},
            {"definition_id": str(uuid4())},
            {"artifact_sha256": "0" * 64},
            {"expected_version": 99},
        ):
            assert api.post(path, headers=headers(owner), json=body | change).status_code == 409
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(
                pool.map(lambda _: api.post(path, headers=headers(owner), json=body), range(2))
            )
        assert [response.status_code for response in responses] == [200, 200]
        result = responses[0].json()
        assert result == responses[1].json() == api.get(path, headers=headers(owner)).json()
        assert result["status"] == "ACTIVE" and result["is_fixture"]
        state = result["initial_state"]
        assert state["bootstrap"] == definition["artifact"]["bootstrap"]
        assert state["owner_relationship_status"] == "UNACQUAINTED"
        assert state["owner_experience_count"] == 0
        assert state["owner_person_id"] != result["person_id"]
        assert api.get("/reviews/capacity", headers=headers(owner)).json()["active_count"] == 1
        with psycopg.connect(ADMIN_DSN) as db:
            for table in (
                "world_private.characters",
                "world_private.character_initial_state",
                "ops_private.character_activation_events",
            ):
                assert db.execute(f"select count(*) from {table}").fetchone() == (1,)
            assert db.execute("select count(*) from world_private.people").fetchone() == (2,)
        assert auth.get("/rest/v1/characters", headers=headers(contributor)).status_code != 200


def test_last_capacity_slot_race_has_no_partial_character_or_audit(activation_accounts):
    (owner, contributor), _ = activation_accounts
    with TestClient(create_app(settings(), moderation=FixtureModeration())) as api:
        limit = api.get("/reviews/capacity", headers=headers(owner)).json()["active_limit"]
        assert (
            api.post(
                "/reviews/capacity", headers=headers(owner), json=capacity_command(limit, 1)
            ).status_code
            == 200
        )
        first, first_definition = prepared(api, owner, contributor)
        second, second_definition = prepared(api, owner, contributor)

        def activate(pair):
            item, definition = pair
            return api.post(
                f"/reviews/{item['id']}/activation",
                headers=headers(owner),
                json=activation_command(item, definition),
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(
                pool.map(activate, ((first, first_definition), (second, second_definition)))
            )
        assert sorted(response.status_code for response in results) == [200, 409]
        assert (
            "kapasitesi"
            in next(response for response in results if response.status_code == 409).json()[
                "detail"
            ]
        )
        winner = next(response.json() for response in results if response.status_code == 200)
        source = first if winner["submission_id"] == first["id"] else second
        definition = first_definition if source == first else second_definition
        assert activate((source, definition)).json()["id"] == winner["id"]
        with psycopg.connect(ADMIN_DSN) as db:
            assert db.execute("select count(*) from world_private.characters").fetchone() == (1,)
            assert db.execute(
                "select count(*) from world_private.character_initial_state"
            ).fetchone() == (1,)
            assert db.execute(
                "select count(*) from ops_private.character_activation_events"
            ).fetchone() == (1,)
            assert db.execute("select count(*) from world_private.people").fetchone() == (2,)


def test_capacity_change_is_audited_idempotent_and_cannot_shrink_below_active(activation_accounts):
    (owner, contributor), _ = activation_accounts
    with TestClient(create_app(settings(), moderation=FixtureModeration())) as api:
        before = api.get("/reviews/capacity", headers=headers(owner)).json()["active_limit"]
        body = capacity_command(before, 2)
        assert (
            api.post("/reviews/capacity", headers=headers(contributor), json=body).status_code
            == 403
        )
        assert (
            api.post(
                "/reviews/capacity", headers=headers(owner), json=body | {"active_limit": 51}
            ).status_code
            == 422
        )
        result = api.post("/reviews/capacity", headers=headers(owner), json=body)
        assert result.status_code == 200
        assert (
            result.json() == api.post("/reviews/capacity", headers=headers(owner), json=body).json()
        )
        assert (
            api.post(
                "/reviews/capacity", headers=headers(owner), json=body | {"active_limit": 3}
            ).status_code
            == 409
        )
        item, definition = prepared(api, owner, contributor)
        assert (
            api.post(
                f"/reviews/{item['id']}/activation",
                headers=headers(owner),
                json=activation_command(item, definition),
            ).status_code
            == 200
        )
        assert (
            api.post(
                "/reviews/capacity", headers=headers(owner), json=capacity_command(2, 0)
            ).status_code
            == 409
        )
        with psycopg.connect(ADMIN_DSN) as db:
            assert db.execute(
                "select count(*) from ops_private.character_capacity_events"
            ).fetchone() == (1,)


def test_activation_disabled_in_local_api_and_sql_gate(activation_accounts):
    (owner, contributor), _ = activation_accounts
    config = settings()
    with TestClient(create_app(config, moderation=FixtureModeration())) as api:
        item, definition = prepared(api, owner, contributor)
    path = f"/reviews/{item['id']}/activation"
    body = activation_command(item, definition)
    with TestClient(create_app(config.model_copy(update={"environment": "local"}))) as local_api:
        assert local_api.post(path, headers=headers(owner), json=body).status_code == 409
    actor = TokenVerifier(config).verify(owner["token"])
    with (
        pytest.raises(psycopg.errors.CheckViolation, match="Fixture activation disabled"),
        psycopg.connect(ADMIN_DSN) as db,
    ):
        db.execute("update ops_private.fixture_activation_policy set enabled=false")
        db.execute(
            "select set_config('cce.actor_id',%s,true),set_config('cce.session_id',%s,true)",
            (str(actor.user_id), str(actor.session_id)),
        )
        db.execute(
            "select ops_private.activate_fixture_character(%s,%s,%s,%s,%s,%s)",
            (
                item["id"],
                item["version"],
                item["revision_id"],
                definition["id"],
                definition["artifact_sha256"],
                body["reason"],
            ),
        )
    with psycopg.connect(ADMIN_DSN) as db:
        assert db.execute("select count(*) from world_private.characters").fetchone() == (0,)


def test_nonfixture_moderation_never_activates_before_model_acceptance(activation_accounts):
    (owner, contributor), _ = activation_accounts
    with TestClient(create_app(settings())) as api:
        item = start(api, submitted(api, contributor), owner)["submission"]
        assert finish(claim(), "PASS")
        approved = api.post(
            f"/reviews/{item['id']}/decision", headers=headers(owner), json=decision(item)
        )
        assert approved.status_code == 200
        item = approved.json()
        definition = api.post(
            f"/reviews/{item['id']}/definition", headers=headers(owner), json=command(item)
        ).json()
        assert definition["artifact"]["source"]["is_fixture"] is False
        assert (
            api.post(
                f"/reviews/{item['id']}/activation",
                headers=headers(owner),
                json=activation_command(item, definition),
            ).status_code
            == 409
        )


def test_runtime_role_has_no_direct_state_or_limit_writes(activation_accounts):
    (owner, contributor), _ = activation_accounts
    config = settings()
    with TestClient(create_app(config, moderation=FixtureModeration())) as api:
        item, definition = prepared(api, owner, contributor)
        assert (
            api.post(
                f"/reviews/{item['id']}/activation",
                headers=headers(owner),
                json=activation_command(item, definition),
            ).status_code
            == 200
        )
    actor = TokenVerifier(config).verify(owner["token"])
    engine = create_database(config, owner_commands=True)
    try:
        for sql in (
            "update ops_private.character_capacity set active_limit=0",
            "delete from world_private.characters",
            "update world_private.characters set status='SUSPENDED'",
            "delete from world_private.character_initial_state",
            "insert into ops_private.character_activation_events default values",
        ):
            with pytest.raises(DBAPIError), actor_transaction(engine, actor) as connection:
                connection.execute(text(sql))
        contributor_actor = TokenVerifier(config).verify(contributor["token"])
        with actor_transaction(engine, contributor_actor) as connection:
            assert connection.execute(text("select * from world_private.characters")).all() == []
    finally:
        engine.dispose()


def test_late_initialization_failure_rolls_back_person_state_and_audit(activation_accounts):
    (owner, contributor), _ = activation_accounts
    config = settings()
    with TestClient(create_app(config, moderation=FixtureModeration())) as api:
        item, definition = prepared(api, owner, contributor)
    actor = TokenVerifier(config).verify(owner["token"])
    with pytest.raises(psycopg.errors.CheckViolation, match="Injected audit failure"):
        # Both the trigger and the entire initialization roll back in this transaction.
        # Nothing is installed permanently or applied to the user's local database.
        with psycopg.connect(ADMIN_DSN) as db:
            db.execute(
                "create function pg_temp.fail_activation_audit() returns trigger "
                "language plpgsql as $$ begin raise exception 'Injected audit failure' "
                "using errcode='23514'; end $$"
            )
            db.execute(
                "create trigger fixture_activation_failure before insert "
                "on ops_private.character_activation_events for each row "
                "execute function pg_temp.fail_activation_audit()"
            )
            db.execute(
                "select set_config('cce.actor_id',%s,true),set_config('cce.session_id',%s,true)",
                (str(actor.user_id), str(actor.session_id)),
            )
            db.execute(
                "select ops_private.activate_fixture_character(%s,%s,%s,%s,%s,%s)",
                (
                    item["id"],
                    item["version"],
                    item["revision_id"],
                    definition["id"],
                    definition["artifact_sha256"],
                    "Isolated rollback test fixture",
                ),
            )
    with psycopg.connect(ADMIN_DSN) as db:
        for table in (
            "world_private.characters",
            "world_private.character_initial_state",
            "ops_private.character_activation_events",
        ):
            assert db.execute(f"select count(*) from {table}").fetchone() == (0,)
        assert db.execute("select count(*) from world_private.people").fetchone() == (1,)


def test_definer_commands_reject_contributor_and_missing_live_identity(activation_accounts):
    (owner, contributor), _ = activation_accounts
    config = settings()
    with TestClient(create_app(config, moderation=FixtureModeration())) as api:
        item, definition = prepared(api, owner, contributor)
    engine = create_database(config, owner_commands=True)
    try:
        for account in (contributor, owner):
            actor = TokenVerifier(config).verify(account["token"])
            for sql, params in (
                (
                    "select ops_private.activate_fixture_character"
                    "(:id,:version,:revision,:definition,:hash,:reason)",
                    {
                        "id": item["id"],
                        "version": item["version"],
                        "revision": item["revision_id"],
                        "definition": definition["id"],
                        "hash": definition["artifact_sha256"],
                        "reason": "Isolated authorization test fixture",
                    },
                ),
                (
                    "select ops_private.set_character_capacity(50,1,:reason,:request)",
                    {"reason": "Isolated authorization test fixture", "request": uuid4()},
                ),
            ):
                with pytest.raises(DBAPIError) as caught, actor_transaction(engine, actor) as db:
                    if account is owner:
                        db.execute(text("select set_config('cce.session_id','',true)"))
                    db.execute(text(sql), params)
                assert caught.value.orig.sqlstate == "42501"
    finally:
        engine.dispose()
