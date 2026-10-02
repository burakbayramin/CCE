"""M4.4 — the processing pipeline's identity and shape rules.

The whole point of the source identity is that it survives a model change, so
most of these tests are about what the key must *not* contain.
"""

from uuid import uuid4

import pytest

from cce.modules.interactions.processing import (
    Affect,
    Goal,
    Memory,
    Relationship,
    Turn,
    character_effects,
    relationship_effects,
    source_identity,
)

IDENTITY = "turn-1:exp:9f2a"


class TestSourceIdentity:
    def test_the_same_experience_yields_the_same_key(self) -> None:
        assert source_identity(IDENTITY, "MEMORY", "liman") == source_identity(
            IDENTITY, "MEMORY", "liman"
        )

    def test_different_content_yields_a_different_key(self) -> None:
        assert source_identity(IDENTITY, "MEMORY", "liman") != source_identity(
            IDENTITY, "MEMORY", "liman gecesi"
        )

    def test_different_kinds_do_not_collide(self) -> None:
        assert source_identity(IDENTITY, "MEMORY", "x") != source_identity(IDENTITY, "GOAL", "x")

    def test_different_turns_do_not_collide(self) -> None:
        assert source_identity("turn-1", "MEMORY", "x") != source_identity("turn-2", "MEMORY", "x")

    def test_the_key_carries_no_model_or_version(self) -> None:
        """A stub satisfying this test while embedding the model would be the
        exact regression the rule exists to prevent."""
        key = source_identity(IDENTITY, "MEMORY", "liman")
        for forbidden in ("model", "llama", "qwen", "gpt", "v1", "v2", "provider", "processor"):
            assert forbidden not in key.lower(), f"{forbidden} leaked into the identity"

    def test_the_key_is_derived_from_content_not_from_a_counter(self) -> None:
        """Two identical memories in different turns stay distinguishable."""
        first = source_identity("turn-1", "MEMORY", "liman")
        second = source_identity("turn-2", "MEMORY", "liman")
        assert first != second


class TestEffectShape:
    def test_a_turn_with_nothing_to_say_still_produces_a_turn(self) -> None:
        assert character_effects(Turn(IDENTITY, "selam", "merhaba")) == []

    def test_memories_goals_and_affect_become_character_effects(self) -> None:
        turn = Turn(
            IDENTITY,
            "neredeydin",
            "limanda",
            memories=[Memory("sabahın ilk ışığı")],
            goals=[Goal("arşivi düzenlemek")],
            affect=Affect(0.4, -0.2, 0.1),
        )
        kinds = [effect["effect_kind"] for effect in character_effects(turn)]
        assert kinds == ["MEMORY", "GOAL", "AFFECT"]

    def test_every_character_effect_carries_a_source_identity(self) -> None:
        turn = Turn(
            IDENTITY,
            "q",
            "a",
            memories=[Memory("m")],
            goals=[Goal("g")],
            affect=Affect(0.0, 0.0, 0.0),
        )
        for effect in character_effects(turn):
            assert effect["source_identity"]

    def test_relationships_are_kept_out_of_the_character_effects(self) -> None:
        """Mixing them would make a social failure fatal, which is the whole
        distinction M4.4 draws."""
        turn = Turn(
            IDENTITY,
            "q",
            "a",
            memories=[Memory("m")],
            relationships=[Relationship(uuid4(), 0.3, 0.1)],
        )
        assert all(effect["effect_kind"] != "RELATIONSHIP" for effect in character_effects(turn))
        assert len(relationship_effects(turn)) == 1

    def test_relationships_are_keyed_by_subject(self) -> None:
        subject = uuid4()
        first = relationship_effects(
            Turn(IDENTITY, "q", "a", relationships=[Relationship(subject, 0.1, 0.2)])
        )
        second = relationship_effects(
            Turn(IDENTITY, "q", "a", relationships=[Relationship(subject, 0.9, 0.9)])
        )
        assert first[0]["source_identity"] == second[0]["source_identity"], (
            "the same relationship to the same subject must collide so the newer "
            "value updates rather than accumulating"
        )

    def test_a_different_subject_is_a_different_relationship(self) -> None:
        first = relationship_effects(
            Turn(IDENTITY, "q", "a", relationships=[Relationship(uuid4(), 0.1, 0.2)])
        )
        second = relationship_effects(
            Turn(IDENTITY, "q", "a", relationships=[Relationship(uuid4(), 0.1, 0.2)])
        )
        assert first[0]["source_identity"] != second[0]["source_identity"]


class TestTurn:
    def test_an_empty_identity_is_refused(self) -> None:
        with pytest.raises(ValueError):
            Turn("   ", "q", "a")
