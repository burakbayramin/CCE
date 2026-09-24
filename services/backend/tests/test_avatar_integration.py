import os
from uuid import UUID, uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from local_environment import ADMIN_DSN, AUTH_URL
from pydantic import SecretStr
from test_avatars import png
from test_contributions_integration import proposal
from test_identity_integration import settings

from cce.api_entrypoint import create_app
from cce.modules.contributions.avatars import AvatarStorage

pytestmark = pytest.mark.integration


def test_private_immutable_avatar_and_retry(accounts) -> None:
    users, auth = accounts
    config = settings()
    config.storage_url = AUTH_URL
    config.supabase_publishable_key = SecretStr(os.environ["CCE_TEST_SUPABASE_PUBLISHABLE_KEY"])
    own = {"Authorization": f"Bearer {users[0]['token']}"}
    other = {"Authorization": f"Bearer {users[1]['token']}"}
    with TestClient(create_app(config)) as api:
        item = api.post(
            "/contributions",
            headers=own,
            json={"creation_key": str(uuid4()), "definition": proposal()},
        ).json()
        path = f"/contributions/{item['id']}/avatar"
        params = {"expected_version": item["version"], "upload_key": str(uuid4())}
        uploaded = api.post(
            path, params=params, headers={**own, "Content-Type": "image/png"}, content=png()
        )
        assert uploaded.status_code == 200, uploaded.text
        asset = uploaded.json()["avatar_id"]
        assert asset
        again = api.post(
            path, params=params, headers={**own, "Content-Type": "image/png"}, content=png()
        )
        assert again.status_code == 200 and again.json()["version"] == uploaded.json()["version"]
        assert api.get(f"/avatars/{asset}", headers=other).status_code == 404
        assert api.get(f"/avatars/{asset}").status_code == 401
        original = api.get(f"/avatars/{asset}", headers=own)
        assert original.status_code == 200
        assert original.headers["content-type"] == "image/png"
        with psycopg.connect(ADMIN_DSN) as db:
            object_name = db.execute(
                "select object_name from public.avatar_assets where id=%s", (UUID(asset),)
            ).fetchone()[0]
        storage = f"/storage/v1/object/cce-avatars/{object_name}"
        assert auth.post(
            storage, headers={**own, "Content-Type": "image/png", "x-upsert": "true"}, content=png()
        ).status_code not in {200, 201}
        assert auth.get(storage, headers=other).status_code != 200
        assert auth.get(f"/storage/v1/object/public/cce-avatars/{object_name}").status_code != 200
        submitted = api.post(
            f"/contributions/{item['id']}/submit",
            headers=own,
            json={"expected_version": uploaded.json()["version"]},
        ).json()
        history = api.get(f"/contributions/{item['id']}/history", headers=own).json()
        assert history["revisions"][0]["avatar_id"] == asset
        params = {"expected_version": submitted["version"], "upload_key": str(uuid4())}
        assert (
            api.post(
                path, params=params, headers={**own, "Content-Type": "image/png"}, content=png()
            ).status_code
            == 409
        )
        assert api.get(f"/avatars/{asset}", headers=own).content == original.content
        assert auth.post("/auth/v1/logout?scope=local", headers=own).status_code == 204
        assert api.get(f"/avatars/{asset}", headers=own).status_code == 401
        assert auth.get(storage, headers=own).status_code != 200


def avatar_settings():
    config = settings()
    config.storage_url = AUTH_URL
    config.supabase_publishable_key = SecretStr(os.environ["CCE_TEST_SUPABASE_PUBLISHABLE_KEY"])
    return config


def test_tampered_pending_object_is_never_attached(accounts, monkeypatch) -> None:
    users, auth = accounts
    own = {"Authorization": f"Bearer {users[0]['token']}"}
    original_store = AvatarStorage.store

    def tamper(storage, asset, image):
        # An authenticated user writes unnormalized bytes into their reserved path.
        response = auth.post(
            f"/storage/v1/object/cce-avatars/{asset.object_name}",
            headers={**own, "Content-Type": "image/png"},
            content=png(),
        )
        assert response.status_code in {200, 201}
        original_store(storage, asset, image)

    monkeypatch.setattr(AvatarStorage, "store", tamper)
    with TestClient(create_app(avatar_settings())) as api:
        item = api.post(
            "/contributions",
            headers=own,
            json={"creation_key": str(uuid4()), "definition": proposal()},
        ).json()
        response = api.post(
            f"/contributions/{item['id']}/avatar",
            params={"expected_version": 1, "upload_key": str(uuid4())},
            headers={**own, "Content-Type": "image/png"},
            content=png(),
        )
        assert response.status_code == 409
        current = api.get(f"/contributions/{item['id']}", headers=own).json()
        assert current["avatar_id"] is None and current["version"] == 1
        with psycopg.connect(ADMIN_DSN) as db:
            asset, state = db.execute(
                "select id,status from public.avatar_assets where submission_id=%s",
                (UUID(item["id"]),),
            ).fetchone()
        assert state == "PENDING"
        assert api.get(f"/avatars/{asset}", headers=own).status_code == 404


