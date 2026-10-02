"""M4.3 — the model boundary.

The fake provider makes the whole thing testable without a model, and the
budget tests pin the property that matters: a limit is enforced by the runner,
not assumed of the provider.
"""

import json
from uuid import uuid4

import pytest

from cce.modules.interactions.llm import (
    Budget,
    BudgetExceeded,
    DeterministicFake,
    GpuSlots,
    Request,
    estimate_tokens,
    parse_effects,
    run_within_budget,
)
from cce.modules.interactions.worker import InvalidOutput


def request() -> Request:
    return Request(
        system="You are a character.", prompt="remember the harbour", request_id=str(uuid4())
    )


def budget(**overrides) -> Budget:
    values = {"max_tokens": 500, "max_seconds": 10.0, "max_attempts": 2}
    values.update(overrides)
    return Budget(**values)


class TestBudget:
    def test_a_normal_call_returns_the_response(self) -> None:
        fake = DeterministicFake(effects=[{"effect_kind": "MEMORY", "payload": {"text": "liman"}}])
        response = run_within_budget(fake, request(), budget())
        assert response.provider == "deterministic-fake"
        assert response.tokens_out > 0

    def test_the_token_ceiling_is_enforced_by_the_runner(self) -> None:
        fake = DeterministicFake(failure="oversized")
        with pytest.raises(BudgetExceeded) as over:
            run_within_budget(fake, request(), budget(max_tokens=100))
        assert over.value.limit == "tokens"

    def test_the_time_ceiling_is_enforced_against_the_providers_clock(self) -> None:
        """A provider that overruns is caught even though it returns normally."""
        ticks = iter([0.0, 99.0])
        fake = DeterministicFake()
        with pytest.raises(BudgetExceeded) as over:
            run_within_budget(fake, request(), budget(max_seconds=1.0), clock=lambda: next(ticks))
        assert over.value.limit == "seconds"

    def test_an_attempt_beyond_the_bound_never_reaches_the_provider(self) -> None:
        fake = DeterministicFake()
        with pytest.raises(BudgetExceeded) as over:
            run_within_budget(fake, request(), budget(max_attempts=2), attempt=3)
        assert over.value.limit == "attempts"
        assert fake.calls == 0, "the budget must stop the call, not observe it"

    def test_a_provider_timeout_is_not_swallowed(self) -> None:
        fake = DeterministicFake(failure="timeout")
        with pytest.raises(TimeoutError):
            run_within_budget(fake, request(), budget())

    @pytest.mark.parametrize(
        "field,value",
        [("max_tokens", 0), ("max_seconds", 0), ("max_attempts", 0)],
    )
    def test_an_invalid_budget_is_rejected_at_construction(self, field: str, value: object) -> None:
        with pytest.raises(ValueError):
            budget(**{field: value})


class TestDeterminism:
    def test_the_same_request_produces_the_same_effect_identity(self) -> None:
        fake = DeterministicFake(effects=[{"effect_kind": "MEMORY", "payload": {"text": "liman"}}])
        fixed = Request(system="s", prompt="p", request_id="req-1")

        first = parse_effects(run_within_budget(fake, fixed, budget()).text)
        second = parse_effects(run_within_budget(fake, fixed, budget()).text)

        assert [e["effect_identity"] for e in first] == [e["effect_identity"] for e in second]

    def test_a_different_request_produces_a_different_identity(self) -> None:
        """A stub returning a constant would pass the test above and fail this
        one; that is why the fake varies with its input."""
        fake = DeterministicFake(effects=[{"effect_kind": "MEMORY", "payload": {}}])
        one = parse_effects(run_within_budget(fake, Request("s", "p", "req-1"), budget()).text)
        two = parse_effects(run_within_budget(fake, Request("s", "p", "req-2"), budget()).text)
        assert one[0]["effect_identity"] != two[0]["effect_identity"]

    def test_varying_payloads_are_carried_through(self) -> None:
        fake = DeterministicFake(
            effects=[
                {"effect_kind": "MEMORY", "payload": {"text": "liman"}},
                {"effect_kind": "GOAL", "payload": {"text": "arşivi düzenlemek"}},
            ]
        )
        effects = parse_effects(run_within_budget(fake, request(), budget()).text)
        assert [e["effect_kind"] for e in effects] == ["MEMORY", "GOAL"]


