from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class DomainModel(BaseModel):
    """Base for domain models and API payloads: snake_case in Python, camelCase on the wire."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_name=True,
        validate_by_alias=True,
        serialize_by_alias=True,
    )


class Role(StrEnum):
    MEMBER = "member"
    ADMIN = "admin"


class Permission(StrEnum):
    VIEW_PROJECTS = "view_projects"
    CREATE_PROJECTS = "create_projects"
    DELETE_PROJECTS = "delete_projects"
    MANAGE_TASKS = "manage_tasks"


_MEMBER_PERMISSIONS = frozenset(
    {Permission.VIEW_PROJECTS, Permission.CREATE_PROJECTS, Permission.MANAGE_TASKS}
)

ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.MEMBER: _MEMBER_PERMISSIONS,
    Role.ADMIN: _MEMBER_PERMISSIONS | {Permission.DELETE_PROJECTS},
}


class Actor(DomainModel):
    """Who is acting, in which organization, with which role: the input to every scoped query."""

    model_config = ConfigDict(frozen=True)

    user_id: str
    org_id: str
    role: Role

    def has_permission(self, permission: Permission) -> bool:
        return permission in ROLE_PERMISSIONS[self.role]


class Org(DomainModel):
    id: str
    name: str
    created_at: datetime


class User(DomainModel):
    id: str
    email: str
    display_name: str
    created_at: datetime


class Profile(DomainModel):
    user: User
    org: Org
    role: Role


class Project(DomainModel):
    id: str
    org_id: str
    owner_id: str
    name: str
    description: str
    created_at: datetime
    updated_at: datetime


class TaskStatus(StrEnum):
    OPEN = "open"
    DONE = "done"


class Task(DomainModel):
    id: str
    project_id: str
    title: str
    status: TaskStatus
    assignee_ids: list[str]
    created_at: datetime
    completed_at: datetime | None


class NewTask(DomainModel):
    title: str = Field(min_length=1, max_length=200)
    assignee_ids: list[str] = Field(default_factory=list, max_length=20)


class NewProject(DomainModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    tasks: list[NewTask] = Field(default_factory=list, max_length=50)


class Page[T](DomainModel):
    items: list[T]
    next_cursor: str | None
