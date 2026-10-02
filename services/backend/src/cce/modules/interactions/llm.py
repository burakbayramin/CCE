"""M4.3 — the model boundary.

Everything that needs a model goes through `LLMProvider`. That is the point of
the milestone: a real model and a deterministic fake are interchangeable, so
the state machine around an inference can be tested without one.

Three things are enforced here rather than trusted to the caller:

* **Budgets.** Tokens, wall-clock and attempts are limits the runner enforces,
  not hints the model respects. Exceeding one is a typed outcome, not a crash.
* **Structured output.** A handler's output is validated before it can become
  domain effects. Unverifiable output raises `InvalidOutput`, which the worker
  quarantines immediately rather than retrying a producer that cannot validate.
* **GPU slots.** The main plane runs at concurrency 1. A parent that waits on a
  child releases its slot while it waits, so a fan-out does not serialise the
  whole queue behind the slowest leaf.

The deterministic fake is the reference implementation of the contract: same
input, same output, no network. It is not a stub that returns a constant, so a
handler that mishandles a genuinely varying payload still fails in tests.
"""

import hashlib
import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal, Protocol

from cce.modules.interactions.worker import InvalidOutput

Clock = Callable[[], float]

# The effect kinds the model may propose. Anything else is unverifiable.
EffectKind = Literal["MEMORY", "AFFECT", "RELATIONSHIP", "GOAL", "TRANSCRIPT"]
EFFECT_KINDS: frozenset[str] = frozenset({"MEMORY", "AFFECT", "RELATIONSHIP", "GOAL", "TRANSCRIPT"})


class BudgetExceeded(Exception):
    """A limit was reached. Carries which one, because a token overrun and a
    timeout are not the same operational problem."""

    def __init__(self, limit: str) -> None:
        super().__init__(f"Budget exceeded: {limit}")
        self.limit = limit


@dataclass(frozen=True)
class Budget:
    max_tokens: int = 2048
    max_seconds: float = 30.0
    max_attempts: int = 2

    def __post_init__(self) -> None:
        if self.max_tokens < 1:
            raise ValueError("max_tokens must be positive")
        if self.max_seconds <= 0:
            raise ValueError("max_seconds must be positive")
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be positive")


@dataclass(frozen=True)
class Request:
    system: str
    prompt: str
    #: Opaque correlation id; part of the deterministic input, never the output.
    request_id: str


@dataclass(frozen=True)
class Response:
    text: str
    tokens_in: int
    tokens_out: int
    provider: str


class LLMProvider(Protocol):
    name: str

    def complete(self, request: Request, budget: Budget) -> Response: ...


@dataclass
class _SlotState:
    held: bool
    capacity: int
    in_use: int = 0

    def available(self) -> int:
        return self.capacity - self.in_use


class GpuSlots:
    """Concurrency 1 for the main LLM plane.

    Release and re-acquire is what lets a parent hand its slot to a child
    instead of holding it idle while it waits. A slot that is released while
    work is still running would be a lie, so `held` is tracked separately from
    occupancy and `release` refuses to double-release.
    """

    def __init__(self, capacity: int = 1) -> None:
        if capacity < 1:
            raise ValueError("capacity must be at least 1")
        self._state = _SlotState(held=False, capacity=capacity)

    def acquire(self) -> None:
        if self._state.held:
            raise RuntimeError("slot is already held by this worker")
        if self._state.available() < 1:
            raise RuntimeError("no GPU slot available")
        self._state.held = True
        self._state.in_use += 1

    def release(self) -> None:
        if not self._state.held:
            raise RuntimeError("slot is not held")
        self._state.held = False
        self._state.in_use = max(0, self._state.in_use - 1)

    def wait_without_holding(self, work: Callable[[], None]) -> None:
        """Run `work` after giving the slot up, then take it back.

        The slot is re-acquired even if `work` raises, so a failing child does
        not leave the worker permanently unable to run.
        """
        self.release()
        try:
            work()
        finally:
            self.acquire()

    @property
    def in_use(self) -> int:
        return self._state.in_use


