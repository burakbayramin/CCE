import os

import psycopg
import pytest
from fastapi.testclient import TestClient
from local_environment import ADMIN_DSN, API_DSN, DB_PORT
from pydantic import SecretStr

from cce.api_entrypoint import create_app
from cce.core.config import Settings
from cce.infrastructure import database as database_module
from cce.infrastructure.database import create_database, database_ready

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
            8,
        )
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            connection.execute("set role cce_migrator")
        connection.rollback()
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            connection.execute("update ops_private.schema_version set version = 8")
        connection.rollback()
    config = Settings(
        environment="test",
        database_url=SecretStr(API_DSN),
    )
    with TestClient(create_app(config)) as client:
        assert client.get("/health/ready").json() == {"status": "ok"}


def test_database_ready_rejects_schema_version_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    if os.environ.get("CCE_ENVIRONMENT") != "test":
        pytest.fail("Integration tests require isolated local fixtures")
    config = Settings(environment="test", database_url=SecretStr(API_DSN))
    engine = create_database(config)
    try:
        assert database_ready(engine)
        monkeypatch.setattr(database_module, "REQUIRED_SCHEMA_VERSION", 9)
        assert not database_ready(engine)
        with pytest.raises(RuntimeError, match="API database identity or schema"):
            with TestClient(create_app(config)):
                pass
    finally:
        engine.dispose()


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


def test_migration_owner_cannot_update_marker_under_forced_rls() -> None:
    if os.environ.get("CCE_ENVIRONMENT") != "test":
        pytest.fail("Integration tests require isolated local fixtures")
    with psycopg.connect(ADMIN_DSN) as connection:
        connection.execute("set role cce_migrator")
        assert connection.execute("select current_user").fetchone() == ("cce_migrator",)
        assert (
            connection.execute(
                "update ops_private.schema_version set version=8 where singleton returning version"
            ).fetchone()
            is None
        )
        connection.execute("reset role")
        assert connection.execute("select version from ops_private.schema_version").fetchone() == (
            8,
        )
