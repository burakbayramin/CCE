from dataclasses import asdict
from uuid import UUID

from sqlalchemy import Connection, text

from cce.modules.contributions.moderation import ModerationProvider
from cce.modules.contributions.repository import (
    ContributionError,
    read_history,
    read_one,
    record_event,
)
from cce.modules.contributions.schemas import (
    ModerationReport,
    ReviewCommand,
    ReviewDetail,
    StartReview,
    Submission,
)
from cce.modules.identity.domain import Actor


def read_review(connection: Connection, submission_id: UUID) -> ReviewDetail:
    item = read_one(connection, submission_id)
    row = (
        connection.execute(
            text("select * from ops_private.submission_moderation where revision_id=:revision"),
            {"revision": item.revision_id},
        )
        .mappings()
        .one_or_none()
    )
    return ReviewDetail(
        submission=item,
        history=read_history(connection, submission_id),
        moderation=ModerationReport.model_validate(row) if row else None,
    )


def start_review(
    connection: Connection,
    actor: Actor,
    submission_id: UUID,
    payload: StartReview,
    provider: ModerationProvider,
    *,
    test_mode: bool,
) -> ReviewDetail:
    item = read_one(connection, submission_id, lock=True)
    if (
        item.version != payload.expected_version
        or item.revision_id != payload.revision_id
        or item.status != "SUBMITTED"
    ):
        raise ContributionError(409, "Başvuru veya incelenecek revizyon değişmiş; sayfayı yenile")
    # Current adapter is bounded/local. A remote scanner must become a durable M3 job;
    # do not hold this lock over a network/model call.
    outcome = provider.scan(item.definition)
    if outcome.is_fixture and not test_mode:
        raise ContributionError(503, "Test moderasyonu gerçek içerikte kullanılamaz")
    connection.execute(
        text(
            "insert into ops_private.submission_moderation "
            "(revision_id,submission_id,result,provider,policy_version,is_fixture,detail) "
            "values (:revision,:id,:result,:provider,:policy_version,:is_fixture,:detail)"
        ),
        {"revision": item.revision_id, "id": item.id, **asdict(outcome)},
    )
    connection.execute(
        text(
            "update public.character_submissions set status='UNDER_REVIEW',version=version+1 "
            "where id=:id"
        ),
        {"id": item.id},
    )
    record_event(connection, actor, read_one(connection, item.id), "START_REVIEW")
    return read_review(connection, item.id)


def decide(
    connection: Connection,
    actor: Actor,
    submission_id: UUID,
    payload: ReviewCommand,
    *,
    test_mode: bool,
) -> Submission:
    item = read_one(connection, submission_id, lock=True)
    if (
        item.version != payload.expected_version
        or item.revision_id != payload.revision_id
        or item.status != "UNDER_REVIEW"
    ):
        raise ContributionError(409, "İncelenen revizyon veya başvuru değişmiş; sayfayı yenile")
    if payload.decision == "APPROVED":
        report = read_review(connection, item.id).moderation
        if (
            report is None
            or report.result in {"BLOCK", "ERROR"}
            or (report.is_fixture and not test_mode)
            or (report.result == "REVIEW" and not payload.review_accepted)
        ):
            raise ContributionError(409, "Moderasyon onay koşulları sağlanmadı")
    elif payload.review_accepted:
        raise ContributionError(422, "Olumlu REVIEW kararı yalnız onayla verilebilir")
    connection.execute(
        text(
            "update public.character_submissions set status=:status, version=version+1, "
            "review_accepted=:accepted where id=:id"
        ),
        {"id": item.id, "status": payload.decision, "accepted": payload.review_accepted},
    )
    updated = read_one(connection, item.id)
    connection.execute(
        text(
            "insert into public.submission_feedback "
            "(submission_id,revision_id,actor_user_id,decision,reason,resulting_version) "
            "values (:id,:revision,:actor,:decision,:reason,:version)"
        ),
        {
            "id": item.id,
            "revision": item.revision_id,
            "actor": actor.user_id,
            "decision": payload.decision,
            "reason": payload.reason,
            "version": updated.version,
        },
    )
    record_event(connection, actor, updated, payload.decision, payload.reason)
    return updated
