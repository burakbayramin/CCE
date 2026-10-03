"""M4.6 — streaming an approved turn.

Three boundaries decide whether a turn may stream at all, and all three are
checked before a single byte is emitted:

* **Session.** The caller must be authenticated, and the identity is resolved
  through the same dependency as every other endpoint, so a revoked session
  stops the stream at the first request rather than mid-delivery.
* **Owner.** Only the World Owner reads this surface. It is the private admin
  chat, not a public projection.
* **Delivery.** Only a turn that has actually been delivered streams. A turn
  that is committed but not delivered is content the recipient is not entitled
  to yet, and a quarantined turn is not content at all.

What leaves the server is exactly the response text, chunked. Provider names,
processing versions, prompts, effect identities and other characters' state
never appear in the stream.
"""

import json
import logging
from collections.abc import Iterator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Connection, Engine, text
from sqlalchemy.exc import SQLAlchemyError

from cce.modules.contributions.repository import ContributionError
from cce.modules.identity.authentication import TokenVerifier
from cce.modules.identity.domain import Actor
from cce.modules.identity.repository import actor_transaction, identity_context
from cce.modules.identity.router import actor_dependency

#: How much of a response is buffered into one SSE frame.
DEFAULT_CHUNK = 240
MAX_CHUNK = 2000
#: A cursor may not start inside the text; this bounds a resumed stream.
MAX_OFFSET = 8000

logger = logging.getLogger(__name__)


class StreamInfo(BaseModel):
    """What the client learns before any content: length and whether more is
    coming. Deliberately no identifiers, so the stream cannot be correlated
    with internal rows by a client that merely has a URL."""

    model_config = ConfigDict(extra="forbid")

    length: int = Field(ge=0)


def _frames(text_body: str, chunk: int) -> Iterator[str]:
    """Yield the response text as SSE data frames.

    JSON-encoded per frame rather than raw so a newline or a stray ``
    cannot terminate a frame early or inject one.
    """
    size = max(1, min(chunk, MAX_CHUNK))
    for start in range(0, len(text_body), size):
        piece = text_body[start : start + size]
        frame = json.dumps({"text": piece}, ensure_ascii=False)
        yield f"event: chunk\ndata: {frame}\n\n"
    yield "event: done\ndata: {}\n\n"


def _resolve(
    connection: Connection,
    reservation_id: str,
    turn_id: str,
    offset: int,
) -> str:
    row = (
        connection.execute(
            text(
                "select t.response_text as response_text, "
                "  (select count(*) from ops_private.interaction_deliveries d "
                "    where d.turn_id = t.id and d.state = 'DELIVERED') as delivered "
                "from ops_private.interaction_turns t "
                "where t.id = :turn and t.reservation_id = :reservation"
            ),
            {"turn": turn_id, "reservation": reservation_id},
        )
        .mappings()
        .one_or_none()
    )

    if row is None:
        raise ContributionError(404, "Tur bulunamadı")
    if not row["delivered"]:
        # Not a leak: the caller cannot learn that the turn exists, only that
        # it is not available to them.
        raise ContributionError(409, "Tur henüz teslim edilmedi")

    body = row["response_text"] or ""
    return body[offset:]


def chat_router(engine: Engine, owner_engine: Engine | None, verifier: TokenVerifier) -> APIRouter:
    verified_actor = actor_dependency(verifier)
    router = APIRouter(prefix="/interactions", tags=["interactions"])
    responses: dict[int | str, dict[str, object]] = {
        401: {"description": "Authentication required"},
        403: {"description": "World Owner role required"},
        404: {"description": "Turn not found"},
        409: {"description": "Turn not delivered"},
        503: {"description": "Interaction service unavailable"},
    }

    @router.get(
        "/{reservation_id}/turns/{turn_id}/stream",
        response_class=StreamingResponse,
        responses=responses,
        operation_id="stream_interaction_turn",
    )
    def stream_turn(
        reservation_id: str,
        turn_id: str,
        actor: Annotated[Actor, Depends(verified_actor)],
        offset: int = Query(default=0, ge=0, le=MAX_OFFSET),
        chunk: int = Query(default=DEFAULT_CHUNK, ge=1, le=MAX_CHUNK),
    ) -> StreamingResponse:
        """Session, role and delivery are all settled before the response
        starts, and the connection is closed before the first byte is sent so a
        slow client cannot hold a pool slot open."""
        if owner_engine is None:
            raise HTTPException(503, "Owner command database is not configured")

        try:
            # The session and the role are resolved on the API engine: identity
            # reads public.profiles, which only the API role may read. Only the
            # turn content needs the owner plane.
            with actor_transaction(engine, actor) as session:
                if identity_context(session, actor)["role"] != "world_owner":
                    raise HTTPException(403, "World Owner role required")
        except HTTPException:
            raise
        except SQLAlchemyError as error:
            logger.warning("cce:stream-identity failed: %s", error)
            raise HTTPException(503, "Identity service unavailable") from None

        try:
            with actor_transaction(owner_engine, actor) as connection:
                body = _resolve(connection, reservation_id, turn_id, offset)
        except HTTPException:
            raise
        except ContributionError as error:
            raise HTTPException(404 if error.status == 404 else 409, error.detail) from None
        except SQLAlchemyError as error:
            # The reason is logged, never returned: the detail can name rows
            # and the client must not learn whether they exist.
            logger.warning("cce:stream-resolve failed: %s", error)
            raise HTTPException(503, "Interaction service unavailable") from None

        return StreamingResponse(
            _frames(body, chunk),
            media_type="text/event-stream",
            headers={
                # Private chat content is never cached and never buffered by a
                # proxy, which would defeat the point of streaming it.
                "Cache-Control": "no-store",
                "X-Accel-Buffering": "no",
            },
        )

    return router
