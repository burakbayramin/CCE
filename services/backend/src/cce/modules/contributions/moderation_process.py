"""Persistent, spawn-only scanner isolation with bounded startup and inference.

This is process supervision, not a sandbox for an untrusted scanner. Factories
must be reviewed and must not leave independent inference processes running.
Only bounded JSON crosses the per-generation pipe; model exceptions never do.
"""

import math
import multiprocessing
import os
import signal
from collections.abc import Callable
from contextlib import AbstractContextManager, redirect_stderr, redirect_stdout
from multiprocessing.process import BaseProcess
from queue import Queue
from threading import Event, Thread
from time import monotonic
from typing import Protocol

from cce.modules.contributions.moderation_worker import (
    AvatarUnavailable,
    LocalScanner,
    ScanEvaluation,
    ScanWork,
    UnconfiguredLocalScanner,
    failure,
)

ScannerFactory = Callable[..., AbstractContextManager[LocalScanner]]
MAX_REQUEST_BYTES = 65536
MAX_RESPONSE_BYTES = 4096
CLEANUP_SECONDS = 1.0


class ByteConnection(Protocol):
    """Shared surface of POSIX Connection and Windows PipeConnection."""

    def send_bytes(self, buffer: bytes) -> None: ...
    def recv_bytes(self, maxlength: int) -> bytes: ...
    def close(self) -> None: ...


def _serve(connection: ByteConnection, factory: ScannerFactory, args: tuple[object, ...]) -> None:
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    try:
        # Reviewed adapters may still print raw output or exception details.
        # Child output is discarded, including native writes to stdout/stderr.
        with open(os.devnull, "w") as sink, redirect_stdout(sink), redirect_stderr(sink):
            os.dup2(sink.fileno(), 1)
            os.dup2(sink.fileno(), 2)
            with factory(*args) as scanner:
                if isinstance(scanner, UnconfiguredLocalScanner):
                    raise ValueError("A configured scanner is required")
                connection.send_bytes(b"READY")
                while True:
                    payload = connection.recv_bytes(MAX_REQUEST_BYTES)
                    if payload == b"STOP":
                        return
                    work = ScanWork.model_validate_json(payload)
                    try:
                        evaluation = scanner.evaluate(work)
                        if not isinstance(evaluation, ScanEvaluation):
                            evaluation = failure("INVALID_OUTPUT")
                    except TimeoutError:
                        evaluation = failure("MODEL_TIMEOUT")
                    except AvatarUnavailable:
                        evaluation = failure("AVATAR_UNAVAILABLE")
                    except Exception:
                        evaluation = failure("SCAN_FAILED")
                    connection.send_bytes(evaluation.model_dump_json().encode())
    except (EOFError, BrokenPipeError):
        pass
    except Exception:
        try:
            connection.send_bytes(b"FAILED")
        except (EOFError, OSError):
            pass
    finally:
        connection.close()


class ProcessLocalScanner:
    """Single-owner proxy. Call prepare before claiming, then evaluate serially.

    A timed-out/crashed generation is killed and its pipe discarded. Restart
    happens only in prepare, before the next claim, not inside a leased scan.
    An I/O thread bounds even a stalled pipe write or partial response; it never
    executes inference. Failure to reap it poisons this supervisor permanently.
    """

    def __init__(
        self,
        factory: ScannerFactory,
        args: tuple[object, ...] = (),
        *,
        startup_seconds: float = 120,
        timeout_seconds: float = 120,
        stop: Event | None = None,
    ) -> None:
        if any(
            not math.isfinite(value) or value <= 0 for value in (startup_seconds, timeout_seconds)
        ):
            raise ValueError("Scanner deadlines must be finite and positive")
        if timeout_seconds > 240:
            raise ValueError("Scanner deadline must leave headroom within the 300-second lease")
        self.factory = factory
        self.args = args
        self.startup_seconds = startup_seconds
        self.timeout_seconds = timeout_seconds
        self.stop = stop if stop is not None else Event()
        self._process: BaseProcess | None = None
        self._connection: ByteConnection | None = None
        self._io: Thread | None = None
        self._poisoned = False

    def prepare(self) -> None:
        if self._poisoned:
            raise RuntimeError("Scanner cleanup failed; supervisor restart required")
        if self.stop.is_set():
            return
        if self._process is not None and self._process.is_alive():
            return
        self.close()
        context = multiprocessing.get_context("spawn")
        parent, child = context.Pipe()
        process = context.Process(target=_serve, args=(child, self.factory, self.args), daemon=True)
        self._connection, self._process = parent, process
        try:
            process.start()
            child.close()
            if self._exchange(None, self.startup_seconds) != b"READY":
                raise RuntimeError("Scanner startup failed")
        except Exception:
            child.close()
            self.close()
            raise RuntimeError("Scanner startup failed or timed out") from None

    def _exchange(self, payload: bytes | None, seconds: float) -> bytes:
        connection = self._connection
        if connection is None:
            raise RuntimeError("Scanner process is not ready")
        result: Queue[tuple[bytes | None, float]] = Queue(maxsize=1)
        done = Event()

        def exchange() -> None:
            try:
                if payload is not None:
                    connection.send_bytes(payload)
                response = connection.recv_bytes(MAX_RESPONSE_BYTES)
            except Exception:
                response = None
            finally:
                result.put((response, monotonic()))
                done.set()

        self._io = Thread(target=exchange, daemon=True)
        deadline = monotonic() + seconds
        self._io.start()
        while not done.is_set():
            remaining = deadline - monotonic()
            if remaining <= 0 or self.stop.is_set():
                self.close()
                if self.stop.is_set():
                    raise RuntimeError("Scanner stopped")
                raise TimeoutError("Scanner deadline exceeded")
            done.wait(min(0.05, remaining))
        self._io.join()
        self._io = None
        response, completed_at = result.get_nowait()
        if completed_at > deadline:
            self.close()
            raise TimeoutError("Scanner deadline exceeded")
        if response is None:
            self.close()
            raise RuntimeError("Scanner process failed")
        return response

    def evaluate(self, work: ScanWork) -> ScanEvaluation:
        if self._process is None or not self._process.is_alive():
            raise RuntimeError("Scanner must be prepared before claiming")
        payload = work.model_dump_json().encode()
        if len(payload) > MAX_REQUEST_BYTES:
            return failure("INVALID_OUTPUT")
        response = self._exchange(payload, self.timeout_seconds)
        try:
            return ScanEvaluation.model_validate_json(response)
        except ValueError:
            self.close()
            return failure("INVALID_OUTPUT")

    def close(self) -> None:
        process, connection = self._process, self._connection
        if process is not None and process.pid is not None:
            if process.is_alive():
                process.terminate()
            process.join(CLEANUP_SECONDS)
            if process.is_alive():
                process.kill()
                process.join(CLEANUP_SECONDS)
            if process.is_alive():
                self._poisoned = True
                raise RuntimeError("Scanner process could not be stopped")
        if connection is not None:
            connection.close()
        if self._io is not None:
            self._io.join(CLEANUP_SECONDS)
            if self._io.is_alive():
                self._poisoned = True
                raise RuntimeError("Scanner transport could not be stopped")
            self._io = None
        if process is not None:
            process.close()
        self._process, self._connection = None, None
