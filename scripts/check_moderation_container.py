"""Docker/Compose guardrails and network-isolated synthetic scanner smoke.

Run on the Docker host with Python's standard library. --inside is used only
in the disposable production-image container; no credentials or DB are needed.
"""

import argparse
import json
import os
import subprocess
from contextlib import contextmanager
from pathlib import Path
from threading import Event
from uuid import uuid4


class SyntheticScanner:
    def __init__(self, mode):
        self.mode = mode
        self.calls = 0

    def evaluate(self, work):
        from cce.modules.contributions.moderation_worker import ScanEvaluation

        if self.mode == "hang":
            Event().wait(60)
        self.calls += 1
        return ScanEvaluation(
            result="REVIEW",
            provider=f"container-fixture-{os.getpid()}",
            policy_version=f"synthetic-{self.calls}",
            text_checked=True,
            checked_avatar_sha256=work.avatar_sha256,
        )


@contextmanager
def synthetic_context(mode):
    yield SyntheticScanner(mode)


def inside():
    from cce.modules.contributions.moderation_process import ProcessLocalScanner
    from cce.modules.contributions.moderation_worker import ScanWork
    from cce.modules.contributions.schemas import CharacterProposal

    assert os.geteuid() == 10001, "Worker image must use the restricted non-root user"
    assert os.statvfs("/app").f_flag & os.ST_RDONLY, (
        "Worker filesystem must be read-only"
    )
    definition = CharacterProposal(
        name="Container fixture",
        introduction="Synthetic test, not a real scanner",
        backstory="Isolated container protocol test.",
        adult_appearance_confirmed=True,
        original_character_confirmed=True,
    )
    work = ScanWork(
        job_id=uuid4(),
        attempt_id=uuid4(),
        revision_id=uuid4(),
        source_sha256="a" * 64,
        definition=definition,
        avatar_id=None,
    )
    scanner = ProcessLocalScanner(synthetic_context, ("ok",), timeout_seconds=5)
    try:
        scanner.prepare()
        first, second = scanner.evaluate(work), scanner.evaluate(work)
        assert first.provider == second.provider != f"container-fixture-{os.getpid()}"
        assert (first.policy_version, second.policy_version) == (
            "synthetic-1",
            "synthetic-2",
        )
        scanner.close()
        scanner.args = ("hang",)
        scanner.timeout_seconds = 0.2
        scanner.prepare()
        try:
            scanner.evaluate(work)
        except TimeoutError:
            pass
        else:
            raise AssertionError("Hung scanner must be terminated")
        assert scanner._process is None and scanner._io is None
        scanner.args = ("ok",)
        scanner.timeout_seconds = 5
        scanner.prepare()
        assert scanner.evaluate(work).result == "REVIEW"
    finally:
        scanner.close()
    print(
        "Non-root/read-only Linux spawn, warm reuse, hard timeout and new generation passed"
    )


def host(image):
    root = Path(__file__).resolve().parents[1]
    # Never use developer credentials or COMPOSE_PROFILES in validation output.
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("CCE_", "COMPOSE_"))
    }
    worker_env = {
        "CCE_ENVIRONMENT": "test",
        "CCE_WORKER_DATABASE_URL": (
            "postgresql+psycopg://cce_worker_cpu:synthetic-only@host.docker.internal:55322/postgres"
        ),
        "CCE_STORAGE_URL": "http://host.docker.internal:55321",
        "CCE_SUPABASE_PUBLISHABLE_KEY": "sb_publishable_synthetic",
        "CCE_MODERATION_AUTH_USER_ID": str(uuid4()),
        "CCE_MODERATION_AUTH_EMAIL": "synthetic@example.invalid",
        "CCE_MODERATION_AUTH_PASSWORD": "synthetic-only",
        "CCE_MODERATION_SCANNER_FACTORY": "synthetic_only:factory",
        "CCE_MODERATION_IDLE_SECONDS": "2",
        "CCE_MODERATION_STARTUP_SECONDS": "120",
        "CCE_MODERATION_TIMEOUT_SECONDS": "120",
    }
    env.update(worker_env)
    env.update(
        CCE_DATABASE_URL="private-api-canary",
        CCE_ENGINE_DATABASE_URL="private-engine-canary",
    )
    env["CCE_TEST_STORAGE_ADMIN_KEY"] = "private-service-canary"
    compose = [
        "docker",
        "compose",
        "--env-file",
        os.devnull,
        "-f",
        str(root / "compose.yaml"),
    ]
    default = subprocess.run(
        [*compose, "config", "--services"],
        env=env,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.split()
    assert set(default) == {"api", "web"}, (
        "Worker must not start in the default profile"
    )
    resolved = subprocess.run(
        [*compose, "--profile", "moderation-worker", "config", "--format", "json"],
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    worker = json.loads(resolved.stdout)["services"]["moderation-worker"]
    assert worker["environment"] == worker_env | {"PYTHONDONTWRITEBYTECODE": "1"}
    assert worker["profiles"] == ["moderation-worker"]
    assert worker["command"] == [
        "/app/services/backend/.venv/bin/cce-moderation-worker"
    ]
    assert not worker.get("ports") and not worker.get("depends_on")
    assert worker["read_only"] and worker["init"]
    assert worker["cap_drop"] == ["ALL"]
    assert "no-new-privileges:true" in worker["security_opt"]
    assert worker["restart"] == "on-failure:3"
    assert worker["stop_grace_period"] == "30s"
    assert worker["pids_limit"] == 256
    assert worker["logging"]["options"] == {"max-file": "3", "max-size": "10m"}
    print("Compose profile, environment allowlist and worker hardening passed")

    run = [
        "docker",
        "run",
        "--rm",
        "--network",
        "none",
        "--read-only",
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,size=64m",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges:true",
        "--init",
        "--pids-limit",
        "256",
    ]
    rejected = subprocess.run(
        [*run, image, "/app/services/backend/.venv/bin/cce-moderation-worker"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert rejected.returncode == 1 and not rejected.stdout
    assert json.loads(rejected.stderr) == {
        "event": "moderation_worker_failed",
        "exception_type": "ValidationError",
    }
    print(
        "Unconfigured worker exits nonzero without private traceback or network access"
    )
    subprocess.run(
        [
            *run,
            "--mount",
            (
                f"type=bind,source={Path(__file__).resolve()},"
                "target=/worker-smoke.py,readonly"
            ),
            image,
            "/app/services/backend/.venv/bin/python",
            "/worker-smoke.py",
            "--inside",
        ],
        check=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="cce-api:test")
    parser.add_argument("--inside", action="store_true")
    args = parser.parse_args()
    inside() if args.inside else host(args.image)
