from collections.abc import Iterator
from contextlib import contextmanager
from types import SimpleNamespace
from typing import cast
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Connection, Engine

from cce.core.config import Settings
from cce.modules.contributions import avatar_router as avatar_routes
from cce.modules.contributions import review_router as review_routes
from cce.modules.contributions import router as contribution_routes
from cce.modules.contributions.repository import ContributionError
from cce.modules.identity.authentication import TokenVerifier
from cce.modules.identity.domain import Actor
from cce.modules.identity.repository import identity_context


def actor() -> Actor:
    return Actor(uuid4(), uuid4())


def verifier_for(value: Actor) -> TokenVerifier:
    return cast(TokenVerifier, SimpleNamespace(verify=lambda _: value))


def test_identity_context_uses_callers_connection() -> None:
    connection = MagicMock(spec=Connection)
    connection.execute.return_value.mappings.return_value.one_or_none.return_value = {
        "actor_role": "contributor",
        "person_id": None,
    }
    value = actor()

    assert identity_context(connection, value) == {
        "user_id": value.user_id,
        "role": "contributor",
        "person_id": None,
    }
    assert connection.execute.call_count == 2


def test_contribution_request_reuses_identity_transaction(monkeypatch: pytest.MonkeyPatch) -> None:
    value = actor()
    connection = MagicMock(spec=Connection)
    connection.execute.return_value.mappings.return_value = []
    opened: list[object] = []
    engine = cast(Engine, object())

    @contextmanager
    def transaction(target: Engine, candidate: Actor) -> Iterator[Connection]:
        assert candidate == value
        opened.append(target)
        yield connection

    def validate(target: Connection, candidate: Actor) -> dict[str, object]:
        assert target is connection and candidate == value
        return {"user_id": value.user_id, "role": "contributor", "person_id": None}

    monkeypatch.setattr(contribution_routes, "actor_transaction", transaction)
    monkeypatch.setattr(contribution_routes, "identity_context", validate)
    app = FastAPI()
    app.include_router(contribution_routes.contributions_router(engine, verifier_for(value)))

    with TestClient(app) as client:
        assert client.get("/contributions", headers={"Authorization": "Bearer test"}).json() == []
    assert opened == [engine]


def test_review_request_checks_owner_in_command_transaction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    value = actor()
    connection = MagicMock(spec=Connection)
    connection.execute.side_effect = [
        SimpleNamespace(scalar_one_or_none=lambda: "world_owner"),
        SimpleNamespace(mappings=lambda: []),
    ]
    opened: list[object] = []
    engine = cast(Engine, object())

    @contextmanager
    def transaction(target: Engine, candidate: Actor) -> Iterator[Connection]:
        assert candidate == value
        opened.append(target)
        yield connection

    monkeypatch.setattr(review_routes, "actor_transaction", transaction)
    app = FastAPI()
    app.include_router(
        review_routes.review_router(engine, verifier_for(value), None, test_mode=True)
    )

    with TestClient(app) as client:
        assert client.get("/reviews", headers={"Authorization": "Bearer test"}).json() == []
    assert opened == [engine]


@pytest.mark.parametrize("role,expected_checkouts", [("contributor", 1), ("world_owner", 2)])
@pytest.mark.parametrize("status,expected_http", [("READY", 200), ("PENDING", 404)])
def test_avatar_read_only_switches_connection_for_owner(
    monkeypatch: pytest.MonkeyPatch,
    role: str,
    expected_checkouts: int,
    status: str,
    expected_http: int,
) -> None:
    value = actor()
    api_engine = cast(Engine, object())
    owner_engine = cast(Engine, object())
    opened: list[object] = []
    connection = MagicMock(spec=Connection)

    @contextmanager
    def transaction(target: Engine, candidate: Actor) -> Iterator[Connection]:
        assert candidate == value
        opened.append(target)
        yield connection

    def validate(target: Connection, candidate: Actor) -> dict[str, object]:
        assert target is connection and candidate == value
        return {"user_id": value.user_id, "role": role, "person_id": None}

    monkeypatch.setattr(avatar_routes, "actor_transaction", transaction)
    monkeypatch.setattr(avatar_routes, "identity_context", validate)
    monkeypatch.setattr(avatar_routes, "read_asset", lambda *_: SimpleNamespace(status=status))
    monkeypatch.setattr(
        avatar_routes, "AvatarStorage", lambda *_: SimpleNamespace(read=lambda *_: b"image")
    )
    app = FastAPI()
    app.include_router(
        avatar_routes.avatar_router(
            cast(Settings, object()), api_engine, owner_engine, verifier_for(value)
        )
    )

    with TestClient(app) as client:
        response = client.get(f"/avatars/{uuid4()}", headers={"Authorization": "Bearer test"})
    assert response.status_code == expected_http
    if status == "READY":
        assert response.content == b"image"
    assert len(opened) == expected_checkouts
    assert opened[0] is api_engine
    if role == "world_owner":
        assert opened[1] is owner_engine


def test_avatar_upload_reuses_each_phase_transaction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    value = actor()
    api_engine = cast(Engine, object())
    connection = MagicMock(spec=Connection)
    opened: list[object] = []
    identity_checks: list[object] = []
    active = False

    @contextmanager
    def transaction(target: Engine, candidate: Actor) -> Iterator[Connection]:
        nonlocal active
        assert target is api_engine and candidate == value and not active
        opened.append(target)
        active = True
        try:
            yield connection
        finally:
            active = False

    def validate(target: Connection, candidate: Actor) -> dict[str, object]:
        assert target is connection and candidate == value and active
        identity_checks.append(target)
        return {"user_id": value.user_id, "role": "contributor", "person_id": None}

    def conflict(*_: object) -> None:
        raise ContributionError(409, "conflict")

    monkeypatch.setattr(avatar_routes, "actor_transaction", transaction)
    monkeypatch.setattr(avatar_routes, "identity_context", validate)
    monkeypatch.setattr(avatar_routes, "verify_image", lambda *_: object())
    monkeypatch.setattr(avatar_routes, "reserve_avatar", lambda *_: object())
    monkeypatch.setattr(avatar_routes, "attach_avatar", conflict)
    monkeypatch.setattr(
        avatar_routes,
        "AvatarStorage",
        lambda *_: SimpleNamespace(store=lambda *_: assert_storage_outside_transaction()),
    )

    def assert_storage_outside_transaction() -> None:
        assert not active

    app = FastAPI()
    app.include_router(
        avatar_routes.avatar_router(cast(Settings, object()), api_engine, None, verifier_for(value))
    )
    with TestClient(app) as client:
        response = client.post(
            f"/contributions/{uuid4()}/avatar?expected_version=1&upload_key={uuid4()}",
            headers={"Authorization": "Bearer test", "Content-Type": "image/png"},
            content=b"image",
        )
    assert response.status_code == 409
    assert opened == [api_engine, api_engine]
    assert identity_checks == [connection, connection]
