"""Owner-only lifecycle commands for fixture characters; M4 consumes lifecycle_version."""

from typing import Literal
from uuid import UUID

from sqlalchemy import Connection, text
from sqlalchemy.exc import DBAPIError

from cce.modules.characters.activation import read_activation
from cce.modules.characters.schemas import LifecycleChange, LifecycleCommand
from cce.modules.contributions.repository import ContributionError, read_one

LifecycleAction = Literal["SUSPEND", "ARCHIVE", "RESTORE", "REACTIVATE"]


def read_lifecycle_history(connection: Connection, submission_id: UUID) -> list[LifecycleChange]:
    read_one(connection, submission_id)
    character = read_activation(connection, submission_id)
    if character is None:
        return []
    rows = connection.execute(
        text(
            "select * from ops_private.character_lifecycle_events "
            "where character_id=:id order by recorded_at desc,id desc limit 100"
        ),
        {"id": character.id},
    ).mappings()
    return [LifecycleChange.model_validate(row) for row in rows]


def apply_lifecycle(
    connection: Connection,
    submission_id: UUID,
    action: LifecycleAction,
    command: LifecycleCommand,
    *,
    test_mode: bool,
) -> LifecycleChange:
    if not test_mode:
        raise ContributionError(409, "Gerçek karakter lifecycle komutları henüz kapalı")
    read_one(connection, submission_id)
    character = read_activation(connection, submission_id)
    if character is None:
        raise ContributionError(404, "Karakter henüz aktive edilmedi")
    try:
        row = (
            connection.execute(
                text(
                    "select * from ops_private.apply_fixture_character_lifecycle"
                    "(:character,:action,:version,:reason,:request,:prior)"
                ),
                {
                    "character": character.id,
                    "action": action,
                    "version": command.expected_version,
                    "reason": command.reason,
                    "request": command.request_id,
                    "prior": command.reviewed_prior_reason,
                },
            )
            .mappings()
            .one()
        )
    except DBAPIError as error:
        if getattr(error.orig, "sqlstate", None) == "23514":
            message = getattr(getattr(error.orig, "diag", None), "message_primary", "")
            detail = (
                "Aktif karakter kapasitesi dolu; yeniden aktivasyon reddedildi"
                if message == "Active character capacity reached"
                else "Lifecycle durumu, gerekçesi veya güncel onay değişti; durumu yenile"
            )
            raise ContributionError(409, detail) from None
        raise
    return LifecycleChange.model_validate(row)
