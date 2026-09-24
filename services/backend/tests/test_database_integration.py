import os

import psycopg
import pytest
from fastapi.testclient import TestClient
from local_environment import API_DSN, DB_PORT
from pydantic import SecretStr

from cce.api_entrypoint import create_app
from cce.core.config import Settings

pytestmark = pytest.mark.integration


def test_local_api_role_and_readiness() -> None:
    if os.environ.get("CCE_ENVIRONMENT") != "test":
        pytest.fail("Integration tests require explicit CCE_ENVIRONMENT=test and local fixtures")
    with psycopg.connect(
        host="127.0.0.1",
        port=DB_PORT,
        dbname="postgres",
        user="cce_api",
        password="cce-local-api-only",
        connect_timeout=3,
    ) as connection:
        assert connection.execute("select current_user").fetchone() == ("cce_api",)
        assert connection.execute("select version from ops_private.schema_version").fetchone() == (
            1,
        )
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            connection.execute("set role cce_migrator")
        connection.rollback()
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            connection.execute("update ops_private.schema_version set version = 2")
        connection.rollback()
    config = Settings(
        environment="test",
        database_url=SecretStr(API_DSN),
    )
    with TestClient(create_app(config)) as client:
        assert client.get("/health/ready").json() == {"status": "ok"}


def test_worker_has_separate_restricted_identity() -> None:
    if os.environ.get("CCE_ENVIRONMENT") != "test":
        pytest.fail("Integration tests require CCE_ENVIRONMENT=test")
    with psycopg.connect(
        host="127.0.0.1",
        port=DB_PORT,
        dbname="postgres",
        user="cce_worker_cpu",
        password="cce-local-worker-only",
        connect_timeout=3,
    ) as connection:
        assert connection.execute("select current_user").fetchone() == ("cce_worker_cpu",)
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            connection.execute("select * from ops_private.schema_version")
