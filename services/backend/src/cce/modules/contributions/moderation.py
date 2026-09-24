"""Moderation boundary. No production allow-all fallback or client-selected verdict."""

from dataclasses import dataclass
from typing import Literal, Protocol

from cce.modules.contributions.schemas import CharacterProposal


@dataclass(frozen=True)
class ModerationOutcome:
    result: Literal["PASS", "REVIEW", "BLOCK", "ERROR"]
    provider: str
    policy_version: str
    is_fixture: bool
    detail: str


class ModerationProvider(Protocol):
    def scan(self, definition: CharacterProposal) -> ModerationOutcome: ...


class UnavailableModeration:
    def scan(self, definition: CharacterProposal) -> ModerationOutcome:
        return ModerationOutcome(
            "ERROR",
            "unconfigured",
            "unconfigured",
            False,
            "Gerçek moderasyon sağlayıcısı henüz yapılandırılmadı. Onay engellendi.",
        )
