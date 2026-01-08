from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum


class MessageStatus(str, Enum):
    AVAILABLE = "available"  # In queue, waiting to be processed
    IN_FLIGHT = "in_flight"  # Being processed by a worker
    FAILED = "failed"  # In dead letter queue


class SQSMessageDetail(BaseModel):
    message_id: str = Field(..., description="SQS Message ID")
    receipt_handle: Optional[str] = Field(None, description="Receipt handle for the message")
    status: MessageStatus = Field(..., description="Current status of the message")
    job_id: Optional[str] = Field(None, description="Job ID from message body")
    message_type: Optional[str] = Field(None, description="Type of job (fetch/partial_rank/full_rank)")
    keyword_ids: Optional[List[int]] = Field(None, description="Keyword IDs being processed")
    user_id: Optional[int] = Field(None, description="User who initiated the job")
    user_full_name: Optional[str] = Field(None, description="Full name of the user who initiated the job")
    retry_count: int = Field(0, description="Number of retry attempts")
    sent_timestamp: Optional[datetime] = Field(None, description="When message was sent to queue")
    first_receive_timestamp: Optional[datetime] = Field(None, description="First time message was received")
    receive_count: int = Field(0, description="Number of times message has been received")
    visibility_timeout: Optional[int] = Field(None, description="Current visibility timeout in seconds")
    body: Optional[Dict[str, Any]] = Field(None, description="Full message body")
    attributes: Optional[Dict[str, Any]] = Field(None, description="Message attributes")


class SQSQueueMessages(BaseModel):
    queue_url: str = Field(..., description="URL of the SQS queue")
    queue_type: str = Field(..., description="Type of queue (main/dlq)")
    total_messages: int = Field(..., description="Total number of messages")
    messages: List[SQSMessageDetail] = Field(..., description="List of message details")
    has_more: bool = Field(False, description="Whether there are more messages not returned")
    fetched_at: datetime = Field(default_factory=datetime.utcnow, description="When data was fetched")


class SQSMonitorResponse(BaseModel):
    main_queue: Optional[SQSQueueMessages] = Field(None, description="Messages in main queue")
    dead_letter_queue: Optional[SQSQueueMessages] = Field(None, description="Messages in DLQ")
    summary: Dict[str, int] = Field(..., description="Summary statistics")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_schema_extra = {
            "example": {
                "main_queue": {
                    "queue_url": "https://sqs.ap-northeast-1.amazonaws.com/123/job-queue",
                    "queue_type": "main",
                    "total_messages": 2,
                    "messages": [
                        {
                            "message_id": "abc-123",
                            "status": "available",
                            "job_id": "550e8400-e29b-41d4",
                            "message_type": "partial_rank",
                            "keyword_ids": [1, 2, 3],
                            "user_id": 123,
                            "retry_count": 0,
                            "receive_count": 0
                        }
                    ],
                    "has_more": False,
                    "fetched_at": "2024-01-15T14:00:00Z"
                },
                "dead_letter_queue": {
                    "queue_url": "https://sqs.ap-northeast-1.amazonaws.com/123/job-dlq",
                    "queue_type": "dlq",
                    "total_messages": 0,
                    "messages": [],
                    "has_more": False,
                    "fetched_at": "2024-01-15T14:00:00Z"
                },
                "summary": {
                    "total_available": 2,
                    "total_in_flight": 1,
                    "total_failed": 0,
                    "total_all": 3
                },
                "timestamp": "2024-01-15T14:00:00Z"
            }
        }


class SQSDeleteRequest(BaseModel):
    message_id: str = Field(..., description="SQS Message ID to delete")
    receipt_handle: str = Field(..., description="Receipt handle from message (required for deletion)")

    class Config:
        json_schema_extra = {
            "example": {
                "message_id": "abc-123-def-456",
                "receipt_handle": "AQEBm3KN..."
            }
        }


class SQSDeleteResponse(BaseModel):
    success: bool = Field(..., description="Whether deletion was successful")
    message_id: str = Field(..., description="Message ID that was deleted")
    message: str = Field(..., description="Status message")
    deleted_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message_id": "abc-123-def-456",
                "message": "Message successfully deleted from queue",
                "deleted_at": "2024-01-15T14:00:00Z"
            }
        }