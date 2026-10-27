from fastapi import APIRouter

from starter_app.core.models import Profile
from starter_app.routers.dependencies import ActorDep, IdentityOrchestratorDep

router = APIRouter(prefix="/me", tags=["me"])


@router.get("")
def get_me(actor: ActorDep, identity: IdentityOrchestratorDep) -> Profile:
    return identity.get_profile(actor)
