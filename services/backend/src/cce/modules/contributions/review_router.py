from collections.abc import Iterator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import Connection, Engine, text
from sqlalchemy.exc import SQLAlchemyError

from cce.modules.characters.repository import prepare_definition, read_definition
from cce.modules.characters.schemas import CompileDefinition, StoredDefinition
from cce.modules.contributions.moderation import ModerationProvider
from cce.modules.contributions.repository import ContributionError
from cce.modules.contributions.review import decide, read_review, retry_moderation, start_review
from cce.modules.contributions.schemas import (
    ContributionProblem,
    ReviewCommand,
    ReviewDetail,
    StartReview,
    Submission,
)
from cce.modules.identity.authentication import TokenVerifier
from cce.modules.identity.domain import Actor, AuthenticationFailed
from cce.modules.identity.repository import actor_transaction
from cce.modules.identity.router import actor_dependency


def review_router(
    owner_engine: Engine | None,
    verifier: TokenVerifier,
    provider: ModerationProvider | None,
    *,
    test_mode: bool,
) -> APIRouter:
    router = APIRouter(
        prefix="/reviews",
        tags=["reviews"],
        responses={code: {"model": ContributionProblem} for code in (401, 403, 404, 409, 422, 503)},
    )
    verified_actor = actor_dependency(verifier)

    def transaction(actor: Annotated[Actor, Depends(verified_actor)]) -> Iterator[Connection]:
        try:
            if owner_engine is None:
                raise HTTPException(503, "Owner command database is not configured")
            with actor_transaction(owner_engine, actor) as connection:
                # Recheck in the command transaction; RLS also checks current sessions/role.
                row = connection.execute(
                    text("select actor_role from ops_private.current_identity()")
                )
                role = row.scalar_one_or_none()
                if role is None:
                    raise HTTPException(401, "Authentication required")
                if role != "world_owner":
                    raise HTTPException(403, "World Owner required")
                yield connection
        except AuthenticationFailed:
            raise HTTPException(401, "Authentication required") from None
        except ContributionError as error:
            raise HTTPException(error.status, error.detail) from None
        except SQLAlchemyError:
            raise HTTPException(503, "Review service unavailable") from None

    @router.get("", response_model=list[Submission], operation_id="reviews_list")
    def list_queue(
        connection: Annotated[Connection, Depends(transaction, scope="function")],
    ) -> list[Submission]:
        rows = connection.execute(
            text(
                "select * from public.character_submissions where revision_id is not null "
                "order by updated_at desc limit 100"
            )
        ).mappings()
        return [Submission.model_validate(row) for row in rows]

    @router.get("/{submission_id}", response_model=ReviewDetail, operation_id="reviews_get")
    def detail(
        submission_id: UUID,
        connection: Annotated[Connection, Depends(transaction, scope="function")],
    ) -> ReviewDetail:
        return read_review(connection, submission_id)

    @router.post(
        "/{submission_id}/start", response_model=ReviewDetail, operation_id="reviews_start"
    )
    def start(
        submission_id: UUID,
        payload: StartReview,
        actor: Annotated[Actor, Depends(verified_actor)],
        connection: Annotated[Connection, Depends(transaction, scope="function")],
    ) -> ReviewDetail:
        return start_review(
            connection, actor, submission_id, payload, provider, test_mode=test_mode
        )

    @router.post(
        "/{submission_id}/moderation/retry",
        response_model=ReviewDetail,
        operation_id="reviews_moderation_retry",
    )
    def retry_scan(
        submission_id: UUID,
        payload: StartReview,
        connection: Annotated[Connection, Depends(transaction, scope="function")],
    ) -> ReviewDetail:
        return retry_moderation(connection, submission_id, payload)

    @router.post(
        "/{submission_id}/decision", response_model=Submission, operation_id="reviews_decide"
    )
    def decision(
        submission_id: UUID,
        payload: ReviewCommand,
        actor: Annotated[Actor, Depends(verified_actor)],
        connection: Annotated[Connection, Depends(transaction, scope="function")],
    ) -> Submission:
        return decide(connection, actor, submission_id, payload, test_mode=test_mode)

    @router.get(
        "/{submission_id}/definition",
        response_model=StoredDefinition | None,
        operation_id="reviews_definition_get",
    )
    def definition(
        submission_id: UUID,
        connection: Annotated[Connection, Depends(transaction, scope="function")],
    ) -> StoredDefinition | None:
        read_review(connection, submission_id)
        return read_definition(connection, submission_id)

    @router.post(
        "/{submission_id}/definition",
        response_model=StoredDefinition,
        operation_id="reviews_definition_compile",
    )
    def compile(
        submission_id: UUID,
        payload: CompileDefinition,
        actor: Annotated[Actor, Depends(verified_actor)],
        connection: Annotated[Connection, Depends(transaction, scope="function")],
    ) -> StoredDefinition:
        return prepare_definition(connection, actor, submission_id, payload, test_mode=test_mode)

    return router
