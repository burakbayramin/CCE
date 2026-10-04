"""M4.7 — the operations surface.

What matters here is that the operator can tell alive from stuck, that the
two commands stay distinct, and that neither can be driven by a stale copy of
the generation or without a reason.
"""

from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from local_environment import ADMIN_DSN
from test_delivery_integration import a_character
from test_identity_integration import settings
from test_interaction_protocol_integration import engine, worker_engine
from test_review_integration import FixtureModeration, headers

from cce.api_entrypoint import create_app
from cce.modules.interactions import protocol
from cce.modules.operations import service

pytestmark = pytest.mark.integration


def a_worker(user_kind: str = "CPU") -> None:
    with psycopg.connect(ADMIN_DSN) as db:
        db.execute(
            "insert into ops_private.job_workers(worker_id, kind, last_seen_at) "
            "values (%s, %s, now()) on conflict (worker_id) do update set last_seen_at = now()",
            (f"{user_kind.lower()}-probe", user_kind),
        )
        db.commit()


def a_stale_worker() -> None:
    with psycopg.connect(ADMIN_DSN) as db:
        db.execute(
            "insert into ops_private.job_workers(worker_id, kind, last_seen_at) "
            "values ('cpu-ghost', 'CPU', now() - interval '1 hour') "
            "on conflict (worker_id) do update set last_seen_at = excluded.last_seen_at"
        )
        db.commit()


class TestSnapshot:
    def test_a_live_idle_worker_reads_idle(self) -> None:
        a_worker("CPU")
        with engine().begin() as connection:
            rows = service.snapshot(connection, stale_seconds=120)
        cpu = [row for row in rows if row.worker.worker_id == "cpu-probe"]
        assert cpu and cpu[0].worker.state == "IDLE"
        assert cpu[0].needs_a_person() is False

    def test_a_worker_that_stopped_reporting_reads_offline(self) -> None:
        a_stale_worker()
        with engine().begin() as connection:
            rows = service.snapshot(connection, stale_seconds=120)
        ghost = [row for row in rows if row.worker.worker_id == "cpu-ghost"]
        assert ghost and ghost[0].worker.state == "OFFLINE"
        assert ghost[0].needs_a_person() is True, "a dead worker needs a person"

    def test_the_snapshot_exposes_no_turn_content(self) -> None:
        a_worker()
        with engine().begin() as connection:
            rows = service.snapshot(connection)
        for row in rows:
            assert row.reservation is None or row.reservation.quarantined in (True, False)
            assert not hasattr(row.reservation, "prompt_text")
            assert not hasattr(row.reservation, "response_text")


def a_stuck_reservation(character, *, purpose: str = "ADMIN_CHAT"):
    """Claim a reservation and deliberately leave it held.

    This is the state operations exists for: a character is not free, and
    either the lease ran out or nobody is working on it.
    """
    workers = worker_engine()
    try:
        with workers.begin() as connection:
            return protocol.claim(
                connection,
                character_id=character,
                purpose=purpose,  # type: ignore[arg-type]
                holder="cpu-worker-1",
                command_id=uuid4(),
                lease_seconds=30,
            )
    finally:
        workers.dispose()


class TestCommands:
    def test_resolving_requires_a_reason(self, activation_accounts) -> None:
        character, _ = a_character(activation_accounts)
        held = a_stuck_reservation(character)

        with engine().begin() as connection:
            with pytest.raises(Exception) as refused:
                service.resolve_stuck(
                    connection,
                    reservation_id=held.id,
                    expected_generation=held.ownership_generation,
                    reason="kısa",
                )
        assert "10-1000" in str(refused.value) or "reason" in str(refused.value).lower()

    def test_a_stale_generation_is_refused(self, activation_accounts) -> None:
        character, _ = a_character(activation_accounts)
        held = a_stuck_reservation(character)

        with engine().begin() as connection:
            with pytest.raises(Exception) as refused:
                service.requeue(
                    connection,
                    reservation_id=held.id,
                    expected_generation=held.ownership_generation + 5,
                    worker_id="operations",
                    reason="Isolated operator requeue against a stale generation",
                )
        # The refusal is a conflict, and the reason is translated for the
        # caller rather than leaked in the database's wording.
        assert getattr(refused.value, "status", None) == 409

    def test_releasing_a_character_records_the_attempt_rather_than_deleting_it(
        self, activation_accounts
    ) -> None:
        character, _ = a_character(activation_accounts)
        held = a_stuck_reservation(character)

        workers = worker_engine()
        try:
            with workers.begin() as connection:
                run = protocol.begin_attempt(connection, reservation=held, worker_id="cpu-worker-1")
        finally:
            workers.dispose()

        with engine().begin() as connection:
            service.resolve_stuck(
                connection,
                reservation_id=held.id,
                expected_generation=held.ownership_generation,
                reason="Isolated operator resolution for an offline worker",
            )

        with psycopg.connect(ADMIN_DSN) as db:
            state, attempt_state = db.execute(
                "select r.state, (select j.state from ops_private.job_runs j "
                "  where j.id=%s) from ops_private.interaction_reservations r where r.id=%s",
                (run.id, held.id),
            ).fetchone()
        assert state == "RESOLVED"
        assert attempt_state == "ABANDONED", "the attempt is recorded as abandoned, never deleted"


class TestApi:
    def test_a_contributor_cannot_read_the_operations_surface(self, activation_accounts) -> None:
        (_owner, contributor), _ = activation_accounts
        with TestClient(create_app(settings(), moderation=FixtureModeration())) as api:
            response = api.get("/operations/snapshot", headers=headers(contributor))
        assert response.status_code == 403

    def test_an_unauthenticated_caller_is_refused(self) -> None:
        with TestClient(create_app(settings(), moderation=FixtureModeration())) as api:
            response = api.get("/operations/snapshot")
        assert response.status_code == 401

    def test_the_owner_sees_worker_presence_without_content(self, activation_accounts) -> None:
        a_worker()
        (owner, _contributor), _ = activation_accounts
        with TestClient(create_app(settings(), moderation=FixtureModeration())) as api:
            response = api.get("/operations/snapshot", headers=headers(owner))
        assert response.status_code == 200
        body = response.json()
        assert "workers" in body and "held" in body
        for word in ("response_text", "prompt_text", "provider", "effect_identity"):
            assert word not in response.text
