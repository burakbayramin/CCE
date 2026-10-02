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


class ActivateCharacter(StartReview):
    definition_id: UUID
    artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    reason: str = Field(min_length=10, max_length=1000)


class InitialCharacterState(FrozenModel):
    definition_id: UUID
    bootstrap: BootstrapCandidates
    owner_person_id: UUID
    owner_relationship_status: Literal["UNACQUAINTED"]
    owner_experience_count: Literal[0]


class ActivatedCharacter(FrozenModel):
    id: UUID
    person_id: UUID
    submission_id: UUID
    active_definition_id: UUID
    status: Literal["ACTIVE", "SUSPENDED", "ARCHIVED"]
    is_fixture: Literal[True]
    activated_at: datetime
    lifecycle_version: int = Field(ge=1)
    updated_at: datetime
    suspension_reason: str | None
    archive_reason: str | None
    initial_state: InitialCharacterState


class CharacterCapacity(FrozenModel):
    active_limit: int = Field(ge=0, le=50)
    active_count: int = Field(ge=0)


class ChangeCharacterCapacity(FrozenModel):
    expected_limit: int = Field(ge=0, le=50)
    active_limit: int = Field(ge=0, le=50)
    reason: str = Field(min_length=10, max_length=1000)
    request_id: UUID


class CapacityChange(FrozenModel):
    id: UUID
    request_id: UUID
    previous_limit: int
    active_limit: int
    active_count: int
    reason: str
    recorded_at: datetime


class LifecycleCommand(FrozenModel):
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=10, max_length=1000)
    request_id: UUID
    reviewed_prior_reason: str | None = Field(default=None, min_length=10, max_length=1000)


class LifecycleChange(FrozenModel):
    id: UUID
    request_id: UUID
    character_id: UUID
    actor_user_id: UUID
    action: Literal["SUSPEND", "ARCHIVE", "RESTORE", "REACTIVATE"]
    previous_status: Literal["ACTIVE", "SUSPENDED", "ARCHIVED"]
    new_status: Literal["ACTIVE", "SUSPENDED", "ARCHIVED"]
    previous_version: int = Field(ge=1)
    new_version: int = Field(ge=2)
    definition_id: UUID
    reason: str
    reviewed_prior_reason: str | None
    recorded_at: datetime
