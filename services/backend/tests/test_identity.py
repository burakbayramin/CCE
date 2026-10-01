import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient
from pydantic import SecretStr

from cce import api_entrypoint
from cce.api_entrypoint import create_app
from cce.core.config import Settings
from cce.modules.identity.authentication import TokenVerifier
from cce.modules.identity.domain import AuthenticationFailed, AuthenticationUnavailable


def config() -> Settings:
    return Settings(
        environment="test",
        database_url=SecretStr("postgresql+psycopg://cce_api:test@127.0.0.1:1/postgres"),
    )


def signed_token(key: ec.EllipticCurvePrivateKey, kid: str) -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "iss": config().auth_issuer,
            "aud": "authenticated",
            "role": "authenticated",
            "sub": str(uuid4()),
            "session_id": str(uuid4()),
            "iat": now,
            "exp": now + timedelta(minutes=5),
        },
        key,
        algorithm="ES256",
        headers={"kid": kid},
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
        verifier.verify(jwt.encode(payload, key, algorithm="ES256", headers={"kid": "test-key"}))


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
    actor = verifier.verify(
        jwt.encode(payload, key, algorithm="ES256", headers={"kid": "test-key"})
    )
    assert actor.user_id == user_id and actor.session_id == session_id
    other = ec.generate_private_key(ec.SECP256R1())
    with pytest.raises(AuthenticationFailed):
        verifier.verify(jwt.encode(payload, other, algorithm="ES256", headers={"kid": "test-key"}))
    with pytest.raises(AuthenticationFailed):
        verifier.verify(jwt.encode(payload, "x" * 32, algorithm="HS256"))
    del payload["session_id"]
    with pytest.raises(AuthenticationFailed):
        verifier.verify(jwt.encode(payload, key, algorithm="ES256", headers={"kid": "test-key"}))


def test_missing_and_malformed_tokens_never_reach_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(api_entrypoint, "database_ready", lambda _: True)
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
        verifier.verify(jwt.encode({}, key, algorithm="ES256", headers={"kid": "test-key"}))


def test_unknown_kid_refresh_outage_is_invalid_not_service_outage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    verifier = TokenVerifier(config())
    key = ec.generate_private_key(ec.SECP256R1())
    monkeypatch.setattr(
        verifier.keys, "get_signing_key_from_jwt", lambda _: SimpleNamespace(key=key.public_key())
    )
    verifier.verify(signed_token(key, "known"))

    def offline(_: str) -> None:
        raise jwt.PyJWKClientConnectionError("private-network-detail")

    monkeypatch.setattr(verifier.keys, "get_signing_key_from_jwt", offline)
    with pytest.raises(AuthenticationFailed):
        verifier.verify(signed_token(key, "unknown"))
    with pytest.raises(AuthenticationUnavailable):
        verifier.verify(signed_token(key, "known"))
    monkeypatch.setattr(api_entrypoint, "database_ready", lambda _: True)
    monkeypatch.setattr(api_entrypoint, "TokenVerifier", lambda _: verifier)
    with TestClient(create_app(config())) as client:
        unknown = client.get(
            "/identity/me",
            headers={"Authorization": f"Bearer {signed_token(key, 'unknown')}"},
        )
        known = client.get(
            "/identity/me", headers={"Authorization": f"Bearer {signed_token(key, 'known')}"}
        )
    assert unknown.status_code == 401
    assert known.status_code == 503
    assert "private-network-detail" not in unknown.text + known.text


def test_new_rotation_key_can_verify_after_successful_refresh(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    verifier = TokenVerifier(config())
    old_key = ec.generate_private_key(ec.SECP256R1())
    new_key = ec.generate_private_key(ec.SECP256R1())

    def signing_key(token: str) -> SimpleNamespace:
        kid = jwt.get_unverified_header(token)["kid"]
        return SimpleNamespace(key=(old_key if kid == "old" else new_key).public_key())

    monkeypatch.setattr(verifier.keys, "get_signing_key_from_jwt", signing_key)
    assert verifier.verify(signed_token(old_key, "old")).user_id
    assert verifier.verify(signed_token(new_key, "new")).user_id


def test_pyjwt_refresh_classifies_unknown_kid_and_recovers_rotation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    verifier = TokenVerifier(config())
    verifier.keys.cooldown_duration = 0
    old_key = ec.generate_private_key(ec.SECP256R1())
    new_key = ec.generate_private_key(ec.SECP256R1())

    def public_jwk(key: ec.EllipticCurvePrivateKey, kid: str) -> dict[str, object]:
        return {
            **json.loads(jwt.algorithms.ECAlgorithm.to_jwk(key.public_key())),
            "kid": kid,
            "use": "sig",
        }

    keys = [public_jwk(old_key, "old")]
    offline = False

    def fetch() -> dict[str, object]:
        if offline:
            raise jwt.PyJWKClientConnectionError("private-network-detail")
        data = {"keys": keys}
        assert verifier.keys.jwk_set_cache is not None
        verifier.keys.jwk_set_cache.put(data)
        return data

    monkeypatch.setattr(verifier.keys, "fetch_data", fetch)
    assert verifier.verify(signed_token(old_key, "old")).user_id
    offline = True
    with pytest.raises(AuthenticationFailed):
        verifier.verify(signed_token(new_key, "new"))
    offline = False
    keys.append(public_jwk(new_key, "new"))
    assert verifier.verify(signed_token(new_key, "new")).user_id


def test_missing_kid_never_fetches_jwks(monkeypatch: pytest.MonkeyPatch) -> None:
    verifier = TokenVerifier(config())
    key = ec.generate_private_key(ec.SECP256R1())

    def unexpected_fetch(_: str) -> None:
        pytest.fail("Token without kid must be rejected before JWKS fetch")

    monkeypatch.setattr(verifier.keys, "get_signing_key_from_jwt", unexpected_fetch)
    with pytest.raises(AuthenticationFailed):
        verifier.verify(jwt.encode({}, key, algorithm="ES256"))


@pytest.mark.parametrize(
    "iat_offset,exp_offset,allowed", [(2, 300, True), (10, 300, False), (-30, -10, False)]
)
def test_clock_skew_is_bounded(monkeypatch, iat_offset, exp_offset, allowed) -> None:
    key = ec.generate_private_key(ec.SECP256R1())
    verifier = TokenVerifier(config())
    monkeypatch.setattr(
        verifier.keys, "get_signing_key_from_jwt", lambda _: SimpleNamespace(key=key.public_key())
    )
    now = datetime.now(UTC)
    payload = {
        "iss": config().auth_issuer,
        "aud": "authenticated",
        "role": "authenticated",
        "sub": str(uuid4()),
        "session_id": str(uuid4()),
        "iat": now + timedelta(seconds=iat_offset),
        "exp": now + timedelta(seconds=exp_offset),
    }
    token = jwt.encode(payload, key, algorithm="ES256", headers={"kid": "test-key"})
    if allowed:
        assert str(verifier.verify(token).user_id) == payload["sub"]
    else:
        with pytest.raises(AuthenticationFailed):
            verifier.verify(token)


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+psycopg://postgres:test@127.0.0.1:1/postgres",
        "postgresql+psycopg://cce_engine:test@127.0.0.1:2/postgres",
    ],
)
def test_owner_engine_requires_restricted_role_and_same_database(url: str) -> None:
    with pytest.raises(ValueError):
        Settings(
            environment="test",
            database_url=config().database_url,
            engine_database_url=SecretStr(url),
        )
