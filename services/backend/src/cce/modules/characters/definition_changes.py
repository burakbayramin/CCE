"""Audited, fixture-only adoption of a newly approved ordinary definition."""

from uuid import UUID

from sqlalchemy import Connection, text
from sqlalchemy.exc import DBAPIError

from cce.modules.characters.activation import read_activation
from cce.modules.characters.schemas import AdoptDefinition, DefinitionChange
from cce.modules.contributions.repository import ContributionError, read_one


def read_definition_changes(connection: Connection, submission_id: UUID) -> list[DefinitionChange]:
    read_one(connection, submission_id)
    character = read_activation(connection, submission_id)
    if character is None:
        return []
    rows = connection.execute(
        text(
            "select * from ops_private.character_definition_events "
            "where character_id=:id order by recorded_at desc,id desc limit 100"
        ),
        {"id": character.id},
    ).mappings()
    return [DefinitionChange.model_validate(row) for row in rows]


def adopt_definition(
    connection: Connection,
    submission_id: UUID,
    command: AdoptDefinition,
    *,
    test_mode: bool,
) -> DefinitionChange:
    if not test_mode:
        raise ContributionError(409, "Gerçek karakter definition değişikliği henüz kapalı")
    read_one(connection, submission_id)
    character = read_activation(connection, submission_id)
    if character is None:
        raise ContributionError(404, "Karakter henüz aktive edilmedi")
    try:
        row = (
            connection.execute(
                text(
                    "select * from ops_private.adopt_fixture_character_definition"
                    "(:character,:definition,:version,:reason,:request)"
                ),
                {
                    "character": character.id,
                    "definition": command.definition_id,
                    "version": command.expected_version,
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
                409, "Güncel onaylı revizyon veya karakter sürümü geçerli değil; durumu yenile"
            ) from None
        raise
    return DefinitionChange.model_validate(row)
