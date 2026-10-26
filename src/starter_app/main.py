from collections.abc import AsyncGenerator, MutableMapping
from contextlib import asynccontextmanager
from typing import Any

from asgi_correlation_id import CorrelationIdMiddleware
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry.sdk.metrics import MeterProvider
from sqlalchemy import Engine
from starlette.middleware.body_limit import RequestBodyLimitMiddleware

from starter_app.clients import Authenticator, DevHeaderAuthenticator
from starter_app.config import Settings, get_settings
from starter_app.data.database import make_engine, make_session_factory
from starter_app.logger import configure_logging_from_settings, get_logger
from starter_app.metrics import AppMetrics, make_meter_provider_from_settings
from starter_app.routers import health_router, me_router, projects_router
from starter_app.routers.error_handlers import register_error_handlers
from starter_app.routers.middleware import (
    AccessLogMiddleware,
    DeclaredBodyLimitMiddleware,
    NoCacheMiddleware,
)

logger = get_logger(__name__)

_PROBE_PATHS = frozenset({"/health", "/ready"})


def make_app(
    settings: Settings | None = None,
    *,
    authenticator: Authenticator | None = None,
    engine: Engine | None = None,
    meter_provider: MeterProvider | None = None,
) -> FastAPI:
    """Build the API. Nothing is built at import time, so tests and tools get fresh apps.

    Serve with `uvicorn --factory starter_app.main:make_app`, or `uv run app serve`.
    """
    settings = settings or get_settings()
    configure_logging_from_settings(settings)
    authenticator = authenticator or _default_authenticator(settings)
    # Resources passed in belong to the caller (tests share them); close only our own.
    owns_engine = engine is None
    engine = engine or make_engine(settings)
    owns_meter_provider = meter_provider is None
    meter_provider = meter_provider or make_meter_provider_from_settings(settings)
    metrics = AppMetrics(meter_provider.get_meter(settings.app_name))

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
        logger.info("app_started", environment=settings.environment)
        yield
        if owns_engine:
            engine.dispose()
        if owns_meter_provider:
            meter_provider.shutdown()
        logger.info("app_stopped")

    app = FastAPI(
        title=settings.app_name,
        lifespan=lifespan,
        docs_url="/docs" if settings.docs_enabled else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.docs_enabled else None,
        # FastAPI's own OpenTelemetry instrumentation records the HTTP metrics
        # (http.server.request.duration, http.server.active_requests). Logs stay with
        # structlog; turn tracing on once a tracer provider is configured.
        telemetry={
            "meter_provider": meter_provider,
            "metrics": True,
            "tracing": False,
            "logs": False,
            "exclude": _is_probe,
        },
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = make_session_factory(engine)
    app.state.authenticator = authenticator
    app.state.metrics = metrics

    register_error_handlers(app)
    app.include_router(health_router.router)
    app.include_router(me_router.router)
    app.include_router(projects_router.router)

    # Added innermost first: the request id is assigned before anything logs.
    app.add_middleware(RequestBodyLimitMiddleware, max_body_size=settings.max_request_body_bytes)
    app.add_middleware(DeclaredBodyLimitMiddleware, max_body_size=settings.max_request_body_bytes)
    app.add_middleware(NoCacheMiddleware)
    app.add_middleware(AccessLogMiddleware)
    if settings.cors_allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_allowed_origins,
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=["X-Request-ID"],
        )
    app.add_middleware(CorrelationIdMiddleware, header_name="X-Request-ID")
    return app


def _is_probe(scope: MutableMapping[str, Any]) -> bool:
    # Health checks run every few seconds and would dominate the request metrics.
    return scope.get("path") in _PROBE_PATHS


def _default_authenticator(settings: Settings) -> Authenticator:
    if settings.dev_auth_enabled:
        return DevHeaderAuthenticator()
    raise RuntimeError(
        "No Authenticator configured: pass one to make_app() (dev header auth is local-only)"
    )
