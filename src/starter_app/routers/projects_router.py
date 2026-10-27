from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from starter_app.core.models import Actor, NewProject, NewTask, Page, Permission, Project, Task
from starter_app.data.pagination import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, PageRequest
from starter_app.routers.dependencies import ProjectOrchestratorDep, require_permission
from starter_app.routers.resource_loaders import ProjectDep

router = APIRouter(prefix="/projects", tags=["projects"])


def get_page_request(
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
) -> PageRequest:
    return PageRequest(limit=limit, cursor=cursor)


PageRequestDep = Annotated[PageRequest, Depends(get_page_request)]
CanViewProjects = Annotated[Actor, Depends(require_permission(Permission.VIEW_PROJECTS))]
CanCreateProjects = Annotated[Actor, Depends(require_permission(Permission.CREATE_PROJECTS))]
CanDeleteProjects = Annotated[Actor, Depends(require_permission(Permission.DELETE_PROJECTS))]
CanManageTasks = Annotated[Actor, Depends(require_permission(Permission.MANAGE_TASKS))]


@router.get("")
def list_projects(
    actor: CanViewProjects, page: PageRequestDep, projects: ProjectOrchestratorDep
) -> Page[Project]:
    return projects.list_projects(actor, page)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_project(
    body: NewProject, actor: CanCreateProjects, projects: ProjectOrchestratorDep
) -> Project:
    return projects.create_project(actor, body)


@router.get("/{project_id}")
def get_project(project: ProjectDep, _actor: CanViewProjects) -> Project:
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project: ProjectDep, actor: CanDeleteProjects, projects: ProjectOrchestratorDep
) -> None:
    projects.delete_project(actor, project.id)


@router.get("/{project_id}/tasks")
def list_tasks(
    project: ProjectDep,
    actor: CanViewProjects,
    page: PageRequestDep,
    projects: ProjectOrchestratorDep,
) -> Page[Task]:
    return projects.list_tasks(actor, project.id, page)


@router.post("/{project_id}/tasks", status_code=status.HTTP_201_CREATED)
def create_task(
    body: NewTask, project: ProjectDep, actor: CanManageTasks, projects: ProjectOrchestratorDep
) -> Task:
    return projects.create_task(actor, project.id, body)


@router.post("/{project_id}/tasks/{task_id}/complete")
def complete_task(
    task_id: str, project: ProjectDep, actor: CanManageTasks, projects: ProjectOrchestratorDep
) -> Task:
    return projects.complete_task(actor, project.id, task_id)
