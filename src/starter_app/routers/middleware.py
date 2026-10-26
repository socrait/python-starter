import time

import structlog
from asgi_correlation_id import correlation_id
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from starter_app.logger import get_logger

logger = get_logger(__name__)


class AccessLogMiddleware:
    """One structured `request_finished` event per HTTP request, carrying the request id.

    Pure ASGI rather than `BaseHTTPMiddleware`, so streaming responses and context
    variables pass through untouched. Sits inside the request-id middleware.
    """

    def __init__(self, app: ASGIApp):
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=correlation_id.get())
        status_code = 500
        start = time.perf_counter_ns()

        async def _send(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self._app(scope, receive, _send)
        finally:
            logger.info(
                "request_finished",
                method=scope["method"],
                path=scope["path"],
                status_code=status_code,
                duration_ms=round((time.perf_counter_ns() - start) / 1_000_000, 2),
            )


class NoCacheMiddleware:
    """Marks every API response, errors included, as uncacheable by browsers and proxies."""

    def __init__(self, app: ASGIApp):
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        async def _send(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = [
                    (k, v)
                    for k, v in message.get("headers", [])
                    if k.lower() not in (b"cache-control", b"pragma")
                ]
                headers += [(b"cache-control", b"no-store"), (b"pragma", b"no-cache")]
                message["headers"] = headers
            await send(message)

        await self._app(scope, receive, _send)
