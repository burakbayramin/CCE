"""Storage RLS must follow the live moderation attempt, not a broad service key."""

from uuid import UUID, uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from local_environment import ADMIN_DSN
from test_avatar_integration import avatar_settings
from test_avatars import png
from test_contributions_integration import proposal
from test_moderation_jobs_integration import claim, finish, worker
from test_review_integration import headers, start

from cce.api_entrypoint import create_app

pytestmark = pytest.mark.integration


def registered_worker(users, auth):
    email = f"cce-moderation-{uuid4()}@example.com"
    signed_up = auth.post(
        "/auth/v1/signup",
        json={"email": email, "password": f"CCE-worker-{uuid4()}!"},
    )
    assert signed_up.status_code == 200, signed_up.text
    identity = signed_up.json()
    worker_user = {"id": identity["user"]["id"], "token": identity["access_token"]}
    users.append(worker_user)  # The accounts fixture removes only its own users.
    with psycopg.connect(ADMIN_DSN) as db:
        db.execute(
            "update auth.users set raw_app_meta_data="
            "coalesce(raw_app_meta_data,'{}'::jsonb) || "
            '\'{"cce_role":"moderation_worker"}\'::jsonb where id=%s',
            (UUID(worker_user["id"]),),
        )
    return worker_user


def test_auth_worker_reads_only_live_moderation_avatar(review_accounts):
    users, auth = review_accounts
    owner, contributor = users
    worker_user = registered_worker(users, auth)
    other_worker = registered_worker(users, auth)

    with TestClient(create_app(avatar_settings())) as api:
        assert api.get("/identity/me", headers=headers(worker_user)).status_code == 401
        created = api.post(
            "/contributions",
            headers=headers(contributor),
            json={"creation_key": str(uuid4()), "definition": proposal()},
        )
        assert created.status_code == 200, created.text
        item = created.json()
        uploaded = api.post(
            f"/contributions/{item['id']}/avatar",
            params={"expected_version": item["version"], "upload_key": str(uuid4())},
            headers={**headers(contributor), "Content-Type": "image/png"},
            content=png(),
        )
        assert uploaded.status_code == 200, uploaded.text
        item = uploaded.json()
        asset_id = item["avatar_id"]
        with psycopg.connect(ADMIN_DSN) as db:
            path = db.execute(
                "select object_name from public.avatar_assets where id=%s", (UUID(asset_id),)
            ).fetchone()[0]
        storage_path = f"/storage/v1/object/authenticated/cce-avatars/{path}"
        assert auth.get(storage_path, headers=headers(worker_user)).status_code != 200
        submitted = api.post(
            f"/contributions/{item['id']}/submit",
            headers=headers(contributor),
            json={"expected_version": item["version"]},
        )
        assert submitted.status_code == 200, submitted.text
        report = start(api, submitted.json(), owner)
        assert report["moderation_job"]["state"] == "PENDING"
        assert auth.get(storage_path, headers=headers(worker_user)).status_code != 200

        work = claim(UUID(worker_user["id"]))
        with worker() as db:
            resolved = db.execute(
                "select ops_private.moderation_avatar_path(%s,%s,%s)",
                (work["job_id"], work["attempt_id"], UUID(worker_user["id"])),
            ).fetchone()[0]
            wrong_attempt = db.execute(
                "select ops_private.moderation_avatar_path(%s,%s,%s)",
                (work["job_id"], uuid4(), UUID(worker_user["id"])),
            ).fetchone()[0]
        assert resolved == path and wrong_attempt is None
        assert auth.get(storage_path, headers=headers(worker_user)).status_code == 200
        assert auth.get(storage_path, headers=headers(other_worker)).status_code != 200

        # Metadata is read from auth.users, so old JWT snapshots do not preserve access.
        with psycopg.connect(ADMIN_DSN) as db:
            db.execute(
                "update auth.users set raw_app_meta_data=raw_app_meta_data-'cce_role' where id=%s",
                (UUID(worker_user["id"]),),
            )
        assert auth.get(storage_path, headers=headers(worker_user)).status_code != 200
        assert finish(work, "ERROR", "MODEL_UNAVAILABLE") is True
        with psycopg.connect(ADMIN_DSN) as db:
            db.execute(
                "update auth.users set raw_app_meta_data="
                "coalesce(raw_app_meta_data,'{}'::jsonb) || "
                '\'{"cce_role":"moderation_worker"}\'::jsonb where id=%s',
                (UUID(worker_user["id"]),),
            )
        assert auth.get(storage_path, headers=headers(worker_user)).status_code != 200
