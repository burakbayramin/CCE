from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, Response
from pydantic import BaseModel

from cce.core.config import Settings
from cce.infrastructure.database import create_database, database_ready
from cce.infrastructure.telemetry import RequestTelemetry, configure_logging
from cce.modules.contributions.avatar_router import avatar_router
from cce.modules.contributions.moderation import ModerationProvider
from cce.modules.contributions.review_router import review_router
from cce.modules.contributions.router import contributions_router
from cce.modules.identity.authentication import TokenVerifier
from cce.modules.identity.router import identity_router


class Health(BaseModel):
    status: Literal["ok", "unavailable"]


def create_app(
    settings: Settings | None = None, *, moderation: ModerationProvider | None = None
) -> FastAPI:
    # BaseSettings loads the required database_url from the environment at runtime.
    config = settings if settings is not None else Settings()  # type: ignore[call-arg]
    configure_logging()
    engine = create_database(config)
    owner_engine = (
        create_database(config, owner_commands=True) if config.engine_database_url else None
    )
    if moderation is not None and config.environment != "test":
        raise ValueError("Injected moderation is restricted to test environments")

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        try:
            if not database_ready(engine):
                raise RuntimeError("API database identity or schema is unavailable")
            yield
        finally:
            engine.dispose()
            if owner_engine is not None:
                owner_engine.dispose()

    app = FastAPI(title="CCE Control Plane", version="0.1.0", lifespan=lifespan)
    app.add_middleware(RequestTelemetry)
    verifier = TokenVerifier(config)
    app.include_router(identity_router(engine, verifier))
    app.include_router(contributions_router(engine, verifier))
    app.include_router(avatar_router(config, engine, owner_engine, verifier))
    app.include_router(
        review_router(
            owner_engine,
            verifier,
            moderation,
            test_mode=config.environment == "test",
        )
    )

    @app.get("/health/live", response_model=Health, operation_id="liveness")
    def liveness() -> Health:
        return Health(status="ok")

    @app.get(
        "/health/ready",
        response_model=Health,
        operation_id="readiness",
        responses={503: {"model": Health, "description": "Database unavailable or not migrated"}},
    )
    def readiness(response: Response) -> Health:
        if not database_ready(engine):
            response.status_code = 503
            return Health(status="unavailable")
        return Health(status="ok")

    return app
