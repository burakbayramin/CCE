"""Source-bound private avatar reader for a dedicated Supabase Auth worker."""

from hashlib import sha256
from uuid import UUID

import httpx
from pydantic import SecretStr
from sqlalchemy import Engine, text

from cce.modules.contributions.images import MAX_AVATAR_BYTES
from cce.modules.contributions.moderation_worker import AvatarUnavailable, ScanWork


class ModerationAvatarReader:
    def __init__(
        self,
        engine: Engine,
        *,
        storage_url: str,
        publishable_key: SecretStr,
        auth_user_id: UUID,
        auth_email: str,
        auth_password: SecretStr,
    ) -> None:
        self.engine = engine
        self.origin = storage_url.rstrip("/")
        self.publishable_key = publishable_key
        self.auth_user_id = auth_user_id
        self.auth_email = auth_email
        self.auth_password = auth_password

    def verify_identity(self) -> None:
        """Fail startup before claiming work if the configured Auth user cannot sign in."""
        try:
            with httpx.Client(timeout=8, follow_redirects=False, base_url=self.origin) as client:
                self._authenticate(client)
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            raise AvatarUnavailable from None

    def _authenticate(self, client: httpx.Client) -> str:
        signed_in = client.post(
            "/auth/v1/token",
            params={"grant_type": "password"},
            headers={"apikey": self.publishable_key.get_secret_value()},
            json={
                "email": self.auth_email,
                "password": self.auth_password.get_secret_value(),
            },
        )
        if signed_in.status_code != 200:
            raise AvatarUnavailable
        auth_body = signed_in.json()
        token = auth_body.get("access_token") if isinstance(auth_body, dict) else None
        user = auth_body.get("user") if isinstance(auth_body, dict) else None
        if (
            not isinstance(token, str)
            or not token
            or not isinstance(user, dict)
            or user.get("id") != str(self.auth_user_id)
        ):
            raise AvatarUnavailable
        return token

    def read(self, work: ScanWork) -> bytes | None:
        if work.avatar_id is None:
            return None
        with self.engine.begin() as connection:
            if connection.execute(text("select current_user")).scalar_one() != "cce_worker_cpu":
                raise AvatarUnavailable
            object_name = connection.execute(
                text("select ops_private.moderation_avatar_path(:job,:attempt,:user)"),
                {"job": work.job_id, "attempt": work.attempt_id, "user": self.auth_user_id},
            ).scalar_one()
        if not isinstance(object_name, str) or not self._matching_path(object_name, work.avatar_id):
            raise AvatarUnavailable
        try:
            with httpx.Client(timeout=8, follow_redirects=False, base_url=self.origin) as client:
                token = self._authenticate(client)
                with client.stream(
                    "GET",
                    f"/storage/v1/object/authenticated/cce-avatars/{object_name}",
                    headers={
                        "apikey": self.publishable_key.get_secret_value(),
                        "Authorization": f"Bearer {token}",
                    },
                ) as response:
                    if response.status_code != 200:
                        raise AvatarUnavailable
                    content = bytearray()
                    for chunk in response.iter_bytes():
                        content.extend(chunk)
                        if len(content) > MAX_AVATAR_BYTES:
                            raise AvatarUnavailable
            if sha256(content).hexdigest() != work.avatar_sha256:
                raise AvatarUnavailable
            return bytes(content)
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            # HTTP/JSON errors can carry private paths, tokens or response bodies.
            raise AvatarUnavailable from None

    @staticmethod
    def _matching_path(object_name: str, avatar_id: UUID) -> bool:
        parts = object_name.split("/")
        if len(parts) != 2 or parts[1] != f"{avatar_id}.png":
            return False
        try:
            return str(UUID(parts[0])) == parts[0]
        except ValueError:
            return False
