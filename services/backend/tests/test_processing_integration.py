"""M4.4 — the processing pipeline against a real database.

The three properties worth proving here cannot be shown by reading: a turn
lands atomically, a repeated turn is inert, and a relationship failure is
recorded without discarding a turn whose character effects all applied.
"""

import json
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from local_environment import ADMIN_DSN
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from test_activation_integration import prepared
from test_identity_integration import settings
from test_interaction_protocol_integration import activate, worker_engine
from test_review_integration import FixtureModeration

from cce.api_entrypoint import create_app
from cce.modules.interactions import protocol
from cce.modules.interactions.processing import Affect, Goal, Memory, Relationship, Turn, apply_turn

pytestmark = pytest.mark.integration


def character_id(submission: dict) -> object:
    with psycopg.connect(ADMIN_DSN) as db:
        return db.execute(
            "select id from world_private.characters where submission_id=%s",
            (submission["id"],),
        ).fetchone()[0]


def count(table: str, character: object) -> int:
    with psycopg.connect(ADMIN_DSN) as db:
        return db.execute(
            f"select count(*) from world_private.{table} where character_id=%s", (character,)
        ).fetchone()[0]


def turn_with(**overrides) -> Turn:
    values = {
        "identity": f"turn-1:exp:{uuid4().hex[:8]}",
        "prompt": "neredeydin",
        "response": "limanda, sabahın ilk ışığında",
        "memories": [Memory("sabahın ilk ışığında limandaydı")],
        "goals": [Goal("arşivi düzenlemek")],
        "affect": Affect(0.4, -0.2, 0.1),
    }
    values.update(overrides)
    return Turn(**values)  # type: ignore[arg-type]


def start_turn(character: object, turn: Turn, *, turn_index: int = 1):
    """Claim, open an attempt, and apply one turn on the worker identity."""
    workers = worker_engine()
    try:
        with workers.begin() as connection:
            reservation = protocol.claim(
                connection,
                character_id=character,  # type: ignore[arg-type]
                purpose="ADMIN_CHAT",
                holder="worker-a",
                command_id=uuid4(),
            )
            run = protocol.begin_attempt(connection, reservation=reservation, worker_id="worker-a")
            return apply_turn(
                connection,
                reservation=reservation,
                run=run,
                holder="worker-a",
                turn=turn,
                turn_index=turn_index,
            )
    finally:
        workers.dispose()


def test_a_turn_lands_atomically_and_closes_the_reservation(activation_accounts) -> None:
    (owner, contributor), _ = activation_accounts
    with TestClient(create_app(settings(), moderation=FixtureModeration())) as api:
        item, definition = prepared(api, owner, contributor)
        activate(api, owner, item, definition)
    target = character_id(item)

    outcome = start_turn(target, turn_with())
    assert (outcome.applied, outcome.skipped) == (3, 0)
    assert outcome.flagged is False

    assert count("character_memories", target) == 1
    assert count("character_goals", target) == 1
    with psycopg.connect(ADMIN_DSN) as db:
        affect = db.execute(
            "select valence, arousal, dominance from world_private.character_affect "
            "where character_id=%s",
            (target,),
        ).fetchone()
        assert affect is not None
        reservation_state = db.execute(
            "select state from ops_private.interaction_reservations "
            "where character_id=%s and state <> 'RESOLVED'",
            (target,),
        ).fetchone()
    assert reservation_state is None or reservation_state[0] == "RESULT_COMMITTED"


