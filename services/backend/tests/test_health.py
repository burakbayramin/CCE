import json
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError

from cce.api_entrypoint import create_app
from cce.core.config import Settings
from cce.infrastructure.telemetry import logger


def settings() -> Settings:
    return Settings(
        environment="test",
        database_url=SecretStr(
            "postgresql+psycopg://cce_api:private-password@127.0.0.1:1/postgres"
        ),
    )


def test_liveness_survives_actual_db_connection_failure() -> None:
    with TestClient(create_app(settings())) as client:
        assert client.get("/health/live").status_code == 200
        response = client.get("/health/ready")
        assert response.status_code == 503
        assert response.json() == {"status": "unavailable"}
        assert "private-password" not in response.text
        assert response.headers["cache-control"] == "no-store"


def test_correlation_and_logs_never_include_request_secrets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    records: list[str] = []
    monkeypatch.setattr(logger, "info", records.append)
    request_id = str(uuid4())
    with TestClient(create_app(settings())) as client:
        response = client.get(
            "/health/live?token=private-query",
            headers={"X-Request-ID": request_id, "Authorization": "Bearer private-token"},
        )
        assert response.headers["x-request-id"] == request_id
        invalid = client.get("/health/live", headers={"X-Request-ID": "private-header"})
        UUID(invalid.headers["x-request-id"])
    assert len(records) == 2
    assert json.loads(records[0])["request_id"] == request_id
    assert "private-" not in "".join(records)


def test_unexpected_exception_is_sanitized(monkeypatch: pytest.MonkeyPatch) -> None:
    records: list[str] = []
    monkeypatch.setattr(logger, "info", records.append)
    app = create_app(settings())

    @app.get("/test-error")
    def fail() -> None:
        raise RuntimeError("private-dsn-and-token")

    with TestClient(app) as client:
        response = client.get("/test-error")
    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    assert "private-dsn" not in "".join(records)


@pytest.mark.parametrize("user", ["postgres", "cce_migrator", "cce_worker_cpu"])
def test_api_rejects_non_api_credentials(user: str) -> None:
    with pytest.raises(ValidationError):
        Settings(database_url=SecretStr(f"postgresql+psycopg://{user}:secret@localhost/postgres"))


def test_readiness_schema_declares_failure_contract() -> None:
    schema = create_app(settings()).openapi()
    assert "503" in schema["paths"]["/health/ready"]["get"]["responses"]


def test_production_rejects_fixture_credentials() -> None:
    with pytest.raises(ValidationError, match="Local fixture credentials"):
        Settings(
            environment="production",
            database_url=SecretStr(
                "postgresql+psycopg://cce_api:cce-local-api-only@localhost/postgres"
            ),
        )
