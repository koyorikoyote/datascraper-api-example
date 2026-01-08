from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_
from sqlalchemy.exc import IntegrityError
import logging
import pytz

from src.models.sqs_message_history import SQSMessageHistory, MessageStatus, MessageType

logger = logging.getLogger(__name__)

# Japan timezone
JAPAN_TZ = pytz.timezone('Asia/Tokyo')


def get_japan_time():
    """Get current time in Japan timezone as naive datetime"""
    # Get UTC time, convert to Japan timezone, then make naive
    # This ensures consistent storage in MySQL DateTime columns
    utc_now = datetime.utcnow().replace(tzinfo=pytz.UTC)
    japan_now = utc_now.astimezone(JAPAN_TZ)
    return japan_now.replace(tzinfo=None)


class SQSMessageHistoryRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_or_update(
        self,
        sqs_message_id: str,
        job_id: Optional[str] = None,
        message_type: Optional[MessageType] = None,
        keyword_ids: Optional[List[int]] = None,
        user_id: Optional[int] = None,
        user_full_name: Optional[str] = None,
        status: MessageStatus = MessageStatus.QUEUED,
        retry_count: int = 0,
        queue_name: Optional[str] = None,
        receipt_handle: Optional[str] = None,
        message_body: Optional[dict] = None,
        message_attributes: Optional[dict] = None,
        queued_at: Optional[datetime] = None,
        sqs_receive_count: Optional[int] = None,
        **kwargs
    ) -> SQSMessageHistory:
        """
        Create a new message history record or update existing one
        """
        # Check if record exists
        existing = self.db.query(SQSMessageHistory).filter(
            SQSMessageHistory.sqs_message_id == sqs_message_id
        ).first()

        if existing:
            # Smart status update - prevent status regression
            if existing.status == MessageStatus.PROCESSING and status == MessageStatus.QUEUED:
                # Don't overwrite PROCESSING with QUEUED - job is still being processed
                logger.warning(
                    f"Message {sqs_message_id} is currently PROCESSING, "
                    f"not reverting to QUEUED (likely visibility timeout)"
                )
                # Still update receive count to track timeout occurrences
                existing.receive_count = sqs_receive_count if sqs_receive_count else existing.receive_count + 1
                existing.updated_at = get_japan_time()
                self.db.commit()
                self.db.refresh(existing)
                return existing

            if existing.status == MessageStatus.COMPLETED and status == MessageStatus.QUEUED:
                # Don't reprocess completed jobs
                logger.warning(
                    f"Message {sqs_message_id} already COMPLETED, "
                    f"not reverting to QUEUED (duplicate message?)"
                )
                # Still update receive count to track duplicate attempts
                existing.receive_count = sqs_receive_count if sqs_receive_count else existing.receive_count + 1
                existing.updated_at = get_japan_time()
                self.db.commit()
                self.db.refresh(existing)
                return existing

            # Allow FAILED -> QUEUED transition for retries
            if existing.status == MessageStatus.FAILED and status == MessageStatus.QUEUED:
                logger.info(f"Message {sqs_message_id} FAILED -> QUEUED for retry")

            # Update existing record
            existing.job_id = job_id or existing.job_id
            existing.message_type = message_type if message_type else existing.message_type
            existing.keyword_ids = keyword_ids or existing.keyword_ids
            existing.user_id = user_id or existing.user_id
            existing.user_full_name = user_full_name or existing.user_full_name
            existing.status = status
            existing.retry_count = retry_count
            existing.queue_name = queue_name or existing.queue_name
            existing.receipt_handle = receipt_handle or existing.receipt_handle
            existing.message_body = message_body or existing.message_body
            existing.message_attributes = message_attributes or existing.message_attributes
            existing.receive_count = sqs_receive_count if sqs_receive_count else existing.receive_count + 1
            existing.updated_at = get_japan_time()

            # Update other fields from kwargs
            for key, value in kwargs.items():
                if hasattr(existing, key):
                    setattr(existing, key, value)

            self.db.commit()
            self.db.refresh(existing)
            return existing
        else:
            # Create new record
            current_japan_time = get_japan_time()

            new_history = SQSMessageHistory(
                sqs_message_id=sqs_message_id,
                job_id=job_id,
                message_type=message_type if message_type else None,
                keyword_ids=keyword_ids,
                user_id=user_id,
                user_full_name=user_full_name,
                status=status,
                retry_count=retry_count,
                queue_name=queue_name,
                receipt_handle=receipt_handle,
                message_body=message_body,
                message_attributes=message_attributes,
                queued_at=queued_at or current_japan_time,
                created_at=current_japan_time,
                updated_at=current_japan_time,
                **kwargs
            )

            self.db.add(new_history)
            try:
                self.db.commit()
                self.db.refresh(new_history)
                return new_history
            except IntegrityError:
                # Race condition: record was created by another process
                # Rollback and retry the update
                self.db.rollback()
                logger.warning(
                    f"Race condition detected for message {sqs_message_id}, "
                    f"retrying as update"
                )
                # Recursively call this method again to update the existing record
                return self.create_or_update(
                    sqs_message_id=sqs_message_id,
                    job_id=job_id,
                    message_type=message_type,
                    keyword_ids=keyword_ids,
                    user_id=user_id,
                    user_full_name=user_full_name,
                    status=status,
                    retry_count=retry_count,
                    queue_name=queue_name,
                    receipt_handle=receipt_handle,
                    message_body=message_body,
                    message_attributes=message_attributes,
                    queued_at=queued_at,
                    sqs_receive_count=sqs_receive_count,
                    **kwargs
                )

    def update_status(
        self,
        sqs_message_id: str,
        status: MessageStatus,
        error_details: Optional[str] = None,
        error_code: Optional[str] = None
    ) -> Optional[SQSMessageHistory]:
        """
        Update the status of a message
        """
        record = self.db.query(SQSMessageHistory).filter(
            SQSMessageHistory.sqs_message_id == sqs_message_id
        ).first()

        if record:
            record.status = status
            record.updated_at = get_japan_time()

            # Update timestamps based on status
            if status == MessageStatus.PROCESSING:
                record.started_processing_at = get_japan_time()
            elif status in [MessageStatus.COMPLETED, MessageStatus.FAILED, MessageStatus.DLQ]:
                record.completed_at = get_japan_time()

            # Add error details if failed
            if status in [MessageStatus.FAILED, MessageStatus.DLQ]:
                record.error_details = error_details
                record.error_code = error_code

            self.db.commit()
            self.db.refresh(record)

        return record

    def get_by_message_id(self, sqs_message_id: str) -> Optional[SQSMessageHistory]:
        """
        Get a message history record by SQS message ID
        """
        return self.db.query(SQSMessageHistory).filter(
            SQSMessageHistory.sqs_message_id == sqs_message_id
        ).first()

    def get_by_job_id(self, job_id: str) -> Optional[SQSMessageHistory]:
        """
        Get a message history record by job ID
        """
        return self.db.query(SQSMessageHistory).filter(
            SQSMessageHistory.job_id == job_id
        ).first()

    def get_by_user_id(
        self,
        user_id: int,
        status: Optional[MessageStatus | List[MessageStatus]] = None,
        limit: int = 100
    ) -> List[SQSMessageHistory]:
        """
        Get message history for a specific user
        """
        query = self.db.query(SQSMessageHistory).filter(
            SQSMessageHistory.user_id == user_id
        )

        if status:
            if isinstance(status, list):
                query = query.filter(SQSMessageHistory.status.in_(status))
            else:
                query = query.filter(SQSMessageHistory.status == status)

        return query.order_by(desc(SQSMessageHistory.created_at)).limit(limit).all()

    def get_recent_messages(
        self,
        status: Optional[MessageStatus | List[MessageStatus]] = None,
        message_type: Optional[MessageType] = None,
        limit: int = 100
    ) -> List[SQSMessageHistory]:
        """
        Get recent messages with optional filtering
        """
        query = self.db.query(SQSMessageHistory)

        if status:
            if isinstance(status, list):
                query = query.filter(SQSMessageHistory.status.in_(status))
            else:
                query = query.filter(SQSMessageHistory.status == status)

        if message_type:
            query = query.filter(SQSMessageHistory.message_type == message_type)

        return query.order_by(desc(SQSMessageHistory.created_at)).limit(limit).all()

    def get_failed_messages(
        self,
        include_dlq: bool = True,
        limit: int = 100
    ) -> List[SQSMessageHistory]:
        """
        Get failed messages
        """
        statuses = [MessageStatus.FAILED]
        if include_dlq:
            statuses.append(MessageStatus.DLQ)

        return self.db.query(SQSMessageHistory).filter(
            SQSMessageHistory.status.in_(statuses)
        ).order_by(desc(SQSMessageHistory.completed_at)).limit(limit).all()

    def get_processing_messages(self) -> List[SQSMessageHistory]:
        """
        Get messages currently being processed
        """
        return self.db.query(SQSMessageHistory).filter(
            SQSMessageHistory.status == MessageStatus.PROCESSING
        ).order_by(SQSMessageHistory.started_processing_at).all()

    def increment_retry_count(self, sqs_message_id: str) -> Optional[SQSMessageHistory]:
        """
        Increment the retry count for a message
        """
        record = self.db.query(SQSMessageHistory).filter(
            SQSMessageHistory.sqs_message_id == sqs_message_id
        ).first()

        if record:
            record.retry_count += 1
            record.updated_at = get_japan_time()
            self.db.commit()
            self.db.refresh(record)

        return record

    def cancel_by_job_id(self, job_id: str) -> Optional[SQSMessageHistory]:
        """
        Cancel a job by job_id. Can only cancel jobs in QUEUED status.
        Returns the updated record if successful, None otherwise.
        """
        record = self.db.query(SQSMessageHistory).filter(
            SQSMessageHistory.job_id == job_id
        ).first()

        if not record:
            logger.warning(f"Job {job_id} not found")
            return None

        # Only allow cancellation of queued or processing jobs
        if record.status not in [MessageStatus.QUEUED, MessageStatus.PROCESSING]:
            logger.warning(
                f"Cannot cancel job {job_id} with status {record.status.value}. "
                f"Only QUEUED or PROCESSING jobs can be cancelled."
            )
            return None

        # Update status to CANCELLED
        record.status = MessageStatus.CANCELLED
        record.updated_at = get_japan_time()
        self.db.commit()
        self.db.refresh(record)

        logger.info(f"Job {job_id} cancelled successfully")
        return record

    def cancel_by_sqs_message_id(self, sqs_message_id: str) -> Optional[SQSMessageHistory]:
        """
        Cancel a job by sqs_message_id. Can only cancel jobs in QUEUED or PROCESSING status.
        Returns the updated record if successful, None otherwise.
        """
        record = self.db.query(SQSMessageHistory).filter(
            SQSMessageHistory.sqs_message_id == sqs_message_id
        ).first()

        if not record:
            logger.warning(f"Message {sqs_message_id} not found")
            return None

        # Only allow cancellation of queued or processing jobs
        if record.status not in [MessageStatus.QUEUED, MessageStatus.PROCESSING]:
            logger.warning(
                f"Cannot cancel message {sqs_message_id} with status {record.status.value}. "
                f"Only QUEUED or PROCESSING jobs can be cancelled."
            )
            return None

        # Update status to CANCELLED
        record.status = MessageStatus.CANCELLED
        record.updated_at = get_japan_time()
        self.db.commit()
        self.db.refresh(record)

        logger.info(f"Message {sqs_message_id} cancelled successfully")
        return record