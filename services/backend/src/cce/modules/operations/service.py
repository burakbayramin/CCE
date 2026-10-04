"""M4.7 — the operations surface.

Two questions, one read and two commands:

* **Who is alive, and what is stuck?** `snapshot` answers both without exposing
  provider detail, effect identities or turn content.
* **What do I do about it?** `resolve_stuck` frees a character whose worker is
  not coming back. `requeue` tries that work again. They answer different
  questions, so they stay separate.

Both commands require the World Owner identity, take a reason, and re-check
the generation rather than trusting the caller's copy of it.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import Connection, text
from sqlalchemy.exc import DBAPIError

from cce.modules.interactions import protocol

#: A worker that has not been seen for this long is reported OFFLINE. Two
#: minutes is longer than a heartbeat interval and shorter than a lunch.
DEFAULT_STALE_SECONDS = 120


@dataclass(frozen=True)
class WorkerRow:
    worker_id: str
    kind: str
    state: str
    last_seen_at: datetime | None
    max_concurrency: int
    current_job: UUID | None


@dataclass(frozen=True)
class ReservationRow:
    id: UUID
    character_id: UUID | None
    purpose: str | None
    state: str | None
    ownership_generation: int | None
    lease_until: datetime | None
    open_run_attempts: int
    last_attempt_state: str | None
    quarantined: bool

    def lapsed(self) -> bool:
        """A lease that ran out while the reservation is still held. The
        character is not free, and nobody is working on it."""
        return self.lease_until is not None and self.lease_until <= datetime.now(
            self.lease_until.tzinfo
        )


@dataclass(frozen=True)
class OperationsRow:
    """One worker and, where it is busy, the reservation it holds."""

    worker: WorkerRow
    reservation: ReservationRow | None

    def needs_a_person(self) -> bool:
        """Whether this row is something an operator should look at."""
        if self.worker.state == "OFFLINE":
            return True
        if self.reservation is None:
            return False
        return self.reservation.quarantined or self.reservation.lapsed()


def snapshot(
    connection: Connection, *, stale_seconds: int = DEFAULT_STALE_SECONDS
) -> list[OperationsRow]:
    rows = (
        connection.execute(
            text("select * from ops_private.operations_snapshot(:stale)"),
            {"stale": max(10, min(stale_seconds, 3600))},
        )
        .mappings()
        .all()
    )

    result: list[OperationsRow] = []
    for row in rows:
        worker = WorkerRow(
            worker_id=row["worker_id"],
            kind=row["worker_kind"],
            state=row["worker_state"],
            last_seen_at=row["last_seen_at"],
            max_concurrency=row["worker_max_concurrency"],
            current_job=row["worker_current_job"],
        )
        reservation = None
        if row["reservation_id"] is not None:
            reservation = ReservationRow(
                id=row["reservation_id"],
                character_id=row["reservation_character"],
                purpose=row["reservation_purpose"],
                state=row["reservation_state"],
                ownership_generation=row["reservation_generation"],
                lease_until=row["reservation_lease_until"],
                open_run_attempts=row["open_run_attempts"] or 0,
                last_attempt_state=row["last_attempt_state"],
                quarantined=bool(row["quarantined"]),
            )
        result.append(OperationsRow(worker=worker, reservation=reservation))
    return result


def resolve_stuck(
    connection: Connection,
    *,
    reservation_id: UUID,
    expected_generation: int,
    reason: str,
) -> None:
    """Free a character whose worker is not coming back.

    Abandoned attempts are recorded, never deleted, so an operator can still
    see what the lost worker was doing.
    """
    try:
        connection.execute(
            text("select ops_private.resolve_interaction(:id,:generation,:reason)"),
            {"id": reservation_id, "generation": expected_generation, "reason": reason},
        )
    except DBAPIError as error:
        raise protocol.classify(error, "Rezervasyon çözümlenemedi") from None


def requeue(
    connection: Connection,
    *,
    reservation_id: UUID,
    expected_generation: int,
    worker_id: str,
    reason: str,
) -> None:
    """Try a failed attempt again.

    The attempt number keeps climbing, so the recovery scan still sees the
    history rather than a silently reset job, and a late worker whose lease
    lapsed cannot revive its own work.
    """
    try:
        connection.execute(
            text("select ops_private.requeue_interaction(:id,:generation,:worker,:reason)"),
            {
                "id": reservation_id,
                "generation": expected_generation,
                "worker": worker_id,
                "reason": reason,
            },
        )
    except DBAPIError as error:
        raise protocol.classify(error, "İş yeniden kuyruğa alınamadı") from None
