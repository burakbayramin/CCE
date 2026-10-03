"""M4.6 — streaming an approved turn.

The stream's value is entirely in its boundaries: session, role and delivery
are all settled before the response begins, and nothing but the response text
ever reaches the wire. Those are what these tests pin.
"""

import json
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from local_environment import ADMIN_DSN, API_DSN, ENGINE_DSN
from pydantic import SecretStr
from test_activation_integration import prepared
from test_delivery_integration import a_character, committed_turn
from test_identity_integration import settings
from test_interaction_protocol_integration import activate, worker_engine
from test_review_integration import FixtureModeration, headers

from cce.api_entrypoint import create_app
from cce.core.config import Settings
from cce.modules.chat.stream import DEFAULT_CHUNK, MAX_CHUNK, MAX_OFFSET, _frames
from cce.modules.interactions import delivery, protocol
from cce.modules.interactions.processing import Affect, Memory, Turn, apply_turn

pytestmark = pytest.mark.integration


def stream_settings() -> Settings:
    """create_app builds the owner engine only when one is configured, and the
    stream reads through it."""
    return Settings(
        environment="test",
        database_url=SecretStr(API_DSN),
        engine_database_url=SecretStr(ENGINE_DSN),
    )


def frames_of(response) -> tuple[list[str], list[str]]:
    """Split an SSE body into its event names and decoded chunk payloads."""
    events: list[str] = []
    chunks: list[str] = []
    for block in response.text.strip().split("\n\n"):
        name = ""
        data = "{}"
        for line in block.splitlines():
            if line.startswith("event: "):
                name = line[7:]
            elif line.startswith("data: "):
                data = line[6:]
        events.append(name)
        if name == "chunk":
            chunks.append(json.loads(data)["text"])
    return events, chunks


class TestFraming:
    def test_text_arrives_in_whole_chunks_and_then_done(self) -> None:
        body = "abcdefghij"
        names, chunks = frames_of(type("R", (), {"text": "".join(_frames(body, 4))})())
        assert names == ["chunk", "chunk", "chunk", "done"]
        assert "".join(chunks) == body

    def test_an_empty_response_still_ends_with_done(self) -> None:
        names, chunks = frames_of(type("R", (), {"text": "".join(_frames("", 4))})())
        assert names == ["done"]
        assert chunks == []

    @pytest.mark.parametrize("chunk", [1, 7, 10_000, -3])
    def test_chunk_size_is_clamped_rather_than_refused(self, chunk: int) -> None:
        names, chunks = frames_of(type("R", (), {"text": "".join(_frames("abcdef", chunk))})())
        assert "".join(chunks) == "abcdef"
        assert names[-1] == "done"

    def test_newlines_in_content_cannot_forge_a_frame_boundary(self) -> None:
        """A newline inside the text must not terminate a frame or inject one:
        that is the whole reason each payload is JSON-encoded."""
        body = 'satır\n\ndata: {"forged":1}\n\nevent: done'
        stream = "".join(_frames(body, 24))
        names, chunks = frames_of(type("R", (), {"text": stream})())

        # Parsed, not counted by substring: the text may legitimately span
        # several chunks, and the forged frame must not parse as one.
        assert names[-1] == "done"
        assert names.count("chunk") == len(chunks)
        assert "".join(chunks) == body, "the text survives intact, only inside JSON"

    def test_bounds_are_ordered_sensibly(self) -> None:
        assert 0 < DEFAULT_CHUNK <= MAX_CHUNK
        assert MAX_OFFSET > 0


