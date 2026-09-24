"""Only two fixed loopback stacks are permitted; never accepts a remote test DSN."""

import os

ISOLATED = os.environ.get("CCE_ISOLATED_TEST_STACK") == "1"
DB_PORT = 55322 if ISOLATED else 54322
AUTH_URL = f"http://127.0.0.1:{55321 if ISOLATED else 54321}"
ADMIN_DSN = f"postgresql://postgres:postgres@127.0.0.1:{DB_PORT}/postgres"
API_DSN = f"postgresql+psycopg://cce_api:cce-local-api-only@127.0.0.1:{DB_PORT}/postgres"
ENGINE_DSN = f"postgresql+psycopg://cce_engine:cce-local-engine-only@127.0.0.1:{DB_PORT}/postgres"
