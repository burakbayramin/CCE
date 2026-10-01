from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool

from cce.core.config import Settings
from cce.modules.contributions.avatars import (
    AvatarStorage,
    attach_avatar,
    read_asset,
    reserve_avatar,
)
from cce.modules.contributions.images import MAX_AVATAR_BYTES, verify_image
from cce.modules.contributions.repository import ContributionError
from cce.modules.contributions.schemas import ContributionProblem, Submission
from cce.modules.identity.authentication import TokenVerifier
from cce.modules.identity.domain import Actor, AuthenticationFailed
from cce.modules.identity.repository import actor_transaction, identity_context
from cce.modules.identity.router import actor_dependency


def avatar_router(
    config: Settings, api_engine: Engine, owner_engine: Engine | None, verifier: TokenVerifier
) -> APIRouter:
    router = APIRouter(
        tags=["avatars"],
        responses={
            code: {"model": ContributionProblem}
            for code in (401, 404, 409, 413, 415, 422, 429, 502, 503)
        },
    )
    verified_actor = actor_dependency(verifier)

    def upload(
        actor: Actor,
        submission_id: UUID,
        expected_version: int,
        upload_key: UUID,
        content: bytes,
        content_type: str,
        authorization: str,
    ) -> Submission:
        try:
            storage = AvatarStorage(config, authorization)
            with actor_transaction(api_engine, actor) as connection:
                identity_context(connection, actor)
                # Reject revoked/banned sessions before bounded CPU decoding.
                # Reuse this checkout; reserve_avatar acquires the draft lock
                # only after decoding, and Storage still runs outside the tx.
                image = verify_image(content, content_type)
                asset = reserve_avatar(
                    connection, actor, submission_id, expected_version, upload_key, image
                )
            # No transaction or draft lock is held while Storage is contacted.
            storage.store(asset, image)
            with actor_transaction(api_engine, actor) as connection:
                identity_context(connection, actor)
                return attach_avatar(connection, actor, asset, expected_version)
        except AuthenticationFailed:
            raise HTTPException(401, "Authentication required") from None
        except ContributionError as error:
            raise HTTPException(error.status, error.detail) from None
        except SQLAlchemyError:
            raise HTTPException(503, "Avatar service unavailable") from None

    @router.post(
        "/contributions/{submission_id}/avatar",
        response_model=Submission,
        operation_id="contributions_avatar_upload",
    )
    async def post(
        submission_id: UUID,
        request: Request,
        actor: Annotated[Actor, Depends(verified_actor)],
        upload_key: UUID,
        expected_version: Annotated[int, Query(ge=1)],
    ) -> Submission:
        content = bytearray()
        async for chunk in request.stream():
            content.extend(chunk)
            if len(content) > MAX_AVATAR_BYTES:
                raise HTTPException(413, "Avatar en fazla 512 KiB olabilir")
        return await run_in_threadpool(
            upload,
            actor,
            submission_id,
            expected_version,
            upload_key,
            bytes(content),
            request.headers.get("content-type", ""),
            request.headers.get("authorization", ""),
        )

    @router.get(
        "/avatars/{asset_id}",
        operation_id="avatars_read",
        response_class=Response,
        responses={200: {"content": {"image/png": {}}, "description": "Private avatar"}},
    )
    def get(
        asset_id: UUID, request: Request, actor: Annotated[Actor, Depends(verified_actor)]
    ) -> Response:
        try:
            with actor_transaction(api_engine, actor) as connection:
                identity = identity_context(connection, actor)
                if identity["role"] != "world_owner":
                    asset = read_asset(connection, asset_id)
                    if asset.status != "READY":
                        raise ContributionError(404, "Avatar bulunamadı")
            if identity["role"] == "world_owner":
                if owner_engine is None:
                    raise ContributionError(503, "Owner command database is not configured")
                with actor_transaction(owner_engine, actor) as connection:
                    asset = read_asset(connection, asset_id)
                    if asset.status != "READY":
                        raise ContributionError(404, "Avatar bulunamadı")
            content = AvatarStorage(config, request.headers.get("authorization", "")).read(asset)
            return Response(
                content,
                media_type="image/png",
                headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store"},
            )
        except AuthenticationFailed:
            raise HTTPException(401, "Authentication required") from None
        except ContributionError as error:
            raise HTTPException(error.status, error.detail) from None
        except SQLAlchemyError:
            raise HTTPException(503, "Avatar service unavailable") from None

    return router
