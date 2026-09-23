import os
from collections.abc import Iterator
from uuid import UUID, uuid4

import httpx
import psycopg
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import text

from cce.api_entrypoint import create_app
from cce.core.config import Settings
from cce.infrastructure.database import create_database
from cce.modules.identity.authentication import TokenVerifier
from cce.modules.identity.repository import actor_transaction

pytestmark = pytest.mark.integration


def settings() -> Settings:
    return Settings(
        environment="test",
        db_pool_size=1,
        database_url=SecretStr(
            "postgresql+psycopg://cce_api:cce-local-api-only@127.0.0.1:54322/postgres"
        ),
    )


@pytest.fixture
def accounts() -> Iterator[tuple[list[dict[str, str]], httpx.Client]]:
    if os.environ.get("CCE_ENVIRONMENT") != "test":
        pytest.fail("Identity integration requires isolated local test fixtures")
    key = os.environ.get("CCE_TEST_SUPABASE_PUBLISHABLE_KEY")
    if not key:
        pytest.fail("Set CCE_TEST_SUPABASE_PUBLISHABLE_KEY from local Supabase status")
    users: list[dict[str, str]] = []
    with httpx.Client(
        base_url="http://127.0.0.1:54321", headers={"apikey": key}, timeout=10
    ) as auth:
        try:
            for _ in range(2):
                email = f"cce-test-{uuid4()}@example.com"
                password = f"CCE-test-{uuid4()}!"
                response = auth.post(
                    "/auth/v1/signup",
                    json={
                        "email": email,
                        "password": password,
                        "data": {"role": "world_owner"},
                    },
                )
                assert response.status_code == 200
                data = response.json()
                users.append(
                    {
                        "id": data["user"]["id"],
                        "token": data["access_token"],
                        "refresh": data["refresh_token"],
                        "email": email,
                        "password": password,
                    }
                )
            yield users, auth
        finally:
            # Only random accounts created by this fixture are removed; never reset the DB.
            with psycopg.connect("postgresql://postgres:postgres@127.0.0.1:54322/postgres") as db:
                for user in users:
                    target = UUID(user["id"])
                    person = db.execute(
                        "delete from ops_private.world_owner where user_id=%s returning person_id",
                        (target,),
                    ).fetchone()
                    db.execute(
                        "delete from ops_private.identity_audit where target_user_id=%s", (target,)
                    )
                    if person:
                        db.execute("delete from world_private.people where id=%s", person)
                    db.execute("delete from public.profiles where user_id=%s", (target,))
                    db.execute("delete from auth.users where id=%s", (target,))


def test_real_auth_owner_bootstrap_and_revoked_session(
    accounts: tuple[list[dict[str, str]], httpx.Client],
) -> None:
    users, auth = accounts
    first, second = users
    headers = {"Authorization": f"Bearer {first['token']}"}
    with TestClient(create_app(settings())) as api:
        assert api.get("/identity/me", headers=headers).json()["role"] == "contributor"
        assert api.get("/identity/owner", headers=headers).status_code == 403
        with psycopg.connect("postgresql://postgres:postgres@127.0.0.1:54322/postgres") as db:
            # A real Owner must never be reassigned by tests.
            assert db.execute("select count(*) from ops_private.world_owner").fetchone() == (0,)
            args = (UUID(first["id"]), "Test person", "integration-test", "M2 acceptance fixture")
            person = db.execute(
                "select ops_private.bootstrap_world_owner(%s,%s,%s,%s)", args
            ).fetchone()
            assert (
                db.execute("select ops_private.bootstrap_world_owner(%s,%s,%s,%s)", args).fetchone()
                == person
            )
            assert db.execute(
                "select count(*) from ops_private.identity_audit where target_user_id=%s",
                (UUID(first["id"]),),
            ).fetchone() == (1,)
            with pytest.raises(psycopg.errors.UniqueViolation), db.transaction():
                db.execute(
                    "select ops_private.bootstrap_world_owner(%s,%s,%s,%s)",
                    (UUID(second["id"]), "Other person", "integration-test", "Must reject"),
                )
        assert api.get("/identity/owner", headers=headers).json()["person_id"] == str(person[0])
        assert (
            api.get(
                "/identity/owner", headers={"Authorization": f"Bearer {second['token']}"}
            ).status_code
            == 403
        )
        direct = auth.post("/rest/v1/profiles", headers=headers, json={"user_id": second["id"]})
        assert direct.status_code in {401, 403}
        refreshed = auth.post(
            "/auth/v1/token?grant_type=refresh_token", json={"refresh_token": first["refresh"]}
        )
        assert refreshed.status_code == 200
        token = refreshed.json()["access_token"]
        assert (
            api.get("/identity/me", headers={"Authorization": f"Bearer {token}"}).status_code == 200
        )
        assert (
            auth.post(
                "/auth/v1/logout?scope=local", headers={"Authorization": f"Bearer {token}"}
            ).status_code
            == 204
        )
        assert api.get("/identity/me", headers=headers).status_code == 401


def test_pool_reuse_and_no_runtime_bootstrap(
    accounts: tuple[list[dict[str, str]], httpx.Client],
) -> None:
    users, _ = accounts
    engine = create_database(settings())
    verifier = TokenVerifier(settings())
    try:
        with TestClient(create_app(settings())) as api:
            for user in users:
                assert (
                    api.get(
                        "/identity/me", headers={"Authorization": f"Bearer {user['token']}"}
                    ).status_code
                    == 200
                )
        for user in users:
            with actor_transaction(engine, verifier.verify(user["token"])) as connection:
                assert connection.execute(
                    text("select user_id from public.profiles")
                ).scalars().all() == [UUID(user["id"])]
        with engine.begin() as connection:
            assert connection.execute(text("select user_id from public.profiles")).all() == []
            assert (
                connection.execute(text("select * from ops_private.current_identity()")).all() == []
            )
            assert (
                connection.execute(
                    text(
                        "select has_function_privilege(current_user, "
                        "'ops_private.bootstrap_world_owner(uuid,text,text,text)', 'EXECUTE')"
                    )
                ).scalar()
                is False
            )
    finally:
        engine.dispose()
