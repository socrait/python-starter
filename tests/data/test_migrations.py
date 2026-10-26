from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine

from starter_app.data.database import make_alembic_config, migrate
from starter_app.data.records import BaseRecord


def test_single_migration_head():
    heads = ScriptDirectory.from_config(make_alembic_config()).get_heads()
    assert len(heads) == 1, f"Multiple migration heads, merge them: {heads}"


def test_migrations_round_trip_and_match_models(empty_engine: Engine):
    migrate(empty_engine)
    assert _schema_drift(empty_engine) == []

    command.downgrade(make_alembic_config(empty_engine), "base")
    migrate(empty_engine)
    assert _schema_drift(empty_engine) == []


def _schema_drift(engine: Engine) -> list[object]:
    with engine.connect() as connection:
        return compare_metadata(MigrationContext.configure(connection), BaseRecord.metadata)
