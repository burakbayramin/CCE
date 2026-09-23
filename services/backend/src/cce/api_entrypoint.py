from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, Response
from pydantic import BaseModel

from cce.core.config import Settings
from cce.infrastructure.database import create_database, database_ready
from cce.infrastructure.telemetry import RequestTelemetry, configure_logging
from cce.modules.identity.authentication import TokenVerifier
from cce.modules.identity.router import identity_router


class Health(BaseModel):
    status: Literal["ok", "unavailable"]


def create_app(settings: Settings | None = None) -> FastAPI:
    # BaseSettings loads the required database_url from the environment at runtime.
    config = settings if settings is not None else Settings()  # type: ignore[call-arg]
    configure_logging()
    engine = create_database(config)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        yield
        engine.dispose()

    app = FastAPI(title="CCE Control Plane", version="0.1.0", lifespan=lifespan)
    app.add_middleware(RequestTelemetry)
    app.include_router(identity_router(engine, TokenVerifier(config)))

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
