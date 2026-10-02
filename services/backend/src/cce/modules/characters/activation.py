"""M3.3 atomic bootstrap. Actual content activation stays closed until model acceptance."""

from uuid import UUID

from sqlalchemy import Connection, text
from sqlalchemy.exc import DBAPIError

from cce.modules.characters.compiler import compile_definition
from cce.modules.characters.repository import read_definition
from cce.modules.characters.schemas import (
    ActivateCharacter,
    ActivatedCharacter,
    CapacityChange,
    ChangeCharacterCapacity,
    CharacterCapacity,
)
from cce.modules.contributions.repository import ContributionError, read_one


def read_activation(connection: Connection, submission_id: UUID) -> ActivatedCharacter | None:
    row = (
        connection.execute(
            text(
                "select c.*,jsonb_build_object('definition_id',s.definition_id,"
                "'bootstrap',s.bootstrap,'owner_person_id',s.owner_person_id,"
                "'owner_relationship_status',s.owner_relationship_status,"
                "'owner_experience_count',s.owner_experience_count) as initial_state "
                "from world_private.characters c "
                "join world_private.character_initial_state s on s.character_id=c.id "
                "where c.submission_id=:id"
            ),
            {"id": submission_id},
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        return None
    return ActivatedCharacter.model_validate(
        {key: row[key] for key in ActivatedCharacter.model_fields}
    )


def activate_fixture(
    connection: Connection, submission_id: UUID, command: ActivateCharacter, *, test_mode: bool
) -> ActivatedCharacter:
    if not test_mode:
        raise ContributionError(409, "Gerçek içerik aktivasyonu model kabulüne kadar kapalı")
    read_one(connection, submission_id)
    definition = read_definition(connection, submission_id)
    if (
        definition is None
        or definition.id != command.definition_id
        or definition.artifact_sha256 != command.artifact_sha256
        or definition.artifact.source.revision_id != command.revision_id
        or not definition.artifact.source.is_fixture
    ):
        raise ContributionError(409, "Güncel derlenmiş test definition gerekli")
    try:
        expected_artifact = compile_definition(
            definition.artifact.proposal, definition.artifact.source
        )
    except ValueError:
        raise ContributionError(503, "Karakter tanımı derleme bütünlüğü doğrulanamadı") from None
    if expected_artifact != definition.artifact:
        raise ContributionError(503, "Karakter tanımı derleme bütünlüğü doğrulanamadı")
    try:
        connection.execute(
            text(
                "select ops_private.activate_fixture_character"
                "(:id,:version,:revision,:definition,:hash,:reason)"
            ),
            {
                "id": submission_id,
                "version": command.expected_version,
                "revision": command.revision_id,
                "definition": command.definition_id,
                "hash": command.artifact_sha256,
                "reason": command.reason,
            },
        )
    except DBAPIError as error:
        if getattr(error.orig, "sqlstate", None) == "23514":
            message = getattr(getattr(error.orig, "diag", None), "message_primary", "")
            detail = (
                "Aktif karakter kapasitesi dolu; limit veya lifecycle durumunu kontrol et"
                if message == "Active character capacity reached"
                else "Aktivasyon kaynağı veya izole test kapısı geçerli değil"
            )
            raise ContributionError(409, detail) from None
        raise
    result = read_activation(connection, submission_id)
    if result is None:
        raise ContributionError(503, "Aktivasyon sonucu doğrulanamadı")
    return result


def read_capacity(connection: Connection) -> CharacterCapacity:
    row = (
        connection.execute(
            text(
                "select active_limit,(select count(*) from world_private.characters "
                "where status='ACTIVE') as active_count from ops_private.character_capacity "
                "where singleton"
            )
        )
        .mappings()
        .one()
    )
    return CharacterCapacity.model_validate(dict(row))


def change_capacity(connection: Connection, command: ChangeCharacterCapacity) -> CapacityChange:
    try:
        row = (
            connection.execute(
                text(
                    "select * from ops_private.set_character_capacity"
                    "(:expected,:limit,:reason,:request)"
                ),
                {
                    "expected": command.expected_limit,
                    "limit": command.active_limit,
                    "reason": command.reason,
                    "request": command.request_id,
                },
            )
            .mappings()
            .one()
        )
    except DBAPIError as error:
        if getattr(error.orig, "sqlstate", None) == "23514":
            raise ContributionError(
                409, "Limit değişikliği çakıştı; aktif sayıyı ve güncel limiti kontrol et"
            ) from None
        raise
    return CapacityChange.model_validate({key: row[key] for key in CapacityChange.model_fields})