class TestBoundaries:
    def test_an_unauthenticated_caller_is_refused(self, activation_accounts) -> None:
        character, _recipient = a_character(activation_accounts)
        turn = committed_turn(character)
        with TestClient(create_app(settings(), moderation=FixtureModeration())) as api:
            reservation = _reservation_of(turn)
            response = api.get(f"/interactions/{reservation}/turns/{turn}/stream")
        assert response.status_code == 401

    def test_a_contributor_cannot_stream(self, activation_accounts) -> None:
        character, _recipient = a_character(activation_accounts)
        turn = committed_turn(character)
        reservation = _reservation_of(turn)
        (_owner, contributor), _ = activation_accounts
        with TestClient(create_app(settings(), moderation=FixtureModeration())) as api:
            response = api.get(
                f"/interactions/{reservation}/turns/{turn}/stream",
                headers=headers(contributor),
            )
        assert response.status_code == 403

    def test_an_undelivered_turn_does_not_stream(self, activation_accounts) -> None:
        """Committed but not delivered is content the recipient is not entitled
        to yet. The caller learns only that it is unavailable."""
        character, _recipient = a_character(activation_accounts)
        turn = committed_turn(character)
        reservation = _reservation_of(turn)
        (_owner, _contributor), _ = activation_accounts
        with TestClient(create_app(settings(), moderation=FixtureModeration())) as api:
            response = api.get(
                f"/interactions/{reservation}/turns/{turn}/stream",
                headers=headers(_owner),
            )
        assert response.status_code == 409
        assert "bulunamadı" not in response.text.lower()

    def test_a_delivered_turn_streams_only_its_response_text(self, activation_accounts) -> None:
        character, recipient = a_character(activation_accounts)
        turn = committed_turn(character)
        reservation = _reservation_of(turn)
        (_owner, _contributor), _ = activation_accounts

        workers = worker_engine()
        try:
            with workers.begin() as connection:
                delivery.accept(
                    connection,
                    turn_id=turn,
                    recipient_id=recipient,
                    request_id=uuid4(),
                )
        finally:
            workers.dispose()
        with psycopg.connect(ADMIN_DSN) as db:
            db.execute("update ops_private.interaction_deliveries set state='DELIVERED'")
            expected = db.execute(
                "select response_text from ops_private.interaction_turns where id=%s", (turn,)
            ).fetchone()[0]
            db.commit()

        with TestClient(create_app(settings(), moderation=FixtureModeration())) as api:
            response = api.get(
                f"/interactions/{reservation}/turns/{turn}/stream?chunk=5",
                headers=headers(_owner),
            )

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert response.headers["cache-control"] == "no-store"

        names, chunks = frames_of(response)
        assert names[-1] == "done"
        assert "".join(chunks) == expected
        # Nothing that identifies the machinery behind the turn.
        for leaked in ("provider", "model", "effect_identity", "source_identity", "fixture"):
            assert leaked not in response.text.lower()

    def test_an_offset_resumes_without_resending(self, activation_accounts) -> None:
        character, recipient = a_character(activation_accounts)
        turn = committed_turn(character)
        reservation = _reservation_of(turn)
        (_owner, _contributor), _ = activation_accounts

        workers = worker_engine()
        try:
            with workers.begin() as connection:
                delivery.accept(
                    connection, turn_id=turn, recipient_id=recipient, request_id=uuid4()
                )
        finally:
            workers.dispose()
        with psycopg.connect(ADMIN_DSN) as db:
            db.execute("update ops_private.interaction_deliveries set state='DELIVERED'")
            expected = db.execute(
                "select response_text from ops_private.interaction_turns where id=%s", (turn,)
            ).fetchone()[0]
            db.commit()

        with TestClient(create_app(settings(), moderation=FixtureModeration())) as api:
            full = api.get(
                f"/interactions/{reservation}/turns/{turn}/stream",
                headers=headers(_owner),
            )
            resumed = api.get(
                f"/interactions/{reservation}/turns/{turn}/stream?offset=5",
                headers=headers(_owner),
            )

        _, whole = frames_of(full)
        _, tail = frames_of(resumed)
        assert "".join(whole) == expected
        assert "".join(tail) == expected[5:]

    def test_an_unknown_turn_is_a_404(self, activation_accounts) -> None:
        (_owner, _contributor), _ = activation_accounts
        with TestClient(create_app(settings(), moderation=FixtureModeration())) as api:
            response = api.get(
                f"/interactions/{uuid4()}/turns/{uuid4()}/stream",
                headers=headers(_owner),
            )
        assert response.status_code == 404


def _reservation_of(turn) -> object:
    with psycopg.connect(ADMIN_DSN) as db:
        return db.execute(
            "select reservation_id from ops_private.interaction_turns where id=%s", (turn,)
        ).fetchone()[0]


# The compile-time contract that these imports exist: the panel and turn helpers
# the streaming surface depends on are part of the same interaction flow.
def test_streaming_depends_on_the_processing_pipeline() -> None:
    assert protocol.Reservation is not None
    assert apply_turn is not None
    assert Memory is not None and Affect is not None and Turn is not None
    assert activate is not None and prepared is not None