class TestStructuredOutput:
    def test_well_formed_output_is_accepted(self) -> None:
        payload = json.dumps(
            {
                "effects": [
                    {
                        "effect_identity": "turn-1:memory:a",
                        "effect_kind": "MEMORY",
                        "payload": {"text": "liman"},
                    },
                ]
            }
        )
        effects = parse_effects(payload)
        assert effects[0]["effect_kind"] == "MEMORY"
        assert effects[0]["topic"] == "EFFECT_APPLIED"

    def test_an_empty_effect_list_is_a_valid_result(self) -> None:
        """A scene that changed nothing must not look like a broken model."""
        assert parse_effects(json.dumps({"effects": []})) == []

    @pytest.mark.parametrize(
        "payload",
        [
            "not json",
            "[]",
            json.dumps({"effects": "nope"}),
            json.dumps({"effects": [{"effect_kind": "MEMORY"}]}),
            json.dumps({"effects": [{"effect_identity": "a", "effect_kind": "SOMETHING_ELSE"}]}),
            json.dumps({"effects": [{"effect_identity": "  ", "effect_kind": "MEMORY"}]}),
            json.dumps({"effects": ["not an object"]}),
        ],
    )
    def test_unverifiable_output_raises_rather_than_retrying(self, payload: str) -> None:
        with pytest.raises(InvalidOutput):
            parse_effects(payload)

    def test_the_provider_version_is_recorded_outside_the_identity(self) -> None:
        payload = json.dumps(
            {
                "effects": [
                    {
                        "effect_identity": "turn-1:memory:a",
                        "effect_kind": "MEMORY",
                        "applied_by_processing_version": "model-b-v2",
                        "payload": {},
                    },
                ]
            }
        )
        effect = parse_effects(payload)[0]
        assert "model-b-v2" not in effect["effect_identity"]
        assert effect["applied_by_processing_version"] == "model-b-v2"


class TestGpuSlots:
    def test_the_plane_runs_at_concurrency_one_by_default(self) -> None:
        slots = GpuSlots()
        slots.acquire()
        with pytest.raises(RuntimeError):
            slots.acquire()

    def test_releasing_frees_the_slot(self) -> None:
        slots = GpuSlots()
        slots.acquire()
        slots.release()
        slots.acquire()
        assert slots.in_use == 1

    def test_double_release_is_refused(self) -> None:
        slots = GpuSlots()
        slots.acquire()
        slots.release()
        with pytest.raises(RuntimeError):
            slots.release()

    def test_waiting_on_a_child_releases_the_parent_slot(self) -> None:
        """The reason release-and-reacquire exists: a fan-out must not serialise
        the queue behind its slowest leaf."""
        slots = GpuSlots()
        slots.acquire()
        observed: list[int] = []

        slots.wait_without_holding(lambda: observed.append(slots.in_use))

        assert observed == [0], "the child must run with the slot free"
        assert slots.in_use == 1, "and the parent takes it back afterwards"

    def test_a_failing_child_still_returns_the_slot(self) -> None:
        slots = GpuSlots()
        slots.acquire()

        def boom() -> None:
            raise RuntimeError("child failed")

        with pytest.raises(RuntimeError):
            slots.wait_without_holding(boom)

        assert slots.in_use == 1, "a failed child must not strand the worker"

    def test_capacity_must_be_positive(self) -> None:
        with pytest.raises(ValueError):
            GpuSlots(0)


class TestTokenEstimate:
    def test_the_estimate_never_returns_zero(self) -> None:
        assert estimate_tokens("") == 1

    def test_it_grows_with_the_input(self) -> None:
        assert estimate_tokens("x" * 400) > estimate_tokens("x" * 40)