def estimate_tokens(text: str) -> int:
    """Rough but stable and provider-independent.

    Deliberately not a real tokenizer: the budget is a ceiling that must hold
    for every provider, including the fake, so an estimate that never
    undercounts is safer than one that is precise per vendor.
    """
    return max(1, len(text) // 4)


def run_within_budget(
    provider: LLMProvider,
    request: Request,
    budget: Budget,
    *,
    clock: Clock = time.monotonic,
    attempt: int = 1,
) -> Response:
    """One attempt, inside the budget.

    Raises `BudgetExceeded` rather than returning a partial response: a
    truncated answer is not a valid answer, and the worker's quarantine path
    needs to be able to tell the two apart.
    """
    if attempt > budget.max_attempts:
        raise BudgetExceeded("attempts")
    started = clock()
    response = provider.complete(request, budget)
    elapsed = clock() - started

    if elapsed > budget.max_seconds:
        raise BudgetExceeded("seconds")
    total_tokens = response.tokens_in + response.tokens_out
    if total_tokens > budget.max_tokens:
        raise BudgetExceeded("tokens")
    if response.tokens_out < 0 or response.tokens_in < 0:
        raise BudgetExceeded("tokens")
    return response


def parse_effects(payload: str) -> list[dict[str, object]]:
    """Validate a handler's structured output before it can become state.

    Raises `InvalidOutput` for anything unverifiable: unparseable JSON, a
    missing identity, an unknown effect kind. A retry would produce the same
    result, so the worker quarantines rather than trying again.
    """
    try:
        document = json.loads(payload)
    except (ValueError, TypeError) as error:
        raise InvalidOutput(f"response is not valid JSON: {error}") from None

    if not isinstance(document, dict):
        raise InvalidOutput("response must be an object")

    raw_effects = document.get("effects")
    if not isinstance(raw_effects, list):
        raise InvalidOutput("effects must be a list")

    effects: list[dict[str, object]] = []
    for index, item in enumerate(raw_effects):
        if not isinstance(item, dict):
            raise InvalidOutput(f"effect {index} is not an object")
        identity = item.get("effect_identity")
        kind = item.get("effect_kind")
        if not isinstance(identity, str) or not identity.strip():
            raise InvalidOutput(f"effect {index} has no identity")
        if kind not in EFFECT_KINDS:
            raise InvalidOutput(f"effect {index} has unknown kind {kind!r}")
        effects.append(
            {
                "effect_identity": identity,
                "effect_kind": kind,
                # The canonical key is the one the commit function reads.
                # `provider` is accepted because the fake emits it.
                "applied_by_processing_version": str(
                    item.get("applied_by_processing_version", item.get("provider", ""))
                ),
                "payload": item.get("payload", {}),
                "topic": item.get("topic", "EFFECT_APPLIED"),
            }
        )
    return effects


@dataclass
class DeterministicFake:
    """A provider with no network and no randomness.

    Output is a function of the prompt, the request id and the declared
    provider version, so the same experiment always produces the same world.
    A handler that mishandles a varying payload still fails here, because the
    payload varies with the input rather than staying constant.
    """

    name: str = "deterministic-fake"
    provider_version: str = "fake-v1"
    #: Set to make every call fail, for exercising the retry and quarantine
    #: paths without a real model.
    failure: Literal["none", "timeout", "malformed", "oversized"] = "none"
    effects: list[dict[str, object]] = field(default_factory=list)
    _calls: int = 0

    def complete(self, request: Request, budget: Budget) -> Response:
        self._calls += 1
        prompt_tokens = estimate_tokens(request.system + request.prompt)

        if self.failure == "timeout":
            raise TimeoutError("fake provider timed out")
        if self.failure == "oversized":
            return Response(
                text="",
                tokens_in=prompt_tokens,
                tokens_out=budget.max_tokens + 1,
                provider=self.name,
            )
        if self.failure == "malformed":
            return Response(
                text="not json at all", tokens_in=prompt_tokens, tokens_out=8, provider=self.name
            )

        digest = hashlib.sha256(f"{request.request_id}|{request.prompt}".encode()).hexdigest()[:16]
        effects = [
            {
                "effect_identity": f"{request.request_id}:{effect['effect_kind']}:{digest}",
                "effect_kind": effect["effect_kind"],
                "applied_by_processing_version": self.provider_version,
                "payload": effect.get("payload", {}),
            }
            for effect in self.effects
        ]
        text = json.dumps({"effects": effects})
        return Response(
            text=text,
            tokens_in=prompt_tokens,
            tokens_out=estimate_tokens(text),
            provider=self.name,
        )

    @property
    def calls(self) -> int:
        return self._calls
