import os
from collections.abc import Iterator
from uuid import UUID, uuid4

import httpx
import psycopg
import pytest


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
                    db.execute("set constraints submission_revision_owner_fk deferred")
                    db.execute(
                        "delete from ops_private.contribution_events where actor_user_id=%s",
                        (target,),
                    )
                    db.execute(
                        "delete from public.submission_revisions where submission_id in "
                        "(select id from public.character_submissions where user_id=%s)",
                        (target,),
                    )
                    db.execute(
                        "delete from public.character_submissions where user_id=%s", (target,)
                    )
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
