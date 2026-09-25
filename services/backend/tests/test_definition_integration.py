from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from local_environment import ADMIN_DSN
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from test_identity_integration import settings
from test_review_integration import FixtureModeration, decision, headers, start, submitted

from cce.api_entrypoint import create_app
from cce.infrastructure.database import create_database
from cce.modules.identity.authentication import TokenVerifier
from cce.modules.identity.repository import actor_transaction

pytestmark = pytest.mark.integration


def approve(api, owner, contributor):
    item = start(api, submitted(api, contributor), owner)["submission"]
    response = api.post(
        f"/reviews/{item['id']}/decision",
        headers=headers(owner),
        json=decision(item, review_accepted=True),
    )
    assert response.status_code == 200
    return response.json()


def command(item):
    return {"expected_version": item["version"], "revision_id": item["revision_id"]}


@pytest.mark.parametrize("verdict", ["PASS", "REVIEW"])
def test_definition_approval_binding_retry_and_immutable_storage(review_accounts, verdict) -> None:
    (owner, contributor), auth = review_accounts
    config = settings()
    with TestClient(create_app(config, moderation=FixtureModeration(verdict))) as api:
        item = approve(api, owner, contributor)
        path = f"/reviews/{item['id']}/definition"
        assert api.get(path, headers=headers(owner)).json() is None
        assert api.post(path, headers=headers(contributor), json=command(item)).status_code == 403
        assert api.get(path).status_code == 401
        assert (
            api.post(
                path, headers=headers(owner), json={**command(item), "revision_id": str(uuid4())}
            ).status_code
            == 409
        )
        assert (
            api.post(
                path, headers=headers(owner), json={**command(item), "system_prompt": "injected"}
            ).status_code
            == 422
        )
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(
                pool.map(
                    lambda _: api.post(path, headers=headers(owner), json=command(item)), range(2)
                )
            )
        assert [r.status_code for r in responses] == [200, 200]
        first = responses[0].json()
        assert first == responses[1].json()
        assert first == api.get(path, headers=headers(owner)).json()
        assert first["artifact"]["source"]["revision_id"] == item["revision_id"]
        assert first["artifact"]["source"]["is_fixture"] is True
        assert (
            api.get(f"/reviews/{item['id']}", headers=headers(owner)).json()["submission"]["status"]
            == "APPROVED"
        )
        assert (
            auth.get("/rest/v1/character_definitions", headers=headers(contributor)).status_code
            != 200
        )
        with psycopg.connect(ADMIN_DSN) as db:
            record = db.execute(
                "select created_by,count(*) over() from world_private.character_definitions "
                "where submission_id=%s",
                (UUID(item["id"]),),
            ).fetchone()
            assert record == (UUID(owner["id"]), 1)
        engine = create_database(config, owner_commands=True)
        actor = TokenVerifier(config).verify(owner["token"])
        try:
            with (
                pytest.raises(DBAPIError) as forged,
                actor_transaction(engine, actor) as connection,
            ):
                connection.execute(
                    text(
                        "insert into world_private.character_definitions "
                        "(submission_id,revision_id,approval_id,definition_version,compiler_version,"
                        "artifact,artifact_sha256,created_by) select submission_id,revision_id,"
                        "approval_id,definition_version,compiler_version,"
                        "jsonb_set(artifact,'{proposal,name}','\"Forged\"'),"
                        "artifact_sha256,created_by "
                        "from world_private.character_definitions where id=:id"
                    ),
                    {"id": UUID(first["id"])},
                )
            assert forged.value.orig.sqlstate == "23514"
            for sql in (
                "update world_private.character_definitions set artifact='{}'",
                "delete from world_private.character_definitions",
            ):
                with pytest.raises(DBAPIError), actor_transaction(engine, actor) as connection:
                    connection.execute(text(sql))
            with engine.begin() as connection:
                assert (
                    connection.execute(
                        text("select * from world_private.character_definitions")
                    ).all()
                    == []
                )
            with actor_transaction(
                engine, TokenVerifier(config).verify(contributor["token"])
            ) as connection:
                assert (
                    connection.execute(
                        text("select * from world_private.character_definitions")
                    ).all()
                    == []
                )
        finally:
            engine.dispose()
        # A stored fixture cannot be retried as a production-approved definition.
        config.environment = "local"
        with TestClient(create_app(config)) as non_test:
            assert (
                non_test.post(path, headers=headers(owner), json=command(item)).status_code == 409
            )
        # Even privileged out-of-band corruption must fail closed on read.
        with psycopg.connect(ADMIN_DSN) as db:
            db.execute(
                "update world_private.character_definitions set artifact_sha256=%s where id=%s",
                ("0" * 64, UUID(first["id"])),
            )
        assert api.get(path, headers=headers(owner)).status_code == 503
        assert auth.post("/auth/v1/logout?scope=local", headers=headers(owner)).status_code == 204
        assert api.get(path, headers=headers(owner)).status_code == 401


@pytest.mark.parametrize("verdict", ["PASS", "BLOCK", "ERROR", "REVIEW"])
def test_definition_requires_explicit_approval(review_accounts, verdict) -> None:
    (owner, contributor), _ = review_accounts
    with TestClient(create_app(settings(), moderation=FixtureModeration(verdict))) as api:
        item = start(api, submitted(api, contributor), owner)["submission"]
        assert (
            api.post(
                f"/reviews/{item['id']}/definition", headers=headers(owner), json=command(item)
            ).status_code
            == 409
        )
