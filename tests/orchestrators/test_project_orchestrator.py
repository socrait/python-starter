import pytest
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from starter_app.core.exceptions import (
    InvalidAssigneesError,
    ProjectNotFoundError,
    TaskAlreadyDoneError,
    TaskNotFoundError,
)
from starter_app.core.models import Actor, NewProject, NewTask, TaskStatus
from starter_app.data.pagination import PageRequest
from starter_app.data.records import ProjectRecord, TaskRecord
from starter_app.orchestrators import ProjectOrchestrator
from tests.fixtures.factories import TaskFactory
from tests.fixtures.metrics import counter_points


def test_create_project_with_tasks(
    projects: ProjectOrchestrator,
    metrics_reader: InMemoryMetricReader,
    sample_member: Actor,
    other_member: Actor,
):
    project = projects.create_project(
        sample_member,
        NewProject(
            name="Launch",
            tasks=[
                NewTask(title="Draft", assignee_ids=[other_member.user_id]),
                NewTask(title="Review"),
            ],
        ),
    )

    assert project.owner_id == sample_member.user_id
    assert [p.value for p in counter_points(metrics_reader, "app.projects.created")] == [1]
    tasks = projects.list_tasks(sample_member, project.id, PageRequest()).items
    assert {t.title: t.assignee_ids for t in tasks} == {
        "Draft": [other_member.user_id],
        "Review": [],
    }


def test_create_project_is_all_or_nothing(
    projects: ProjectOrchestrator, session: Session, sample_member: Actor, other_org_admin: Actor
):
    with pytest.raises(InvalidAssigneesError) as excinfo:
        projects.create_project(
            sample_member,
            NewProject(
                name="Launch",
                tasks=[
                    NewTask(title="Fine"),
                    NewTask(title="Cross-tenant", assignee_ids=[other_org_admin.user_id]),
                ],
            ),
        )

    assert excinfo.value.user_ids == {other_org_admin.user_id}
    assert session.scalar(select(func.count()).select_from(ProjectRecord)) == 0
    assert session.scalar(select(func.count()).select_from(TaskRecord)) == 0


def test_create_task_checks_project_visibility(
    projects: ProjectOrchestrator, sample_project: ProjectRecord, other_member: Actor
):
    with pytest.raises(ProjectNotFoundError):
        projects.create_task(other_member, sample_project.id, NewTask(title="Sneaky"))


def test_complete_task_twice_conflicts(
    projects: ProjectOrchestrator,
    make_task: TaskFactory,
    sample_project: ProjectRecord,
    sample_member: Actor,
):
    task = make_task(sample_project)

    completed = projects.complete_task(sample_member, sample_project.id, task.id)

    assert completed.status == TaskStatus.DONE
    with pytest.raises(TaskAlreadyDoneError):
        projects.complete_task(sample_member, sample_project.id, task.id)


def test_complete_unknown_task_is_not_found(
    projects: ProjectOrchestrator, sample_project: ProjectRecord, sample_member: Actor
):
    with pytest.raises(TaskNotFoundError):
        projects.complete_task(sample_member, sample_project.id, "tsk_missing")


def test_delete_project_hides_it(
    projects: ProjectOrchestrator, sample_project: ProjectRecord, sample_admin: Actor
):
    projects.delete_project(sample_admin, sample_project.id)

    with pytest.raises(ProjectNotFoundError):
        projects.get_project(sample_admin, sample_project.id)
    with pytest.raises(ProjectNotFoundError):
        projects.delete_project(sample_admin, sample_project.id)