def test_the_same_turn_under_a_different_model_collides(activation_accounts) -> None:
    """The source identity is content-derived, so a second run of the same
    experience adds nothing even though the effect list is resent.

    Affect is the exception and deliberately so: it is the character's current
    state rather than an append, so re-applying it is correct and counts as
    applied. Memories and goals are append-only and collide instead.
    """
    (owner, contributor), _ = activation_accounts
    with TestClient(create_app(settings(), moderation=FixtureModeration())) as api:
        item, definition = prepared(api, owner, contributor)
        activate(api, owner, item, definition)
    target = character_id(item)

    shared = f"turn-1:exp:{uuid4().hex[:8]}"
    body = {"memories": [Memory("aynı gece")], "goals": [Goal("aynı hedef")]}
    first = start_turn(target, turn_with(identity=shared, **body))
    assert (first.applied, first.skipped) == (3, 0)

    second = start_turn(target, turn_with(identity=shared, **body))
    assert (second.applied, second.skipped) == (1, 2), (
        "only the current-state affect re-applies; the append-only effects collide"
    )
    assert count("character_memories", target) == 1
    assert count("character_goals", target) == 1


def test_an_unknown_effect_kind_is_refused_before_anything_is_written(activation_accounts) -> None:
    """A caller that bypasses the effect builder must still be stopped by the
    database, and must not half-apply the turn."""
    (owner, contributor), _ = activation_accounts
    with TestClient(create_app(settings(), moderation=FixtureModeration())) as api:
        item, definition = prepared(api, owner, contributor)
        activate(api, owner, item, definition)
    target = character_id(item)

    workers = worker_engine()
    try:
        with workers.begin() as connection:
            reservation = protocol.claim(
                connection,
                character_id=target,  # type: ignore[arg-type]
                purpose="ADMIN_CHAT",
                holder="worker-a",
                command_id=uuid4(),
            )
            protocol.begin_attempt(connection, reservation=reservation, worker_id="worker-a")
            # Called directly rather than through apply_turn, so the database's
            # own refusal is what surfaces here.
            with pytest.raises(DBAPIError):
                connection.execute(
                    text(
                        "select * from ops_private.apply_interaction_turn("
                        ":reservation,:generation,:holder,:index,:identity,"
                        ":prompt,:response,cast(:effects as jsonb),'[]'::jsonb)"
                    ),
                    {
                        "reservation": reservation.id,
                        "generation": reservation.ownership_generation,
                        "holder": "worker-a",
                        "index": 1,
                        "identity": "turn-1:exp:bogus",
                        "prompt": "q",
                        "response": "a",
                        "effects": json.dumps(
                            [
                                {
                                    "effect_kind": "SOMETHING_ELSE",
                                    "source_identity": "memory:deadbeef",
                                    "text": "x",
                                }
                            ]
                        ),
                    },
                )
    finally:
        workers.dispose()

    assert count("character_memories", target) == 0, "a refused effect must write nothing"
    with psycopg.connect(ADMIN_DSN) as db:
        turns = db.execute(
            "select count(*) from ops_private.interaction_turns where character_id=%s", (target,)
        ).fetchone()[0]
    assert turns == 0, "the refused turn must roll back with the rest"


def test_a_relationship_failure_is_recorded_and_flagged(activation_accounts) -> None:
    """Losing a social bond is recoverable; losing the turn is not. The subject
    does not exist, so the relationship insert violates its foreign key and the
    turn must survive it."""
    (owner, contributor), _ = activation_accounts
    with TestClient(create_app(settings(), moderation=FixtureModeration())) as api:
        item, definition = prepared(api, owner, contributor)
        activate(api, owner, item, definition)
    target = character_id(item)

    outcome = start_turn(
        target,
        turn_with(relationships=[Relationship(uuid4(), 0.5, 0.2)]),
    )
    assert outcome.flagged is True, "a failed relationship must flag the turn"
    # The character effects still landed: the failure was isolated.
    assert count("character_memories", target) == 1
    assert count("character_relationships", target) == 0

    with psycopg.connect(ADMIN_DSN) as db:
        row = db.execute(
            "select state, flagged, flag_reason from ops_private.interaction_turns "
            "where character_id=%s",
            (target,),
        ).fetchone()
    assert row is not None
    assert row[0] == "COMMITTED"
    assert row[1] is True
    assert row[2] == "RELATIONSHIP_UPDATE_FAILED"
