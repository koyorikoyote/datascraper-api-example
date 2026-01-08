from fastapi import APIRouter, Depends

from src.schemas import DashboardOut, TokenInfo
from src.services import DashboardService
from src.utils.dependencies import get_service, get_current_user

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

DashboardServiceDep = Depends(get_service(DashboardService))

@router.get("/", response_model=DashboardOut)
async def read_dashboard(
    service: DashboardService = DashboardServiceDep,
    token: TokenInfo = Depends(get_current_user),
):
    return service.get_dashboard(token.id)
