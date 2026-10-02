"""M4.2 — the job queue adapter.

Work is enqueued rather than polled from a table, and the acknowledgement rule
is the whole design: a message is acknowledged only after its result has
committed. The queue's visibility timeout then covers the work itself, so a
worker that dies mid-job leaves the message visible and it is retried instead
of the job being lost along with the message.

`JobQueue` is a protocol so the worker loop can be exercised without a database.
The only implementation here is pgmq, which is what Supabase Queues speaks.
"""

import json
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import Connection, text
from sqlalchemy.exc import DBAPIError

from cce.modules.contributions.repository import ContributionError

# Short enough that a dead worker's message returns to the queue quickly, long
# enough that a healthy handler finishes inside one visibility window.
DEFAULT_VISIBILITY_SECONDS = 60
QUEUE_NAME = "cce_jobs"


@dataclass(frozen=True)
class JobMessage:
    """One unit of work. `reservation_id` is the identity every handler must
    carry through to the commit, because that is what the fence checks."""

    msg_id: int
    reservation_id: str
    character_id: str
    purpose: str
    attempt: int


class JobQueue(Protocol):
    def send(self, reservation_id: str, character_id: str, purpose: str) -> None: ...

    def read(self, *, limit: int, visibility_timeout: int) -> list[JobMessage]: ...

    def ack(self, message: JobMessage) -> None: ...

    def close(self) -> None: ...


def _map(error: DBAPIError) -> ContributionError:
    message = str(getattr(error, "orig", error))
    if "queue" in message and "not exist" in message:
        return ContributionError(503, "İş kuyruğu hazır değil")
    return ContributionError(503, "İş kuyruğu erişilemedi")


class PgmqQueue:
    """Supabase Queues adapter.

    Ack is a delete, and it is deliberately not called anywhere except after the
    interaction result has committed. A redelivered message is safe because the
    effect identity is stable, so a retry collides with what already applied
    rather than duplicating it.
    """

    def __init__(self, connection: Connection, *, queue: str = QUEUE_NAME) -> None:
        self._connection = connection
        self._queue = queue

    def send(self, reservation_id: str, character_id: str, purpose: str) -> None:
        try:
            self._connection.execute(
                text("select pgmq.send(:queue, cast(:body as jsonb), 0)"),
                {
                    "queue": self._queue,
                    "body": json.dumps(
                        {
                            "reservation_id": reservation_id,
                            "character_id": character_id,
                            "purpose": purpose,
                        }
                    ),
                },
            )
        except DBAPIError as error:
            raise _map(error) from None

    def read(self, *, limit: int, visibility_timeout: int) -> list[JobMessage]:
        bounded = max(1, min(visibility_timeout, 900))
        try:
            rows = self._connection.execute(
                text(
                    "select msg_id, message->>'reservation_id' as reservation_id,"
                    " message->>'character_id' as character_id,"
                    " message->>'purpose' as purpose,"
                    " coalesce((message->>'attempt')::int, 1) as attempt "
                    "from pgmq.read_with_poll(:queue, :vt, :qty, :max_poll_seconds, true)"
                ),
                {
                    "queue": self._queue,
                    "vt": bounded,
                    "qty": max(1, min(limit, 10)),
                    "max_poll_seconds": 1,
                },
            ).mappings()
        except DBAPIError as error:
            raise _map(error) from None

        messages: list[JobMessage] = []
        for row in rows:
            if not row["reservation_id"]:
                # A message whose body is not ours. Leave it alone rather than
                # guessing: acknowledging it would drop work we do not own.
                continue
            messages.append(
                JobMessage(
                    msg_id=row["msg_id"],
                    reservation_id=str(row["reservation_id"]),
                    character_id=str(row["character_id"]),
                    purpose=str(row["purpose"]),
                    attempt=int(row["attempt"]),
                )
            )
        return messages

    def ack(self, message: JobMessage) -> None:
        """Delete the message. Call only after the result committed.

        Delete rather than archive: job_runs is the durable ledger, and the
        pgmq archive table would grow without bound for a queue that retries.
        """
        try:
            self._connection.execute(
                text("select pgmq.delete(:queue, :msg)"),
                {"queue": self._queue, "msg": message.msg_id},
            )
        except DBAPIError as error:
            raise _map(error) from None
