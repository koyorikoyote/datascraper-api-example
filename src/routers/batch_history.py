from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks

from src.schemas import BatchHistoryOut, TokenInfo, BatchHistoryExecutionParams
from src.services import BatchHistoryService, KeywordService
from src.utils.dependencies import get_service, get_current_user

router = APIRouter(prefix="/batch-history", tags=["batch-history"])

BatchHistoryServiceDep = Depends(get_service(BatchHistoryService))
KeywordServiceDep = Depends(get_service(KeywordService))

@router.get("/{batch_id}", response_model=BatchHistoryOut)
def read_batch(
    batch_id: int,
    service: BatchHistoryService = BatchHistoryServiceDep,
    token: TokenInfo = Depends(get_current_user),
):
    batch = service.get_batch(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    return batch

@router.post("/", response_model=list[BatchHistoryOut])
def list_batches(
    execution_param: BatchHistoryExecutionParams,
    skip: int = 0,
    limit: int | None = None,
    service: BatchHistoryService = BatchHistoryServiceDep,
    token: TokenInfo = Depends(get_current_user),
):
    return service.list_batches(execution_param.execution_id_list, skip=skip, limit=limit)

@router.post("/{batch_id}/rerun-rank")
def rerun_rank_from_batch(
    batch_id: int,
    background_tasks: BackgroundTasks,
    keyword_service: KeywordService = KeywordServiceDep,
    token: TokenInfo = Depends(get_current_user),
):
    """
    Re-run rank operations for all details in a specific batch history.
    This endpoint processes all details in the batch, regardless of their status.
    The operation runs in the background to prevent timeout issues.
    
    Args:
        batch_id: The ID of the batch history to re-run
        background_tasks: FastAPI background tasks
        
    Returns:
        A dictionary with information about the job being started
    """
    try:
        # Validate the batch exists and is a RANK_FETCH type
        keyword_service.validate_batch_for_rerun(batch_id)
        
        # Add the task to background tasks
        background_tasks.add_task(
            keyword_service.run_rank_from_failed_batch_bg,
            batch_id=batch_id, 
            token=token
        )
        
        return {
            "message": f"Rerun rank operation started for batch ID {batch_id}",
            "batch_id": batch_id,
            "status": "processing"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
