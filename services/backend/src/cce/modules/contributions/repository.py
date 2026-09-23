from uuid import UUID

from sqlalchemy import Connection, text

from cce.modules.contributions.schemas import CharacterProposal, Submission
from cce.modules.identity.domain import Actor


class ContributionError(Exception):
    def __init__(self, status: int, detail: str) -> None:
        self.status = status
        self.detail = detail


def read_one(connection: Connection, submission_id: UUID, *, lock: bool = False) -> Submission:
    row = (
        connection.execute(
            text(
                "select * from public.character_submissions where id=:id"
                + (" for update" if lock else "")
            ),
            {"id": submission_id},
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise ContributionError(404, "Başvuru bulunamadı")
    return Submission.model_validate(row)


def record_event(connection: Connection, actor: Actor, item: Submission, action: str) -> None:
    connection.execute(
        text(
            "insert into ops_private.contribution_events "
            "(submission_id, actor_user_id, action, resulting_version, revision_id) "
            "values (:id,:actor,:action,:version,:revision)"
        ),
        {
            "id": item.id,
            "actor": actor.user_id,
            "action": action,
            "version": item.version,
            "revision": item.revision_id,
        },
    )


def create_draft(
    connection: Connection, actor: Actor, key: UUID, definition: CharacterProposal
) -> Submission:
    # Serializes per-contributor creation and quotas, including idempotent retries.
    connection.execute(
        text("select pg_advisory_xact_lock(hashtextextended(:actor, 0))"),
        {"actor": str(actor.user_id)},
    )
    existing = (
        connection.execute(
            text(
                "select * from public.character_submissions "
                "where user_id=:actor and creation_key=:key"
            ),
            {"actor": actor.user_id, "key": key},
        )
        .mappings()
        .one_or_none()
    )
    if existing:
        item = Submission.model_validate(existing)
        if item.definition != definition:
            raise ContributionError(409, "Aynı işlem kimliği farklı içerikle kullanılamaz")
        return item
    count = connection.execute(
        text(
            "select count(*) from public.character_submissions where user_id=:actor "
            "and (status in ('DRAFT','SUBMITTED') or created_at > now() - interval '1 day')"
        ),
        {"actor": actor.user_id},
    ).scalar_one()
    if count >= 10:
        raise ContributionError(429, "Taslak/başvuru limiti doldu; daha sonra tekrar dene")
    submission_id = connection.execute(
        text(
            "insert into public.character_submissions(user_id, creation_key, definition) "
            "values (:actor,:key,cast(:definition as jsonb)) returning id"
        ),
        {"actor": actor.user_id, "key": key, "definition": definition.model_dump_json()},
    ).scalar_one()
    item = read_one(connection, submission_id)
    record_event(connection, actor, item, "CREATED")
    return item


def change_draft(
    connection: Connection,
    actor: Actor,
    submission_id: UUID,
    expected: int,
    action: str,
    definition: CharacterProposal | None = None,
) -> Submission:
    item = read_one(connection, submission_id, lock=True)
    if item.version != expected:
        raise ContributionError(409, "Başvuru değişmiş; sayfayı yenileyip tekrar dene")
    if action == "WITHDRAW":
        if item.status != "SUBMITTED":
            raise ContributionError(409, "Yalnız gönderilmiş başvuru geri çekilebilir")
        status = "WITHDRAWN"
    else:
        if item.status != "DRAFT":
            raise ContributionError(409, "Gönderilmiş veya geri çekilmiş başvuru değiştirilemez")
        status = "DRAFT" if action == "SAVE" else "SUBMITTED"
    proposed = definition if definition is not None else item.definition
    revision = item.revision_id
    if action == "SUBMIT":
        if not (
            proposed.name
            and proposed.introduction
            and proposed.backstory
            and proposed.adult_appearance_confirmed
            and proposed.original_character_confirmed
        ):
            raise ContributionError(422, "İsim, tanıtım, geçmiş ve iki uygunluk onayı gerekli")
        revision = connection.execute(
            text(
                "insert into public.submission_revisions(submission_id, definition) "
                "values (:id,cast(:definition as jsonb)) returning id"
            ),
            {"id": item.id, "definition": proposed.model_dump_json()},
        ).scalar_one()
    connection.execute(
        text(
            "update public.character_submissions set definition=cast(:definition as jsonb), "
            "status=:status, revision_id=:revision, version=version+1, "
            "updated_at=now() where id=:id"
        ),
        {
            "id": item.id,
            "definition": proposed.model_dump_json(),
            "status": status,
            "revision": revision,
        },
    )
    changed = read_one(connection, item.id)
    record_event(connection, actor, changed, action)
    return changed
