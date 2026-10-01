from collections.abc import Iterator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import Connection, Engine, text
from sqlalchemy.exc import SQLAlchemyError

from cce.modules.contributions.repository import (
    ContributionError,
    change_draft,
    create_draft,
    read_history,
    read_one,
)
from cce.modules.contributions.schemas import (
    ContributionProblem,
    CreateDraft,
    Submission,
    SubmissionHistory,
    UpdateDraft,
    VersionCommand,
)
from cce.modules.identity.authentication import TokenVerifier
from cce.modules.identity.domain import Actor, AuthenticationFailed
from cce.modules.identity.repository import actor_transaction, identity_context
from cce.modules.identity.router import actor_dependency


def contributions_router(engine: Engine, verifier: TokenVerifier) -> APIRouter:
    router = APIRouter(
        prefix="/contributions",
        tags=["contributions"],
        responses={code: {"model": ContributionProblem} for code in (401, 404, 409, 422, 429, 503)},
    )
    verified_actor = actor_dependency(verifier)

    def transaction(actor: Annotated[Actor, Depends(verified_actor)]) -> Iterator[Connection]:
        try:
            with actor_transaction(engine, actor) as connection:
                identity_context(connection, actor)
                yield connection
        except AuthenticationFailed:
            raise HTTPException(401, "Authentication required") from None
        except ContributionError as error:
            raise HTTPException(error.status, error.detail) from None
        except SQLAlchemyError:
            raise HTTPException(503, "Contribution service unavailable") from None

    @router.get("", response_model=list[Submission], operation_id="contributions_list")
    def list_mine(
        connection: Annotated[Connection, Depends(transaction, scope="function")],
    ) -> list[Submission]:
        rows = connection.execute(
            text("select * from public.character_submissions order by created_at desc limit 50")
        ).mappings()
        return [Submission.model_validate(row) for row in rows]

    @router.post("", response_model=Submission, operation_id="contributions_create")
    def create(
        payload: CreateDraft,
        actor: Annotated[Actor, Depends(verified_actor)],
        connection: Annotated[Connection, Depends(transaction, scope="function")],
    ) -> Submission:
        return create_draft(connection, actor, payload.creation_key, payload.definition)

    @router.get("/{submission_id}", response_model=Submission, operation_id="contributions_get")
    def get_one(
        submission_id: UUID,
        connection: Annotated[Connection, Depends(transaction, scope="function")],
    ) -> Submission:
        return read_one(connection, submission_id)

    @router.put("/{submission_id}", response_model=Submission, operation_id="contributions_update")
    def update(
        submission_id: UUID,
        payload: UpdateDraft,
        actor: Annotated[Actor, Depends(verified_actor)],
        connection: Annotated[Connection, Depends(transaction, scope="function")],
    ) -> Submission:
        return change_draft(
            connection, actor, submission_id, payload.expected_version, "SAVE", payload.definition
        )

    @router.post(
        "/{submission_id}/submit", response_model=Submission, operation_id="contributions_submit"
    )
    def submit(
        submission_id: UUID,
        payload: VersionCommand,
        actor: Annotated[Actor, Depends(verified_actor)],
        connection: Annotated[Connection, Depends(transaction, scope="function")],
    ) -> Submission:
        return change_draft(connection, actor, submission_id, payload.expected_version, "SUBMIT")

    @router.post(
        "/{submission_id}/withdraw",
        response_model=Submission,
        operation_id="contributions_withdraw",
    )
    def withdraw(
        submission_id: UUID,
        payload: VersionCommand,
        actor: Annotated[Actor, Depends(verified_actor)],
        connection: Annotated[Connection, Depends(transaction, scope="function")],
    ) -> Submission:
        return change_draft(connection, actor, submission_id, payload.expected_version, "WITHDRAW")

    @router.get(
        "/{submission_id}/history",
        response_model=SubmissionHistory,
        operation_id="contributions_history",
    )
    def history(
        submission_id: UUID,
        connection: Annotated[Connection, Depends(transaction, scope="function")],
    ) -> SubmissionHistory:
        return read_history(connection, submission_id)

    @router.post(
        "/{submission_id}/revise", response_model=Submission, operation_id="contributions_revise"
    )
    def revise(
        submission_id: UUID,
        payload: VersionCommand,
        actor: Annotated[Actor, Depends(verified_actor)],
        connection: Annotated[Connection, Depends(transaction, scope="function")],
    ) -> Submission:
        return change_draft(connection, actor, submission_id, payload.expected_version, "REVISE")

    return router
