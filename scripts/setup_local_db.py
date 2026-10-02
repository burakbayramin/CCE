"""Provision disposable local credentials; never accepts a cloud database URL."""

import argparse
import os

import psycopg
from cce.infrastructure.database import REQUIRED_SCHEMA_VERSION
from psycopg import sql


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--isolated-test-stack", action="store_true")
    parser.add_argument(
        "--activation-fixtures",
        action="store_true",
        help="Opt in only on a disposable test DB; never enables real-content activation",
    )
    args = parser.parse_args()
    if os.environ.get("CCE_ENVIRONMENT") not in {"local", "test"}:
        raise SystemExit("Set CCE_ENVIRONMENT=local or test explicitly")
    if args.activation_fixtures and os.environ["CCE_ENVIRONMENT"] != "test":
        raise SystemExit(
            "Activation fixtures require an explicit disposable test environment"
        )
    # Fixed loopback target, no configurable host/DSN or real user fixture data.
    with psycopg.connect(
        host="127.0.0.1",
        port=55322 if args.isolated_test_stack else 54322,
        dbname="postgres",
        user="postgres",
        password="postgres",
        connect_timeout=3,
    ) as connection:
        version = connection.execute(
            "select version from ops_private.schema_version"
        ).fetchone()
        if version != (REQUIRED_SCHEMA_VERSION,):
            raise SystemExit(
                "Expected the CCE foundation migration in the local database"
            )
        # The script accepts loopback only; no runtime role can turn this on.
        # Reprovisioning a former test stack as local must switch it off again.
        connection.execute(
            "update ops_private.fixture_approval_policy set enabled=%s where singleton",
            (os.environ["CCE_ENVIRONMENT"] == "test",),
        )
        connection.execute(
            "update ops_private.fixture_activation_policy set enabled=%s where singleton",
            (args.activation_fixtures,),
        )
        for role, password in [
            ("cce_api", "cce-local-api-only"),
            ("cce_engine", "cce-local-engine-only"),
            ("cce_worker_cpu", "cce-local-worker-only"),
        ]:
            connection.execute(
                sql.SQL("alter role {} login password {}").format(
                    sql.Identifier(role),
                    sql.Literal(password),
                )
            )
    print("Local CCE API/worker fixture credentials provisioned")


if __name__ == "__main__":
    main()
