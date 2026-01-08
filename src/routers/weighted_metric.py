from fastapi import APIRouter, Depends, HTTPException, status

from src.schemas import (
    WeightedMetricOut,
    WeightedMetricCreate,
    WeightedMetricUpdate,
    TokenInfo,
)
from src.services import WeightedMetricService
from src.utils.dependencies import get_service, get_current_user

router = APIRouter(prefix="/weighted-metrics", tags=["weighted-metrics"])

WeightedMetricServiceDep = Depends(get_service(WeightedMetricService))


@router.post("/", response_model=WeightedMetricOut, status_code=status.HTTP_201_CREATED)
async def create_metric(
    metric_in: WeightedMetricCreate,
    service: WeightedMetricService = WeightedMetricServiceDep,
    token: TokenInfo = Depends(get_current_user),
):
    return service.create_metric(metric_in)


@router.get("/{metric_id}/", response_model=WeightedMetricOut)
async def read_metric(
    metric_id: int,
    service: WeightedMetricService = WeightedMetricServiceDep,
    token: TokenInfo = Depends(get_current_user),
):
    metric = service.get_metric(metric_id)
    if not metric:
        raise HTTPException(status_code=404, detail="Metric not found")
    return metric


@router.get("/", response_model=list[WeightedMetricOut])
async def list_metrics(
    skip: int = 0,
    limit: int | None = None,
    service: WeightedMetricService = WeightedMetricServiceDep,
    token: TokenInfo = Depends(get_current_user),
):
    return service.list_metrics(skip=skip, limit=limit)


@router.put("/{metric_id}/", response_model=WeightedMetricOut)
async def update_metric(
    metric_id: int,
    metric_in: WeightedMetricUpdate,
    service: WeightedMetricService = WeightedMetricServiceDep,
    token: TokenInfo = Depends(get_current_user),
):
    updated = service.update_metric(metric_id, metric_in)
    if not updated:
        raise HTTPException(status_code=404, detail="Metric not found")
    return updated


@router.delete("/{metric_id}/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_metric(
    metric_id: int,
    service: WeightedMetricService = WeightedMetricServiceDep,
    token: TokenInfo = Depends(get_current_user),
):
    success = service.delete_metric(metric_id)
    if not success:
        raise HTTPException(status_code=404, detail="Metric not found")
    return None
