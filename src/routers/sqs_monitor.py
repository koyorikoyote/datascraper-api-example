from fastapi import APIRouter, Depends, Query, HTTPException
from typing import Optional, List
from sqlalchemy.orm import Session

from src.schemas.sqs_monitor import SQSMonitorResponse, SQSDeleteRequest, SQSDeleteResponse
from src.schemas.sqs_message_history import SQSMessageHistoryOut, MessageStatusEnum
from src.schemas.user import TokenInfo
from src.services.sqs_monitor import SQSMonitorService
from src.repositories.sqs_message_history import SQSMessageHistoryRepository
from src.models.sqs_message_history import MessageStatus as DBMessageStatus
from src.utils.dependencies import get_current_user, get_db

router = APIRouter(prefix="/sqs", tags=["sqs-monitor"])


@router.get("/messages", response_model=SQSMonitorResponse)
async def get_all_sqs_messages(
    max_messages: int = Query(default=100, ge=1, le=1000, description="Maximum messages to fetch per queue"),
    include_in_flight: bool = Query(default=False, description="Attempt to peek at in-flight messages (may briefly affect processing)"),
    token: TokenInfo = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all messages currently in SQS queues (both main queue and DLQ).

    This endpoint provides visibility into:
    - Messages waiting to be processed (available)
    - Messages currently being processed (in-flight)
    - Failed messages in the dead letter queue

    Note: This reads messages without removing them from the queue.

    Args:
        max_messages: Maximum number of messages to fetch per queue (1-1000)
        include_in_flight: If True, attempts to peek at in-flight messages by temporarily
                          making them visible (use with caution in production)

    Returns:
        SQSMonitorResponse with all message details and summary statistics
    """
    try:
        service = SQSMonitorService(db=db)
        return service.get_all_messages(
            max_messages=max_messages,
            db=db,
            include_in_flight=include_in_flight
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch SQS messages: {str(e)}")


@router.get("/queue/stats")
async def get_queue_statistics(
    token: TokenInfo = Depends(get_current_user)
):
    """
    Get basic queue statistics without fetching individual messages.

    This is a lightweight endpoint that returns queue attributes like:
    - ApproximateNumberOfMessages (available messages)
    - ApproximateNumberOfMessagesNotVisible (in-flight messages)
    - ApproximateAgeOfOldestMessage
    - And other queue metrics

    Returns:
        Dictionary with queue statistics for both main queue and DLQ
    """
    try:
        service = SQSMonitorService()
        return service.get_queue_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch queue stats: {str(e)}")


@router.delete("/messages", response_model=SQSDeleteResponse)
async def delete_sqs_message(
    request: SQSDeleteRequest,
    token: TokenInfo = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete/Cancel a message from the SQS queue.

    This endpoint can only delete messages that are AVAILABLE (not yet being processed).
    Messages that are IN_FLIGHT (being processed) cannot be deleted.

    You must provide both the message_id and receipt_handle from the GET /messages response.

    Args:
        request: Contains message_id and receipt_handle

    Returns:
        SQSDeleteResponse indicating success or failure

    Example:
        If GET /messages returns:
        {
            "message_id": "abc-123",
            "receipt_handle": "AQEBm3KN...",
            "status": "available"
        }

        You can delete it by sending:
        {
            "message_id": "abc-123",
            "receipt_handle": "AQEBm3KN..."
        }
    """
    try:
        service = SQSMonitorService(db=db)
        return service.delete_message(
            message_id=request.message_id,
            receipt_handle=request.receipt_handle
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete message: {str(e)}")


@router.get("/history", response_model=List[SQSMessageHistoryOut])
async def get_sqs_message_history(
    limit: int = Query(default=10, ge=1, le=100, description="Number of records to retrieve"),
    status: Optional[List[MessageStatusEnum]] = Query(default=None, description="Filter by one or more statuses"),
    user_id: Optional[int] = Query(default=None, description="Filter by user ID"),
    token: TokenInfo = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get recent SQS message history from the database.

    This endpoint retrieves historical records of SQS messages, including:
    - Messages that were successfully processed
    - Failed messages with error details
    - Messages currently being processed
    - Deleted messages

    Args:
        limit: Number of records to retrieve (1-100, default 10)
        status: Optional filter by one or more message statuses (can provide multiple)
        user_id: Optional filter by user ID

    Returns:
        List of SQSMessageHistoryOut records ordered by creation time (newest first)

    Examples:
        - /history?status=completed&status=failed (get completed and failed messages)
        - /history?status=processing (get only processing messages)
        - /history (get all messages)
    """
    try:
        repo = SQSMessageHistoryRepository(db)

        # Convert status enum(s) if provided
        db_status = None
        if status:
            status_map = {
                MessageStatusEnum.QUEUED: DBMessageStatus.QUEUED,
                MessageStatusEnum.PROCESSING: DBMessageStatus.PROCESSING,
                MessageStatusEnum.COMPLETED: DBMessageStatus.COMPLETED,
                MessageStatusEnum.FAILED: DBMessageStatus.FAILED,
                MessageStatusEnum.DLQ: DBMessageStatus.DLQ,
                MessageStatusEnum.CANCELLED: DBMessageStatus.CANCELLED,
                MessageStatusEnum.DELETED: DBMessageStatus.DELETED
            }
            db_status = [status_map[s] for s in status if s in status_map]

        # Get messages based on filters
        if user_id:
            messages = repo.get_by_user_id(user_id, status=db_status, limit=limit)
        else:
            messages = repo.get_recent_messages(status=db_status, limit=limit)

        # Convert to response schema
        return [
            SQSMessageHistoryOut(
                id=msg.id,
                sqs_message_id=msg.sqs_message_id,
                job_id=msg.job_id,
                message_type=msg.message_type.value if msg.message_type else None,
                keyword_ids=msg.keyword_ids,
                user_id=msg.user_id,
                user_full_name=msg.user_full_name,
                status=msg.status.value,
                retry_count=msg.retry_count,
                queue_name=msg.queue_name,
                error_details=msg.error_details,
                error_code=msg.error_code,
                queued_at=msg.queued_at,
                started_processing_at=msg.started_processing_at,
                completed_at=msg.completed_at,
                receive_count=msg.receive_count,
                visibility_timeout=msg.visibility_timeout,
                created_at=msg.created_at,
                updated_at=msg.updated_at,
                message_body=msg.message_body
            )
            for msg in messages
        ]

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch message history: {str(e)}")


@router.get("/history/failed", response_model=List[SQSMessageHistoryOut])
async def get_failed_sqs_messages(
    limit: int = Query(default=10, ge=1, le=100, description="Number of records to retrieve"),
    include_dlq: bool = Query(default=True, description="Include dead letter queue messages"),
    token: TokenInfo = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get recent failed SQS messages with error details.

    This endpoint specifically retrieves messages that failed processing,
    showing the error details and reasons for failure.

    Args:
        limit: Number of records to retrieve (1-100, default 10)
        include_dlq: Whether to include messages in the dead letter queue

    Returns:
        List of failed SQSMessageHistoryOut records with error details
    """
    try:
        repo = SQSMessageHistoryRepository(db)
        messages = repo.get_failed_messages(include_dlq=include_dlq, limit=limit)

        # Convert to response schema
        return [
            SQSMessageHistoryOut(
                id=msg.id,
                sqs_message_id=msg.sqs_message_id,
                job_id=msg.job_id,
                message_type=msg.message_type.value if msg.message_type else None,
                keyword_ids=msg.keyword_ids,
                user_id=msg.user_id,
                user_full_name=msg.user_full_name,
                status=msg.status.value,
                retry_count=msg.retry_count,
                queue_name=msg.queue_name,
                error_details=msg.error_details,
                error_code=msg.error_code,
                queued_at=msg.queued_at,
                started_processing_at=msg.started_processing_at,
                completed_at=msg.completed_at,
                receive_count=msg.receive_count,
                visibility_timeout=msg.visibility_timeout,
                created_at=msg.created_at,
                updated_at=msg.updated_at,
                message_body=msg.message_body
            )
            for msg in messages
        ]

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch failed messages: {str(e)}")


@router.post("/cancel/sqs-message/{sqs_message_id}")
async def cancel_sqs_message(
    sqs_message_id: str,
    token: TokenInfo = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Cancel a queued SQS job by sqs_message_id.
    Useful when job_id is missing or unavailable.
    This will attempt to delete the message from SQS if possible.
    """
    try:
        repo = SQSMessageHistoryRepository(db)

        # First check if message exists
        msg = repo.get_by_message_id(sqs_message_id)
        if msg is None:
            raise HTTPException(
                status_code=404,
                detail=f"Message {sqs_message_id} not found"
            )

        # Check if cancellable
        if msg.status not in [DBMessageStatus.QUEUED, DBMessageStatus.PROCESSING]:
            raise HTTPException(
                status_code=400,
                detail=f"Message {sqs_message_id} cannot be cancelled. Current status: {msg.status.value}. Only QUEUED or PROCESSING jobs can be cancelled."
            )

        # Try to delete from SQS if we have a receipt_handle
        sqs_deleted = False
        if msg.receipt_handle:
            try:
                service = SQSMonitorService(db=db)
                delete_result = service.delete_message(
                    message_id=sqs_message_id,
                    receipt_handle=msg.receipt_handle
                )
                sqs_deleted = delete_result.success
            except Exception as e:
                import logging
                logging.warning(f"Failed to delete message from SQS (may already be processed): {str(e)}")

        # Update database status
        final_status = DBMessageStatus.DELETED if sqs_deleted else DBMessageStatus.CANCELLED
        result = repo.update_status(sqs_message_id, final_status)

        return {
            "success": True,
            "message": f"Message {sqs_message_id} {'deleted from SQS and database' if sqs_deleted else 'marked as cancelled (SQS deletion may be pending)'}",
            "sqs_message_id": sqs_message_id,
            "status": result.status.value if result else final_status.value,
            "sqs_deleted": sqs_deleted,
            "cancelled_at": result.updated_at if result else None
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to cancel message: {str(e)}")


@router.post("/cancel/{job_id}")
async def cancel_sqs_job(
    job_id: str,
    token: TokenInfo = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Cancel a queued SQS job by job_id.

    This endpoint cancels jobs that are still in QUEUED status.
    Jobs that are already PROCESSING, COMPLETED, or FAILED cannot be cancelled.

    When a job is cancelled:
    - The database status is updated to CANCELLED
    - The worker will check the status before processing
    - If the worker finds a CANCELLED job, it will delete it from SQS and mark it as DELETED

    Args:
        job_id: The job ID to cancel

    Returns:
        Success message with job details

    Raises:
        404: Job not found
        400: Job cannot be cancelled (not in QUEUED status)
    """
    try:
        repo = SQSMessageHistoryRepository(db)

        # Attempt to cancel the job
        result = repo.cancel_by_job_id(job_id)

        if result is None:
            # Check if job exists
            job = repo.get_by_job_id(job_id)
            if job is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Job {job_id} not found"
                )
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Job {job_id} cannot be cancelled. Current status: {job.status.value}. Only QUEUED or PROCESSING jobs can be cancelled."
                )

        return {
            "success": True,
            "message": f"Job {job_id} cancelled successfully",
            "job_id": job_id,
            "status": result.status.value,
            "cancelled_at": result.updated_at
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to cancel job: {str(e)}")