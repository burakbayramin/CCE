"""M4.1 — the durable-job protocol's invariants.

Each test corresponds to a clause in WADR-011 that the schema, not the
caller, has to enforce: a character holds one reservation, a lapsed lease does
not free it, a lost generation cannot commit, and an effect identity does not
depend on which model produced it.

The protocol is exercised through the worker identities that hold those
grants, so a passing test also proves the grants are right.
"""

from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from local_environment import ADMIN_DSN, ENGINE_DSN
from pydantic import SecretStr
from sqlalchemy import text
from test_activation_integration import prepared
from test_identity_integration import settings
from test_review_integration import FixtureModeration, headers

from cce.api_entrypoint import create_app
from cce.core.config import Settings
from cce.infrastructure.database import create_database
from cce.modules.contributions.repository import ContributionError
from cce.modules.interactions import protocol

pytestmark = pytest.mark.integration


def engine():
    """A cce_engine connection: the identity the protocol grants execute to."""
    return create_database(Settings(environment="test", database_url=SecretStr(ENGINE_DSN)))


def character_id(submission: dict) -> object:
    with psycopg.connect(ADMIN_DSN) as db:
        return db.execute(
            "select id from world_private.characters where submission_id=%s",
            (submission["id"],),
        ).fetchone()[0]


def expire(reservation_id) -> None:
    with psycopg.connect(ADMIN_DSN) as db:
        db.execute(
            "update ops_private.interaction_reservations "
            "set lease_until=clock_timestamp() - interval '1 second' where id=%s",
            (reservation_id,),
        )


def effect_count(identity: str) -> int:
    with psycopg.connect(ADMIN_DSN) as db:
        return db.execute(
            "select count(*) from ops_private.domain_effects where effect_identity=%s",
            (identity,),
        ).fetchone()[0]


def activate(api: TestClient, owner: dict, item: dict, definition: dict) -> None:
    response = api.post(
        f"/reviews/{item['id']}/activation",
        headers=headers(owner),
        json={
            "expected_version": item["version"],
            "revision_id": item["revision_id"],
            "definition_id": definition["id"],
            "artifact_sha256": definition["artifact_sha256"],
            "reason": "Isolated activation for the protocol invariants",
        },
    )
    assert response.status_code == 200, response.text


def test_one_reservation_per_character_and_resume_is_fenced(activation_accounts) -> None:
    (owner, contributor), _ = activation_accounts
    with TestClient(create_app(settings(), moderation=FixtureModeration())) as api:
        item, definition = prepared(api, owner, contributor)
        activate(api, owner, item, definition)
    target = character_id(item)

    worker_engine = engine()
    try:
        with worker_engine.begin() as connection:
            held = protocol.claim(
                connection,
                character_id=target,
                purpose="ADMIN_CHAT",
                holder="worker-a",
                command_id=uuid4(),
            )
            assert held.ownership_generation == 1

            # A second worker is refused while the lease is live.
            with pytest.raises(ContributionError) as refused:
                protocol.claim(
                    connection,
                    character_id=target,
                    purpose="ADMIN_CHAT",
                    holder="worker-b",
                    command_id=uuid4(),
                )
            assert refused.value.status == 409

            # The holder resuming renews and fences its own earlier generation.
            resumed = protocol.claim(
                connection,
                character_id=target,
                purpose="ADMIN_CHAT",
                holder="worker-a",
                command_id=uuid4(),
            )
            assert resumed.ownership_generation == 2

            # The superseded generation cannot open an attempt.
            with pytest.raises(ContributionError) as stale:
                protocol.begin_attempt(connection, reservation=held, worker_id="worker-a")
            assert stale.value.status == 409

            run = protocol.begin_attempt(connection, reservation=resumed, worker_id="worker-a")
            assert run.ownership_generation == 2
    finally:
        worker_engine.dispose()


