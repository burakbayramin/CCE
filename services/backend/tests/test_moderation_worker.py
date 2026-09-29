from contextlib import contextmanager
from uuid import uuid4

import pytest
from pydantic import ValidationError
from test_character_definitions import proposal

from cce.modules.contributions.moderation_worker import (
    ScanEvaluation,
    ScanWork,
    UnconfiguredLocalScanner,
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
