from contextlib import contextmanager
from hashlib import sha256
from uuid import uuid4

import httpx
import pytest
from pydantic import SecretStr
from test_moderation_worker import work

from cce.modules.contributions import moderation_avatar
from cce.modules.contributions.moderation_avatar import ModerationAvatarReader
from cce.modules.contributions.moderation_worker import AvatarUnavailable, ScanWork

AUTH_USER_ID = uuid4()


class Database:
    def __init__(self, path, role="cce_worker_cpu"):
        self.path = path
        self.role = role
        self.active = False
        self.value = None

    @contextmanager
    def begin(self):
        assert not self.active
        self.active = True
        try:
            yield self
        finally:
            self.active = False

    def execute(self, query, params=None):
        statement = str(query)
        self.value = self.role if "current_user" in statement else self.path
        return self

    def scalar_one(self):
        return self.value


def build_reader(db, monkeypatch, handler):
    client = httpx.Client
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        moderation_avatar.httpx,
        "Client",
        lambda **kwargs: client(transport=transport, **kwargs),
    )
    return ModerationAvatarReader(
        db,
        storage_url="http://127.0.0.1:55321",
        publishable_key=SecretStr("sb_publishable_test"),
        auth_user_id=AUTH_USER_ID,
        auth_email="worker@example.com",
        auth_password=SecretStr("worker-secret"),
    )


def test_avatar_reader_checks_path_and_digest_outside_db_transaction(monkeypatch):
    content = b"verified avatar bytes"
    payload = work(True) | {"avatar_sha256": sha256(content).hexdigest()}
    scan = ScanWork.model_validate(payload)
    path = f"{uuid4()}/{scan.avatar_id}.png"
    db = Database(path)
    calls = []

    def handler(request):
        assert not db.active
        calls.append(request.url.path)
        assert request.headers["apikey"] == "sb_publishable_test"
        if request.url.path == "/auth/v1/token":
            assert request.url.params["grant_type"] == "password"
            assert b"worker-secret" in request.content
            return httpx.Response(
                200, json={"access_token": "worker-jwt", "user": {"id": str(AUTH_USER_ID)}}
            )
        assert request.headers["authorization"] == "Bearer worker-jwt"
        return httpx.Response(200, content=content)

    reader = build_reader(db, monkeypatch, handler)
    assert reader.read(scan) == content
    assert calls == ["/auth/v1/token", f"/storage/v1/object/authenticated/cce-avatars/{path}"]


@pytest.mark.parametrize("mode", ["valid", "wrong_user", "invalid_password", "malformed"])
def test_worker_identity_is_verified_before_claiming_work(monkeypatch, mode):
    db = Database(None)
    calls = []

    def handler(request):
        calls.append(request.url.path)
        if mode == "invalid_password":
            return httpx.Response(401)
        if mode == "malformed":
            return httpx.Response(200, json={"access_token": "jwt"})
        user_id = str(uuid4()) if mode == "wrong_user" else str(AUTH_USER_ID)
        return httpx.Response(200, json={"access_token": "jwt", "user": {"id": user_id}})

    reader = build_reader(db, monkeypatch, handler)
    if mode == "valid":
        reader.verify_identity()
    else:
        with pytest.raises(AvatarUnavailable):
            reader.verify_identity()
    assert calls == ["/auth/v1/token"]


@pytest.mark.parametrize("path", [None, "../other.png", "not-a-uuid/avatar.png"])
def test_avatar_reader_rejects_unbound_path_before_network(monkeypatch, path):
    scan = ScanWork.model_validate(work(True))
    db = Database(path)

    def handler(request):
        raise AssertionError("Storage must not be contacted")

    with pytest.raises(AvatarUnavailable):
        build_reader(db, monkeypatch, handler).read(scan)


def test_avatar_reader_requires_worker_database_identity(monkeypatch):
    scan = ScanWork.model_validate(work(True))
    db = Database(f"{uuid4()}/{scan.avatar_id}.png", role="cce_api")

    def handler(request):
        raise AssertionError("Storage must not be contacted")

    with pytest.raises(AvatarUnavailable):
        build_reader(db, monkeypatch, handler).read(scan)


@pytest.mark.parametrize("mode", ["auth", "storage", "digest", "oversize"])
def test_avatar_reader_fails_closed_on_auth_storage_and_content(monkeypatch, mode):
    scan = ScanWork.model_validate(work(True))
    db = Database(f"{uuid4()}/{scan.avatar_id}.png")

    def handler(request):
        if request.url.path == "/auth/v1/token":
            return httpx.Response(
                401 if mode == "auth" else 200,
                json={"access_token": "jwt", "user": {"id": str(AUTH_USER_ID)}},
            )
        if mode == "storage":
            return httpx.Response(403)
        return httpx.Response(200, content=b"x" * (524289 if mode == "oversize" else 10))

    with pytest.raises(AvatarUnavailable):
        build_reader(db, monkeypatch, handler).read(scan)


def test_avatar_reader_skips_storage_when_no_avatar(monkeypatch):
    db = Database(None)

    def handler(request):
        raise AssertionError("Storage must not be contacted")

    assert build_reader(db, monkeypatch, handler).read(ScanWork.model_validate(work())) is None