def test_a_lapsed_lease_does_not_free_the_character(activation_accounts) -> None:
    """WADR-011: an expired lease is not evidence the worker stopped, so the
    character stays reserved until an operator decides."""
    (owner, contributor), _ = activation_accounts
    with TestClient(create_app(settings(), moderation=FixtureModeration())) as api:
        item, definition = prepared(api, owner, contributor)
        activate(api, owner, item, definition)
    target = character_id(item)

    worker_engine = engine()
    try:
        with worker_engine.begin() as connection:
            held = protocol.claim(
                connection,
                character_id=target,
                purpose="SCENE",
                holder="worker-a",
                command_id=uuid4(),
                lease_seconds=30,
            )
            expire(held.id)

            # Neither a new worker nor the old one gets the character back.
            for holder in ("worker-b", "worker-a"):
                with pytest.raises(ContributionError) as stuck:
                    protocol.claim(
                        connection,
                        character_id=target,
                        purpose="SCENE",
                        holder=holder,
                        command_id=uuid4(),
                    )
                assert stuck.value.status == 409

            stale = protocol.stale_reservations(connection)
            assert [row["reservation_id"] for row in stale] == [held.id]

            resolved = protocol.resolve(
                connection,
                reservation_id=held.id,
                expected_generation=held.ownership_generation,
                reason="Isolated operator resolution for a lapsed lease",
            )
            assert resolved.state == "RESOLVED"

            # Only after the decision can a new interaction start.
            again = protocol.claim(
                connection,
                character_id=target,
                purpose="SCENE",
                holder="worker-b",
                command_id=uuid4(),
            )
            assert again.ownership_generation == 1
    finally:
        worker_engine.dispose()


def test_effect_identity_ignores_the_model_that_produced_it(activation_accounts) -> None:
    """Re-running the same experience under a different model must collide with
    the effects already applied instead of duplicating them."""
    (owner, contributor), _ = activation_accounts
    with TestClient(create_app(settings(), moderation=FixtureModeration())) as api:
        item, definition = prepared(api, owner, contributor)
        activate(api, owner, item, definition)
    target = character_id(item)

    identity = f"turn-1:memory:{uuid4()}"
    worker_engine = engine()
    try:
        with worker_engine.begin() as connection:
            first = protocol.claim(
                connection,
                character_id=target,
                purpose="ADMIN_CHAT",
                holder="worker-a",
                command_id=uuid4(),
            )
            first_run = protocol.begin_attempt(connection, reservation=first, worker_id="worker-a")
            applied = protocol.commit_result(
                connection,
                run=first_run,
                reservation=first,
                holder="worker-a",
                effect_identity=f"turn-1:{uuid4()}",
                effects=[
                    {
                        "effect_identity": identity,
                        "effect_kind": "MEMORY",
                        "applied_by_processing_version": "model-a-v1",
                        "payload": {"text": "Sahilde bir gün geçirdi"},
                        "topic": "MEMORY_WRITTEN",
                    }
                ],
            )
            assert (applied.applied, applied.skipped) == (1, 0)

            # Same experience, different model, same identity: nothing applies.
            retry = protocol.claim(
                connection,
                character_id=target,
                purpose="ADMIN_CHAT",
                holder="worker-a",
                command_id=uuid4(),
            )
            retry_run = protocol.begin_attempt(connection, reservation=retry, worker_id="worker-a")
            repeated = protocol.commit_result(
                connection,
                run=retry_run,
                reservation=retry,
                holder="worker-a",
                effect_identity=f"turn-1:{uuid4()}",
                effects=[
                    {
                        "effect_identity": identity,
                        "effect_kind": "MEMORY",
                        "applied_by_processing_version": "model-b-v2",
                        "payload": {"text": "Sahilde bir gün geçirdi"},
                        "topic": "MEMORY_WRITTEN",
                    }
                ],
            )
            assert (repeated.applied, repeated.skipped) == (0, 1)
        assert effect_count(identity) == 1
    finally:
        worker_engine.dispose()


def test_an_empty_result_is_a_result(activation_accounts) -> None:
    """A scene that changed nothing still has to resolve its reservation."""
    (owner, contributor), _ = activation_accounts
    with TestClient(create_app(settings(), moderation=FixtureModeration())) as api:
        item, definition = prepared(api, owner, contributor)
        activate(api, owner, item, definition)
    target = character_id(item)

    worker_engine = engine()
    try:
        with worker_engine.begin() as connection:
            held = protocol.claim(
                connection,
                character_id=target,
                purpose="SCENE",
                holder="worker-a",
                command_id=uuid4(),
            )
            run = protocol.begin_attempt(connection, reservation=held, worker_id="worker-a")
            outcome = protocol.commit_result(
                connection,
                run=run,
                reservation=held,
                holder="worker-a",
                effect_identity=f"turn-1:{uuid4()}",
                effects=[],
            )
            assert (outcome.applied, outcome.skipped) == (0, 0)

            state = connection.execute(
                text("select state from ops_private.interaction_reservations where id=:id"),
                {"id": held.id},
            ).scalar_one()
            assert state == "RESULT_COMMITTED"

            # And the character is available again.
            protocol.claim(
                connection,
                character_id=target,
                purpose="ADMIN_CHAT",
                holder="worker-b",
                command_id=uuid4(),
            )
    finally:
        worker_engine.dispose()
