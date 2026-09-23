from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError

from cce.modules.identity.authentication import TokenVerifier
from cce.modules.identity.domain import AuthenticationFailed, AuthenticationUnavailable
from cce.modules.identity.repository import identity_context


class Identity(BaseModel):
    user_id: UUID
    role: Literal["contributor", "world_owner"]
    person_id: UUID | None


class IdentityError(BaseModel):
    detail: str


def identity_router(engine: Engine, verifier: TokenVerifier) -> APIRouter:
    router = APIRouter(prefix="/identity", tags=["identity"])
    bearer = HTTPBearer(auto_error=False)

    def current_identity(
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    ) -> Identity:
        try:
            if credentials is None:
                raise AuthenticationFailed
            actor = verifier.verify(credentials.credentials)
            return Identity.model_validate(identity_context(engine, actor))
        except AuthenticationFailed:
            raise HTTPException(
                401,
                "Authentication required",
                headers={
                    "WWW-Authenticate": "Bearer",
                },
            ) from None
        except (AuthenticationUnavailable, SQLAlchemyError):
            raise HTTPException(503, "Identity service unavailable") from None

    responses: dict[int | str, dict[str, Any]] = {
        401: {"model": IdentityError},
        503: {"model": IdentityError},
    }

    @router.get("/me", response_model=Identity, responses=responses, operation_id="identity_me")
    def me(identity: Annotated[Identity, Depends(current_identity)]) -> Identity:
        return identity

    @router.get(
        "/owner",
        response_model=Identity,
        responses={
            **responses,
            403: {"model": IdentityError},
        },
        operation_id="identity_owner",
    )
    def owner(identity: Annotated[Identity, Depends(current_identity)]) -> Identity:
        if identity.role != "world_owner":
            raise HTTPException(403, "World Owner access required")
        return identity

    return router
