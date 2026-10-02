"""Opt-in process entrypoint for the local moderation worker.

This module intentionally ships without a scanner implementation or default
credentials. Operators must configure a reviewed local scanner factory before
pending submissions can be consumed.
"""

import json
import signal
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from importlib import import_module
from threading import Event
from types import FrameType
from typing import Literal, cast
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

from cce.modules.contributions.moderation_avatar import ModerationAvatarReader
from cce.modules.contributions.moderation_process import ProcessLocalScanner
from cce.modules.contributions.moderation_worker import (
    LocalScanner,
    UnconfiguredLocalScanner,
    run_loop,
)


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CCE_", env_file=".env", extra="ignore", hide_input_in_errors=True
    )

    environment: Literal["local", "test", "staging", "production"]
    worker_database_url: SecretStr
    storage_url: str
    supabase_publishable_key: SecretStr
    moderation_auth_user_id: UUID
    moderation_auth_email: str = Field(min_length=3, max_length=254)
    moderation_auth_password: SecretStr
    moderation_scanner_factory: str = Field(
        pattern=r"^[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*:[A-Za-z_]\w*$"
    )
    moderation_idle_seconds: float = Field(default=2.0, gt=0, le=60)
    moderation_startup_seconds: float = Field(default=120.0, gt=0, le=600, allow_inf_nan=False)
    moderation_timeout_seconds: float = Field(default=120.0, gt=0, le=240, allow_inf_nan=False)

    @field_validator("worker_database_url")
    @classmethod
    def restricted_worker_identity(cls, value: SecretStr) -> SecretStr:
        try:
            url = make_url(value.get_secret_value())
        except (ArgumentError, ValueError):
            raise ValueError("Invalid worker database URL") from None
        if (
            url.drivername != "postgresql+psycopg"
            or url.username != "cce_worker_cpu"
            or not url.password
            or not url.host
            or not url.database
        ):
            raise ValueError("Moderation requires a cce_worker_cpu database URL")
        return value

    @model_validator(mode="after")
    def disallow_deployed_fixture(self) -> "WorkerSettings":
        password = make_url(self.worker_database_url.get_secret_value()).password or ""
        if self.environment in {"staging", "production"} and password.startswith("cce-local-"):
            raise ValueError("Local worker fixture credentials cannot be deployed")
        storage = urlsplit(self.storage_url)
        if (
            not storage.hostname
            or storage.username
            or storage.password
            or storage.query
            or storage.fragment
            or storage.path not in {"", "/"}
            or (
                storage.scheme != "https"
                and not (
                    self.environment in {"local", "test"}
                    and storage.scheme == "http"
                    and storage.hostname in {"127.0.0.1", "localhost", "host.docker.internal"}
                )
            )
        ):
            raise ValueError("Storage URL requires a safe origin")
        return self


def load_scanner(factory_path: str, avatar_reader: ModerationAvatarReader) -> LocalScanner:
    """Load an operator-selected scanner; never fall back to a test fixture."""
    try:
        module_name, factory_name = factory_path.rsplit(":", 1)
        factory = getattr(import_module(module_name), factory_name)
        scanner = factory(avatar_reader)
        if isinstance(scanner, UnconfiguredLocalScanner) or not callable(
            getattr(scanner, "evaluate", None)
        ):
            raise TypeError("Scanner does not implement evaluate")
        return cast(LocalScanner, scanner)
    except Exception:
        # Import exceptions can include local paths or operator secrets.
        raise ValueError("Configured local scanner could not be loaded") from None


def create_worker_engine(settings: WorkerSettings) -> Engine:
    return create_engine(
        settings.worker_database_url.get_secret_value(),
        pool_size=1,
        max_overflow=0,
        pool_timeout=2,
        pool_pre_ping=True,
        hide_parameters=True,
        connect_args={"connect_timeout": 3, "options": "-c statement_timeout=2000"},
    )


@contextmanager
def scanner_context(settings: WorkerSettings) -> Iterator[LocalScanner]:
    """Create process-local DB resources; never pass a pooled Engine to spawn."""
    engine = create_worker_engine(settings)
    try:
        reader = ModerationAvatarReader(
            engine,
            storage_url=settings.storage_url,
            publishable_key=settings.supabase_publishable_key,
            auth_user_id=settings.moderation_auth_user_id,
            auth_email=settings.moderation_auth_email,
            auth_password=settings.moderation_auth_password,
        )
        reader.verify_identity()
        yield load_scanner(settings.moderation_scanner_factory, reader)
    finally:
        engine.dispose()


def main() -> None:
    settings = WorkerSettings()
    stop = Event()

    def request_stop(signum: int, frame: FrameType | None) -> None:
        stop.set()

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)
    engine = create_worker_engine(settings)
    scanner = ProcessLocalScanner(
        scanner_context,
        (settings,),
        startup_seconds=settings.moderation_startup_seconds,
        timeout_seconds=settings.moderation_timeout_seconds,
        stop=stop,
    )
    try:
        avatar_reader = ModerationAvatarReader(
            engine,
            storage_url=settings.storage_url,
            publishable_key=settings.supabase_publishable_key,
            auth_user_id=settings.moderation_auth_user_id,
            auth_email=settings.moderation_auth_email,
            auth_password=settings.moderation_auth_password,
        )
        avatar_reader.verify_identity()
        run_loop(
            engine,
            scanner,
            stop,
            auth_worker_user_id=settings.moderation_auth_user_id,
            idle_seconds=settings.moderation_idle_seconds,
            before_claim=scanner.prepare,
        )
    finally:
        try:
            scanner.close()
        finally:
            engine.dispose()


def cli() -> None:
    """Supervisor exit contract: nonzero status, never a private traceback."""
    try:
        main()
    except Exception as error:
        print(
            json.dumps(
                {"event": "moderation_worker_failed", "exception_type": type(error).__name__}
            ),
            file=sys.stderr,
        )
        raise SystemExit(1) from None
