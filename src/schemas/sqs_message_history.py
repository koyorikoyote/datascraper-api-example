from pydantic import BaseModel, Field, field_serializer
from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum
import pytz

# Japan timezone for serialization
JAPAN_TZ = pytz.timezone('Asia/Tokyo')


class MessageStatusEnum(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    DLQ = "dlq"
    CANCELLED = "cancelled"
    DELETED = "deleted"


class MessageTypeEnum(str, Enum):
    FETCH = "fetch"
    PARTIAL_RANK = "partial_rank"
    FULL_RANK = "full_rank"
    FETCH_AND_RANK = "fetch_and_rank"


class SQSMessageHistoryBase(BaseModel):
    sqs_message_id: str = Field(..., description="SQS Message ID")
    job_id: Optional[str] = Field(None, description="Job ID associated with the message")
    message_type: Optional[MessageTypeEnum] = Field(None, description="Type of message/job")
    keyword_ids: Optional[List[int]] = Field(None, description="List of keyword IDs processed")
    user_id: Optional[int] = Field(None, description="User ID who initiated the job")
    user_full_name: Optional[str] = Field(None, description="Full name of the user")
    status: MessageStatusEnum = Field(..., description="Current status of the message")
    retry_count: int = Field(0, description="Number of retry attempts")
    queue_name: Optional[str] = Field(None, description="Queue name (main/dlq)")


class SQSMessageHistoryCreate(SQSMessageHistoryBase):
    message_body: Optional[Dict[str, Any]] = Field(None, description="Complete message body")
    message_attributes: Optional[Dict[str, Any]] = Field(None, description="SQS message attributes")
    queued_at: Optional[datetime] = Field(None, description="When message was queued")


class SQSMessageHistoryUpdate(BaseModel):
    status: Optional[MessageStatusEnum] = Field(None, description="Updated status")
    error_details: Optional[str] = Field(None, description="Error details if failed")
    error_code: Optional[str] = Field(None, description="Error code if applicable")
    started_processing_at: Optional[datetime] = Field(None, description="Processing start time")
    completed_at: Optional[datetime] = Field(None, description="Completion time")


class SQSMessageHistoryOut(SQSMessageHistoryBase):
    id: int = Field(..., description="Database record ID")
    error_details: Optional[str] = Field(None, description="Error details if failed")
    error_code: Optional[str] = Field(None, description="Error code if applicable")
    queued_at: Optional[datetime] = Field(None, description="When message was sent to queue")
    started_processing_at: Optional[datetime] = Field(None, description="When processing started")
    completed_at: Optional[datetime] = Field(None, description="When processing completed")
    receive_count: int = Field(0, description="Number of times message was received")
    visibility_timeout: Optional[int] = Field(None, description="Visibility timeout in seconds")
    created_at: datetime = Field(..., description="Record creation time")
    updated_at: datetime = Field(..., description="Last update time")
    message_body: Optional[Dict[str, Any]] = Field(None, description="Complete message body")

    @field_serializer('queued_at', 'started_processing_at', 'completed_at', 'created_at', 'updated_at')
    def serialize_datetime(self, dt: Optional[datetime], _info):
        """Attach Japan timezone to naive datetimes for proper serialization"""
        if dt is None:
            return None
        # If naive datetime, localize to Japan timezone
        if dt.tzinfo is None:
            return JAPAN_TZ.localize(dt)
        return dt

    class Config:
        from_attributes = True


class SQSMessageHistoryDetail(SQSMessageHistoryOut):
    message_body: Optional[Dict[str, Any]] = Field(None, description="Complete message body")
    message_attributes: Optional[Dict[str, Any]] = Field(None, description="SQS message attributes")
    receipt_handle: Optional[str] = Field(None, description="Last known receipt handle")


class SQSMessageHistoryFilter(BaseModel):
    status: Optional[MessageStatusEnum] = Field(None, description="Filter by status")
    message_type: Optional[MessageTypeEnum] = Field(None, description="Filter by message type")
    user_id: Optional[int] = Field(None, description="Filter by user ID")
    job_id: Optional[str] = Field(None, description="Filter by job ID")
    date_from: Optional[datetime] = Field(None, description="Filter messages created after this date")
    date_to: Optional[datetime] = Field(None, description="Filter messages created before this date")
    include_failed: bool = Field(True, description="Include failed messages")
    include_dlq: bool = Field(True, description="Include DLQ messages")


class SQSMessageHistorySummary(BaseModel):
    total_messages: int = Field(..., description="Total number of messages")
    queued: int = Field(0, description="Messages currently queued")
    processing: int = Field(0, description="Messages being processed")
    completed: int = Field(0, description="Successfully completed messages")
    failed: int = Field(0, description="Failed messages")
    dlq: int = Field(0, description="Messages in dead letter queue")
    deleted: int = Field(0, description="Manually deleted messages")

    average_processing_time_seconds: Optional[float] = Field(None, description="Average processing time")
    failure_rate_percentage: Optional[float] = Field(None, description="Percentage of failed messages")

    by_type: Dict[str, int] = Field(default_factory=dict, description="Count by message type")
    by_user: Dict[str, int] = Field(default_factory=dict, description="Count by user")
    recent_failures: List[SQSMessageHistoryOut] = Field(default_factory=list, description="Recent failed messages")