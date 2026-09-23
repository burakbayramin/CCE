from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
TextItems = Annotated[list[ShortText], Field(max_length=8)]


class Personality(BaseModel):
    model_config = ConfigDict(extra="forbid")
    openness: int = Field(default=50, ge=0, le=100)
    sociability: int = Field(default=50, ge=0, le=100)
    conscientiousness: int = Field(default=50, ge=0, le=100)
    assertiveness: int = Field(default=50, ge=0, le=100)
    warmth: int = Field(default=50, ge=0, le=100)


class CharacterProposal(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    schema_version: Literal[1] = 1
    name: str = Field(default="", max_length=80)
    pronouns: str = Field(default="", max_length=60)
    age: int = Field(default=18, ge=18, le=10000)
    introduction: str = Field(default="", max_length=400)
    occupation: str = Field(default="", max_length=120)
    cultural_background: str = Field(default="", max_length=400)
    personality: Personality = Field(default_factory=Personality)
    strengths: TextItems = Field(default_factory=list)
    flaws: TextItems = Field(default_factory=list)
    values: TextItems = Field(default_factory=list)
    fears: TextItems = Field(default_factory=list)
    motivations: TextItems = Field(default_factory=list)
    likes: TextItems = Field(default_factory=list)
    dislikes: TextItems = Field(default_factory=list)
    humor: str = Field(default="", max_length=200)
    speech_style: str = Field(default="", max_length=300)
    backstory: str = Field(default="", max_length=4000)
    important_events: TextItems = Field(default_factory=list)
    initial_goals: TextItems = Field(default_factory=list)
    known_people: TextItems = Field(default_factory=list)
    secret_proposals: TextItems = Field(default_factory=list)
    adult_appearance_confirmed: bool = False
    original_character_confirmed: bool = False


class CreateDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    creation_key: UUID
    definition: CharacterProposal


class UpdateDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    definition: CharacterProposal


class VersionCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)


class Submission(BaseModel):
    id: UUID
    user_id: UUID
    status: Literal["DRAFT", "SUBMITTED", "WITHDRAWN"]
    version: int
    definition: CharacterProposal
    revision_id: UUID | None
    created_at: datetime
    updated_at: datetime


class ContributionProblem(BaseModel):
    detail: str | list[dict[str, object]]
