from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import Response
from sqlalchemy.orm import Session
from src.schemas import KeywordOut, KeywordCreate, KeywordUpdate, KeywordBulk, KeywordComputedOut, SerpResponse, TokenInfo
from src.services import KeywordService, SerpService
from src.services.sqs_producer import SQSProducerService
from src.utils.dependencies import get_service, get_current_user, get_db
from src.utils.constants import StatusConst
import os

router = APIRouter(prefix="/keywords", tags=["keywords"])

KeywordServiceDep = Depends(get_service(KeywordService))
SerpServiceDep = Depends(get_service(SerpService))

@router.post("/", response_model=KeywordOut, status_code=status.HTTP_201_CREATED)
def create_keyword(
    keyword_in: KeywordCreate,
    service: KeywordService = KeywordServiceDep,
    token: TokenInfo = Depends(get_current_user),
):
    return service.create_keyword(keyword_in, token)


@router.get("/{keyword_id}/", response_model=KeywordOut)
def read_keyword(
    keyword_id: int,
    service: KeywordService = KeywordServiceDep,
    token: TokenInfo = Depends(get_current_user),
):
    keyword = service.get_keyword(keyword_id)
    if not keyword:
        raise HTTPException(status_code=404, detail="Keyword not found")
    return keyword


@router.get("/", response_model=list[KeywordComputedOut])
def list_keywords(
    skip: int = 0,
    limit: int | None = None,
    service: KeywordService = KeywordServiceDep,
    token: TokenInfo = Depends(get_current_user),
):
    return service.list_keywords(skip=skip, limit=limit)


@router.put("/{keyword_id}/", response_model=KeywordOut)
def update_keyword(
    keyword_id: int,
    keyword_in: KeywordUpdate,
    service: KeywordService = KeywordServiceDep,
    token: TokenInfo = Depends(get_current_user),
):
    updated = service.update_keyword(keyword_id, keyword_in)
    if not updated:
        raise HTTPException(status_code=404, detail="Keyword not found")
    return updated


@router.delete("/{keyword_id}/", status_code=status.HTTP_204_NO_CONTENT)
def delete_keyword(
    keyword_id: int,
    service: KeywordService = KeywordServiceDep,
    token: TokenInfo = Depends(get_current_user),
):
    success = service.delete_keyword(keyword_id)
    return None


@router.post("/bulk-delete/", status_code=status.HTTP_204_NO_CONTENT)
def delete_keywords_bulk(
    ids_in: KeywordBulk,
    service: KeywordService = KeywordServiceDep,
    token: TokenInfo = Depends(get_current_user),
):
    deleted = service.delete_keywords_bulk(ids_in.ids)
    if deleted == 0:
        raise HTTPException(status_code=404, detail="Keywords not found")
    return None

