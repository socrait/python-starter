"""Object graph construction, framework-free: used by the API, the CLI, and workers alike."""

from sqlalchemy.orm import Session

from starter_app.data.repositories import (
    MembershipRepository,
    OrgRepository,
    ProjectRepository,
    TaskRepository,
    UserRepository,
)
from starter_app.data.unit_of_work import UnitOfWork
from starter_app.metrics import AppMetrics
from starter_app.orchestrators import IdentityOrchestrator, ProjectOrchestrator


def make_identity_orchestrator(session: Session, uow: UnitOfWork) -> IdentityOrchestrator:
    return IdentityOrchestrator(
        uow, OrgRepository(session), UserRepository(session), MembershipRepository(session)
    )


def make_project_orchestrator(
    session: Session, uow: UnitOfWork, identity: IdentityOrchestrator, metrics: AppMetrics
) -> ProjectOrchestrator:
    return ProjectOrchestrator(
        uow, ProjectRepository(session), TaskRepository(session), identity, metrics
    )
