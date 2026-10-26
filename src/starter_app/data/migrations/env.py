from typing import Any, Literal

from alembic import context
from sqlalchemy import Engine

from starter_app.config import get_settings
from starter_app.data.database import make_engine
from starter_app.data.records import BaseRecord, UtcDateTime

config = context.config
target_metadata = BaseRecord.metadata


def _engine() -> Engine:
    # Callers that already hold an engine (the app CLI, tests) pass it in; the bare
    # `alembic` command falls back to the configured database.
    engine = config.attributes.get("engine")
    return engine if engine is not None else make_engine(get_settings())


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
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
