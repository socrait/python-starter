import argparse
import subprocess
import sys
from collections.abc import Callable, Generator, Sequence
from contextlib import contextmanager
from pathlib import Path

import uvicorn
from alembic import command
from sqlalchemy import Engine

from starter_app.config import Settings, get_settings
from starter_app.core.models import Actor, NewProject, NewTask, Role
from starter_app.data.database import (
    DANGER_drop_schema,
    create_schema,
    make_alembic_config,
    make_engine,
    make_session_factory,
    migrate,
)
from starter_app.data.unit_of_work import UnitOfWork
from starter_app.dependencies import make_identity_orchestrator, make_project_orchestrator
from starter_app.logger import configure_logging_from_settings
from starter_app.metrics import AppMetrics, make_meter_provider_from_settings

type Handler = Callable[[argparse.Namespace, Settings], int]


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for `uv run app ...`."""
    parser = _build_parser()
    # `app test` passes anything it doesn't recognize through to pytest.
    args, extra = parser.parse_known_args(argv)
    if extra and args.handler is not _test:
        parser.error(f"unrecognized arguments: {' '.join(extra)}")
    args.pytest_args = extra
    settings = get_settings()
    configure_logging_from_settings(settings)
    handler: Handler = args.handler
    return handler(args, settings)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="app", description="Run, migrate, and check the app.")
    commands = parser.add_subparsers(required=True, metavar="COMMAND")

    serve = commands.add_parser("serve", help="Run the API server")
    serve.add_argument("--reload", action="store_true", help="Restart on code changes")
    serve.add_argument("--host", help="Bind address (default: settings.host)")
    serve.add_argument("--port", type=int, help="Port (default: settings.port)")
    serve.set_defaults(handler=_serve)

    db = commands.add_parser("db", help="Database schema and migrations")
    db_commands = db.add_subparsers(required=True, metavar="DB_COMMAND")
    db_commands.add_parser("create", help="Create a new database's schema at head").set_defaults(
        handler=_db_create
    )
    upgrade = db_commands.add_parser("migrate", help="Apply migrations (default: to head)")
    upgrade.add_argument("revision", nargs="?", default="head")
    upgrade.set_defaults(handler=_db_migrate)
    downgrade = db_commands.add_parser("downgrade", help="Revert migrations to a revision")
    downgrade.add_argument("revision", help='e.g. "-1" or a revision id')
    downgrade.set_defaults(handler=_db_downgrade)
    revision = db_commands.add_parser("revision", help="Autogenerate a migration from the models")
    revision.add_argument("-m", "--message", required=True)
    revision.set_defaults(handler=_db_revision)
    db_commands.add_parser("check", help="Fail if the models and migrations disagree").set_defaults(
        handler=_db_check
    )
    db_commands.add_parser("current", help="Show the applied revision").set_defaults(
        handler=_db_current
    )
    reset = db_commands.add_parser("reset", help="Drop everything and recreate (local only)")
    reset.add_argument("--yes", action="store_true", help="Skip the confirmation prompt")
    reset.set_defaults(handler=_db_reset)

    commands.add_parser(
        "seed", help="Create a demo org, users, and project (local only)"
    ).set_defaults(handler=_seed)

    for name, help_text, handler in (
        ("lint", "ruff lint and format check", _lint),
        ("fmt", "Format and auto-fix with ruff", _fmt),
        ("typecheck", "Type-check with ty", _typecheck),
        ("rules", "Run the ast-grep architecture rules", _rules),
        ("check", "lint + typecheck + rules + test", _check),
    ):
        commands.add_parser(name, help=help_text).set_defaults(handler=handler)
    commands.add_parser("test", help="Run pytest; extra arguments pass through").set_defaults(
        handler=_test
    )
    return parser


def _serve(args: argparse.Namespace, settings: Settings) -> int:
    uvicorn.run(
        "starter_app.main:make_app",
        factory=True,
        host=args.host or settings.host,
        port=args.port or settings.port,
        reload=args.reload,
        # Logging is configured by the app; the access log comes from its middleware.
        log_config=None,
        access_log=False,
        timeout_graceful_shutdown=settings.graceful_shutdown_timeout_seconds,
    )
    return 0


@contextmanager
def _engine(settings: Settings) -> Generator[Engine]:
    engine = make_engine(settings)
    try:
        yield engine
    finally:
        engine.dispose()


def _db_create(_args: argparse.Namespace, settings: Settings) -> int:
    with _engine(settings) as engine:
        create_schema(engine)
    print("Schema created and stamped at head.")
    return 0


def _db_migrate(args: argparse.Namespace, settings: Settings) -> int:
    with _engine(settings) as engine:
        migrate(engine, args.revision)
    return 0


def _db_downgrade(args: argparse.Namespace, settings: Settings) -> int:
    with _engine(settings) as engine:
        command.downgrade(make_alembic_config(engine), args.revision)
    return 0


def _db_revision(args: argparse.Namespace, settings: Settings) -> int:
    with _engine(settings) as engine:
        config = make_alembic_config(engine)
        # Format the generated migration with the project's own ruff.
        ruff = str(Path(sys.executable).parent / "ruff")
        config.set_section_option("post_write_hooks", "hooks", "format, fix")
        for name, options in (("format", "format"), ("fix", "check --fix --quiet")):
            config.set_section_option("post_write_hooks", f"{name}.type", "exec")
            config.set_section_option("post_write_hooks", f"{name}.executable", ruff)
            config.set_section_option(
                "post_write_hooks", f"{name}.options", f"{options} REVISION_SCRIPT_FILENAME"
            )
        command.revision(config, message=args.message, autogenerate=True)
    print("Review the generated migration before committing it.")
    return 0


def _db_check(_args: argparse.Namespace, settings: Settings) -> int:
    with _engine(settings) as engine:
        command.check(make_alembic_config(engine))
    return 0


def _db_current(_args: argparse.Namespace, settings: Settings) -> int:
    with _engine(settings) as engine:
        command.current(make_alembic_config(engine), verbose=True)
    return 0


def _db_reset(args: argparse.Namespace, settings: Settings) -> int:
    if settings.environment.is_deployed:
        print(f"Refusing to reset a {settings.environment} database.", file=sys.stderr)
        return 1
    with _engine(settings) as engine:
        if not args.yes:
            answer = input(f"Drop every table in {engine.url.render_as_string()}? [y/N] ")
            if answer.strip().lower() != "y":
                print("Aborted.")
                return 1
        DANGER_drop_schema(engine)
        create_schema(engine)
    print("Database reset.")
    return 0


def _seed(_args: argparse.Namespace, settings: Settings) -> int:
    if settings.environment.is_deployed:
        print(f"Refusing to seed a {settings.environment} database.", file=sys.stderr)
        return 1
    meter_provider = make_meter_provider_from_settings(settings)
    with _engine(settings) as engine, make_session_factory(engine)() as session:
        uow = UnitOfWork(session)
        identity = make_identity_orchestrator(session, uow)
        metrics = AppMetrics(meter_provider.get_meter(settings.app_name))
        projects = make_project_orchestrator(session, uow, identity, metrics)
        org, admin = identity.create_org_with_admin(
            org_name="Demo Org", admin_email="admin@example.com", admin_display_name="Ada Admin"
        )
        admin_actor = Actor(user_id=admin.id, org_id=org.id, role=Role.ADMIN)
        member = identity.add_member(
            admin_actor, email="member@example.com", display_name="Max Member", role=Role.MEMBER
        )
        member_actor = Actor(user_id=member.id, org_id=org.id, role=Role.MEMBER)
        projects.create_project(
            member_actor,
            NewProject(
                name="Launch plan",
                tasks=[NewTask(title="Write the README", assignee_ids=[member.id])],
            ),
        )
    meter_provider.shutdown()
    print(f"Seeded org {org.id}.")
    print(f"  admin:  {admin.id}")
    print(f"  member: {member.id}")
    print(f"Try: curl -H 'X-User-Id: {member.id}' http://{settings.host}:{settings.port}/projects")
    return 0


def _run(*cmd: str) -> int:
    tool_dir = Path(sys.executable).parent
    return subprocess.call([str(tool_dir / cmd[0]), *cmd[1:]])  # noqa: S603


def _lint(_args: argparse.Namespace, _settings: Settings) -> int:
    return _run("ruff", "check") or _run("ruff", "format", "--check")


def _fmt(_args: argparse.Namespace, _settings: Settings) -> int:
    return _run("ruff", "format") or _run("ruff", "check", "--fix")


def _typecheck(_args: argparse.Namespace, _settings: Settings) -> int:
    return _run("ty", "check")


def _rules(_args: argparse.Namespace, _settings: Settings) -> int:
    return _run("ast-grep", "scan")


def _test(args: argparse.Namespace, _settings: Settings) -> int:
    return _run("pytest", *args.pytest_args)


def _check(args: argparse.Namespace, settings: Settings) -> int:
    for step in (_lint, _typecheck, _rules):
        if code := step(args, settings):
            return code
    return _run("pytest", "-n", "auto")
