from enum import StrEnum
from http import HTTPStatus


class ErrorCode(StrEnum):
    INTERNAL_ERROR = "internal_error"
    SERVICE_UNAVAILABLE = "service_unavailable"
    VALIDATION_ERROR = "validation_error"
    HTTP_ERROR = "http_error"
    REQUEST_TOO_LARGE = "request_too_large"
    NOT_FOUND = "not_found"
    METHOD_NOT_ALLOWED = "method_not_allowed"
    UNAUTHENTICATED = "unauthenticated"
    FORBIDDEN = "forbidden"
    ORG_REQUIRED = "org_required"
    INVALID_CURSOR = "invalid_cursor"
    PROJECT_NOT_FOUND = "project_not_found"
    TASK_NOT_FOUND = "task_not_found"
    TASK_ALREADY_DONE = "task_already_done"
    INVALID_ASSIGNEES = "invalid_assignees"


class AppError(Exception):
    """Base for errors the application knows how to describe.

    The exception message is for logs and may carry ids; `public_message` is static and is
    the only text a client ever sees.
    """

    code: ErrorCode = ErrorCode.INTERNAL_ERROR
    status_code: HTTPStatus = HTTPStatus.INTERNAL_SERVER_ERROR
    public_message: str = "An internal error occurred"


class ServiceUnavailableError(AppError):
    """A dependency (database, upstream service) can't serve requests right now."""

    code = ErrorCode.SERVICE_UNAVAILABLE
    status_code = HTTPStatus.SERVICE_UNAVAILABLE
    public_message = "Service unavailable"


class AuthenticationError(AppError):
    code = ErrorCode.UNAUTHENTICATED
    status_code = HTTPStatus.UNAUTHORIZED
    public_message = "Authentication required"

    def __init__(self, message: str, *, challenge: str):
        super().__init__(message)
        # The auth scheme the client should use, sent back as WWW-Authenticate.
        self.challenge = challenge


class PermissionDeniedError(AppError):
    code = ErrorCode.FORBIDDEN
    status_code = HTTPStatus.FORBIDDEN
    public_message = "Forbidden"

    def __init__(self, permission: str):
        super().__init__(f"Missing permission: {permission}")
        self.permission = permission


class NoOrgAccessError(PermissionDeniedError):
    def __init__(self, user_id: str):
        super().__init__("org membership")
        self.user_id = user_id


class OrgSelectionRequiredError(AppError):
    code = ErrorCode.ORG_REQUIRED
    status_code = HTTPStatus.BAD_REQUEST
    public_message = "Select an organization with the X-Org-Id header"


class NotFoundError(AppError):
    code = ErrorCode.NOT_FOUND
    status_code = HTTPStatus.NOT_FOUND
    public_message = "Not found"


# A user who is not a member of an org gets the same answer as for an org that doesn't exist.
class OrgNotFoundError(NotFoundError):
    def __init__(self, org_id: str):
        super().__init__(f"Org not found: {org_id}")
        self.org_id = org_id


class ProjectNotFoundError(NotFoundError):
    code = ErrorCode.PROJECT_NOT_FOUND
    public_message = "Project not found"

    def __init__(self, project_id: str):
        super().__init__(f"Project not found: {project_id}")
        self.project_id = project_id


class TaskNotFoundError(NotFoundError):
    code = ErrorCode.TASK_NOT_FOUND
    public_message = "Task not found"

    def __init__(self, task_id: str):
        super().__init__(f"Task not found: {task_id}")
        self.task_id = task_id


class TaskAlreadyDoneError(AppError):
    code = ErrorCode.TASK_ALREADY_DONE
    status_code = HTTPStatus.CONFLICT
    public_message = "Task is already done"

    def __init__(self, task_id: str):
        super().__init__(f"Task already done: {task_id}")
        self.task_id = task_id


class InvalidAssigneesError(AppError):
    code = ErrorCode.INVALID_ASSIGNEES
    status_code = HTTPStatus.UNPROCESSABLE_CONTENT
    public_message = "Every assignee must be a member of the organization"

    def __init__(self, user_ids: set[str]):
        super().__init__(f"Not org members: {sorted(user_ids)}")
        self.user_ids = user_ids


class InvalidCursorError(AppError):
    code = ErrorCode.INVALID_CURSOR
    status_code = HTTPStatus.BAD_REQUEST
    public_message = "Invalid pagination cursor"
