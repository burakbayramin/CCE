from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from cce.modules.contributions.schemas import CharacterProposal, Personality, StartReview


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class DefinitionSource(FrozenModel):
    submission_id: UUID
    revision_id: UUID
    revision_number: int = Field(ge=1)
    approval_id: UUID
    approved_by: UUID
    approved_at: datetime
    moderation_policy_version: str
    moderation_provider: str
    moderation_result: Literal["PASS", "REVIEW"]
    is_fixture: bool
    avatar_id: UUID | None
    avatar_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class SeedCandidate(FrozenModel):
    kind: Literal["background", "goal", "drive", "relationship_proposal", "secret_proposal"]
    text: str = Field(min_length=1, max_length=4000)
    source_revision_id: UUID
    source_field: str
    access: Literal["private"] = "private"
    sharing_policy: Literal["character_only"] = "character_only"
    requires_validation: Literal[True] = True
    is_lived_experience: Literal[False] = False


class AffectBaseline(FrozenModel):
    valence: float = Field(ge=-1, le=1)
    arousal: float = Field(ge=-1, le=1)
    dominance: float = Field(ge=-1, le=1)


class BootstrapCandidates(FrozenModel):
    derivation_version: Literal["bootstrap-v1"] = "bootstrap-v1"
    calibration_status: Literal["provisional"] = "provisional"
    source_revision_id: UUID
    temperament: Personality
    baseline_source_fields: tuple[str, ...]
    baseline: AffectBaseline
    initial_affect: AffectBaseline
    core_memories: tuple[SeedCandidate, ...]
    core_drives: tuple[SeedCandidate, ...]
    goals: tuple[SeedCandidate, ...]
    relationships: tuple[SeedCandidate, ...]
    secrets: tuple[SeedCandidate, ...]


class PromptTemplate(FrozenModel):
    template_version: Literal["character-v1"] = "character-v1"
    system_instructions: str
    character_data_json: str
    # Not a model-ready context: recipient filtering and runtime authorization are mandatory.
    requires_context_filtering: Literal[True] = True


class CharacterDefinition(FrozenModel):
    schema_version: Literal[1] = 1
    compiler_version: Literal["definition-v1"] = "definition-v1"
    source: DefinitionSource
    proposal: CharacterProposal
    bootstrap: BootstrapCandidates
    prompt: PromptTemplate


class StoredDefinition(FrozenModel):
    id: UUID
    definition_version: int = Field(ge=1)
    artifact_sha256: str
    artifact: CharacterDefinition
    created_at: datetime


class CompileDefinition(StartReview):
    """Client supplies only the expected source, never derived state or prompt text."""
