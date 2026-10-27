# starter-app

A FastAPI + SQLAlchemy service starter: layered architecture, tenant-scoped data access,
structured logging, metrics, migrations, a fast test suite, and the tooling to keep it that
way: ruff, ty, architecture rules in ast-grep, pre-commit, CI, and a container image.

It ships with a small working example (orgs, members, projects, and tasks) that shows each
pattern once. Replace it with your own domain; the patterns stay.

<!-- begin: template-repo-only -->
## Start a project from this template

```bash
uvx copier copy gh:socrait/python-starter my-service
```

Copier asks for the project name, the database (SQLite or Postgres), and the forge
(GitHub, GitLab, or neither), then writes a project with this repository's code under your
names. `uvx copier update` later pulls in newer releases. Maintaining the template itself
is covered in [the template guide](docs/guides/guide-maintaining-the-template.md).
<!-- end: template-repo-only -->

## Quick start

Requires [uv](https://docs.astral.sh/uv/) 0.13 or newer (`uv self update`). uv installs
Python 3.15 for you.

```bash
uv sync                      # create .venv with all dependencies
uv run pre-commit install    # run the checks on every commit
uv run app db create         # create the SQLite schema (./starter_app.db)
uv run app seed              # demo org, two users, a project; prints their ids
uv run app serve --reload    # http://127.0.0.1:8000/docs
```

Locally, requests authenticate with an `X-User-Id` header (printed by `app seed`); add
`X-Org-Id` when a user belongs to more than one org:

```bash
curl -H "X-User-Id: usr_..." http://127.0.0.1:8000/projects
```

## Commands

Everything runs through one entry point, `uv run app <command>`:

| Command | What it does |
|---|---|
| `serve [--reload]` | Run the API server |
| `db create` | Create a new database's schema from the models and mark it migrated |
| `db migrate [REV]` | Apply migrations to an existing database (default: head) |
| `db downgrade REV` | Revert migrations, e.g. `-1` |
| `db revision -m MSG` | Autogenerate a migration from model changes |
| `db check` | Fail if the models and the migrations disagree |
| `db current` | Show the applied revision |
| `db reset [--yes]` | Drop and recreate everything (refused when deployed) |
| `seed` | Load demo data (refused when deployed) |
| `test [ARGS]` | pytest; arguments pass through (`app test -k projects -x`) |
| `lint` / `fmt` | ruff check and format check / format and auto-fix |
| `typecheck` | ty |
| `rules` | ast-grep architecture rules |
| `check` | lint, typecheck, rules, then the test suite in parallel |
| `profile` | run the server under Python's sampling profiler (see [Profiling](#profiling)) |

## Layout

```
src/starter_app/
├── main.py            make_app(): the FastAPI app factory
├── cli/               the `app` command
├── config.py          Settings, read from STARTER_APP_* environment variables
├── dependencies.py    builds orchestrators; shared by the API, CLI, and jobs
├── routers/           HTTP: routes, auth dependencies, error handlers, middleware
├── orchestrators/     one per subsystem; each public method is a unit of work
├── data/              records, repositories, QueryScope, migrations, unit of work
├── clients/           wrappers around external services (here: the Authenticator)
├── core/              domain models and exceptions; imports nothing else
├── libs/              app-agnostic mechanisms (logging, metrics setup)
├── logger.py, metrics.py   the app's bindings of those libs
└── utils/
rules/, rule-tests/    ast-grep rules and their tests
tests/starter_app/     mirrors src/starter_app/; fixtures in tests/starter_app/fixtures/
docs/                  architecture, decisions, guides
```

[docs/architecture.md](docs/architecture.md) explains how a request flows through these
layers. Cross-cutting decisions and their reasons go in [docs/decisions.md](docs/decisions.md).

## Configuration

Settings come from `STARTER_APP_*` environment variables or a `.env` file; every setting
and its default is in [config.py](src/starter_app/config.py). The ones you'll set first:

| Variable | Default | Notes |
|---|---|---|
| `STARTER_APP_ENVIRONMENT` | `local` | `local`, `test`, `preview`, `production` |
| `STARTER_APP_DATABASE_URL` | `sqlite:///./starter_app.db` | any SQLAlchemy URL |
| `STARTER_APP_LOG_FORMAT` | text locally, JSON when deployed | |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | unset | OTLP/HTTP collector, e.g. `http://localhost:4318`; the standard OpenTelemetry variables apply |
| `STARTER_APP_CORS_ALLOWED_ORIGINS` | `[]` | JSON list of origins |
| `STARTER_APP_FORWARDED_ALLOW_IPS` | unset (127.0.0.1) | proxies trusted to set `X-Forwarded-*`; set behind a load balancer |
| `STARTER_APP_MAX_REQUEST_BODY_BYTES` | `1048576` | larger request bodies get a 413 |

## Tests

```bash
uv run app test              # in-memory SQLite, about a second
uv run app test -n auto -x   # pytest arguments pass through
```

Each test runs inside a transaction that is rolled back afterwards, including everything
the code under test committed, so tests never see each other's data. CI runs the suite for
Python 3.14 and 3.15.
<!-- begin: postgres-only -->

CI runs it on Postgres, which catches what SQLite forgives. To do the same locally, with
one database per test worker:

```bash
docker compose up -d         # Postgres 18 on 127.0.0.1:5432 (POSTGRES_PORT to change)
STARTER_APP_TEST_DATABASE_URL=postgresql+psycopg://app:app@localhost:5432/app_test \
  uv run app test -n auto
```
<!-- end: postgres-only -->

## Profiling

`app profile` runs the server under Python 3.15's built-in sampling profiler, sampling every
thread on wall-clock time, so the threadpool's request handling and time spent waiting on
the database both show up. Exercise the endpoints, stop the server, and open the flame graph:

```bash
uv run app profile                     # writes profile.html when you stop the server (Ctrl-C)
uv run app profile --duration 30       # stop after 30 seconds
uv run app profile --live              # interactive top-like view
uv run app profile --attach PID        # profile a server that is already running
uv run app profile -- --heatmap        # any other profiler flag passes through
```

On macOS the profiler needs root to read the server's memory: `sudo -E uv run app profile`.
On Linux, profiling a process you start needs no privileges; attaching to another one needs
ptrace permission (`--cap-add SYS_PTRACE` in a container).

## Deploying

```bash
docker build -t starter-app .
docker run --rm -v starter-app-data:/data starter-app app db migrate   # before rolling out
docker run -p 8000:8000 -v starter-app-data:/data starter-app
```

Before the first deploy:

- **Authentication.** The `X-User-Id` header authenticator only runs locally; a deployed
  app refuses to start until you pass a real `Authenticator` (for example, OIDC token
  verification) to `make_app` in [main.py](src/starter_app/main.py).
<!-- begin: sqlite-only -->
- **Database.** SQLite serves a single machine well: one writer at a time, many readers,
  with write-ahead logging on. The image keeps it at `/data/starter_app.db`; mount durable
  storage there (`-v starter-app-data:/data`) and back the file up. If you outgrow one
  machine, switch `STARTER_APP_DATABASE_URL` to Postgres and add `psycopg[binary]`.
<!-- end: sqlite-only -->
<!-- begin: postgres-only -->
- **Database.** Point `STARTER_APP_DATABASE_URL` at Postgres.
<!-- end: postgres-only -->
- **Schema.** Create a new database with `app db create`; upgrade existing ones with
  `app db migrate`.
- **Proxies.** Behind a load balancer, set `STARTER_APP_FORWARDED_ALLOW_IPS` to its address
  range so client addresses and the request scheme come through.
- **Probes.** `/health` answers while the process is up; `/ready` also checks the database.
- **Metrics.** Set `OTEL_EXPORTER_OTLP_ENDPOINT` to export to an OpenTelemetry collector.

## Working with coding agents

[AGENTS.md](AGENTS.md) gives coding agents the commands and the
rules of this codebase. The rules that can be checked mechanically are ast-grep rules in
[rules/](rules), so agents and people get the same feedback from `uv run app check`.
