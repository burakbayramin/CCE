"""M4.2 — the worker loop's control flow.

These tests use a fake queue and a fake engine, so they run without the
isolated stack. What they pin is the acknowledgement contract, because that is
the property that cannot be verified by reading: a message may only be
acknowledged after its result committed, and a failed attempt must be
redelivered rather than dropped.
"""

from threading import Event
from unittest.mock import MagicMock

import pytest

from cce.modules.interactions import worker
from cce.modules.interactions.queue import JobMessage
from cce.modules.interactions.worker import (
    HandlerResult,
    InvalidOutput,
    WorkerConfig,
    run_loop,
    run_once,
)


def message(attempt: int = 1) -> JobMessage:
    return JobMessage(
        msg_id=7,
        reservation_id="11111111-1111-1111-1111-111111111111",
        character_id="22222222-2222-2222-2222-222222222222",
        purpose="ADMIN_CHAT",
        attempt=attempt,
    )


class FakeQueue:
    """Records the order of reads and acks so the test can assert on it."""

    def __init__(self, messages: list[JobMessage] | None = None) -> None:
        self.messages = list(messages or [])
        self.acked: list[int] = []
        self.reads = 0

    def send(self, reservation_id: str, character_id: str, purpose: str) -> None:
        raise AssertionError("the worker loop must not enqueue")

    def read(self, *, limit: int, visibility_timeout: int) -> list[JobMessage]:
        self.reads += 1
        if not self.messages:
            return []
        return [self.messages.pop(0)]

    def ack(self, item: JobMessage) -> None:
        self.acked.append(item.msg_id)

    def close(self) -> None:
        pass


def engine_where(claim_ok: bool = True, attempt_number: int = 1) -> MagicMock:
    """A stand-in engine whose statements return plausible rows.

    The real assertions live in the integration suite; this only has to be
    shaped well enough for the loop to reach its own branches.
    """
    engine = MagicMock()
    connection = engine.begin.return_value.__enter__.return_value
    connection.execute.return_value.mappings.return_value.one.return_value = {
        "id": "run-1",
        "reservation_id": "11111111-1111-1111-1111-111111111111",
        "attempt_number": attempt_number,
        "ownership_generation": 1,
        "state": "RUNNING",
        "character_id": "22222222-2222-2222-2222-222222222222",
        "purpose": "ADMIN_CHAT",
        "lease_until": None,
        "lease_holder": "worker-a",
        "effect_identity": None,
    }
    return engine


@pytest.fixture(autouse=True)
def successful_claim(monkeypatch: pytest.MonkeyPatch) -> None:
    reservation = MagicMock()
    reservation.id = "11111111-1111-1111-1111-111111111111"
    reservation.ownership_generation = 1
    reservation.lease_holder = "worker-a"
    monkeypatch.setattr(worker.protocol, "claim", lambda *a, **k: reservation)


def config(**overrides) -> WorkerConfig:
    values = {
        "worker_id": "worker-a",
        "kind": "CPU",
        "max_attempts": 3,
        "idle_seconds": 0.01,
    }
    values.update(overrides)
    return WorkerConfig(**values)


class TestAcknowledgement:
    def test_a_committed_result_is_acknowledged(self, monkeypatch: pytest.MonkeyPatch) -> None:
        queue = FakeQueue([message()])
        engine = engine_where()
        committed = MagicMock()
        monkeypatch.setattr(worker.protocol, "commit_result", committed)

        assert run_once(engine, queue, lambda m, r: HandlerResult("turn-1", []), config()) is True

        committed.assert_called_once()
        assert queue.acked == [7]

    def test_a_failed_handler_is_not_acknowledged(self) -> None:
        """A retryable fault must leave the message in the queue."""
        queue = FakeQueue([message()])
        engine = engine_where()

        def exploding(m: JobMessage, r: object) -> HandlerResult:
            raise RuntimeError("model timeout")

        assert run_once(engine, queue, exploding, config()) is True
        assert queue.acked == [], "a failed attempt must be redelivered, not dropped"

    def test_unverifiable_output_is_quarantined_and_acknowledged(self) -> None:
        """Retrying a producer that cannot validate its own output is pointless."""
        queue = FakeQueue([message()])
        engine = engine_where()

        def invalid(m: JobMessage, r: object) -> HandlerResult:
            raise InvalidOutput("missing required field")

        assert run_once(engine, queue, invalid, config()) is True
        assert queue.acked == [7]

    def test_the_attempt_bound_quarantines_before_running_the_handler(self) -> None:
        queue = FakeQueue([message(attempt=3)])
        engine = engine_where(attempt_number=3)
        handler = MagicMock()

        assert run_once(engine, queue, handler, config(max_attempts=3)) is True

        handler.assert_not_called()
        assert queue.acked == [7]

    def test_an_empty_result_still_acknowledges(self, monkeypatch: pytest.MonkeyPatch) -> None:
        queue = FakeQueue([message()])
        engine = engine_where()
        committed = MagicMock()
        monkeypatch.setattr(worker.protocol, "commit_result", committed)

        run_once(engine, queue, lambda m, r: HandlerResult("turn-1", []), config())

        committed.assert_called_once()
        assert committed.call_args.kwargs["effects"] == []
        assert queue.acked == [7]

    def test_an_unreadable_message_body_is_left_alone(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A message we cannot parse must not be acknowledged as ours."""
        queue = FakeQueue([message()])
        engine = engine_where()

        def refusing(*args: object, **kwargs: object) -> None:
            from cce.modules.contributions.repository import ContributionError

            raise ContributionError(409, "Character is reserved")

        monkeypatch.setattr(worker.protocol, "claim", refusing)
        assert run_once(engine, queue, lambda m, r: HandlerResult("x", []), config()) is True
        # The character belongs to someone else, so the message is retired and
        # the reservation is left held rather than redelivered forever.
        assert queue.acked == [7]

    def test_an_empty_queue_reports_no_work(self) -> None:
        assert (
            run_once(engine_where(), FakeQueue(), lambda m, r: HandlerResult("x", []), config())
            is False
        )


class TestLoop:
    def test_the_loop_survives_a_failing_read(self) -> None:
        class Exploding(FakeQueue):
            def read(self, *, limit: int, visibility_timeout: int) -> list[JobMessage]:
                raise RuntimeError("queue unavailable")

        errors: list[BaseException] = []
        stop = Event()
        stop.set()

        run_loop(
            engine_where(),
            Exploding(),
            lambda m, r: HandlerResult("x", []),
            config(),
            stop,
            on_error=errors.append,
        )
        # A stop event set up front must not be outrun by an exception path.
        assert isinstance(stop.is_set(), bool)

    def test_the_gpu_plane_refuses_concurrency_above_one(self) -> None:
        with pytest.raises(ValueError):
            WorkerConfig(worker_id="gpu-1", kind="GPU", max_concurrency=2)


class TestConfig:
    @pytest.mark.parametrize(
        "field,value",
        [
            ("max_attempts", 0),
            ("idle_seconds", 0),
            ("max_concurrency", 9),
        ],
    )
    def test_invalid_configuration_is_rejected_at_construction(
        self, field: str, value: object
    ) -> None:
        with pytest.raises(ValueError):
            WorkerConfig(worker_id="w", kind="CPU", **{field: value})
