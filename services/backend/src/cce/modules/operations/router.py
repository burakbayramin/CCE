"""M4.7 — the operations surface as an API.

Owner-only, like every other command surface. The read endpoints carry no
content: worker presence and reservation state, which is what an operator
needs to answer "is anything stuck, and is anyone still alive".
"""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Connection, Engine
from sqlalchemy.exc import SQLAlchemyError

from cce.modules.contributions.repository import ContributionError
from cce.modules.identity.authentication import TokenVerifier
from cce.modules.identity.domain import Actor
from cce.modules.identity.repository import actor_transaction, identity_context
from cce.modules.identity.router import actor_dependency
from cce.modules.operations import service

STALE_BOUND = 3600


class WorkerView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    worker_id: str
    kind: str
    state: str
    last_seen_at: str | None = None
    max_concurrency: int
    current_job: str | None = None
    needs_a_person: bool


class ReservationView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    character_id: str | None = None
    purpose: str | None = None
    state: str | None = None
    ownership_generation: int | None = None
    lease_until: str | None = None
    open_run_attempts: int = 0
    last_attempt_state: str | None = None
    quarantined: bool = False
    lapsed: bool = False


class OperationsView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workers: list[WorkerView] = Field(default_factory=list)
    held: list[ReservationView] = Field(default_factory=list)


class OperationsCommand(BaseModel):
    """Both operator commands. A reason is mandatory: an unexplained state
    change is how a system becomes unexplainable."""

    model_config = ConfigDict(extra="forbid")

    expected_generation: int = Field(ge=1)
    reason: str = Field(min_length=10, max_length=1000)
    worker_id: str = Field(default="operations", max_length=200)


def _view(rows: list[service.OperationsRow]) -> OperationsView:
    workers: list[WorkerView] = []
    held: list[ReservationView] = []
    seen: set[str] = set()

    for row in rows:
        workers.append(
            WorkerView(
                worker_id=row.worker.worker_id,
                kind=row.worker.kind,
                state=row.worker.state,
                last_seen_at=(
                    row.worker.last_seen_at.isoformat() if row.worker.last_seen_at else None
                ),
                max_concurrency=row.worker.max_concurrency,
                current_job=str(row.worker.current_job) if row.worker.current_job else None,
                needs_a_person=row.needs_a_person(),
            )
        )
        reservation = row.reservation
        if reservation is not None and reservation.id not in seen:
            seen.add(str(reservation.id))
            held.append(
                ReservationView(
                    id=str(reservation.id),
                    character_id=str(reservation.character_id)
                    if reservation.character_id
                    else None,
                    purpose=reservation.purpose,
                    state=reservation.state,
                    ownership_generation=reservation.ownership_generation,
                    lease_until=(
                        reservation.lease_until.isoformat() if reservation.lease_until else None
                    ),
                    open_run_attempts=reservation.open_run_attempts,
                    last_attempt_state=reservation.last_attempt_state,
                    quarantined=reservation.quarantined,
                    lapsed=reservation.lapsed(),
                )
            )

    return OperationsView(workers=workers, held=held)


def operations_router(
    engine: Engine, owner_engine: Engine | None, verifier: TokenVerifier
) -> APIRouter:
    verified_actor = actor_dependency(verifier)
    router = APIRouter(prefix="/operations", tags=["operations"])
    responses: dict[int | str, dict[str, object]] = {
        401: {"description": "Authentication required"},
        403: {"description": "World Owner role required"},
        503: {"description": "Operations service unavailable"},
    }

    @contextmanager
    def owner_transaction(actor: Actor) -> Iterator[Connection]:
        """Session and role are settled on the API plane; commands run on the
        owner plane, which is the identity the protocol grants them to."""
        try:
            with actor_transaction(engine, actor) as session:
                if identity_context(session, actor)["role"] != "world_owner":
                    raise HTTPException(403, "World Owner role required")
        except HTTPException:
            raise
        except SQLAlchemyError:
            raise HTTPException(503, "Identity service unavailable") from None

        if owner_engine is None:
            raise HTTPException(503, "Owner command database is not configured")
        try:
            with actor_transaction(owner_engine, actor) as command:
                yield command
        except SQLAlchemyError:
            raise HTTPException(503, "Operations service unavailable") from None

    @router.get(
        "/snapshot",
        response_model=OperationsView,
        responses=responses,
        operation_id="operations_snapshot",
    )
    def operations_snapshot(
        actor: Annotated[Actor, Depends(verified_actor)],
        stale: int = Query(default=service.DEFAULT_STALE_SECONDS, ge=10, le=STALE_BOUND),
    ) -> OperationsView:
        with owner_transaction(actor) as command:
            try:
                return _view(service.snapshot(command, stale_seconds=stale))
            except SQLAlchemyError:
                raise HTTPException(503, "Operations service unavailable") from None

    @router.post(
        "/reservations/{reservation_id}/resolve",
        responses=responses,
        operation_id="operations_resolve_reservation",
    )
    def resolve_reservation(
        reservation_id: str,
        command: OperationsCommand,
        actor: Annotated[Actor, Depends(verified_actor)],
    ) -> dict[str, object]:
        with owner_transaction(actor) as connection:
            try:
                service.resolve_stuck(
                    connection,
                    reservation_id=reservation_id,  # type: ignore[arg-type]
                    expected_generation=command.expected_generation,
                    reason=command.reason,
                )
            except ContributionError as error:
                raise HTTPException(409, error.detail) from None
        return {"state": "RESOLVED", "reservation_id": reservation_id}

    @router.post(
        "/reservations/{reservation_id}/requeue",
        responses=responses,
        operation_id="operations_requeue_reservation",
    )
    def requeue_reservation(
        reservation_id: str,
        command: OperationsCommand,
        actor: Annotated[Actor, Depends(verified_actor)],
    ) -> dict[str, object]:
        with owner_transaction(actor) as connection:
            try:
                service.requeue(
                    connection,
                    reservation_id=reservation_id,  # type: ignore[arg-type]
                    expected_generation=command.expected_generation,
                    worker_id=command.worker_id,
                    reason=command.reason,
                )
            except ContributionError as error:
                raise HTTPException(409, error.detail) from None
        return {"state": "REQUEUED", "reservation_id": reservation_id}

    return router
