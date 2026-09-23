"""Generate an API contract without connecting to a database."""

import json
from pathlib import Path

from cce.api_entrypoint import create_app
from cce.core.config import Settings
from pydantic import SecretStr

settings = Settings(
    environment="test",
    database_url=SecretStr("postgresql+psycopg://cce_api:unused@127.0.0.1:1/postgres"),
)
target = Path(__file__).resolve().parents[1] / ".artifacts" / "openapi.json"
target.parent.mkdir(exist_ok=True)
target.write_text(
    json.dumps(create_app(settings).openapi(), indent=2) + "\n", encoding="utf-8"
)
