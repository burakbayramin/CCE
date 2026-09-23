from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient
from pydantic import SecretStr

from cce.api_entrypoint import create_app
from cce.core.config import Settings
from cce.modules.identity.authentication import TokenVerifier
from cce.modules.identity.domain import AuthenticationFailed, AuthenticationUnavailable


def config() -> Settings:
    return Settings(
        environment="test",
        database_url=SecretStr("postgresql+psycopg://cce_api:test@127.0.0.1:1/postgres"),
    )


@pytest.mark.parametrize(
    "change",
    [
        {"iss": "https://attacker.invalid"},
        {"aud": "service_role"},
        {"exp": 1},
        {"role": "service_role"},
        {"sub": "bad-uuid"},
        {"session_id": None},
        {"is_anonymous": True},
        {"iat": 9999999999},
    ],
)
def test_invalid_claims_rejected(
    monkeypatch: pytest.MonkeyPatch, change: dict[str, object]
) -> None:
    key = ec.generate_private_key(ec.SECP256R1())
    verifier = TokenVerifier(config())
    monkeypatch.setattr(
        verifier.keys, "get_signing_key_from_jwt", lambda _: SimpleNamespace(key=key.public_key())
    )
    payload = {
        "iss": config().auth_issuer,
        "aud": "authenticated",
        "role": "authenticated",
        "sub": str(uuid4()),
        "session_id": str(uuid4()),
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + timedelta(minutes=5),
    }
    payload.update(change)
    with pytest.raises(AuthenticationFailed):
        verifier.verify(jwt.encode(payload, key, algorithm="ES256"))


def test_signature_required_and_metadata_does_not_define_actor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    key = ec.generate_private_key(ec.SECP256R1())
    verifier = TokenVerifier(config())
    monkeypatch.setattr(
        verifier.keys, "get_signing_key_from_jwt", lambda _: SimpleNamespace(key=key.public_key())
    )
    user_id, session_id = uuid4(), uuid4()
    payload = {
        "iss": config().auth_issuer,
        "aud": "authenticated",
        "role": "authenticated",
        "sub": str(user_id),
        "session_id": str(session_id),
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + timedelta(minutes=5),
        "user_metadata": {"role": "world_owner"},
    }
    actor = verifier.verify(jwt.encode(payload, key, algorithm="ES256"))
    assert actor.user_id == user_id and actor.session_id == session_id
    other = ec.generate_private_key(ec.SECP256R1())
    with pytest.raises(AuthenticationFailed):
        verifier.verify(jwt.encode(payload, other, algorithm="ES256"))
    with pytest.raises(AuthenticationFailed):
        verifier.verify(jwt.encode(payload, "x" * 32, algorithm="HS256"))
    del payload["session_id"]
    with pytest.raises(AuthenticationFailed):
        verifier.verify(jwt.encode(payload, key, algorithm="ES256"))


def test_missing_and_malformed_tokens_never_reach_database() -> None:
    with TestClient(create_app(config())) as client:
        for path in ("/identity/me", "/identity/owner"):
            assert client.get(path).status_code == 401
            response = client.get(path, headers={"Authorization": "Bearer private-invalid-token"})
            assert response.status_code == 401
            assert "private-invalid-token" not in response.text


def test_jwks_outage_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    verifier = TokenVerifier(config())
    key = ec.generate_private_key(ec.SECP256R1())

    def offline(_: str) -> None:
        raise jwt.PyJWKClientConnectionError("private-network-detail")

    monkeypatch.setattr(verifier.keys, "get_signing_key_from_jwt", offline)
    with pytest.raises(AuthenticationUnavailable):
        verifier.verify(jwt.encode({}, key, algorithm="ES256"))
