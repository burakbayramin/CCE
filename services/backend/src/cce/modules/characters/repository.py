from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import Connection, text

from cce.modules.characters.compiler import artifact_hash, canonical_json, compile_definition
from cce.modules.characters.schemas import CompileDefinition, DefinitionSource, StoredDefinition
from cce.modules.contributions.repository import ContributionError, read_one
from cce.modules.contributions.schemas import CharacterProposal
from cce.modules.identity.domain import Actor


def read_definition(
    connection: Connection, submission_id: UUID, revision_id: UUID | None = None
) -> StoredDefinition | None:
    row = (
        connection.execute(
            text(
                "select * from world_private.character_definitions "
                "where submission_id=:id and (cast(:revision as uuid) is null "
                "or revision_id=cast(:revision as uuid)) "
                "order by definition_version desc limit 1"
            ),
            {"id": submission_id, "revision": revision_id},
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        return None
    try:
        result = StoredDefinition.model_validate(
            {key: row[key] for key in StoredDefinition.model_fields}
        )
        if artifact_hash(result.artifact) != result.artifact_sha256:
            raise ValueError("Artifact integrity mismatch")
        return result
    except (ValidationError, ValueError):
        raise ContributionError(503, "Karakter tanımı bütünlüğü doğrulanamadı") from None


def prepare_definition(
    connection: Connection,
    actor: Actor,
    submission_id: UUID,
    command: CompileDefinition,
    *,
    test_mode: bool,
) -> StoredDefinition:
    item = read_one(connection, submission_id, lock=True)
    if (
        item.status != "APPROVED"
        or item.version != command.expected_version
        or item.revision_id != command.revision_id
    ):
        raise ContributionError(409, "Güncel onaylı revizyon gerekli; sayfayı yenile")
    row = (
        connection.execute(
            text(
                "select r.definition,r.revision_number,r.avatar_id,a.sha256 as avatar_sha256,"
                "f.id as approval_id,f.actor_user_id as approved_by,f.created_at as approved_at,"
                "m.provider as moderation_provider,m.policy_version as moderation_policy_version,"
                "m.result as moderation_result,m.is_fixture,s.review_accepted "
                "from public.character_submissions s "
                "join public.submission_revisions r on r.id=s.revision_id and r.submission_id=s.id "
                "join public.submission_feedback f on f.submission_id=s.id and f.revision_id=r.id "
                "and f.decision='APPROVED' and f.resulting_version=s.version "
                "join ops_private.submission_moderation m on m.revision_id=r.id "
                "left join public.avatar_assets a on a.id=r.avatar_id and a.status='READY' "
                "where s.id=:id"
            ),
            {"id": item.id},
        )
        .mappings()
        .one_or_none()
    )
    if (
        row is None
        or row["moderation_result"] not in {"PASS", "REVIEW"}
        or (row["moderation_result"] == "REVIEW" and not row["review_accepted"])
        or (row["is_fixture"] and not test_mode)
    ):
        raise ContributionError(409, "Geçerli onay ve moderasyon kanıtı gerekli")
    existing = read_definition(connection, submission_id, item.revision_id)
    if existing is not None:
        return existing
    source = DefinitionSource.model_validate(
        {
            "submission_id": item.id,
            "revision_id": item.revision_id,
            **{
                key: row[key]
                for key in DefinitionSource.model_fields
                if key not in {"submission_id", "revision_id"}
            },
        }
    )
    try:
        artifact = compile_definition(CharacterProposal.model_validate(row["definition"]), source)
    except ValueError:
        raise ContributionError(409, "Onaylı kaynağın derleme koşulları sağlanmadı") from None
    connection.execute(
        text(
            "insert into world_private.character_definitions "
            "(submission_id,revision_id,approval_id,definition_version,compiler_version,"
            "artifact,artifact_sha256,created_by) values "
            "(:submission,:revision,:approval,:version,:compiler,"
            "cast(:artifact as jsonb),:hash,:actor)"
        ),
        {
            "submission": item.id,
            "revision": item.revision_id,
            "approval": source.approval_id,
            "version": source.revision_number,
            "compiler": artifact.compiler_version,
            "artifact": canonical_json(artifact.model_dump(mode="json")),
            "hash": artifact_hash(artifact),
            "actor": actor.user_id,
        },
    )
    result = read_definition(connection, submission_id, item.revision_id)
    if result is None:
        raise ContributionError(503, "Karakter tanımı kaydı okunamadı")
    return result
