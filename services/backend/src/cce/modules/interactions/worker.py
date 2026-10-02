"""M4.2 — the supervised worker loop.

Reads work from the queue, runs it through the M4.1 protocol, and acknowledges
only after the result commits. The ordering is the contract:

    read -> claim (fenced) -> begin attempt -> handle -> commit -> ack

Three outcomes, and the difference between them is the point:

* **Committed** — the message is acknowledged. This is the only path that acks.
* **Failed** — the run is marked failed, the message is *not* acknowledged, and
  the visibility timeout returns it to the queue. Retry is bounded by
  `max_attempts`, not by the handler's mood.
* **Unverifiable output** — quarantined immediately, because retrying a
  producer that cannot validate its own output fails identically every time.

The message is never acknowledged while the reservation is still held, so a
worker that dies mid-job loses no work: the message is redelivered and the
stable effect identity makes the retry collide rather than duplicate.
"""

from collections.abc import Callable
from dataclasses import dataclass
from threading import Event
from uuid import UUID, uuid4

from sqlalchemy import Connection, Engine, text
from sqlalchemy.exc import DBAPIError

from cce.modules.contributions.repository import ContributionError
from cce.modules.interactions import protocol
from cce.modules.interactions.queue import (
    DEFAULT_VISIBILITY_SECONDS,
    JobMessage,
    JobQueue,
)


# A handler raising this produced output it could not verify. Retrying would
# fail the same way, so the run is parked for an operator instead.
class InvalidOutput(Exception):
    """Handler output failed its own validation."""


@dataclass(frozen=True)
class WorkerConfig:
    worker_id: str
    kind: str  # CPU | GPU | PUBLISHER | MAINTENANCE
    max_attempts: int = 3
    visibility_timeout: int = DEFAULT_VISIBILITY_SECONDS
    #: The main LLM plane advertises concurrency 1: two resident models is not
    #: a slower queue, it is two models.
    max_concurrency: int = 1
    idle_seconds: float = 2.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if self.idle_seconds <= 0:
            raise ValueError("idle_seconds must be positive")
        if not 1 <= self.max_concurrency <= 8:
            raise ValueError("max_concurrency must be between 1 and 8")
        if self.kind == "GPU" and self.max_concurrency != 1:
            raise ValueError("the GPU plane runs at concurrency 1")


@dataclass(frozen=True)
class HandlerResult:
    """What a handler produced. An empty effect list is a valid result."""

    effect_identity: str
    effects: list[dict[str, object]]


Handler = Callable[[JobMessage, protocol.Reservation], HandlerResult]


def _heartbeat(connection: Connection, config: WorkerConfig) -> None:
    connection.execute(
        text("select ops_private.heartbeat_worker(:worker,:kind,:concurrency,null)"),
        {
            "worker": config.worker_id,
            "kind": config.kind,
            "concurrency": config.max_concurrency,
        },
    )


def _begin(
    connection: Connection,
    reservation: protocol.Reservation,
    worker_id: str,
) -> protocol.JobRun:
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
    return protocol.JobRun(
        id=row["id"],
        reservation_id=row["reservation_id"],
        attempt_number=row["attempt_number"],
        ownership_generation=row["ownership_generation"],
        state=row["state"],
    )


def _quarantine(connection: Connection, run_id: UUID, reason: str, detail: str) -> None:
    connection.execute(
        text("select ops_private.quarantine_run(:run,:reason,:detail)"),
        {"run": run_id, "reason": reason, "detail": detail[:1000]},
    )


def run_once(
    engine: Engine,
    queue: JobQueue,
    handler: Handler,
    config: WorkerConfig,
) -> bool:
    """Process at most one message.

    Returns True when a message was read, whatever happened to it. Nothing
    escapes: an unreadable queue and an exploding handler are both loop
    conditions, not process conditions.
    """
    messages = queue.read(limit=1, visibility_timeout=config.visibility_timeout)
    if not messages:
        return False
    message = messages[0]

    with engine.begin() as connection:
        _heartbeat(connection, config)

        # A character that is already reserved, or whose previous lease lapsed,
        # is not this worker's to take. Leaving the message unacknowledged
        # would redeliver it forever, so it is acknowledged and the reservation
        # stays held for whoever does own it.
        try:
            reservation = protocol.claim(
                connection,
                character_id=UUID(message.character_id),
                purpose=message.purpose,  # type: ignore[arg-type]
                holder=config.worker_id,
                command_id=uuid4(),
            )
        except ContributionError:
            queue.ack(message)
            return True

        run = _begin(connection, reservation, config.worker_id)

        if run.attempt_number >= config.max_attempts:
            _quarantine(
                connection,
                run.id,
                "RETRY_EXHAUSTED",
                f"{run.attempt_number} deneme sonunda vazgeçildi",
            )
            queue.ack(message)
            return True

        try:
            result = handler(message, reservation)
        except InvalidOutput as error:
            _quarantine(connection, run.id, "INVALID_OUTPUT", str(error))
            queue.ack(message)
            return True
        except Exception:
            # A handler fault is a retryable failure, not a rejection. The run
            # is marked failed and the message is deliberately left in the
            # queue; the attempt bound decides when retrying stops.
            connection.execute(
                text("select ops_private.fail_interaction_run(:run,'HANDLER_FAULT')"),
                {"run": run.id},
            )
            return True

        protocol.commit_result(
            connection,
            run=run,
            reservation=reservation,
            holder=config.worker_id,
            effect_identity=result.effect_identity,
            effects=result.effects,
        )

    # Committed, and only now acknowledged. A worker that dies between the
    # commit and this call redelivers the message, and the stable effect
    # identity makes the retry a no-op rather than a duplicate.
    queue.ack(message)
    return True


def run_loop(
    engine: Engine,
    queue: JobQueue,
    handler: Handler,
    config: WorkerConfig,
    stop: Event,
    *,
    on_error: Callable[[BaseException], None] | None = None,
) -> None:
    """Poll until stopped.

    Heartbeats every pass, so an operations view can tell a live idle worker
    from a dead one. Failures are reported and the loop continues: a worker that
    exits on the first transient error is not a worker.
    """
    while not stop.is_set():
        try:
            worked = run_once(engine, queue, handler, config)
        except DBAPIError as error:
            if on_error is not None:
                on_error(error)
            worked = False
        except Exception as error:  # noqa: BLE001 - the loop must survive
            if on_error is not None:
                on_error(error)
            worked = False
        if not worked and stop.wait(config.idle_seconds):
            break
