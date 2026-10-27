import sqlite3
from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from starter_app.config import Settings
from starter_app.data.records import BaseRecord

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def make_engine(settings: Settings, *, url: str | None = None) -> Engine:
    """Build the engine for `url` (default: the configured database). Opens no connection."""
    db_url = make_url(url or settings.database_url.get_secret_value())
    if db_url.get_backend_name() == "sqlite":
        return _make_sqlite_engine(str(db_url))
    return create_engine(
        db_url,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_pre_ping=True,
    )


def _make_sqlite_engine(url: str) -> Engine:
    in_memory = make_url(url).database in (None, "", ":memory:")
    engine = create_engine(
        url,
        connect_args={
            # FastAPI runs sync handlers in a threadpool.
            "check_same_thread": False,
            # The driver's legacy transaction handling silently commits around DDL and
            # SAVEPOINTs; this makes it begin and roll back exactly when SQLAlchemy says.
            "autocommit": False,
        },
        # An in-memory database lives only as long as its one connection.
        **({"poolclass": StaticPool} if in_memory else {}),
    )

    @event.listens_for(engine, "connect")
    def _configure_connection(dbapi_connection: Any, _connection_record: Any) -> None:
        if not isinstance(dbapi_connection, sqlite3.Connection):
            return
        # SQLite ignores these pragmas inside a transaction, and with autocommit=False the
        # driver keeps one open, so step outside it while they run.
        dbapi_connection.autocommit = True
        try:
            dbapi_connection.execute("PRAGMA foreign_keys=ON")
            if not in_memory:
                # Readers don't block the writer, and a writer waits for a lock instead of
                # failing at once: what a small production deployment on one machine needs.
                dbapi_connection.execute("PRAGMA journal_mode=WAL")
                dbapi_connection.execute("PRAGMA synchronous=NORMAL")
                dbapi_connection.execute("PRAGMA busy_timeout=5000")
        finally:
            dbapi_connection.autocommit = False

    return engine


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    # expire_on_commit=False: objects stay readable after the unit of work commits, so an
    # orchestrator can map them to domain models without a second round trip.
    return sessionmaker(bind=engine, expire_on_commit=False)


def ping(engine: Engine) -> None:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))


def make_alembic_config(engine: Engine | None = None) -> Config:
    """Alembic config that works from an installed package as well as a checkout."""
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    config.set_main_option("path_separator", "os")
    config.set_main_option("file_template", "%%(year)d%%(month).2d%%(day).2d_%%(rev)s_%%(slug)s")
    config.set_main_option("timezone", "UTC")
    if engine is not None:
        config.attributes["engine"] = engine
    return config


def migrate(engine: Engine, revision: str = "head") -> None:
    command.upgrade(make_alembic_config(engine), revision)


def create_schema(engine: Engine) -> None:
    """Build a new database from the models and mark it as migrated to head.

    Replaying every migration against a new database only re-tests history; the models
    are the current schema. Existing databases are upgraded with `migrate` instead.
    """
    BaseRecord.metadata.create_all(engine)
    command.stamp(make_alembic_config(engine), "head")


def DANGER_drop_schema(engine: Engine) -> None:  # noqa: N802
    """Drop every table, including Alembic's version table. Callers guard the environment."""
    BaseRecord.metadata.drop_all(engine)
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
