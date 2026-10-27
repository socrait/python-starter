# AGENTS.md

Guide for coding agents working in this repository. Read
[docs/architecture.md](docs/architecture.md) before changing structure, and append to
[docs/decisions.md](docs/decisions.md) when you make a decision that outlives one change.

## Commands

```bash
uv sync                                  # install (uv >= 0.13)
uv run app check                         # lint, typecheck, rules, then the whole suite
uv run app test tests/starter_app/<path> -x   # targeted tests while iterating; flags go to pytest
uv run app lint                          # ruff check + format check (`app fmt` fixes)
uv run app typecheck                     # ty
uv run app rules                         # ast-grep architecture rules
uv run ast-grep test --skip-snapshot-tests   # after editing rules/ or rule-tests/
uv run app db revision -m "add x"        # after changing data/records.py; review the file
uv run app serve --reload                # local server; `app seed` prints test user ids
uv run app profile --duration 30         # flame graph of the server (profile.html)
```

A change is done when `uv run app check` and `uv run pre-commit run --all-files` pass
(pre-commit adds YAML and schema checks for CI, compose, and Renovate files).

## Layers

`routers → orchestrators → (services) → data / clients`, with `core` (domain models,
exceptions) imported by all and importing none. A layer calls only layers below it.

- **Routers** parse input, resolve the actor, call one orchestrator method, return a
  `DomainModel`. No business logic, no repositories, no commits.
- **Orchestrators** are each subsystem's only entry point. Each public method runs in
  `with self._uow.transaction():`; nested calls join the outer transaction. Subsystems call
  each other downward only: `projects → identity`. Network calls happen after the
  transaction, not inside it.
- **Repositories** add, flush, and query. They never commit. ORM records never leave
  `data/`; map them with `data/mappers.py`.
- **Clients** wrap external services and translate their errors into `core/exceptions.py`.
- **libs/** never imports the app; the app binds a lib in a top-level module
  (`logger.py`, `metrics.py`).
- Object graphs are built in `dependencies.py` (framework-free) and wired to FastAPI in
  `routers/dependencies.py`. Constructors only store their dependencies.
- Settings are fields on `Settings` in `config.py`, read from `STARTER_APP_*` variables;
  secrets are `SecretStr`. Operational commands go in `cli/main.py`.

## Data access and tenancy

- Every read or update of tenant data takes `actor: Actor` and starts from
  `QueryScope.from_actor(actor).where(Record)`. Never hand-write `org_id ==` filters in
  those methods. Register each new tenant-owned record type in `data/query_scope.py`.
- Inserts take bare `org_id` / `owner_id` from the caller's actor. Inserts can't carry a
  visibility predicate, so the orchestrator checks the parent is visible first.
- Client-supplied ids of other resources (assignees, related records) are checked against
  the actor's org before use, in one query, not one per id.
- State transitions put the precondition in the `UPDATE ... WHERE` and use `.returning()`;
  never load, check, assign, commit.
- SQLAlchemy 2.x style: `session.execute(select(...))`, never `session.query(...)`.
  Datetimes are timezone-aware UTC (naive ones raise).
- New tables: `TimestampedRecord` or `SoftDeletedRecord`, ids from `genpk(IdPrefix.X)`,
  enums via `string_enum(...)`. Then `app db revision`, read the migration, and keep
  `tests/starter_app/data/test_migrations.py` passing.

## HTTP and security

- Every route depends on an Actor: `ActorDep` or a permission gate (`CanViewProjects`, …).
  Routes on one resource also depend on its loader (`ProjectDep`) first, so an invisible
  resource answers 404 before any 403.
- Not visible (other tenant, other owner) → 404. Visible but not permitted → 403.
- Errors are `AppError` subclasses in `core/exceptions.py` with a `code`, `status_code`, and
  a static `public_message`. Routes raise them; handlers in `routers/error_handlers.py`
  render `{code, message, requestId}`. Never put exception text in a response.
- Request and response bodies are `DomainModel`s: snake_case in Python, camelCase on the
  wire. Routes declare their return type so FastAPI validates and documents the response.

## Logging and metrics

- `logger = get_logger(__name__)`; log events, not sentences:
  `log.info("project_created", project_id=p.id)`. Bind correlating ids with
  `logger.bind(...)`; the request id is bound by middleware.
- `debug` for steps, `info` for an operation's outcome, `warning` for handled surprises,
  `error`/`exception` for failures. Use `exc_info=exc` when not inside the `except` block.
- Metrics go through `AppMetrics` methods named for business events; attributes are
  low-cardinality (never ids, emails, or free text).

## Tests

- Tests mirror `src/`: `tests/starter_app/` holds the tests for `src/starter_app/`, and each
  further package gets its own folder. A package's shared fixtures live in modules under
  `tests/<package>/fixtures/`, loaded by `pytest_plugins` in the root `tests/conftest.py`
  (pytest reads it nowhere else). Tests may import types and helpers from
  those modules (factory Protocols, `counter_points`), never fixtures.
- `make_*` factories create one record variant; `sample_*` fixtures are ready-made graphs.
  Add a factory parameter for a variant instead of mutating a `sample_*` record.
- Tests use the `session` fixture: its work is rolled back afterwards, commits included.
  Don't open other sessions; the fixture fails a test that leaves rows behind.
- Business rules are tested at the orchestrator; routers test the HTTP contract (status,
  shape, error code). Cover the other-owner and other-org cases for every scoped read.
- Mock only at the network boundary.
- The suite runs on in-memory SQLite. `STARTER_APP_TEST_DATABASE_URL` points it at another
  database.

## Rules and suppressions

`rules/` holds ast-grep rules for the conventions above, each with cases in `rule-tests/`.
When a rule is wrong for one statement, suppress that rule only, with a reason:

```python
# sg-ignore(routes-require-actor): liveness probe touches no tenant data
@router.get("/health")
```

Unnamed or mismatched suppressions are ignored. When a rule is wrong in general, fix the
rule and its tests rather than suppressing it repeatedly.
<!-- begin: template-repo-only -->

## This repository is also a Copier template

New projects are generated from this code by [scripts/build_template.py](scripts/build_template.py),
which renames `starter_app` / `starter-app` / `STARTER_APP` and turns marker comments into
conditionals. Treat these lines as code:

- `begin: postgres-only` / `end: postgres-only` (and `sqlite-only`): kept only for that
  database answer. `template-repo-only`: never reaches generated projects.
- Markers are whole comment lines (`#` or `<!-- -->`); put them where removing the block
  leaves valid, formatted code, and keep them out of import blocks.

After changing anything a generated project receives, build and check a variant as in
[the template guide](docs/guides/guide-maintaining-the-template.md#making-a-change).
<!-- end: template-repo-only -->
