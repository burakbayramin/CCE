"""Explicit operator-only Owner provisioning; never used by the running API."""

import argparse
import os
from uuid import UUID

import psycopg


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-id", required=True, type=UUID)
    parser.add_argument("--display-name", required=True)
    parser.add_argument("--operator", required=True)
    parser.add_argument("--reason", required=True)
    args = parser.parse_args()
    dsn = os.environ.get("CCE_ADMIN_DATABASE_URL")
    if not dsn:
        raise SystemExit(
            "Set CCE_ADMIN_DATABASE_URL explicitly; do not use API credentials"
        )
    try:
        with psycopg.connect(dsn, connect_timeout=5) as connection:
            if connection.execute("select current_user").fetchone() != ("postgres",):
                raise SystemExit(
                    "Provisioning requires the trusted postgres operator role"
                )
            row = connection.execute(
                "select ops_private.bootstrap_world_owner(%s, %s, %s, %s)",
                (args.user_id, args.display_name, args.operator, args.reason),
            ).fetchone()
        print(
            f"Owner provisioned; persistent person ID: {row[0] if row else 'missing'}"
        )
    except psycopg.Error:
        raise SystemExit(
            "Owner provisioning rejected; check target user and existing assignment"
        ) from None


if __name__ == "__main__":
    main()
