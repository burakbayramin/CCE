"""M4.4 — the processing pipeline.

M4.1 recorded that effects happened. This turns them into what a character
becomes, and it is where the source-identity rule from WADR-011 has to hold in
code rather than in a comment.

The identity of an applied effect is derived from the turn, the effect kind and
the effect's own content. It never contains a model name, a provider or a
processing version, so re-running the same experience under a different model
collapses onto the same rows instead of giving the world a second copy of the
same memory.

The two failure classes are deliberately asymmetric. Losing a character's own
state — a memory, its affect, a goal — is fatal and quarantines the turn.
Losing a relationship is recorded on the turn as flagged, because a social bond
can be recovered and the fact that the turn happened cannot.
"""

import hashlib
import json
from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import Connection, text
from sqlalchemy.exc import DBAPIError

from cce.modules.interactions import protocol

EffectKind = str

#: Kinds that change the character itself. A failure here is fatal.
CHARACTER_EFFECTS = frozenset({"MEMORY", "AFFECT", "GOAL"})
#: The transcript is recorded with the turn; it never writes character state.
TRANSCRIPT_EFFECT = "TRANSCRIPT"


def source_identity(turn_identity: str, kind: EffectKind, *parts: str) -> str:
    """A stable key for one applied effect.

    Derived only from the turn and the effect's own content. A different model
    producing the same memory produces the same key, which is what makes a
    retry a no-op instead of a duplicate.
    """
    digest = hashlib.sha256("\x1f".join((turn_identity, kind, *parts)).encode()).hexdigest()
    return f"{kind.lower()}:{digest[:32]}"


@dataclass(frozen=True)
class Affect:
    valence: float
    arousal: float
    dominance: float


@dataclass(frozen=True)
class Memory:
    text: str


@dataclass(frozen=True)
class Goal:
    description: str


@dataclass(frozen=True)
class Relationship:
    subject_id: UUID
    affinity: float
    trust: float


@dataclass(frozen=True)
class Turn:
    """What a handler produced for one interaction.

    `identity` must be derived from the experience, not from the run: it is the
    anchor every effect below hangs from.
    """

    identity: str
    prompt: str
    response: str
    memories: list[Memory] = field(default_factory=list)
    goals: list[Goal] = field(default_factory=list)
    affect: Affect | None = None
    relationships: list[Relationship] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.identity.strip():
            raise ValueError("turn identity must not be empty")


@dataclass(frozen=True)
class TurnOutcome:
    turn_id: UUID
    applied: int
    skipped: int
    flagged: bool


def character_effects(turn: Turn) -> list[dict[str, object]]:
    """Effects that change the character. A failure here is fatal."""
    effects: list[dict[str, object]] = []
    for memory in turn.memories:
        effects.append(
            {
                "effect_kind": "MEMORY",
                "source_identity": source_identity(turn.identity, "MEMORY", memory.text),
                "text": memory.text,
            }
        )
    for goal in turn.goals:
        effects.append(
            {
                "effect_kind": "GOAL",
                "source_identity": source_identity(turn.identity, "GOAL", goal.description),
                "description": goal.description,
            }
        )
    if turn.affect is not None:
        # Affect is the character's current state, not an append, so it is keyed
        # by the turn rather than by its content.
        effects.append(
            {
                "effect_kind": "AFFECT",
                "source_identity": source_identity(turn.identity, "AFFECT"),
                "valence": turn.affect.valence,
                "arousal": turn.affect.arousal,
                "dominance": turn.affect.dominance,
            }
        )
    return effects


def relationship_effects(turn: Turn) -> list[dict[str, object]]:
    """Relationships, isolated from the character effects."""
    return [
        {
            "subject_id": str(item.subject_id),
            "source_identity": source_identity(turn.identity, "RELATIONSHIP", str(item.subject_id)),
            "affinity": item.affinity,
            "trust": item.trust,
        }
        for item in turn.relationships
    ]


def apply_turn(
    connection: Connection,
    *,
    reservation: protocol.Reservation,
    run: protocol.JobRun,
    holder: str,
    turn: Turn,
    turn_index: int,
) -> TurnOutcome:
    """Apply one turn atomically.

    The transaction that calls this either lands the turn and every character
    effect together or lands nothing. A repeated turn index returns the
    original turn unchanged, so a redelivered message is inert.
    """
    try:
        row = (
            connection.execute(
                text(
                    "select * from ops_private.apply_interaction_turn("
                    ":reservation,:generation,:holder,:index,:identity,"
                    ":prompt,:response,cast(:effects as jsonb),cast(:relationships as jsonb))"
                ),
                {
                    "reservation": reservation.id,
                    "generation": reservation.ownership_generation,
                    "holder": holder,
                    "index": turn_index,
                    "identity": turn.identity,
                    "prompt": turn.prompt,
                    "response": turn.response,
                    "effects": json.dumps(character_effects(turn)),
                    "relationships": json.dumps(relationship_effects(turn)),
                },
            )
            .mappings()
            .one()
        )
    except DBAPIError as error:
        raise protocol.classify(error, "Tur uygulanamadı") from None
    return TurnOutcome(
        turn_id=row["turn_id"],
        applied=row["applied"],
        skipped=row["skipped"],
        flagged=row["flagged"],
    )
