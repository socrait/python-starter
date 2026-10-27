import pytest
from sqlalchemy.orm import Session

from starter_app.data.unit_of_work import UnitOfWork
from starter_app.dependencies import make_identity_orchestrator, make_project_orchestrator
from starter_app.metrics import AppMetrics
from starter_app.orchestrators import IdentityOrchestrator, ProjectOrchestrator


@pytest.fixture
def identity(session: Session, uow: UnitOfWork) -> IdentityOrchestrator:
    return make_identity_orchestrator(session, uow)


@pytest.fixture
def projects(
    session: Session, uow: UnitOfWork, identity: IdentityOrchestrator, app_metrics: AppMetrics
) -> ProjectOrchestrator:
    return make_project_orchestrator(session, uow, identity, app_metrics)
