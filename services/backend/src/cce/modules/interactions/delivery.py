"""M4.5 — accepting a turn and delivering it.

Acceptance is a separate, explicit act: M4.4 leaves a committed turn, and
handing it to a recipient is the caller's decision. The caller's `request_id`
is the idempotency key, so a retry after a lost response returns the original
delivery instead of sending the turn twice.

The outbox row and the delivery row are written in the same transaction, and
the publisher drains them afterwards. A crash between the two loses nothing
and duplicates nothing.
"""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import Connection, text
from sqlalchemy.exc import DBAPIError

from cce.modules.contributions.repository import ContributionError
from cce.modules.interactions import protocol

#: A caller may not choose how many rows the publisher drains.
MAX_PUBLISH_BATCH = 50


@dataclass(frozen=True)
class Delivery:
    """One turn handed to one recipient."""

    id: UUID
    turn_id: UUID
    reservation_id: UUID
    recipient_id: UUID
    request_id: UUID
    state: str
    delivered_at: object | None
    failure_reason: str | None

    @property
    def delivered(self) -> bool:
        return self.state == "DELIVERED"


def parse_request_id(raw: object) -> UUID:
    """Validate the caller's idempotency key before it reaches the database.

    Only the canonical hyphenated form is accepted. Python's `UUID` also parses
    `urn:uuid:` and unhyphenated spellings, which the database rejects, so
    accepting them here would hand the caller a key that fails later at a place
    that says nothing about the key. Coercing anything would be worse: a
    generated uuid would deduplicate against an unrelated delivery and hide the
    client bug behind a successful-looking no-op.
    """
    if not isinstance(raw, str):
        raise ContributionError(422, "request_id bir UUID olmalı")
    try:
        parsed = UUID(raw)
    except (ValueError, AttributeError, TypeError):
        raise ContributionError(422, "request_id bir UUID olmalı") from None
    if str(parsed) != raw.lower():
        raise ContributionError(422, "request_id bir UUID olmalı")
    return parsed


def accept(
    connection: Connection,
    *,
    turn_id: UUID,
    recipient_id: UUID,
    request_id: UUID,
) -> Delivery:
    """Accept a committed turn for delivery. Idempotent on `request_id`."""
    try:
        row = (
            connection.execute(
                text("select * from ops_private.accept_turn_delivery(:turn,:recipient,:request)"),
                {
                    "turn": turn_id,
                    "recipient": recipient_id,
                    "request": request_id,
                },
            )
            .mappings()
            .one()
        )
    except DBAPIError as error:
        raise protocol.classify(error, "Tur teslimi kabul edilemedi") from None
    return Delivery(
        id=row["id"],
        turn_id=row["turn_id"],
        reservation_id=row["reservation_id"],
        recipient_id=row["recipient_id"],
        request_id=row["request_id"],
        state=row["state"],
        delivered_at=row["delivered_at"],
        failure_reason=row["failure_reason"],
    )


def state_of(connection: Connection, *, request_id: UUID) -> Delivery | None:
    """What happened to an accepted delivery."""
    row = (
        connection.execute(
            text("select * from ops_private.delivery_state(:request)"),
            {"request": request_id},
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        return None
    return Delivery(
        id=row["delivery_id"],
        turn_id=row["turn_id"],
        reservation_id=None,  # type: ignore[arg-type]
        recipient_id=row["recipient_id"],
        request_id=request_id,
        state=row["state"],
        delivered_at=row["delivered_at"],
        failure_reason=row["failure_reason"],
    )


def publish(connection: Connection, *, batch: int = 10) -> int:
    """Drain pending outbox rows into deliveries. Returns how many published."""
    bounded = max(1, min(batch, MAX_PUBLISH_BATCH))
    try:
        return int(
            connection.execute(
                text("select ops_private.publish_interaction_outbox(:batch)"),
                {"batch": bounded},
            ).scalar_one()
        )
    except DBAPIError as error:
        raise protocol.classify(error, "Teslim kuyruğu işlenemedi") from None
