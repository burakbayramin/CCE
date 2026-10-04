"""M4.6 — response tokens, sequence control, and the durable message log.

Two properties a bare stream endpoint cannot give.

**A response token is scoped, expiring and single-use.** It authorises one
attempt of one turn, for one reader, for a moment. Only its hash is stored, so
a database read cannot replay it. A token whose attempt is no longer the live
one stops being valid with it — which is what makes a lapsed lease actually
fence the stream rather than merely the write.

**Inbound messages and final replies dedupe separately.** A retried inbound
delivery must not be recorded twice, and a re-sent reply must not append a
second copy — but neither may suppress the other, or a replayed inbound would
swallow the reply it caused.
"""

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import Connection, text
from sqlalchemy.exc import DBAPIError

from cce.modules.interactions import protocol

Direction = str  # INBOUND | REPLY
DIRECTIONS: frozenset[str] = frozenset({"INBOUND", "REPLY"})

#: Long enough to finish a read, short enough that a leaked token dies quickly.
DEFAULT_TOKEN_TTL_SECONDS = 120
MAX_TOKEN_TTL_SECONDS = 600
TOKEN_BYTES = 32


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@dataclass(frozen=True)
class MessageRecord:
    """What a commit did. `recorded` is False for a replay, which is a
    success rather than a conflict."""

    recorded: bool
    sequence: int


def issue_token(
    connection: Connection,
    *,
    token: str,
    reservation_id: UUID,
    turn_id: UUID,
    attempt_id: UUID,
    issued_to: UUID,
    ttl_seconds: int = DEFAULT_TOKEN_TTL_SECONDS,
) -> str:
    """Register a freshly minted token. The caller generates the value; only
    its hash reaches the database."""
    if not token or len(token) < 32:
        raise ValueError("a response token must be at least 32 characters")
    bounded = max(10, min(ttl_seconds, MAX_TOKEN_TTL_SECONDS))
    try:
        connection.execute(
            text(
                "select ops_private.issue_response_token("
                ":hash,:reservation,:turn,:attempt,:issued_to,:ttl)"
            ),
            {
                "hash": _hash(token),
                "reservation": reservation_id,
                "turn": turn_id,
                "attempt": attempt_id,
                "issued_to": issued_to,
                "ttl": bounded,
            },
        )
    except DBAPIError as error:
        raise protocol.classify(error, "Yanıt token'ı üretilemedi") from None
    return token


def new_token() -> str:
    return secrets.token_urlsafe(TOKEN_BYTES)


def commit_message(
    connection: Connection,
    *,
    turn_id: UUID,
    attempt_id: UUID | None,
    direction: Direction,
    sequence: int,
    effect_identity: str,
    body: str,
) -> MessageRecord:
    """Append one message. A replay is skipped, never duplicated."""
    if direction not in DIRECTIONS:
        raise ValueError(f"unknown message direction: {direction!r}")
    if sequence < 1:
        raise ValueError("sequence must be positive")
    try:
        row = (
            connection.execute(
                text(
                    "select * from ops_private.commit_message("
                    ":turn,:attempt,:direction,:sequence,:identity,:body)"
                ),
                {
                    "turn": turn_id,
                    "attempt": attempt_id,
                    "direction": direction,
                    "sequence": sequence,
                    "identity": effect_identity,
                    "body": body,
                },
            )
            .mappings()
            .one()
        )
    except DBAPIError as error:
        raise protocol.classify(error, "Mesaj kaydedilemedi") from None
    return MessageRecord(recorded=bool(row["recorded"]), sequence=int(row["accepted_sequence"]))


def watermark(connection: Connection, *, turn_id: UUID) -> dict[str, int]:
    """The highest accepted sequence per direction.

    A resuming reader asks the database rather than trusting a local counter
    it may have lost on reconnect.
    """
    rows = (
        connection.execute(
            text("select * from ops_private.message_watermark(:turn)"),
            {"turn": turn_id},
        )
        .mappings()
        .all()
    )
    return {row["direction"]: int(row["sequence"]) for row in rows}


def token_expiry(connection: Connection, *, token: str) -> datetime | None:
    """When a token dies. Expiry is observable so a client can refresh rather
    than discover it as a mid-stream failure."""
    row = (
        connection.execute(
            text(
                "select expires_at from ops_private.interaction_response_tokens "
                "where token_hash = :hash and revoked_at is null and consumed_at is null"
            ),
            {"hash": _hash(token)},
        )
        .mappings()
        .one_or_none()
    )
    return row["expires_at"] if row else None


def retry_delay(attempt: int, *, base: float = 2.0, ceiling: float = 30.0) -> float:
    """Exponential backoff for the polling fallback, capped so a reconnect
    storm cannot turn into a load test against the API."""
    if attempt < 1:
        raise ValueError("attempt must be positive")
    return min(base ** min(attempt, 10), ceiling)
