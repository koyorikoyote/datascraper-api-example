from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, Enum as SQLEnum
from sqlalchemy.sql import func
import enum

from src.config.database import Base


class MessageStatus(enum.Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    DLQ = "dlq"  # Dead Letter Queue
    CANCELLED = "cancelled"  # User requested cancellation
    DELETED = "deleted"  # Manually deleted


class MessageType(enum.Enum):
    FETCH = "fetch"
    PARTIAL_RANK = "partial_rank"
    FULL_RANK = "full_rank"
    FETCH_AND_RANK = "fetch_and_rank"


class SQSMessageHistory(Base):
    __tablename__ = 'sqs_message_history'

    id = Column(Integer, primary_key=True, autoincrement=True)

    # SQS Message identifiers
    sqs_message_id = Column(String(255), nullable=False, unique=True, index=True)
    job_id = Column(String(255), nullable=True, index=True)

    # Message details
    message_type = Column(SQLEnum(MessageType, values_callable=lambda x: [e.value for e in x]), nullable=True)
    keyword_ids = Column(JSON, nullable=True)  # Array of keyword IDs
    user_id = Column(Integer, nullable=True, index=True)
    user_full_name = Column(String(100), nullable=True)

    # Processing details
    status = Column(SQLEnum(MessageStatus, values_callable=lambda x: [e.value for e in x]), nullable=False, default=MessageStatus.QUEUED)
    retry_count = Column(Integer, default=0)

    # Error tracking
    error_details = Column(Text, nullable=True)  # Reason for failure if status is FAILED
    error_code = Column(String(50), nullable=True)  # Specific error code if applicable

    # Timestamps
    queued_at = Column(DateTime, nullable=True)  # When message was sent to queue
    started_processing_at = Column(DateTime, nullable=True)  # When worker picked it up
    completed_at = Column(DateTime, nullable=True)  # When processing finished (success or failure)

    # Additional metadata
    queue_name = Column(String(100), nullable=True)  # Which queue (main/dlq)
    receipt_handle = Column(Text, nullable=True)  # Last known receipt handle
    visibility_timeout = Column(Integer, nullable=True)
    receive_count = Column(Integer, default=0)

    # Full message data for debugging
    message_body = Column(JSON, nullable=True)  # Complete message body
    message_attributes = Column(JSON, nullable=True)  # SQS message attributes

    # Audit fields
    created_at = Column(DateTime, server_default=func.current_timestamp(), nullable=False)
    updated_at = Column(DateTime, server_default=func.current_timestamp(), onupdate=func.current_timestamp(), nullable=False)