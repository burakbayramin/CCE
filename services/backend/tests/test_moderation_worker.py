from contextlib import contextmanager
from threading import Event
from uuid import uuid4

import pytest
from pydantic import ValidationError
from test_character_definitions import proposal

from cce.modules.contributions.moderation_worker import (
    ScanEvaluation,
    ScanWork,
    UnconfiguredLocalScanner,
    run_loop,
    run_once,
)


def work(avatar=False):
    return {
        "job_id": str(uuid4()),
        "attempt_id": str(uuid4()),
        "revision_id": str(uuid4()),
        "definition": proposal().model_dump(mode="json"),
        "source_sha256": "a" * 64,
        "avatar_id": str(uuid4()) if avatar else None,
        "avatar_sha256": "b" * 64 if avatar else None,
    }


class Database:
    def __init__(self, payload):
        self.payload = payload
        self.active = False
        self.written = None

    @contextmanager
    def begin(self):
        assert not self.active
        self.active = True
        try:
            yield self
        finally:
            self.active = False

    def execute(self, query, params=None):
        assert self.active
        statement = str(query)
        if "current_user" in statement:
            self.value = "cce_worker_cpu"
        elif "claim_moderation" in statement:
            self.value = self.payload
        else:
            self.written = params
        return self

    def scalar_one(self):
        return self.value


@pytest.mark.parametrize("avatar", [False, True])
def test_no_transaction_held_while_model_runs(avatar):
    db = Database(work(avatar))

    class Scanner:
        def evaluate(self, request):
            assert db.active is False
            return ScanEvaluation(
                result="REVIEW",
                provider="fixture",
                policy_version="test-v1",
                text_checked=True,
                checked_avatar_sha256=request.avatar_sha256,
            )

    assert run_once(db, Scanner()) is True
    assert db.written["verdict"] == "REVIEW"
    assert db.written["source"] == db.payload["source_sha256"]


@pytest.mark.parametrize(
    "mode,error",
    [
        ("missing_text", "INVALID_OUTPUT"),
        ("missing_avatar", "AVATAR_UNAVAILABLE"),
        ("timeout", "MODEL_TIMEOUT"),
        ("exception", "SCAN_FAILED"),
        ("bad_output", "INVALID_OUTPUT"),
    ],
)
def test_incomplete_or_failed_model_never_passes(mode, error):
    db = Database(work(True))

    class Scanner:
        def evaluate(self, request):
            if mode == "timeout":
                raise TimeoutError("private content")
            if mode == "exception":
                raise RuntimeError("secret credentials")
            if mode == "bad_output":
                return {"result": "PASS"}
            return ScanEvaluation(
                result="PASS",
                provider="fixture",
                policy_version="test-v1",
                text_checked=mode != "missing_text",
            )

    assert run_once(db, Scanner()) is True
    assert db.written["verdict"] == "ERROR"
    assert db.written["error"] == error
    assert "private" not in db.written["detail"]
    assert "secret" not in db.written["detail"]


def test_no_model_and_empty_queue_are_not_success():
    db = Database(work())
    assert run_once(db, UnconfiguredLocalScanner()) is True
    assert db.written["verdict"] == "ERROR"
    empty = Database(None)
    assert run_once(empty, UnconfiguredLocalScanner()) is False
    assert empty.written is None


def test_malformed_evidence_rejected():
    with pytest.raises(ValidationError):
        ScanWork.model_validate(work() | {"avatar_sha256": "b" * 64})
    with pytest.raises(ValidationError):
        ScanEvaluation(result="PASS", provider="x", policy_version="v1", error_code="SCAN_FAILED")


def test_worker_loop_processes_claims_and_stops_without_idle_wait():
    stop = Event()
    db = Database(work())
    calls = 0

    class Scanner:
        def evaluate(self, request):
            nonlocal calls
            calls += 1
            assert db.active is False
            if calls == 2:
                stop.set()
            return ScanEvaluation(
                result="PASS",
                provider="fixture",
                policy_version="test-v1",
                text_checked=True,
            )

    run_loop(db, Scanner(), stop, idle_seconds=0.01)
    assert calls == 2


def test_worker_loop_waits_when_queue_is_empty():
    class Stop:
        waits = []

        def is_set(self):
            return bool(self.waits)

        def wait(self, seconds):
            self.waits.append(seconds)

    stop = Stop()
    db = Database(None)

    class Scanner:
        def evaluate(self, request):
            raise AssertionError("Empty queue must not call the scanner")

    run_loop(db, Scanner(), stop, idle_seconds=0.25)
    assert stop.waits == [0.25]
    assert db.written is None


def test_worker_loop_rejects_invalid_poll_interval():
    with pytest.raises(ValueError, match="idle_seconds"):
        run_loop(Database(None), UnconfiguredLocalScanner(), Event(), idle_seconds=0)


def test_worker_loop_never_consumes_work_without_a_scanner():
    db = Database(work())
    with pytest.raises(ValueError, match="configured local scanner"):
        run_loop(db, UnconfiguredLocalScanner(), Event())
    assert db.written is None
