from uuid import UUID

import jwt
from jwt import PyJWKClient

from cce.core.config import Settings
from cce.modules.identity.domain import Actor, AuthenticationFailed, AuthenticationUnavailable


class TokenVerifier:
    def __init__(self, settings: Settings) -> None:
        self.issuer = settings.auth_issuer
        self.keys = PyJWKClient(settings.auth_jwks_url, lifespan=60, timeout=3)

    def verify(self, token: str) -> Actor:
        try:
            if len(token) > 16384:
                raise AuthenticationFailed
            header = jwt.get_unverified_header(token)
            if header.get("alg") not in {"ES256", "RS256"}:
                raise AuthenticationFailed
            key = self.keys.get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                key.key,
                algorithms=["ES256", "RS256"],
                issuer=self.issuer,
                audience="authenticated",
                # Bounded clock skew between Auth and API hosts; expiry remains enforced.
                leeway=5,
                options={
                    "require": ["exp", "iat", "iss", "aud", "sub", "session_id", "role"],
                },
            )
            if claims["role"] != "authenticated" or claims.get("is_anonymous", False):
                raise AuthenticationFailed
            return Actor(UUID(claims["sub"]), UUID(claims["session_id"]))
        except jwt.PyJWKClientConnectionError:
            raise AuthenticationUnavailable from None
        except (jwt.PyJWTError, ValueError, TypeError, KeyError, AttributeError):
            raise AuthenticationFailed from None
