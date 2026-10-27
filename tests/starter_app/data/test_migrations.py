from alembic import command
from alembic.script import ScriptDirectory
from sqlalchemy import Engine

from starter_app.data.database import make_alembic_config, migrate


def test_single_migration_head():
    heads = ScriptDirectory.from_config(make_alembic_config()).get_heads()
    assert len(heads) == 1, f"Multiple migration heads, merge them: {heads}"


def test_migrations_round_trip_and_match_models(empty_engine: Engine):
    config = make_alembic_config(empty_engine)

    # `alembic check` raises if autogenerate would find any difference from the models.
    migrate(empty_engine)
    command.check(config)
    command.downgrade(config, "base")
    migrate(empty_engine)
    command.check(config)
