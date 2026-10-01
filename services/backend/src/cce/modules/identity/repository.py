from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Connection, Engine, text

from cce.modules.identity.domain import Actor, AuthenticationFailed


@contextmanager
def actor_transaction(engine: Engine, actor: Actor) -> Iterator[Connection]:
    """Only verified actors enter repositories; SET LOCAL never leaks through the pool.

    Custom Postgres GUCs are writable by the DB role: current_identity() trusts
    this API boundary to verify JWTs and never accepts an actor from request data.
    SQL execution as cce_api/cce_engine is therefore a trusted-server capability.
    """
    with engine.begin() as connection:
        connection.execute(
            text(
                "select set_config('cce.actor_id', :user_id, true), "
                "set_config('cce.session_id', :session_id, true)"
            ),
            {"user_id": str(actor.user_id), "session_id": str(actor.session_id)},
        )
        yield connection


def identity_context(engine: Engine, actor: Actor) -> dict[str, object]:
    with actor_transaction(engine, actor) as connection:
        record = connection.execute(text("select * from ops_private.current_identity()"))
        row = record.mappings().one_or_none()
        if row is None:
            raise AuthenticationFailed
        connection.execute(
            text("insert into public.profiles (user_id) values (:user_id) on conflict do nothing"),
            {"user_id": actor.user_id},
        )
        return {"user_id": actor.user_id, "role": row["actor_role"], "person_id": row["person_id"]}
