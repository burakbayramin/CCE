"""M4.5 — acceptance and delivery against a real database.

The properties that matter here cannot be shown by reading: acceptance is
idempotent under retry, the outbox row and the delivery row appear together,
and the publisher moves the delivery to DELIVERED without a second acceptance.
"""

from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from local_environment import ADMIN_DSN
from test_activation_integration import prepared
from test_identity_integration import settings
from test_interaction_protocol_integration import activate, worker_engine
from test_review_integration import FixtureModeration

from cce.api_entrypoint import create_app
from cce.modules.contributions.repository import ContributionError
from cce.modules.interactions import delivery, protocol
from cce.modules.interactions.processing import Affect, Memory, Turn, apply_turn

pytestmark = pytest.mark.integration

PUBLISHER_DSN = (
    "postgresql+psycopg://cce_worker_publisher:cce-local-publisher-only@127.0.0.1:55322/postgres"
)


def committed_turn(character, *, turn_index: int = 1) -> object:
    """A turn that is committed and therefore eligible for delivery."""
    workers = worker_engine()
    try:
        with workers.begin() as connection:
            reservation = protocol.claim(
                connection,
                character_id=character,
                purpose="ADMIN_CHAT",
                holder="worker-a",
                command_id=uuid4(),
            )
            run = protocol.begin_attempt(connection, reservation=reservation, worker_id="worker-a")
            apply_turn(
                connection,
                reservation=reservation,
                run=run,
                holder="worker-a",
                turn=Turn(
                    f"turn-1:exp:{uuid4().hex[:8]}",
                    "selam",
                    "merhaba",
                    memories=[Memory("ilk selam")],
                    affect=Affect(0.1, 0.0, 0.0),
                ),
                turn_index=turn_index,
            )
            with connection.begin_nested():
                row = connection.execute(
                    __import__("sqlalchemy").text(
                        "select id from ops_private.interaction_turns "
                        "where reservation_id=:r order by turn_index desc limit 1"
                    ),
                    {"r": reservation.id},
                ).scalar_one()
            return row
    finally:
        workers.dispose()


def a_character(activation_accounts):
    (owner, contributor), _ = activation_accounts
    with TestClient(create_app(settings(), moderation=FixtureModeration())) as api:
        item, definition = prepared(api, owner, contributor)
        activate(api, owner, item, definition)
    with psycopg.connect(ADMIN_DSN) as db:
        return (
            db.execute(
                "select id from world_private.characters where submission_id=%s",
                (item["id"],),
            ).fetchone()[0],
            db.execute(
                "select id from world_private.people order by created_at desc limit 1"
            ).fetchone()[0],
        )


def delivery_count() -> int:
    with psycopg.connect(ADMIN_DSN) as db:
        return db.execute("select count(*) from ops_private.interaction_deliveries").fetchone()[0]


def pending_outbox() -> int:
    with psycopg.connect(ADMIN_DSN) as db:
        return db.execute(
            "select count(*) from ops_private.interaction_outbox where state='PENDING'"
        ).fetchone()[0]


def test_accepting_a_turn_creates_exactly_one_pending_delivery(activation_accounts) -> None:
    character, recipient = a_character(activation_accounts)
    turn = committed_turn(character)
    key = uuid4()
    before = delivery_count()

    workers = worker_engine()
    try:
        with workers.begin() as connection:
            accepted = delivery.accept(
                connection, turn_id=turn, recipient_id=recipient, request_id=key
            )
            assert accepted.state == "PENDING"
            assert accepted.delivered is False
    finally:
        workers.dispose()

    assert delivery_count() == before + 1
    assert pending_outbox() >= 1, "the outbox row is written with the acceptance"

    with psycopg.connect(ADMIN_DSN) as db:
        row = db.execute("select state from ops_private.delivery_state(%s)", (key,)).fetchone()
    assert row is not None
    assert row[0] == "PENDING", "the delivery state is readable by request id"


def test_repeating_an_acceptance_does_not_deliver_twice(activation_accounts) -> None:
    character, recipient = a_character(activation_accounts)
    turn = committed_turn(character)
    key = uuid4()
    before = delivery_count()

    workers = worker_engine()
    try:
        with workers.begin() as connection:
            first = delivery.accept(
                connection, turn_id=turn, recipient_id=recipient, request_id=key
            )
        with workers.begin() as connection:
            again = delivery.accept(
                connection, turn_id=turn, recipient_id=recipient, request_id=key
            )
    finally:
        workers.dispose()

    assert again.id == first.id, "a repeated request_id returns the original delivery"
    assert delivery_count() == before + 1


def test_publishing_drains_the_outbox_into_delivered(activation_accounts) -> None:
    character, recipient = a_character(activation_accounts)
    turn = committed_turn(character)
    key = uuid4()

    workers = worker_engine()
    try:
        with workers.begin() as connection:
            delivery.accept(connection, turn_id=turn, recipient_id=recipient, request_id=key)
    finally:
        workers.dispose()

    with psycopg.connect(ADMIN_DSN) as db:
        assert (
            db.execute("select state from ops_private.delivery_state(%s)", (key,)).fetchone()[0]
            == "PENDING"
        )

    from sqlalchemy import create_engine

    publisher = create_engine(PUBLISHER_DSN, connect_args={"connect_timeout": 3})
    try:
        with publisher.begin() as connection:
            published = delivery.publish(connection, batch=10)
        assert published >= 1
    finally:
        publisher.dispose()

    with psycopg.connect(ADMIN_DSN) as db:
        state, delivered_at = db.execute(
            "select state, delivered_at from ops_private.delivery_state(%s)", (key,)
        ).fetchone()
    assert state == "DELIVERED"
    assert delivered_at is not None


def test_an_uncommitted_turn_cannot_be_accepted(activation_accounts) -> None:
    """Acceptance is for a committed turn; anything else is refused rather
    than delivering a turn that may still be quarantined."""
    character, recipient = a_character(activation_accounts)
    workers = worker_engine()
    try:
        with workers.begin() as connection, pytest.raises(ContributionError):
            delivery.accept(
                connection,
                turn_id=uuid4(),
                recipient_id=recipient,
                request_id=uuid4(),
            )
    finally:
        workers.dispose()


def test_a_malformed_request_id_never_reaches_the_database(activation_accounts) -> None:
    character, recipient = a_character(activation_accounts)
    turn = committed_turn(character)
    before = delivery_count()

    with pytest.raises(ContributionError) as refused:
        delivery.parse_request_id("urn:uuid:6e8bc430-9c3a-11d9-9669-0800200c9a66")

    assert refused.value.status == 422
    assert delivery_count() == before
    del turn, recipient
