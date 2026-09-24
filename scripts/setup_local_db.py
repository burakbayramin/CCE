"""Provision disposable local credentials; never accepts a cloud database URL."""

import argparse
import os

import psycopg
from psycopg import sql


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--isolated-test-stack", action="store_true")
    args = parser.parse_args()
    if os.environ.get("CCE_ENVIRONMENT") not in {"local", "test"}:
        raise SystemExit("Set CCE_ENVIRONMENT=local or test explicitly")
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
        if version != (1,):
            raise SystemExit(
                "Expected the CCE foundation migration in the local database"
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
