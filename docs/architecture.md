# Architecture

## Layers

```
            HTTP                      CLI / jobs
              │                           │
   routers/ (auth, errors, middleware)    │
              │                           │
              └──────► orchestrators/ ◄───┘     one per subsystem; owns the transaction
                            │
                  services/ (when needed)        focused, never call each other
                            │
             ┌──────────────┴──────────────┐
          data/                        clients/
   repositories, records,          external services behind
   QueryScope, unit of work        an interface (Authenticator)

   core/  domain models + exceptions: imported by every layer, imports none
   libs/  app-agnostic mechanisms, bound by logger.py and metrics.py
```

Each arrow is an allowed import direction. The ast-grep rules in [rules/](../rules)
enforce the ones that matter most: routers don't touch the data layer, core stays pure, web
frameworks stop at the routers, libs don't import the app, SDKs stay in clients.

## A request, end to end

`POST /projects` with a body of `{"name": "Launch", "tasks": [...]}`:

1. **Middleware.** `CorrelationIdMiddleware` assigns a request id (or accepts the
   caller's `X-Request-ID`); `AccessLogMiddleware` binds it to every log event and, when
   the response finishes, logs `request_finished` and records the duration histogram.
2. **Validation.** FastAPI parses the body into `NewProject`, accepting camelCase or
   snake_case keys. Invalid input returns 422 in the standard error shape.
3. **Authentication.** `get_actor` asks the configured `Authenticator` for a user id, then
   `IdentityOrchestrator.resolve_actor` turns it into an `Actor`: the user, the org they
   act in, and their role there.
4. **Authorization.** The route's gate (`CanCreateProjects`) checks the role's
   permissions. Routes on one resource first load it with the actor's visibility (404 if
   not visible), then check the permission (403).
5. **The operation.** `ProjectOrchestrator.create_project` opens a unit of work, checks
   every assignee is an org member (via `IdentityOrchestrator`, which joins the same
   transaction), inserts the project and its tasks, and commits once. Any failure rolls
   all of it back.
6. **Response.** The orchestrator maps records to `Project`, which FastAPI serializes as
   camelCase. Errors raised anywhere become `{code, message, requestId}`.

## Tenancy

Every tenant-owned table has an `org_id`. Repositories derive their WHERE clause from the
actor with `QueryScope`, which also encodes ownership: members see the projects they own,
admins see every project in their org, and tasks are visible exactly when their project is.
Because scoping is derived in one place, adding a query can't forget it, and a reviewer
checks `query_scope.py` instead of every query.

Users exist outside orgs; `membership` rows give a user a role in an org. A user with
several memberships picks one per request with `X-Org-Id`.

## Transactions

`UnitOfWork.transaction()` wraps every orchestrator entry point. The outermost one commits
or rolls back; nested ones join it, so an orchestrator can call another subsystem's
orchestrator and the whole operation stays atomic. Repositories only flush. The request's
session dependency provides and closes the session but never commits: its cleanup runs
after the response is sent, too late to report a failure.

## Data and migrations

Records use `UtcDateTime` (aware datetimes only, stored as UTC), string-valued enums, and
time-ordered ids (`prj_<uuid7>`), which also give list endpoints a stable newest-first
order for keyset pagination.

New databases are built from the models (`app db create`) and stamped at the latest
migration; existing ones are upgraded with `app db migrate`. A test checks that the
migrations apply, downgrade, re-apply, and produce exactly the models' schema.

## Observability

- **Logs:** structlog events with key-value fields, rendered as text locally and JSON when
  deployed. Library logs (uvicorn, SQLAlchemy, Alembic) go through the same pipeline.
  Tracebacks are structured and omit local variables.
- **Metrics:** OpenTelemetry, exported over OTLP/HTTP when `STARTER_APP_OTLP_ENDPOINT` is
  set. Request duration is labeled by route template, never by raw path.
- **Health:** `/health` (liveness) and `/ready` (database reachable).
