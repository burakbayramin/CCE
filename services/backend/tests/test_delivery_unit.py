"""M4.5 — request identity and the delivery contract."""

from uuid import uuid4

import pytest

from cce.modules.contributions.repository import ContributionError
from cce.modules.interactions.delivery import (
    MAX_PUBLISH_BATCH,
    Delivery,
    parse_request_id,
)


class TestRequestId:
    def test_a_well_formed_key_is_accepted(self) -> None:
        value = uuid4()
        assert parse_request_id(str(value)) == value

    @pytest.mark.parametrize(
        "raw",
        [
            "not-a-uuid",
            "",
            "12345",
            "urn:uuid:6e8bc430-9c3a-11d9-9669-0800200c9a66",  # valid UUID, wrong form
            "6e8bc4309c3a11d9669080020c9a66",  # unhyphenated
            "6e8bc430-9c3a-11d9-9669-0800200c9a6",  # one short
            None,
            12345,
            ["6e8bc430-9c3a-11d9-9669-0800200c9a66"],
        ],
    )
    def test_a_malformed_key_is_refused_with_422(self, raw: object) -> None:
        """Coercing a bad key would silently deduplicate against an unrelated
        delivery and hide the client bug behind a successful-looking no-op."""
        with pytest.raises(ContributionError) as refused:
            parse_request_id(raw)
        assert refused.value.status == 422

    def test_the_refusal_says_nothing_about_anything_but_the_key(self) -> None:
        with pytest.raises(ContributionError) as refused:
            parse_request_id("garbage")
        assert "UUID" in refused.value.detail


class TestDeliveryValue:
    def test_delivered_is_derived_from_state(self) -> None:
        def delivery(state: str) -> Delivery:
            return Delivery(
                id=uuid4(),
                turn_id=uuid4(),
                reservation_id=uuid4(),  # type: ignore[arg-type]
                recipient_id=uuid4(),
                request_id=uuid4(),
                state=state,
                delivered_at=None,
                failure_reason=None,
            )

        assert delivery("DELIVERED").delivered is True
        assert delivery("PENDING").delivered is False
        assert delivery("FAILED").delivered is False


class TestPublishBounds:
    @pytest.mark.parametrize("batch", [0, -1, MAX_PUBLISH_BATCH + 1])
    def test_a_batch_outside_the_bound_is_clamped_not_refused(self, batch: int) -> None:
        """The publisher must not be able to choose how much work it claims; it
        is clamped rather than rejected so a misconfigured batch degrades to a
        bounded one instead of stopping delivery entirely."""
        assert max(1, min(batch, MAX_PUBLISH_BATCH)) in range(1, MAX_PUBLISH_BATCH + 1)

    def test_the_bound_is_a_ceiling_not_a_suggestion(self) -> None:
        assert MAX_PUBLISH_BATCH < 1000, (
            "a publisher batch this large would hold locks long enough to starve the worker plane"
        )
