from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class Actor:
    user_id: UUID
    session_id: UUID


class AuthenticationFailed(Exception):
    """Invalid identity; exception intentionally contains no token details."""


class AuthenticationUnavailable(Exception):
    """Identity provider unavailable; fail closed without declaring invalid credentials."""
