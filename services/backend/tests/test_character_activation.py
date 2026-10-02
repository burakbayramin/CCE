from datetime import UTC, datetime
from unittest.mock import Mock
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError
from test_character_definitions import proposal, source

from cce.modules.characters import activation
from cce.modules.characters.compiler import artifact_hash, compile_definition
from cce.modules.characters.schemas import (
    ActivateCharacter,
    ChangeCharacterCapacity,
    StoredDefinition,
)
from cce.modules.contributions.repository import ContributionError


def fixture_definition():
    artifact = compile_definition(proposal(), source())
    return StoredDefinition(
        id=UUID(int=5),
        definition_version=1,
        artifact_sha256=artifact_hash(artifact),
        artifact=artifact,
        created_at=datetime.now(UTC),
    )


def activation_command(definition):
    return ActivateCharacter(
        expected_version=4,
        revision_id=definition.artifact.source.revision_id,
        definition_id=definition.id,
        artifact_sha256=definition.artifact_sha256,
        reason="Isolated unit test activation",
    )


def test_local_activation_gate_runs_before_database_access():
    connection = Mock()
    with pytest.raises(ContributionError) as caught:
        activation.activate_fixture(
            connection, UUID(int=1), activation_command(fixture_definition()), test_mode=False
        )
    assert caught.value.status == 409
    connection.execute.assert_not_called()


@pytest.mark.parametrize("tamper", ["prompt", "bootstrap", "invalid_proposal", "nonfixture"])
def test_activation_rejects_tampered_or_real_artifact_before_sql(monkeypatch, tamper):
    definition = fixture_definition()
    artifact = definition.artifact
    if tamper == "prompt":
        artifact = artifact.model_copy(
            update={
                "prompt": artifact.prompt.model_copy(
                    update={"system_instructions": "Injected instruction"}
                )
            }
        )
    elif tamper == "bootstrap":
        artifact = artifact.model_copy(
            update={"bootstrap": artifact.bootstrap.model_copy(update={"core_memories": ()})}
        )
    elif tamper == "invalid_proposal":
        artifact = artifact.model_copy(
            update={
                "proposal": artifact.proposal.model_copy(
                    update={"adult_appearance_confirmed": False}
                )
            }
        )
    else:
        artifact = artifact.model_copy(
            update={"source": artifact.source.model_copy(update={"is_fixture": False})}
        )
    definition = definition.model_copy(
        update={"artifact": artifact, "artifact_sha256": artifact_hash(artifact)}
    )
    monkeypatch.setattr(activation, "read_one", lambda *_: None)
    monkeypatch.setattr(activation, "read_definition", lambda *_: definition)
    connection = Mock()
    with pytest.raises(ContributionError) as caught:
        activation.activate_fixture(
            connection, UUID(int=1), activation_command(definition), test_mode=True
        )
    assert caught.value.status == (409 if tamper == "nonfixture" else 503)
    connection.execute.assert_not_called()


@pytest.mark.parametrize("value", [-1, 51])
def test_capacity_contract_enforces_hard_maximum(value):
    with pytest.raises(ValidationError):
        ChangeCharacterCapacity(
            expected_limit=50,
            active_limit=value,
            reason="Owner capacity change",
            request_id=uuid4(),
        )


def test_client_cannot_supply_initial_state_or_lifecycle():
    command = activation_command(fixture_definition()).model_dump()
    for extra in ({"status": "ACTIVE"}, {"initial_state": {}}, {"is_fixture": True}):
        with pytest.raises(ValidationError):
            ActivateCharacter.model_validate(command | extra)
