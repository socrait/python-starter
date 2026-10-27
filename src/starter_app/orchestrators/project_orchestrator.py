from starter_app.core.exceptions import (
    InvalidAssigneesError,
    ProjectNotFoundError,
    TaskAlreadyDoneError,
    TaskNotFoundError,
)
from starter_app.core.models import Actor, NewProject, NewTask, Page, Project, Task
from starter_app.data.mappers import map_project_to_model, map_task_to_model
from starter_app.data.pagination import PageRequest
from starter_app.data.repositories import ProjectRepository, TaskRepository
from starter_app.data.unit_of_work import UnitOfWork
from starter_app.logger import get_logger
from starter_app.metrics import AppMetrics
from starter_app.orchestrators.identity_orchestrator import IdentityOrchestrator

logger = get_logger(__name__)


class ProjectOrchestrator:
    """Projects and their tasks. Calls down to IdentityOrchestrator, never the reverse."""

    def __init__(
        self,
        uow: UnitOfWork,
        projects: ProjectRepository,
        tasks: TaskRepository,
        identity: IdentityOrchestrator,
        metrics: AppMetrics,
    ):
        self._uow = uow
        self._projects = projects
        self._tasks = tasks
        self._identity = identity
        self._metrics = metrics

    def get_project(self, actor: Actor, project_id: str) -> Project:
        """Raises ProjectNotFoundError if the project is missing or not visible to the actor."""
        with self._uow.transaction():
            record = self._projects.get_project(actor, project_id)
        if record is None:
            raise ProjectNotFoundError(project_id)
        return map_project_to_model(record)

    def list_projects(self, actor: Actor, page: PageRequest) -> Page[Project]:
        with self._uow.transaction():
            result = self._projects.list_projects(actor, page)
        return Page(
            items=[map_project_to_model(r) for r in result.items], next_cursor=result.next_cursor
        )

    def create_project(self, actor: Actor, new_project: NewProject) -> Project:
        """Create a project with its initial tasks, all or nothing.

        Raises InvalidAssigneesError if any task names an assignee outside the org.
        """
        log = logger.bind(org_id=actor.org_id, user_id=actor.user_id)
        with self._uow.transaction():
            self._ensure_members(actor, {a for t in new_project.tasks for a in t.assignee_ids})
            project = self._projects.create_project(
                org_id=actor.org_id,
                owner_id=actor.user_id,
                name=new_project.name,
                description=new_project.description,
            )
            for new_task in new_project.tasks:
                self._tasks.create_task(
                    org_id=actor.org_id,
                    project_id=project.id,
                    title=new_task.title,
                    assignee_ids=set(new_task.assignee_ids),
                )
        log.info("project_created", project_id=project.id, task_count=len(new_project.tasks))
        self._metrics.record_project_created()
        return map_project_to_model(project)

    def delete_project(self, actor: Actor, project_id: str) -> None:
        """Raises ProjectNotFoundError if the project is missing or not visible to the actor."""
        with self._uow.transaction():
            deleted = self._projects.soft_delete_project(actor, project_id)
        if not deleted:
            raise ProjectNotFoundError(project_id)
        logger.info("project_deleted", org_id=actor.org_id, project_id=project_id)

    def list_tasks(self, actor: Actor, project_id: str, page: PageRequest) -> Page[Task]:
        with self._uow.transaction():
            result = self._tasks.list_tasks(actor, project_id, page)
        return Page(
            items=[map_task_to_model(r) for r in result.items], next_cursor=result.next_cursor
        )

    def create_task(self, actor: Actor, project_id: str, new_task: NewTask) -> Task:
        """Raises ProjectNotFoundError or InvalidAssigneesError."""
        with self._uow.transaction():
            # Inserts can't carry a visibility predicate, so check the parent explicitly.
            if self._projects.get_project(actor, project_id) is None:
                raise ProjectNotFoundError(project_id)
            self._ensure_members(actor, set(new_task.assignee_ids))
            task = self._tasks.create_task(
                org_id=actor.org_id,
                project_id=project_id,
                title=new_task.title,
                assignee_ids=set(new_task.assignee_ids),
            )
        logger.info("task_created", org_id=actor.org_id, project_id=project_id, task_id=task.id)
        return map_task_to_model(task)

    def complete_task(self, actor: Actor, project_id: str, task_id: str) -> Task:
        """Raises TaskNotFoundError, or TaskAlreadyDoneError if it was already completed."""
        with self._uow.transaction():
            completed = self._tasks.complete_task(actor, project_id, task_id)
            task = self._tasks.get_task(actor, project_id, task_id)
        if task is None:
            raise TaskNotFoundError(task_id)
        if not completed:
            raise TaskAlreadyDoneError(task_id)
        logger.info("task_completed", org_id=actor.org_id, project_id=project_id, task_id=task_id)
        self._metrics.record_task_completed()
        return map_task_to_model(task)

    def _ensure_members(self, actor: Actor, user_ids: set[str]) -> None:
        # Client-supplied ids are checked against the org before they reach an insert.
        non_members = self._identity.find_non_members(actor, user_ids)
        if non_members:
            raise InvalidAssigneesError(non_members)
