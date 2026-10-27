# Decisions

Cross-cutting decisions and their reasons, newest first. Add an entry when a decision
outlives a single change; when one is reversed, add a new entry rather than editing the old.
<!-- begin: template-repo-only -->

## 2026-10-26: SQLite by default, Postgres on request

Many services run on one machine with durable storage for their whole life, and SQLite
serves them with nothing to operate: write-ahead logging gives concurrent readers, a busy
timeout makes writers queue instead of failing, and backups are file copies. Projects that
need several app instances, or a managed database, choose Postgres when they are generated.
The code is the same either way; only the driver, the local services, and CI differ.

## 2026-10-26: GitHub or GitLab

Generated projects get CI for the forge they choose (GitHub Actions or GitLab CI), running the
same checks. Renovate works on both.

## 2026-10-26: Sync route handlers with sync SQLAlchemy

Handlers are plain `def`; FastAPI runs them in its threadpool. Async SQLAlchemy adds
greenlets, `AsyncSession` lifecycle rules, and lazy-load pitfalls, for throughput most
services don't need. Revisit when a hot path is I/O-bound on something other than the
database; async clients can be added per call site without converting the data layer.

## 2026-10-26: Orchestrators own transactions

Each subsystem has one orchestrator, and each of its public methods is a reentrant unit of
work. Repositories never commit and HTTP never commits. Cross-subsystem calls join the
caller's transaction, so composed operations are atomic without either side knowing the
other's call pattern.

## 2026-10-26: Tenant scoping through QueryScope

Visibility is derived from the actor in one module instead of written into each query.
Tasks inherit visibility from their project through a subquery. The cost is a level of
indirection when reading a repository; the benefit is that a missing tenant filter is a
missing registration, which fails loudly, rather than a silent leak.

## 2026-10-26: camelCase on the wire

Models are snake_case in Python and serialize as camelCase, matching JavaScript clients.
Requests accept both. `DomainModel` carries the configuration.

## 2026-10-26: One error shape

Every error response is `{code, message, requestId}` (plus `details` for validation
errors). Codes are stable for clients to branch on; messages are static so no exception
text, ids, or SQL reach clients. 5xx responses always say `internal_error`, except 503.

## 2026-10-26: Time-ordered ids and keyset pagination

Ids are `<prefix>_<uuid7 hex>`, so ordering by id is creation order. Lists page newest
first with an opaque cursor over the last id: stable under inserts and index-friendly,
unlike offsets.

## 2026-10-26: Tests roll back, including commits

The `session` fixture binds to a connection inside an outer transaction and turns commits
into SAVEPOINT releases. Code under test behaves as in production; nothing persists between
tests; factories don't need teardown. SQLite connections run with the driver's
`autocommit=False` so that SAVEPOINTs and rollbacks are real. A teardown check fails any
test that leaves rows behind. The suite runs on SQLite by default;
`STARTER_APP_TEST_DATABASE_URL` points it at another database.

## 2026-10-26: New databases from the models, existing ones from migrations

`create_all` plus `alembic stamp head` builds a new database from the current schema
instead of replaying history. A test keeps the migrations and models in step.

## 2026-10-26: ty as the type checker

ty is fast and understands Pydantic and SQLAlchemy's typed APIs well enough for this
codebase. If it misses a class of errors you care about, pyright is the fallback.

## 2026-10-26: Architecture rules in ast-grep, suppressed by name

Conventions that a linter can't express (layer boundaries, where commits happen, route
authentication) are ast-grep rules with tests. A suppression must name its rule,
`# sg-ignore(<rule-id>): <reason>`, so it can't silence other rules by accident.

## 2026-10-26: Dependencies wait a week

`exclude-newer = "P7D"` in uv and `minimumReleaseAge` in Renovate keep releases out until
they are a week old, when most broken or compromised releases have been yanked.
<!-- end: template-repo-only -->
