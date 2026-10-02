"""M4.1 — the shared durable-job protocol.

Everything M4 builds on lives here: a character holds one interaction
reservation, a worker holds a fenced lease with an ownership generation, a
domain effect is applied at most once under a stable identity, and the result
lands in one transaction that also emits its outbox rows.

Two rules from WADR-006 and WADR-011 shape the API and are enforced in the
database rather than here:

* Losing a lease does **not** make the character available again. The
  reservation stays held until it is explicitly resolved, because a worker
  whose lease lapsed may still be writing to the character.
* The effect identity deliberately excludes any model name or processing
  version, so retrying the same experience under a different model collides
  with the effects already applied instead of duplicating them.

This module is deliberately thin: it validates input and shapes rows. It holds
no state of its own, so the fencing rules cannot be bypassed by importing
around them.
"""

import json
import logging
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from sqlalchemy import Connection, text
from sqlalchemy.exc import DBAPIError

from cce.modules.contributions.repository import ContributionError

Purpose = Literal["ADMIN_CHAT", "SCENE"]
EffectKind = Literal["MEMORY", "AFFECT", "RELATIONSHIP", "GOAL", "TRANSCRIPT"]

MINIMUM_REASON = 10
MAXIMUM_REASON = 1000
DEFAULT_LEASE_SECONDS = 300

logger = logging.getLogger(__name__)

# Every distinct refusal the protocol can produce, in the wording the database
# uses. Each maps to the one message a caller should see: "retry", "wait for an
# operator" and "this input is wrong" are three different operational
# situations and must not collapse into one.
_FAILURES: tuple[tuple[str, int, str], ...] = (
    (
        "Stale reservation requires operator resolution",
        409,
        "Kiralama süresi doldu ve bir operatör kararı bekliyor",
    ),
    (
        # fence_interaction and resolve_interaction word this differently.
        "Lease generation is stale",
        409,
        "Kiralama nesli değişti; yeniden denemelisin",
    ),
    (
        "Reservation generation is stale",
        409,
        "Rezervasyon nesli değişti; yeniden denemelisin",
    ),
    ("Lease belongs to another worker", 409, "Kiralama başka bir worker'a ait"),
    ("Lease expired", 409, "Kiralama artık geçerli değil"),
    ("Character is reserved", 409, "Karakter şu anda başka bir etkileşimde"),
    ("Reservation is not held", 409, "Rezervasyon artık tutulmuyor"),
    ("Reservation is no longer held", 409, "Rezervasyon artık tutulmuyor"),
    ("Unknown job run", 404, "İş kaydı bulunamadı"),
    ("Resolution reason must be", 422, "Gerekçe 10-1000 karakter olmalı"),
    ("Unknown quarantine reason", 422, "Bilinmeyen quarantine gerekçesi"),
    ("Unknown interaction purpose", 422, "Bilinmeyen etkileşim amacı"),
    ("Effect requires identity and kind", 422, "Etki kimliği ve türü eksik"),
    ("Unknown effect kind", 422, "Etki kaydı geçersiz"),
)


@dataclass(frozen=True)
class Reservation:
    """A held character. `ownership_generation` is the fence value."""

    id: UUID
    character_id: UUID
    purpose: str
    state: str
    ownership_generation: int
    lease_until: object | None
    lease_holder: str | None
    effect_identity: str | None


@dataclass(frozen=True)
class JobRun:
    """One attempt. `ownership_generation` is copied from the lease that
    authorised it, so a stale run can be recognised without a join."""

    id: UUID
    reservation_id: UUID
    attempt_number: int
    ownership_generation: int
    state: str


@dataclass(frozen=True)
class EffectOutcome:
    """Result counts. `skipped` is not failure: it means the effect was already
    applied under the same identity."""

    applied: int
    skipped: int


def classify(error: DBAPIError, fallback: str) -> ContributionError:
    """Translate a database refusal into the one error a caller should see.

    Exposed so other protocol modules translate errors the same way instead of
    each inventing its own mapping.
    """
    message = str(getattr(error, "orig", error))
    logger.warning("cce:interaction-protocol error=%s", message)
    for needle, status, detail in _FAILURES:
        if needle in message:
            return ContributionError(status, detail)
    return ContributionError(503, fallback)


def _map(error: DBAPIError) -> ContributionError:
    """Preserve the database's reason; never collapse it into a generic 500.

    The distinction between "the lease is stale" and "the effect is malformed"
    is the difference between a retry and an operator intervention.

    Matching is by exact substring rather than by scanning for a word: four
    distinct lease failures used to collapse into one message, which made the
    real reason unrecoverable from the outside.
    """
    return classify(error, "İş protokolü kaydı tamamlanamadı")


