from dataclasses import dataclass
from datetime import UTC, datetime

from cce.core.clock import WorldClock


@dataclass
class FixedWorldClock:
    timestamp: datetime

    def now(self) -> datetime:
        return self.timestamp


def test_world_clock_is_injectable_without_system_time() -> None:
    expected = datetime(2040, 1, 1, tzinfo=UTC)
    clock: WorldClock = FixedWorldClock(expected)
    assert clock.now() == expected
    assert clock.now().tzinfo is not None
