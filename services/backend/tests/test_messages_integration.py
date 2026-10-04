"""M4.6 — response tokens and the durable message log.

The two properties under test: a token cannot be replayed, and the two message
directions dedupe independently of each other.
"""

from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from local_environment import ADMIN_DSN
from test_delivery_integration import a_character, committed_turn
from test_identity_integration import settings
from test_interaction_protocol_integration import engine
from test_review_integration import FixtureModeration, headers

from cce.api_entrypoint import create_app
from cce.modules.interactions import messages

pytestmark = pytest.mark.integration


def a_turn(character):
    """A committed turn to hang messages off, with its reservation."""
    turn = committed_turn(character)
    with psycopg.connect(ADMIN_DSN) as db:
        reservation = db.execute(
            "select reservation_id from ops_private.interaction_turns where id = %s",
            (turn,),
        ).fetchone()[0]
    return turn, reservation


def recorded() -> int:
    with psycopg.connect(ADMIN_DSN) as db:
        return db.execute("select count(*) from ops_private.interaction_messages").fetchone()[0]


class TestMessageDedup:
    def test_a_replay_is_skipped_rather_than_duplicated(self, activation_accounts) -> None:
        character, _ = a_character(activation_accounts)
        turn, reservation = a_turn(character)
        identity = f"reply:turn:{uuid4()}"

        with engine().begin() as connection:
            first = messages.commit_message(
                connection,
                turn_id=turn,
                attempt_id=None,
                direction="REPLY",
                sequence=1,
                effect_identity=identity,
                body="ilk yanıt",
            )
            again = messages.commit_message(
                connection,
                turn_id=turn,
                attempt_id=None,
                direction="REPLY",
                sequence=1,
                effect_identity=identity,
                body="ilk yanıt",
            )

        assert first.recorded is True
        assert again.recorded is False, "a replay is a success, not a duplicate"
        assert again.sequence == 1

    def test_a_later_sequence_is_appended_in_order(self, activation_accounts) -> None:
        character, _ = a_character(activation_accounts)
        turn, _reservation = a_turn(character)

        with engine().begin() as connection:
            for sequence, body in ((1, "bir"), (2, "iki"), (3, "üç")):
                outcome = messages.commit_message(
                    connection,
                    turn_id=turn,
                    attempt_id=None,
                    direction="REPLY",
                    sequence=sequence,
                    effect_identity=f"reply:{turn}:{sequence}",
                    body=body,
                )
                assert outcome.recorded is True

            marks = messages.watermark(connection, turn_id=turn)
        assert marks["REPLY"] == 3

    def test_a_late_frame_does_not_move_the_sequence_backwards(self, activation_accounts) -> None:
        character, _ = a_character(activation_accounts)
        turn, _reservation = a_turn(character)

        with engine().begin() as connection:
            messages.commit_message(
                connection,
                turn_id=turn,
                attempt_id=None,
                direction="REPLY",
                sequence=5,
                effect_identity=f"reply:{turn}:5",
                body="beş",
            )
            late = messages.commit_message(
                connection,
                turn_id=turn,
                attempt_id=None,
                direction="REPLY",
                sequence=2,
                effect_identity=f"reply:{turn}:2",
                body="iki (geç)",
            )

        assert late.recorded is False, "a late frame is refused, not reordered"
        assert late.sequence == 5, "the watermark does not move backwards"

    def test_the_two_directions_dedupe_independently(self, activation_accounts) -> None:
        """A replayed inbound must not swallow the reply it caused."""
        character, _ = a_character(activation_accounts)
        turn, _reservation = a_turn(character)
        inbound_identity = f"inbound:{turn}:1"
        reply_identity = f"reply:{turn}:1"

        with engine().begin() as connection:
            inbound = messages.commit_message(
                connection,
                turn_id=turn,
                attempt_id=None,
                direction="INBOUND",
                sequence=1,
                effect_identity=inbound_identity,
                body="merhaba",
            )
            reply = messages.commit_message(
                connection,
                turn_id=turn,
                attempt_id=None,
                direction="REPLY",
                sequence=1,
                effect_identity=reply_identity,
                body="selam",
            )
            replay_inbound = messages.commit_message(
                connection,
                turn_id=turn,
                attempt_id=None,
                direction="INBOUND",
                sequence=1,
                effect_identity=inbound_identity,
                body="merhaba",
            )

            marks = messages.watermark(connection, turn_id=turn)

        assert inbound.recorded is True
        assert reply.recorded is True, "the reply is not suppressed by the inbound"
        assert replay_inbound.recorded is False
        assert marks == {"INBOUND": 1, "REPLY": 1}

    def test_an_unknown_direction_is_refused(self, activation_accounts) -> None:
        character, _ = a_character(activation_accounts)
        turn, _reservation = a_turn(character)
        with engine().begin() as connection:
            with pytest.raises(ValueError):
                messages.commit_message(
                    connection,
                    turn_id=turn,
                    attempt_id=None,  # type: ignore[arg-type]
                    direction="SIDEWAYS",
                    sequence=1,
                    effect_identity=f"x:{uuid4()}",
                    body="nope",
                )


class TestResponseTokens:
    def test_a_token_is_stored_only_as_a_hash(self, activation_accounts) -> None:
        character, _ = a_character(activation_accounts)
        turn, reservation = a_turn(character)
        attempt, reader = uuid4(), uuid4()
        secret = messages.new_token()

        with engine().begin() as connection:
            messages.issue_token(
                connection,
                token=secret,
                reservation_id=reservation,
                turn_id=turn,
                attempt_id=attempt,
                issued_to=reader,
            )

        with psycopg.connect(ADMIN_DSN) as db:
            stored = db.execute(
                "select token_hash from ops_private.interaction_response_tokens"
            ).fetchall()
        assert secret not in [row[0] for row in stored], "the token itself is never stored"
        assert stored, "but its hash is"

    def test_a_short_token_is_refused_before_it_reaches_the_database(self) -> None:
        with pytest.raises(ValueError):
            messages.issue_token(
                None,  # type: ignore[arg-type]
                token="kısa",
                reservation_id=uuid4(),
                turn_id=uuid4(),
                attempt_id=uuid4(),
                issued_to=uuid4(),
            )

    def test_minted_tokens_are_unguessable(self) -> None:
        tokens = {messages.new_token() for _ in range(64)}
        assert len(tokens) == 64, "token generation must not collide"

    def test_an_unknown_token_has_no_expiry(self) -> None:
        with engine().begin() as connection:
            assert messages.token_expiry(connection, token=messages.new_token()) is None


class TestPollingFallback:
    @pytest.mark.parametrize(
        "attempt,expected_ceiling",
        [(1, 2.0), (2, 4.0), (3, 8.0), (6, 30.0), (20, 30.0)],
    )
    def test_backoff_grows_and_is_capped(self, attempt: int, expected_ceiling: float) -> None:
        """Realtime failing must not turn a reconnect storm into a load test."""
        delay = messages.retry_delay(attempt)
        assert delay <= 30.0
        assert delay == expected_ceiling

    def test_a_non_positive_attempt_is_refused(self) -> None:
        with pytest.raises(ValueError):
            messages.retry_delay(0)


class TestApiUnaffected:
    def test_the_operations_surface_still_refuses_a_contributor(self, activation_accounts) -> None:
        (_owner, contributor), _ = activation_accounts
        with TestClient(create_app(settings(), moderation=FixtureModeration())) as api:
            assert api.get("/operations/snapshot", headers=headers(contributor)).status_code == 403
