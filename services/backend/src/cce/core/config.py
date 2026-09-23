from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CCE_", env_file=".env", extra="ignore", hide_input_in_errors=True
    )

    environment: Literal["local", "test", "staging", "production"] = "local"
    database_url: SecretStr
    db_pool_size: int = Field(default=3, ge=1, le=10)
    auth_issuer: str = "http://127.0.0.1:54321/auth/v1"
    auth_jwks_url: str = "http://127.0.0.1:54321/auth/v1/.well-known/jwks.json"

    @field_validator("database_url")
    @classmethod
    def runtime_identity(cls, value: SecretStr) -> SecretStr:
        try:
            url = make_url(value.get_secret_value())
        except (ArgumentError, ValueError):
            raise ValueError("Invalid database URL") from None
        if url.drivername != "postgresql+psycopg" or url.username != "cce_api":
            raise ValueError("API requires a postgresql+psycopg URL with the cce_api role")
        if not url.host or not url.database or not url.password:
            raise ValueError("Database host, database and password are required")
        return value

    @model_validator(mode="after")
    def disallow_deployed_fixture(self) -> "Settings":
        password = make_url(self.database_url.get_secret_value()).password or ""
        if self.environment in {"staging", "production"} and password.startswith("cce-local-"):
            raise ValueError("Local fixture credentials cannot be used in deployed environments")
        for address in (self.auth_issuer, self.auth_jwks_url):
            url = urlsplit(address)
            if not url.hostname or url.username or url.password or url.query or url.fragment:
                raise ValueError("Auth URLs must not contain credentials, queries or fragments")
            if url.scheme != "https" and not (
                self.environment in {"local", "test"}
                and url.scheme == "http"
                and url.hostname in {"127.0.0.1", "localhost", "host.docker.internal"}
            ):
                raise ValueError("Auth URLs require HTTPS outside local/test")
        return self
