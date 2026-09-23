from datetime import datetime
from typing import Protocol


class WorldClock(Protocol):
    """World time supplied by an adapter; never used for leases or timeouts.

    M5 will implement the persisted world clock. Tests can supply a fixed clock.
    """

    def now(self) -> datetime:
        """Return a timezone-aware world timestamp."""
        ...
