# Adding a resource

Walkthrough for a new tenant-owned resource with its own endpoints, using a hypothetical
`Comment` on a task as the example. Each step names the file that already does the same
thing for projects or tasks: copy its shape.

## 1. Domain model and errors

In [core/models.py](../../src/starter_app/core/models.py), add the response model
(`Comment`) and the input model (`NewComment`), both subclassing `DomainModel`. Put length
limits on input fields with `Field(...)`.

In [core/exceptions.py](../../src/starter_app/core/exceptions.py), add an `ErrorCode`
member and a `CommentNotFoundError(NotFoundError)` with a static `public_message`.

## 2. Record and migration

In [data/records.py](../../src/starter_app/data/records.py), add `CommentRecord`:

- subclass `SoftDeletedRecord` (or `TimestampedRecord` if rows are never deleted)
- `id` defaulting to `genpk(IdPrefix.COMMENT)`; add the prefix in
  [utils/ids.py](../../src/starter_app/utils/ids.py)
- `org_id` and the parent's id as indexed foreign keys
- enums through `string_enum(...)`

Register it in [data/query_scope.py](../../src/starter_app/data/query_scope.py). A record
that belongs to a parent usually inherits the parent's visibility; `TaskRecord` shows how.

Then generate and review the migration:

```bash
uv run app db revision -m "add comment"
uv run app test tests/data/test_migrations.py
```

## 3. Repository and mapper

Add `CommentRepository` in `data/repositories/` and export it from the package
`__init__.py`. Reads take `actor` first and start from `QueryScope`; inserts take bare ids;
nothing commits. Add `map_comment_to_model` to
[data/mappers.py](../../src/starter_app/data/mappers.py).

## 4. Orchestrator

Decide which subsystem owns comments. If it's the projects subsystem, add methods to
[ProjectOrchestrator](../../src/starter_app/orchestrators/project_orchestrator.py) and the
repository to its constructor and to
[dependencies.py](../../src/starter_app/dependencies.py). A new subsystem gets its own
orchestrator; write down in [architecture.md](../architecture.md) which subsystems it may
call.

Wrap each public method in `with self._uow.transaction():`, check the parent is visible
before inserting, and log the outcome as an event.

## 5. Routes

Add routes to an existing router or a new `routers/<name>_router.py` included in
[main.py](../../src/starter_app/main.py). Each route depends on the parent's loader first
(`ProjectDep`), then a permission gate, then the orchestrator. If the resource needs a new
permission, add it to `Permission` and `ROLE_PERMISSIONS`.

## 6. Tests

- Factory: `make_comment` in [tests/fixtures/factories.py](../../tests/fixtures/factories.py),
  with a Protocol.
- Repository: visible to the owner and admin, hidden from another member and another org.
- Orchestrator: the business rules and every error it raises.
- Router: status codes, camelCase payloads, and error codes; not the business rules again.

Finish with `uv run app check`.
