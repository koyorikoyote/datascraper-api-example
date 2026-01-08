from fastapi import APIRouter, Depends

from src.schemas import ScoreSetting, TokenInfo
from src.services import ScoreSettingService
from src.utils.dependencies import get_service, get_current_user

router = APIRouter(prefix="/score-settings", tags=["score-settings"])

ScoreSettingDep = Depends(get_service(ScoreSettingService))


@router.get("/", response_model=ScoreSetting)
async def list_score_settings(
    service: ScoreSettingService = ScoreSettingDep,
    token: TokenInfo = Depends(get_current_user),
):
    return service.list_settings()


@router.put("/", response_model=ScoreSetting)
async def update_score_settings(
    settings: ScoreSetting,
    service: ScoreSettingService = ScoreSettingDep,
    token: TokenInfo = Depends(get_current_user),
):
    return service.update_settings(settings)
