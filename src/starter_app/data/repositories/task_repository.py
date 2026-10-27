from collections.abc import Collection

from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload

from starter_app.core.models import Actor, TaskStatus
from starter_app.data.pagination import PageRequest, PageSlice, apply_keyset_page, slice_page
from starter_app.data.query_scope import QueryScope
from starter_app.data.records import TaskAssigneeRecord, TaskRecord, utcnow


class TaskRepository:
    def __init__(self, session: Session):
        self._session = session

    def get_task(self, actor: Actor, project_id: str, task_id: str) -> TaskRecord | None:
        predicate = QueryScope.from_actor(actor).where(TaskRecord)
        return self._session.execute(
            select(TaskRecord)
            .options(selectinload(TaskRecord.assignees))
            .where(predicate)
            .where(TaskRecord.project_id == project_id)
            .where(TaskRecord.id == task_id)
        ).scalar_one_or_none()

    def list_tasks(self, actor: Actor, project_id: str, page: PageRequest) -> PageSlice[TaskRecord]:
        predicate = QueryScope.from_actor(actor).where(TaskRecord)
        stmt = (
            select(TaskRecord)
            .options(selectinload(TaskRecord.assignees))
            .where(predicate)
            .where(TaskRecord.project_id == project_id)
        )
        rows = self._session.execute(apply_keyset_page(stmt, TaskRecord.id, page)).scalars().all()
        return slice_page(rows, page, id_of=lambda r: r.id)

    def create_task(
        self, *, org_id: str, project_id: str, title: str, assignee_ids: Collection[str]
    ) -> TaskRecord:
        record = TaskRecord(
            org_id=org_id,
            project_id=project_id,
            title=title,
            assignees=[TaskAssigneeRecord(user_id=user_id) for user_id in assignee_ids],
        )
        self._session.add(record)
        self._session.flush()
        return record

    def complete_task(self, actor: Actor, project_id: str, task_id: str) -> bool:
        """True if a visible open task was marked done; False if missing or already done.

        The status precondition lives in the WHERE clause, so two concurrent completions
        can't both succeed.
        """
        predicate = QueryScope.from_actor(actor).where(TaskRecord)
        completed_id = self._session.execute(
            update(TaskRecord)
            .where(predicate)
            .where(TaskRecord.project_id == project_id)
            .where(TaskRecord.id == task_id)
            .where(TaskRecord.status == TaskStatus.OPEN)
            .values(status=TaskStatus.DONE, completed_at=utcnow())
            .returning(TaskRecord.id)
        ).scalar_one_or_none()
        return completed_id is not None
