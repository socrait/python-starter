from sqlalchemy.orm import Session

from starter_app.core.models import Actor, TaskStatus
from starter_app.data.pagination import PageRequest
from starter_app.data.records import ProjectRecord
from starter_app.data.repositories import TaskRepository
from tests.starter_app.fixtures.factories import ProjectFactory, TaskFactory


def test_tasks_inherit_project_visibility(
    session: Session,
    make_task: TaskFactory,
    sample_project: ProjectRecord,
    sample_member: Actor,
    sample_admin: Actor,
    other_member: Actor,
    other_org_admin: Actor,
):
    task = make_task(sample_project)
    repo = TaskRepository(session)

    def visible_to(actor: Actor) -> list[str]:
        return [t.id for t in repo.list_tasks(actor, sample_project.id, PageRequest()).items]

    assert visible_to(sample_member) == [task.id]
    assert visible_to(sample_admin) == [task.id]
    assert visible_to(other_member) == []
    assert visible_to(other_org_admin) == []


def test_tasks_of_deleted_project_are_hidden(
    session: Session, make_project: ProjectFactory, make_task: TaskFactory, sample_member: Actor
):
    project = make_project(sample_member, deleted=True)
    task = make_task(project)

    assert TaskRepository(session).get_task(sample_member, project.id, task.id) is None


def test_complete_task_succeeds_once(
    session: Session, make_task: TaskFactory, sample_project: ProjectRecord, sample_member: Actor
):
    task = make_task(sample_project)
    repo = TaskRepository(session)

    assert repo.complete_task(sample_member, sample_project.id, task.id) is True
    assert repo.complete_task(sample_member, sample_project.id, task.id) is False
    completed = repo.get_task(sample_member, sample_project.id, task.id)
    assert completed is not None
    assert completed.status == TaskStatus.DONE
    assert completed.completed_at is not None


def test_complete_task_requires_visibility(
    session: Session, make_task: TaskFactory, sample_project: ProjectRecord, other_org_admin: Actor
):
    task = make_task(sample_project)

    assert (
        TaskRepository(session).complete_task(other_org_admin, sample_project.id, task.id) is False
    )
