from typing import Any, Literal

from alembic import context
from sqlalchemy import Engine

from starter_app.data.records import BaseRecord, UtcDateTime

config = context.config
target_metadata = BaseRecord.metadata


def _engine() -> Engine:
    engine = config.attributes.get("engine")
    if engine is None:
        raise RuntimeError("Run migrations through `uv run app db ...`, which supplies the engine")
    return engine


def _render_item(type_: str, obj: Any, _autogen_context: Any) -> str | Literal[False]:
    # Migrations must not import app types: they'd break when the type later changes.
    if type_ == "type" and isinstance(obj, UtcDateTime):
        return "sa.DateTime(timezone=True)"
    return False


def run_migrations_offline() -> None:
    context.configure(
        url=_engine().url,
        target_metadata=target_metadata,
        literal_binds=True,
        render_as_batch=True,
        render_item=_render_item,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    with _engine().connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # SQLite can't ALTER most constraints, so batch mode rebuilds the table there;
            # on Postgres the same batch operations run as plain ALTERs.
            render_as_batch=True,
            render_item=_render_item,
            compare_server_default=True,
            # The engine's SQLite driver runs DDL inside transactions, so a failed migration
            # rolls back completely there too, as it does on Postgres.
            transactional_ddl=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
