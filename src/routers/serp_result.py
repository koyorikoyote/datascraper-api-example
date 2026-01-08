from fastapi import APIRouter, Depends, HTTPException, status

from src.schemas import SearchResult, SerpResultOut, TokenInfo
from src.services import SerpResultService
from src.utils.dependencies import get_service, get_current_user

router = APIRouter(prefix="/serp-results", tags=["serp-results"])

SerpResultServiceDep = Depends(get_service(SerpResultService))

@router.post("/keywords/{keyword_id}/", response_model=SerpResultOut, status_code=status.HTTP_201_CREATED)
def create_result(
    keyword_id: int,
    result_in: SearchResult,
    service: SerpResultService = SerpResultServiceDep,
    token: TokenInfo = Depends(get_current_user),
):
    return service.create_result(keyword_id, result_in)


@router.get("/keywords/{keyword_id}/", response_model=list[SerpResultOut])
def list_results(
    keyword_id: int,
    skip: int = 0,
    limit: int | None = None,
    service: SerpResultService = SerpResultServiceDep,
    token: TokenInfo = Depends(get_current_user),
):
    return service.list_results(keyword_id, skip=skip, limit=limit)


@router.get("/{serp_id}/", response_model=SerpResultOut)
def read_result(
    serp_id: int,
    service: SerpResultService = SerpResultServiceDep,
    token: TokenInfo = Depends(get_current_user),
):
    result = service.get_result(serp_id)
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")
    return result


@router.put("/{serp_id}/", response_model=SerpResultOut)
def update_result(
    serp_id: int,
    result_in: SearchResult,
    service: SerpResultService = SerpResultServiceDep,
    token: TokenInfo = Depends(get_current_user),
):
    updated = service.update_result(serp_id, result_in)
    if not updated:
        raise HTTPException(status_code=404, detail="Result not found")
    return updated


@router.delete("/{serp_id}/", status_code=status.HTTP_204_NO_CONTENT)
def delete_result(
    serp_id: int,
    service: SerpResultService = SerpResultServiceDep,
    token: TokenInfo = Depends(get_current_user),
):
    success = service.delete_result(serp_id)
    if not success:
        raise HTTPException(status_code=404, detail="Result not found")
    return None
