import json
import sys
from types import ModuleType
from uuid import uuid4

import pytest
from pydantic import ValidationError

from cce.modules.contributions import moderation_service
from cce.modules.contributions.moderation_service import WorkerSettings, load_scanner
from cce.modules.contributions.moderation_worker import AvatarUnavailable


def settings(**overrides):
    values = {
        "environment": "local",
        "worker_database_url": (
            "postgresql+psycopg://cce_worker_cpu:cce-local-worker-only@127.0.0.1:55322/postgres"
        ),
        "storage_url": "http://127.0.0.1:55321",
        "supabase_publishable_key": "sb_publishable_test",
        "moderation_auth_user_id": str(uuid4()),
        "moderation_auth_email": "worker@example.com",
        "moderation_auth_password": "worker-test-password",
        "moderation_scanner_factory": "fixture_local_scanner:Scanner",
    }
    return WorkerSettings(_env_file=None, **(values | overrides))


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+psycopg://cce_api:secret@127.0.0.1:55322/postgres",
        "sqlite:///local.db",
        "postgresql+psycopg://cce_worker_cpu@127.0.0.1:55322/postgres",
    ],
)
def test_worker_database_requires_restricted_role(url):
    with pytest.raises(ValidationError, match="cce_worker_cpu database URL"):
        settings(worker_database_url=url)


def test_deployed_worker_refuses_local_fixture_credentials():
    with pytest.raises(ValidationError, match="Local worker fixture"):
        settings(environment="production")


def test_worker_environment_must_be_explicit(monkeypatch):
    monkeypatch.delenv("CCE_ENVIRONMENT", raising=False)
    with pytest.raises(ValidationError, match="environment"):
        WorkerSettings(
            _env_file=None,
            worker_database_url=(
                "postgresql+psycopg://cce_worker_cpu:secret@127.0.0.1:55322/postgres"
            ),
            storage_url="http://127.0.0.1:55321",
            supabase_publishable_key="sb_publishable_test",
            moderation_auth_user_id=str(uuid4()),
            moderation_auth_email="worker@example.com",
            moderation_auth_password="worker-test-password",
            moderation_scanner_factory="fixture_local_scanner:Scanner",
        )


def test_scanner_must_be_explicit_and_loadable(monkeypatch):
    module = ModuleType("fixture_local_scanner")

    class Scanner:
        def __init__(self, reader):
            self.reader = reader

        def evaluate(self, work):
            return work

    module.Scanner = Scanner
    monkeypatch.setitem(sys.modules, "fixture_local_scanner", module)
    reader = object()
    loaded = load_scanner("fixture_local_scanner:Scanner", reader)
    assert isinstance(loaded, Scanner) and loaded.reader is reader
    with pytest.raises(ValueError, match="could not be loaded"):
        load_scanner("cce.modules.contributions.moderation_worker:UnconfiguredLocalScanner", reader)


def test_scanner_import_failure_does_not_echo_private_details(monkeypatch):
    module = ModuleType("fixture_local_scanner")

    def explode():
        raise RuntimeError("secret scanner path and credentials")

    module.explode = explode
    monkeypatch.setitem(sys.modules, "fixture_local_scanner", module)
    with pytest.raises(ValueError) as failure:
        load_scanner("fixture_local_scanner:explode", object())
    assert "secret" not in str(failure.value)


def test_worker_engine_uses_one_restricted_connection(monkeypatch):
    captured = {}

    def fake_engine(url, **kwargs):
        captured.update(url=url, **kwargs)
        return object()

    monkeypatch.setattr(moderation_service, "create_engine", fake_engine)
    moderation_service.create_worker_engine(settings())
    assert captured["url"].startswith("postgresql+psycopg://cce_worker_cpu:")
    assert captured["pool_size"] == 1
    assert captured["max_overflow"] == 0
    assert captured["hide_parameters"] is True


@pytest.mark.parametrize("seconds", [0, 241, float("inf"), float("nan")])
def test_worker_timeout_is_finite_and_below_lease(seconds):
    with pytest.raises(ValidationError):
        settings(moderation_timeout_seconds=seconds)


def test_worker_startup_rejects_bad_auth_before_loading_scanner_or_claiming(monkeypatch):
    calls = []

    class Engine:
        def dispose(self):
            calls.append("dispose")

    class Reader:
        def __init__(self, engine, **kwargs):
            calls.append("reader")

        def verify_identity(self):
            calls.append("verify")
            raise AvatarUnavailable

    monkeypatch.setattr(moderation_service, "WorkerSettings", lambda: settings())
    monkeypatch.setattr(moderation_service, "create_worker_engine", lambda _: Engine())
    monkeypatch.setattr(moderation_service, "ModerationAvatarReader", Reader)
    monkeypatch.setattr(moderation_service.signal, "signal", lambda *args: None)
    monkeypatch.setattr(
        moderation_service,
        "load_scanner",
        lambda *args: pytest.fail("No scanner should load before Auth verification"),
    )
    with pytest.raises(AvatarUnavailable):
        moderation_service.main()
    assert calls == ["reader", "verify", "dispose"]


def test_worker_cli_reports_failure_without_traceback_or_private_details(monkeypatch, capsys):
    def fail():
        raise RuntimeError("private DSN password token scanner input")

    monkeypatch.setattr(moderation_service, "main", fail)
    with pytest.raises(SystemExit) as stopped:
        moderation_service.cli()
    assert stopped.value.code == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert json.loads(output.err) == {
        "event": "moderation_worker_failed",
        "exception_type": "RuntimeError",
    }
    assert "private" not in output.err and "Traceback" not in output.err


def test_worker_cli_returns_normally_after_clean_stop(monkeypatch, capsys):
    monkeypatch.setattr(moderation_service, "main", lambda: None)
    moderation_service.cli()
    assert capsys.readouterr() == ("", "")
