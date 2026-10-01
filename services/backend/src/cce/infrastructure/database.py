from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from cce.core.config import Settings

REQUIRED_SCHEMA_VERSION = 2


def create_database(settings: Settings, *, owner_commands: bool = False) -> Engine:
    dsn = settings.engine_database_url if owner_commands else settings.database_url
    if dsn is None:
        raise ValueError("Engine database is not configured")
    return create_engine(
        dsn.get_secret_value(),
        pool_size=settings.db_pool_size,
        max_overflow=0,
        pool_timeout=2,
        pool_pre_ping=True,
        hide_parameters=True,
        connect_args={"connect_timeout": 3, "options": "-c statement_timeout=2000"},
    )


def database_ready(engine: Engine) -> bool:
    """Require the expected migration and a non-privileged API identity."""
    try:
        with engine.connect() as connection:
            return bool(
                connection.execute(
                    text(
                        "SELECT current_user = 'cce_api' AND NOT r.rolsuper "
                        "AND NOT r.rolbypassrls AND NOT r.rolcreaterole "
                        "AND NOT r.rolcreatedb AND v.version = :version "
                        "FROM pg_roles r CROSS JOIN ops_private.schema_version v "
                        "WHERE r.rolname = current_user AND v.singleton = true"
                    ),
                    {"version": REQUIRED_SCHEMA_VERSION},
                ).scalar_one()
            )
    except SQLAlchemyError:
        # Driver errors may include DSNs or parameters. Do not log their contents.
        return False
