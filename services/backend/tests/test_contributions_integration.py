from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import httpx
import psycopg
import pytest
from fastapi.testclient import TestClient
from local_environment import ADMIN_DSN, API_DSN, AUTH_URL
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from cce.api_entrypoint import create_app
from cce.core.config import Settings
from cce.infrastructure.database import create_database
from cce.modules.identity.authentication import TokenVerifier
from cce.modules.identity.repository import actor_transaction

pytestmark = pytest.mark.integration


def settings() -> Settings:
    return Settings(
        environment="test",
        database_url=SecretStr(API_DSN),
        auth_issuer=f"{AUTH_URL}/auth/v1",
        auth_jwks_url=f"{AUTH_URL}/auth/v1/.well-known/jwks.json",
    )


def proposal() -> dict[str, object]:
    return {
        "schema_version": 1,
        "name": "Deniz",
        "age": 28,
        "introduction": "Meraklı bir arşivci.",
        "backstory": "Küçük bir sahil kentinde büyüdü.",
        "adult_appearance_confirmed": True,
        "original_character_confirmed": True,
    }


def test_isolation_revision_and_withdrawal(
    accounts: tuple[list[dict[str, str]], httpx.Client],
) -> None:
    users, auth = accounts
    headers = {"Authorization": f"Bearer {users[0]['token']}"}
    other = {"Authorization": f"Bearer {users[1]['token']}"}
    with TestClient(create_app(settings())) as api:
        assert api.get("/contributions").status_code == 401
        created = api.post(
            "/contributions",
            headers=headers,
            json={"creation_key": str(uuid4()), "definition": proposal()},
        )
        assert created.status_code == 200
        item = created.json()
        path = f"/contributions/{item['id']}"
        assert api.get(path, headers=other).status_code == 404
        assert api.get("/contributions", headers=other).json() == []
        changed = {**proposal(), "name": "Ada"}
        assert (
            api.put(
                path, headers=headers, json={"expected_version": 1, "definition": changed}
            ).status_code
            == 200
        )
        assert (
            api.put(
                path, headers=headers, json={"expected_version": 1, "definition": proposal()}
            ).status_code
            == 409
        )
        submitted = api.post(path + "/submit", headers=headers, json={"expected_version": 2})
        assert submitted.status_code == 200
        assert submitted.json()["revision_id"]
        assert (
            api.post(path + "/submit", headers=headers, json={"expected_version": 2}).status_code
            == 409
        )
        assert (
            api.put(
                path, headers=headers, json={"expected_version": 3, "definition": proposal()}
            ).status_code
            == 409
        )
        assert (
            api.post(path + "/withdraw", headers=headers, json={"expected_version": 3}).status_code
            == 200
        )
        assert (
            api.put(
                path, headers=headers, json={"expected_version": 4, "definition": proposal()}
            ).status_code
            == 409
        )
        assert api.get(path, headers=headers).json()["status"] == "WITHDRAWN"
        direct = auth.post(
            "/rest/v1/character_submissions", headers=headers, json={"user_id": users[0]["id"]}
        )
        assert direct.status_code in {401, 403}
        with psycopg.connect(ADMIN_DSN) as db:
            assert db.execute(
                "select count(*) from public.submission_revisions where submission_id=%s",
                (UUID(item["id"]),),
            ).fetchone() == (1,)
            assert db.execute(
                "select definition->>'name' from public.submission_revisions "
                "where submission_id=%s",
                (UUID(item["id"]),),
            ).fetchone() == ("Ada",)
            assert db.execute(
                "select count(*) from ops_private.contribution_events where submission_id=%s",
                (UUID(item["id"]),),
            ).fetchone() == (4,)
        engine = create_database(settings())
        try:
            with (
                pytest.raises(DBAPIError),
                actor_transaction(
                    engine, TokenVerifier(settings()).verify(users[0]["token"])
                ) as connection,
            ):
                connection.execute(
                    text(
                        "update public.submission_revisions set definition='{}' "
                        "where submission_id=:id"
                    ),
                    {"id": UUID(item["id"])},
                )
        finally:
            engine.dispose()


def test_concurrent_retry_and_optimistic_save(
    accounts: tuple[list[dict[str, str]], httpx.Client],
) -> None:
    users, _ = accounts
    headers = {"Authorization": f"Bearer {users[0]['token']}"}
    key = str(uuid4())
    with TestClient(create_app(settings())) as api:

        def create(_: int) -> httpx.Response:
            return api.post(
                "/contributions",
                headers=headers,
                json={"creation_key": key, "definition": proposal()},
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(create, range(2)))
        assert [r.status_code for r in responses] == [200, 200]
        assert responses[0].json()["id"] == responses[1].json()["id"]
        item = responses[0].json()

        def save(index: int) -> int:
            return api.put(
                f"/contributions/{item['id']}",
                headers=headers,
                json={
                    "expected_version": 1,
                    "definition": {**proposal(), "name": f"Name {index}"},
                },
            ).status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            assert sorted(pool.map(save, range(2))) == [200, 409]
        assert len(api.get("/contributions", headers=headers).json()) == 1


def test_schema_submit_validation_and_limit(
    accounts: tuple[list[dict[str, str]], httpx.Client],
) -> None:
    users, _ = accounts
    headers = {"Authorization": f"Bearer {users[0]['token']}"}
    with TestClient(create_app(settings())) as api:
        for invalid in ({**proposal(), "system_prompt": "injected"}, {**proposal(), "age": 17}):
            assert (
                api.post(
                    "/contributions",
                    headers=headers,
                    json={"creation_key": str(uuid4()), "definition": invalid},
                ).status_code
                == 422
            )
        item = api.post(
            "/contributions", headers=headers, json={"creation_key": str(uuid4()), "definition": {}}
        ).json()
        assert (
            api.post(
                f"/contributions/{item['id']}/submit", headers=headers, json={"expected_version": 1}
            ).status_code
            == 422
        )
        for _ in range(9):
            assert (
                api.post(
                    "/contributions",
                    headers=headers,
                    json={"creation_key": str(uuid4()), "definition": proposal()},
                ).status_code
                == 200
            )
        assert (
            api.post(
                "/contributions",
                headers=headers,
                json={"creation_key": str(uuid4()), "definition": proposal()},
            ).status_code
            == 429
        )
