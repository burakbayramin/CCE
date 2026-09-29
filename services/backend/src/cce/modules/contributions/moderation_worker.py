"""Durable local-scan protocol. No model is silently enabled or cloud fallback used.

The model-specific scanner is intentionally a boundary: a calibrated text AND
image implementation must be supplied before real content can pass. The existing
request-path ModerationProvider is test-only and cannot be used here.
"""

from threading import Event
from typing import Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import Engine, text

from cce.modules.contributions.schemas import CharacterProposal


class ScanWork(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    job_id: UUID
    attempt_id: UUID
    revision_id: UUID
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    definition: CharacterProposal
    avatar_id: UUID | None
    avatar_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def avatar_pair(self) -> "ScanWork":
        if (self.avatar_id is None) != (self.avatar_sha256 is None):
            raise ValueError("Avatar identity and digest must be supplied together")
        return self


class ScanEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    result: Literal["PASS", "REVIEW", "BLOCK", "ERROR"]
    provider: str = Field(min_length=1, max_length=100)
    policy_version: str = Field(min_length=1, max_length=100)
    text_checked: bool = False
    checked_avatar_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    error_code: (
        Literal[
            "MODEL_UNAVAILABLE",
            "MODEL_TIMEOUT",
            "INVALID_OUTPUT",
            "AVATAR_UNAVAILABLE",
            "SCAN_FAILED",
        ]
        | None
    ) = None

    @model_validator(mode="after")
    def error_pair(self) -> "ScanEvaluation":
        if (self.result == "ERROR") != (self.error_code is not None):
            raise ValueError("Only ERROR results require an error code")
        return self


class LocalScanner(Protocol):
    def evaluate(self, work: ScanWork) -> ScanEvaluation: ...


class UnconfiguredLocalScanner:
    def evaluate(self, work: ScanWork) -> ScanEvaluation:
        return failure("MODEL_UNAVAILABLE")


def failure(
    code: Literal[
        "MODEL_UNAVAILABLE", "MODEL_TIMEOUT", "INVALID_OUTPUT", "AVATAR_UNAVAILABLE", "SCAN_FAILED"
    ],
) -> ScanEvaluation:
    return ScanEvaluation(
        result="ERROR",
        provider="local-unconfigured",
        policy_version="unconfigured",
        error_code=code,
    )


def run_once(engine: Engine, scanner: LocalScanner) -> bool:
    """Claim -> release connection -> scan -> fenced commit.

    True means work was claimed, NOT that it passed moderation. Exceptions never
    interpolate submitted content, model output, database URLs or credentials.
    DB failures propagate to the supervisor; an unfinished lease remains durable.
    """
    with engine.begin() as connection:
        if connection.execute(text("select current_user")).scalar_one() != "cce_worker_cpu":
            raise ValueError("Moderation requires the restricted cce_worker_cpu identity")
        payload = connection.execute(text("select ops_private.claim_moderation()")).scalar_one()
    if payload is None:
        return False
    work = ScanWork.model_validate(payload)
    try:
        evaluation = scanner.evaluate(work)
        if not isinstance(evaluation, ScanEvaluation):
            evaluation = failure("INVALID_OUTPUT")
        elif evaluation.result != "ERROR" and not evaluation.text_checked:
            evaluation = failure("INVALID_OUTPUT")
        elif (
            evaluation.result != "ERROR" and evaluation.checked_avatar_sha256 != work.avatar_sha256
        ):
            evaluation = failure("AVATAR_UNAVAILABLE")
    except TimeoutError:
        evaluation = failure("MODEL_TIMEOUT")
    except Exception:
        # Provider errors may contain private inputs, URLs or raw model output.
        evaluation = failure("SCAN_FAILED")
    with engine.begin() as connection:
        connection.execute(
            text(
                "select ops_private.finish_moderation(:job,:attempt,:source,:avatar,:verdict,"
                ":provider,:policy,:detail,:error)"
            ),
            {
                "job": work.job_id,
                "attempt": work.attempt_id,
                "source": work.source_sha256,
                "avatar": work.avatar_sha256,
                "verdict": evaluation.result,
                "provider": evaluation.provider,
                "policy": evaluation.policy_version,
                "detail": "Yerel tarama tamamlandı; Owner incelemesi gerekir."
                if evaluation.result != "ERROR"
                else "Yerel tarama tamamlanamadı; onay kapalı.",
                "error": evaluation.error_code,
            },
        )
    return True


def run_loop(
    engine: Engine,
    scanner: LocalScanner,
    stop: Event,
    *,
    idle_seconds: float = 2.0,
) -> None:
    """Poll until stopped; never turn a database failure into a scan verdict.

    An operator must explicitly supply a calibrated scanner. The unconfigured
    placeholder is rejected so an accidentally started process cannot consume
    pending work. The caller owns engine disposal and process signal handling.
    """
    if idle_seconds <= 0:
        raise ValueError("idle_seconds must be positive")
    if isinstance(scanner, UnconfiguredLocalScanner):
        raise ValueError("A configured local scanner is required")
    while not stop.is_set():
        if not run_once(engine, scanner):
            stop.wait(idle_seconds)