@pytest.mark.parametrize("count,age", [(20, "0 days"), (100, "2 days")])
def test_avatar_quota_and_unreserved_storage_path(accounts, count, age) -> None:
    users, auth = accounts
    own = {"Authorization": f"Bearer {users[0]['token']}"}
    with TestClient(create_app(avatar_settings())) as api:
        item = api.post(
            "/contributions",
            headers=own,
            json={"creation_key": str(uuid4()), "definition": proposal()},
        ).json()
        with psycopg.connect(ADMIN_DSN) as db:
            db.execute(
                "insert into public.avatar_assets "
                "(submission_id,user_id,upload_key,sha256,byte_size,width,height,created_at) "
                "select %s,%s,gen_random_uuid(),repeat('a',64),1,64,64,now()-%s::interval "
                "from generate_series(1,%s)",
                (UUID(item["id"]), UUID(users[0]["id"]), age, count),
            )
        assert (
            api.post(
                f"/contributions/{item['id']}/avatar",
                params={"expected_version": 1, "upload_key": str(uuid4())},
                headers={**own, "Content-Type": "image/png"},
                content=png(),
            ).status_code
            == 429
        )
        assert auth.post(
            f"/storage/v1/object/cce-avatars/{users[0]['id']}/{uuid4()}.png",
            headers={**own, "Content-Type": "image/png"},
            content=png(),
        ).status_code not in {200, 201}
        assert auth.post("/rest/v1/avatar_assets", headers=own, json={}).status_code in {401, 403}


def test_owner_can_read_contributor_avatar(review_accounts) -> None:
    (owner, contributor), _ = review_accounts
    own = {"Authorization": f"Bearer {contributor['token']}"}
    with TestClient(create_app(avatar_settings())) as api:
        item = api.post(
            "/contributions",
            headers=own,
            json={"creation_key": str(uuid4()), "definition": proposal()},
        ).json()
        uploaded = api.post(
            f"/contributions/{item['id']}/avatar",
            params={"expected_version": 1, "upload_key": str(uuid4())},
            headers={**own, "Content-Type": "image/png"},
            content=png(),
        )
        assert uploaded.status_code == 200
        response = api.get(
            f"/avatars/{uploaded.json()['avatar_id']}",
            headers={"Authorization": f"Bearer {owner['token']}"},
        )
        assert response.status_code == 200
        assert "no-store" in response.headers["cache-control"]
        assert response.headers["x-content-type-options"] == "nosniff"


def test_submit_during_upload_never_changes_committed_revision(accounts, monkeypatch) -> None:
    users, _ = accounts
    own = {"Authorization": f"Bearer {users[0]['token']}"}
    original_store = AvatarStorage.store
    with TestClient(create_app(avatar_settings())) as api:
        item = api.post(
            "/contributions",
            headers=own,
            json={"creation_key": str(uuid4()), "definition": proposal()},
        ).json()

        def submit_while_uploading(storage, asset, image):
            original_store(storage, asset, image)
            response = api.post(
                f"/contributions/{item['id']}/submit",
                headers=own,
                json={"expected_version": 1},
            )
            assert response.status_code == 200

        monkeypatch.setattr(AvatarStorage, "store", submit_while_uploading)
        result = api.post(
            f"/contributions/{item['id']}/avatar",
            params={"expected_version": 1, "upload_key": str(uuid4())},
            headers={**own, "Content-Type": "image/png"},
            content=png(),
        )
        assert result.status_code == 409
        current = api.get(f"/contributions/{item['id']}", headers=own).json()
        assert current["status"] == "SUBMITTED" and current["avatar_id"] is None
        history = api.get(f"/contributions/{item['id']}/history", headers=own).json()
        assert history["revisions"][0]["avatar_id"] is None
        with psycopg.connect(ADMIN_DSN) as db:
            assert db.execute(
                "select status from public.avatar_assets where submission_id=%s",
                (UUID(item["id"]),),
            ).fetchone() == ("PENDING",)