@router.post("/run-fetch/", response_model=dict)
def run_fetch(
    ids_in: KeywordBulk,
    background_tasks: BackgroundTasks,
    service: KeywordService = KeywordServiceDep,
    token: TokenInfo = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service._verify_hubspot_token(token) # raises 401 if invalid

    use_sqs = os.getenv("SQS_JOB_QUEUE_URL")

    # Log for debugging
    import logging
    logging.info(f"run-fetch: SQS_JOB_QUEUE_URL = {use_sqs}")

    # Identify current statuses but ALLOW re-queuing even if processing (to fix stuck jobs)
    from src.models.keyword import Keyword
    # We don't filter out processing items anymore
    
    ids_processing = []
    ids_to_process = list(ids_in.ids)
    results = []

    # Old logic removed:
    # for kw_id, status in current_keywords:
    #     if status == StatusConst.PROCESSING:
    #         ids_processing.append(kw_id)
    #         results.append({"id": kw_id, "status": StatusConst.PROCESSING})
    #     else:
    #         ids_to_process.append(kw_id)

    # Simplified: Process ALL requested IDs

         
    # From here, we only work with ids_to_process

    if use_sqs:
        try:
            sqs_service = SQSProducerService(db=db)
            
            # Check queue depth to decide status
            # queue_attrs = sqs_service.get_queue_attributes()
            initial_status = StatusConst.WAITING
            
            # if queue_attrs:
            #     approx_msgs = int(queue_attrs.get('ApproximateNumberOfMessages', 0))
            #     approx_not_visible = int(queue_attrs.get('ApproximateNumberOfMessagesNotVisible', 0))
                
            #     # If there are messages in queue or processing, set to WAITING
            #     if approx_msgs > 0 or approx_not_visible > 0:
            #         initial_status = StatusConst.WAITING

            # Set status to WAITING in DB so worker picks it up (if set to PROCESSING, worker skips it)
            if ids_to_process:
                service.set_fetch_status(ids_to_process, StatusConst.WAITING)
                
                result = sqs_service.send_fetch_job(
                    keyword_ids=ids_to_process,
                    token=token,
                    metadata={"source": "api"},
                    db=db
                )
                logging.info(f"Successfully sent fetch job to SQS queue: {result}")
                
                # Add these to results
                for kw_id in ids_to_process:
                    results.append({"id": kw_id, "status": initial_status})
                    
                return {
                    "status": "mixed",
                    "job_id": result["job_id"],
                    "message_id": result["message_id"],
                    "ids": ids_in.ids,
                    "results": results
                }
            else:
                 return {
                     "status": "processing",
                     "ids": ids_in.ids,
                     "results": results
                 }
                 
        except Exception as e:
            # Fallback to background task if SQS fails
            logging.error(f"Failed to send to SQS, falling back to background task: {str(e)}")
            background_tasks.add_task(service.run_fetch, ids_to_process, token)
            
            # Add fallback statuses
            for kw_id in ids_to_process:
                results.append({"id": kw_id, "status": StatusConst.WAITING})
                
            return {"status": StatusConst.WAITING, "ids": ids_in.ids, "date": results, "note": "Using background task due to SQS error"}
    else:
        # Use existing background task implementation
        logging.info("No SQS_JOB_QUEUE_URL configured, using background task")
        if ids_to_process:
            background_tasks.add_task(service.run_fetch, ids_to_process, token)
            for kw_id in ids_to_process:
                results.append({"id": kw_id, "status": StatusConst.WAITING})
                
        return {"status": StatusConst.WAITING, "ids": ids_in.ids, "results": results}

@router.post("/run-rank/")
def run_rank(
    ids_in: KeywordBulk,
    background_tasks: BackgroundTasks,
    service: KeywordService = KeywordServiceDep,
    token: TokenInfo = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    use_sqs = os.getenv("SQS_JOB_QUEUE_URL")

    # Log for debugging
    import logging
    logging.info(f"run-rank: SQS_JOB_QUEUE_URL = {use_sqs}")
    
    # Identify current statuses but ALLOW re-queuing even if processing
    from src.models.keyword import Keyword
    
    # We apply same logic as run_fetch, allow re-queueing
    ids_processing = []
    ids_to_process = list(ids_in.ids)
    results = []
    
    # Old logic removed:
    # current_keywords = db.query(Keyword.id, Keyword.rank_status).filter(Keyword.id.in_(ids_in.ids)).all()
    # ... filtering loop ...

    if use_sqs:
        try:
            sqs_service = SQSProducerService(db=db)
            
            # Check queue depth to decide status
            # queue_attrs = sqs_service.get_queue_attributes()
            initial_status = StatusConst.WAITING
            
            # if queue_attrs:
            #     approx_msgs = int(queue_attrs.get('ApproximateNumberOfMessages', 0))
            #     approx_not_visible = int(queue_attrs.get('ApproximateNumberOfMessagesNotVisible', 0))
                
            #     # If there are messages in queue or processing, set to WAITING
            #     if approx_msgs > 0 or approx_not_visible > 0:
            #         initial_status = StatusConst.WAITING

            if ids_to_process:
                # Set status to WAITING in DB so worker picks it up
                service.set_rank_status(ids_to_process, StatusConst.WAITING)
                
                result = sqs_service.send_full_rank_job(
                    keyword_ids=ids_to_process,
                    token=token,
                    metadata={"source": "api"},
                    db=db
                )
                logging.info(f"Successfully sent full rank job to SQS queue: {result}")
                
                for kw_id in ids_to_process:
                    results.append({"id": kw_id, "status": initial_status})
                
                return {
                    "status": "mixed",
                    "job_id": result["job_id"],
                    "message_id": result["message_id"],
                    "ids": ids_in.ids,
                    "results": results
                }
            else:
                return {
                    "status": "mixed",
                    "ids": ids_in.ids,
                    "results": results
                }
        except Exception as e:
            # Fallback to background task if SQS fails
            logging.error(f"Failed to send to SQS, falling back to background task: {str(e)}")
            background_tasks.add_task(service.run_rank, ids_to_process, token)
            
            for kw_id in ids_to_process:
                results.append({"id": kw_id, "status": StatusConst.WAITING})
                
            return {"status": StatusConst.WAITING, "ids": ids_in.ids, "results": results, "note": "Using background task due to SQS error"}
    else:
        # Use existing background task implementation
        logging.info("No SQS_JOB_QUEUE_URL configured, using background task")
        if ids_to_process:
            background_tasks.add_task(service.run_rank, ids_to_process, token)
            for kw_id in ids_to_process:
                results.append({"id": kw_id, "status": StatusConst.WAITING})
        return {"status": StatusConst.WAITING, "ids": ids_in.ids, "results": results}

@router.post("/run-partial-rank/")
def run_partialrank(
    ids_in: KeywordBulk,
    background_tasks: BackgroundTasks,
    service: KeywordService = KeywordServiceDep,
    token: TokenInfo = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    use_sqs = os.getenv("SQS_JOB_QUEUE_URL")

    # Log for debugging
    import logging
    logging.info(f"run-partial-rank: SQS_JOB_QUEUE_URL = {use_sqs}")
    
    # Identify current statuses but ALLOW re-queuing even if processing
    from src.models.keyword import Keyword
    
    # We apply same logic as run_fetch, allow re-queueing
    ids_processing = []
    ids_to_process = list(ids_in.ids)
    results = []

    # Old logic removed:
    # current_keywords = db.query(Keyword.id, Keyword.partial_rank_status).filter(Keyword.id.in_(ids_in.ids)).all()
    # ... filtering loop ...

    if use_sqs:
        try:
            sqs_service = SQSProducerService(db=db)
            
            # Check queue depth to decide status
            # queue_attrs = sqs_service.get_queue_attributes()
            initial_status = StatusConst.WAITING
            
            # if queue_attrs:
            #     approx_msgs = int(queue_attrs.get('ApproximateNumberOfMessages', 0))
            #     approx_not_visible = int(queue_attrs.get('ApproximateNumberOfMessagesNotVisible', 0))
                
            #     # If there are messages in queue or processing, set to WAITING
            #     if approx_msgs > 0 or approx_not_visible > 0:
            #         initial_status = StatusConst.WAITING

            if ids_to_process:
                # Set status to WAITING in DB so worker picks it up
                service.set_partial_rank_status(ids_to_process, StatusConst.WAITING)
                
                result = sqs_service.send_partial_rank_job(
                    keyword_ids=ids_to_process,
                    token=token,
                    metadata={"source": "api"},
                    db=db
                )
                
                for kw_id in ids_to_process:
                    results.append({"id": kw_id, "status": initial_status})
                    
                return {
                    "status": "processing",
                    "job_id": result["job_id"],
                    "message_id": result["message_id"],
                    "ids": ids_in.ids,
                    "results": results
                }
            else:
                 return {
                    "status": "processing",
                    "ids": ids_in.ids,
                    "results": results
                }
        except Exception as e:
            # Fallback to background task if SQS fails
            import logging
            logging.error(f"Failed to send to SQS, falling back to background task: {str(e)}")
            background_tasks.add_task(service.run_partial_rank, ids_to_process, token)
            
            for kw_id in ids_to_process:
                results.append({"id": kw_id, "status": StatusConst.WAITING})
                
            return {"status": StatusConst.WAITING, "ids": ids_in.ids, "results": results, "note": "Using background task due to SQS error"}
    else:
        # Use existing background task implementation
        if ids_to_process:
            background_tasks.add_task(service.run_partial_rank, ids_to_process, token)
            for kw_id in ids_to_process:
                results.append({"id": kw_id, "status": StatusConst.WAITING})
        return {"status": StatusConst.WAITING, "ids": ids_in.ids, "results": results}

@router.post("/run-fetch-and-rank-scheduled/")
def run_fetch_and_rank_scheduled(
    background_tasks: BackgroundTasks,
    service: KeywordService = KeywordServiceDep,
    token: TokenInfo = Depends(get_current_user),
):
    """
    Run fetch and rank operations for all scheduled keywords.
    This endpoint does not require any parameters as it automatically
    processes all keywords that have is_scheduled set to true.
    """
    background_tasks.add_task(service.run_fetch_and_rank_scheduled, token=token)
    return {"status": "processing"}


@router.post("/export/csv/")
def export_csv(
    ids_in: KeywordBulk,
    service: KeywordService = KeywordServiceDep,
    token: TokenInfo = Depends(get_current_user),
):
    """Export SERP results to CSV file"""
    csv_content, encoded_filename  = service.export_to_csv(ids_in.ids, token)
        
    return Response(
        content=csv_content,
        media_type="text/csv; charset=utf-8",
        headers={
            # RFC 5987-compliant
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
        }
    )
    
@router.post("/import/")
def import_keywords(
    file: UploadFile = File(...),
    service: KeywordService = KeywordServiceDep,
    token: TokenInfo = Depends(get_current_user),
):
    result = service.import_keywords_bytes(file.file.read(), file.filename, token)
    return result

@router.post("/unstick-processing/{keyword_id}/")
def unstick_processing_records(
    keyword_id: int,
    service: KeywordService = KeywordServiceDep,
    token: TokenInfo = Depends(get_current_user),
):
    """
    Find and update records with 'processing' status to 'pending' for a specific keyword.
    This updates both the keyword record and its associated SERP results.
    """
    # Check if keyword exists
    keyword = service.get_keyword(keyword_id)
    if not keyword:
        raise HTTPException(status_code=404, detail="Keyword not found")
    
    result = service.unstick_processing_records(keyword_id)
    return result
