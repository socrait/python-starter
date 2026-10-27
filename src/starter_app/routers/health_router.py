from fastapi import APIRouter, Request
from sqlalchemy.exc import SQLAlchemyError

from starter_app.core.exceptions import ServiceUnavailableError
from starter_app.core.models import DomainModel
from starter_app.data.database import ping
from starter_app.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["health"])


class HealthResponse(DomainModel):
    status: str


# sg-ignore(routes-require-actor): liveness probe touches no tenant data
@router.get("/health")
def health() -> HealthResponse:
    """Liveness: the process is up and serving."""
    return HealthResponse(status="ok")


# sg-ignore(routes-require-actor): readiness probe touches no tenant data
@router.get("/ready")
def ready(request: Request) -> HealthResponse:
    """Readiness: the database answers. Load balancers stop routing here when it doesn't."""
    try:
        ping(request.app.state.engine)
    except SQLAlchemyError as e:
        logger.warning("readiness_check_failed", error_type=type(e).__name__)
        raise ServiceUnavailableError("Database ping failed") from e
    return HealthResponse(status="ok")
