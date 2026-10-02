import os
from contextlib import contextmanager
from threading import Event, Timer
from time import monotonic

import pytest
from test_moderation_worker import Database, work

from cce.modules.contributions.moderation_process import ProcessLocalScanner
from cce.modules.contributions.moderation_worker import (
    AvatarUnavailable,
    ScanEvaluation,
    ScanWork,
    UnconfiguredLocalScanner,
    run_loop,
    run_once,
)


class FixtureScanner:
    def __init__(self, mode):
        self.mode = mode
        self.calls = 0

    def evaluate(self, request):
        self.calls += 1
        if self.mode == "hang":
            Event().wait(60)
        if self.mode == "crash":
            os._exit(3)
        if self.mode == "error":
            print("private scanner content and credentials")
            raise RuntimeError("private scanner content and credentials")
        if self.mode == "avatar":
            raise AvatarUnavailable("private storage details")
        if self.mode == "invalid":
            return {"result": "PASS"}
        if self.mode == "oversized":
            return ScanEvaluation.model_construct(result="PASS", provider="x" * 10000)
        return ScanEvaluation(
            result="REVIEW",
            provider=f"fixture-{os.getpid()}",
            policy_version=f"test-{self.calls}",
            text_checked=True,
            checked_avatar_sha256=request.avatar_sha256,
        )


@contextmanager
def fixture_context(mode):
    if mode == "startup_hang":
        Event().wait(60)
    if mode == "startup_error":
        raise RuntimeError("private factory configuration")
    yield UnconfiguredLocalScanner() if mode == "unconfigured" else FixtureScanner(mode)


def scanner(mode="ok", **kwargs):
    return ProcessLocalScanner(fixture_context, (mode,), startup_seconds=15, **kwargs)


def test_spawn_process_is_persistent_and_preserves_source_evidence():
    proxy = scanner()
    try:
        proxy.prepare()
        request = ScanWork.model_validate(work(True))
        first = proxy.evaluate(request)
        second = proxy.evaluate(request)
        assert first.provider == second.provider != f"fixture-{os.getpid()}"
        assert (first.policy_version, second.policy_version) == ("test-1", "test-2")
        assert first.checked_avatar_sha256 == request.avatar_sha256
    finally:
        proxy.close()


def test_hard_timeout_reaps_process_records_error_and_prepares_fresh_generation():
    proxy = scanner("hang", timeout_seconds=0.15)
    try:
        proxy.prepare()
        old = proxy._process
        old_pid = old.pid
        db = Database(work())
        started = monotonic()
        assert run_once(db, proxy)
        assert monotonic() - started < 5
        assert db.written["verdict"] == "ERROR"
        assert db.written["error"] == "MODEL_TIMEOUT"
        assert proxy._process is None and proxy._io is None
        assert old._closed
        with pytest.raises(RuntimeError, match="prepared before claiming"):
            proxy.evaluate(ScanWork.model_validate(work()))
        proxy.args = ("ok",)
        proxy.prepare()
        assert proxy._process.pid != old_pid
        assert proxy.evaluate(ScanWork.model_validate(work())).result == "REVIEW"
    finally:
        proxy.close()


@pytest.mark.parametrize("mode", ["startup_error", "unconfigured"])
def test_startup_failure_cannot_claim_or_expose_factory_details(mode, capfd):
    proxy = scanner(mode)
    db = Database(work())
    try:
        with pytest.raises(RuntimeError, match="Scanner startup failed") as error:
            run_loop(db, proxy, Event(), before_claim=proxy.prepare)
        assert db.claim_params is None and db.written is None
        assert proxy._process is None
        assert "private" not in str(error.value)
        assert "private" not in str(capfd.readouterr())
    finally:
        proxy.close()


def test_startup_deadline_is_bounded_without_claim():
    proxy = ProcessLocalScanner(fixture_context, ("startup_hang",), startup_seconds=0.15)
    try:
        started = monotonic()
        with pytest.raises(RuntimeError, match="timed out"):
            proxy.prepare()
        assert monotonic() - started < 5
        assert proxy._process is None
    finally:
        proxy.close()


@pytest.mark.parametrize(
    "mode,expected",
    [
        ("crash", "SCAN_FAILED"),
        ("error", "SCAN_FAILED"),
        ("avatar", "AVATAR_UNAVAILABLE"),
        ("invalid", "INVALID_OUTPUT"),
        ("oversized", "SCAN_FAILED"),
    ],
)
def test_process_failure_is_sanitized_and_never_passes(mode, expected, capfd):
    proxy = scanner(mode)
    try:
        proxy.prepare()
        db = Database(work())
        assert run_once(db, proxy)
        assert db.written["verdict"] == "ERROR"
        assert db.written["error"] == expected
        assert "private" not in db.written["detail"]
        assert "private" not in str(capfd.readouterr())
    finally:
        proxy.close()


def test_stop_interrupts_hung_scan_and_never_restarts():
    stop = Event()
    proxy = scanner("hang", timeout_seconds=10, stop=stop)
    try:
        proxy.prepare()
        timer = Timer(0.15, stop.set)
        timer.start()
        started = monotonic()
        try:
            with pytest.raises(RuntimeError, match="Scanner stopped"):
                proxy.evaluate(ScanWork.model_validate(work()))
        finally:
            timer.cancel()
            timer.join()
        assert monotonic() - started < 5
        proxy.prepare()
        assert proxy._process is None
    finally:
        proxy.close()


@pytest.mark.parametrize("value", [0, -1, float("inf"), float("nan"), 241])
def test_inference_deadline_leaves_lease_headroom(value):
    with pytest.raises(ValueError):
        scanner(timeout_seconds=value)


def test_cleanup_failure_prevents_another_generation_or_claim(monkeypatch):
    proxy = scanner()

    class StuckTransport:
        def join(self, seconds):
            pass

        def is_alive(self):
            return True

    proxy._io = StuckTransport()
    with pytest.raises(RuntimeError, match="transport could not be stopped"):
        proxy.close()
    assert proxy._poisoned
    db = Database(work())
    with pytest.raises(RuntimeError, match="supervisor restart required"):
        run_loop(db, proxy, Event(), before_claim=proxy.prepare)
    assert db.written is None
