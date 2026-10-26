from collections.abc import Mapping
from http import HTTPStatus
from typing import Any

from asgi_correlation_id import correlation_id
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from fastapi.utils import is_body_allowed_for_status_code
from starlette.exceptions import HTTPException

from starter_app.core.exceptions import AppError, AuthenticationError, ErrorCode
from starter_app.logger import get_logger

logger = get_logger(__name__)

_INTERNAL_MESSAGE = "An internal error occurred"

_HTTP_STATUS_CODES: dict[int, ErrorCode] = {
    HTTPStatus.UNAUTHORIZED: ErrorCode.UNAUTHENTICATED,
    HTTPStatus.FORBIDDEN: ErrorCode.FORBIDDEN,
    HTTPStatus.NOT_FOUND: ErrorCode.NOT_FOUND,
    HTTPStatus.METHOD_NOT_ALLOWED: ErrorCode.METHOD_NOT_ALLOWED,
    HTTPStatus.CONTENT_TOO_LARGE: ErrorCode.REQUEST_TOO_LARGE,
}


def register_error_handlers(app: FastAPI) -> None:
    """Every error leaves as `{code, message, requestId}`; 5xx never reveals internals."""
    # Starlette types handlers as taking any Exception, though it only calls each with
    # the class it was registered for.
    app.add_exception_handler(AppError, _handle_app_error)  # ty: ignore[invalid-argument-type]
    app.add_exception_handler(RequestValidationError, _handle_validation_error)  # ty: ignore[invalid-argument-type]
    app.add_exception_handler(HTTPException, _handle_http_exception)  # ty: ignore[invalid-argument-type]
    app.add_exception_handler(Exception, _handle_unexpected)


def error_response(
    status_code: int,
    code: ErrorCode,
    message: str,
    *,
    details: Any = None,
    headers: Mapping[str, str] | None = None,
) -> Response:
    request_id = correlation_id.get()
    # The request-id middleware sits inside the server-error layer, so 5xx responses
    # would otherwise go out without the header.
    all_headers = {**(headers or {}), **({"X-Request-ID": request_id} if request_id else {})}
    if not is_body_allowed_for_status_code(status_code):
        return Response(status_code=status_code, headers=all_headers)
    content: dict[str, Any] = {"code": code, "message": message, "requestId": request_id}
    if details is not None:
        content["details"] = details
    return JSONResponse(status_code=int(status_code), content=content, headers=all_headers)


async def _handle_app_error(_request: Request, exc: AppError) -> Response:
    # 503 is a deliberate signal to retry later, not a leak of internals.
    if exc.status_code >= HTTPStatus.INTERNAL_SERVER_ERROR and (
        exc.status_code != HTTPStatus.SERVICE_UNAVAILABLE
    ):
        logger.error("app_error", code=exc.code, exc_info=exc)
        return error_response(exc.status_code, ErrorCode.INTERNAL_ERROR, _INTERNAL_MESSAGE)
    logger.info("app_error", code=exc.code, status_code=int(exc.status_code), reason=str(exc))
    headers = {"WWW-Authenticate": exc.challenge} if isinstance(exc, AuthenticationError) else None
    return error_response(exc.status_code, exc.code, exc.public_message, headers=headers)


async def _handle_validation_error(_request: Request, exc: RequestValidationError) -> Response:
    details = [{"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]} for e in exc.errors()]
    logger.info("request_invalid", error_count=len(details))
    return error_response(
        HTTPStatus.UNPROCESSABLE_CONTENT,
        ErrorCode.VALIDATION_ERROR,
        "The request is invalid",
        details=details,
    )


async def _handle_http_exception(_request: Request, exc: HTTPException) -> Response:
    if exc.status_code >= HTTPStatus.INTERNAL_SERVER_ERROR:
        logger.error("http_error", status_code=exc.status_code, exc_info=exc)
        return error_response(exc.status_code, ErrorCode.INTERNAL_ERROR, _INTERNAL_MESSAGE)
    # Keep the exception's headers: Allow on a 405, WWW-Authenticate on a 401.
    return error_response(
        exc.status_code,
        _HTTP_STATUS_CODES.get(exc.status_code, ErrorCode.HTTP_ERROR),
        _status_phrase(exc.status_code),
        headers=exc.headers,
    )


async def _handle_unexpected(_request: Request, exc: Exception) -> Response:
    logger.error("unhandled_error", exc_info=exc)
    return error_response(
        HTTPStatus.INTERNAL_SERVER_ERROR, ErrorCode.INTERNAL_ERROR, _INTERNAL_MESSAGE
    )


def _status_phrase(status_code: int) -> str:
    # Starlette accepts non-standard codes (e.g. 499), which HTTPStatus doesn't know.
    try:
        return HTTPStatus(status_code).phrase
    except ValueError:
        return "HTTP error"