def claim(
    connection: Connection,
    *,
    character_id: UUID,
    purpose: Purpose,
    holder: str,
    command_id: UUID,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
) -> Reservation:
    """Take or renew the character's single reservation.

    Returns the live reservation. Raises 409 when another holder holds an
    unexpired lease — deliberately not a retry, because the character is
    genuinely busy.
    """
    try:
        row = (
            connection.execute(
                text(
                    "select * from ops_private.claim_interaction("
                    ":id,:purpose,:holder,:lease,:command)"
                ),
                {
                    "id": character_id,
                    "purpose": purpose,
                    "holder": holder,
                    "lease": lease_seconds,
                    "command": command_id,
                },
            )
            .mappings()
            .one()
        )
    except DBAPIError as error:
        raise _map(error) from None
    return Reservation(
        id=row["id"],
        character_id=row["character_id"],
        purpose=row["purpose"],
        state=row["state"],
        ownership_generation=row["ownership_generation"],
        lease_until=row["lease_until"],
        lease_holder=row["lease_holder"],
        effect_identity=row["effect_identity"],
    )


def begin_attempt(
    connection: Connection,
    *,
    reservation: Reservation,
    worker_id: str,
) -> JobRun:
    """Open an attempt against the reservation's current generation."""
    try:
        row = (
            connection.execute(
                text(
                    "select * from ops_private.begin_interaction_attempt("
                    ":id,:generation,:holder,:worker)"
                ),
                {
                    "id": reservation.id,
                    "generation": reservation.ownership_generation,
                    "holder": reservation.lease_holder or "",
                    "worker": worker_id,
                },
            )
            .mappings()
            .one()
        )
    except DBAPIError as error:
        raise _map(error) from None
    return JobRun(
        id=row["id"],
        reservation_id=row["reservation_id"],
        attempt_number=row["attempt_number"],
        ownership_generation=row["ownership_generation"],
        state=row["state"],
    )


def commit_result(
    connection: Connection,
    *,
    run: JobRun,
    reservation: Reservation,
    holder: str,
    effect_identity: str,
    effects: list[dict[str, object]],
) -> EffectOutcome:
    """Apply every effect under its stable identity and close the reservation.

    Caller must have already produced `effects`; this function only validates
    and commits. An empty list is a valid result: a scene that changed nothing
    still resolves its reservation rather than leaking it.
    """
    try:
        row = (
            connection.execute(
                text(
                    "select * from ops_private.commit_interaction_result("
                    ":run,:generation,:holder,:identity,cast(:effects as jsonb))"
                ),
                {
                    "run": run.id,
                    "generation": reservation.ownership_generation,
                    "holder": holder,
                    "identity": effect_identity,
                    # A list of effect objects has no psycopg adapter, so it is
                    # serialised here rather than left to fail at the driver.
                    "effects": json.dumps(effects),
                },
            )
            .mappings()
            .one()
        )
    except DBAPIError as error:
        raise _map(error) from None
    return EffectOutcome(applied=row["applied"], skipped=row["skipped"])


def stale_reservations(connection: Connection) -> list[dict[str, object]]:
    """Expired leases awaiting an operator decision.

    Nothing is auto-released here. That is the point: the character stays
    reserved until `resolve` is called with a reason.
    """
    rows = connection.execute(text("select * from ops_private.stale_interactions()")).mappings()
    return [dict(row) for row in rows]


def resolve(
    connection: Connection,
    *,
    reservation_id: UUID,
    expected_generation: int,
    reason: str,
) -> Reservation:
    """Operator decision on a stuck reservation.

    Abandoned attempts are recorded, never deleted, so an operator can see
    what the lost worker was doing.
    """
    try:
        row = (
            connection.execute(
                text("select * from ops_private.resolve_interaction(:id,:generation,:reason)"),
                {
                    "id": reservation_id,
                    "generation": expected_generation,
                    "reason": reason,
                },
            )
            .mappings()
            .one()
        )
    except DBAPIError as error:
        raise _map(error) from None
    return Reservation(
        id=row["id"],
        character_id=row["character_id"],
        purpose=row["purpose"],
        state=row["state"],
        ownership_generation=row["ownership_generation"],
        lease_until=row["lease_until"],
        lease_holder=row["lease_holder"],
        effect_identity=row["effect_identity"],
    )
