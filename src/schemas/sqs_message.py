from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum


class SQSMessageType(str, Enum):
    PARTIAL_RANK = "partial_rank"
    FULL_RANK = "full_rank"
    FETCH = "fetch"
    FETCH_AND_RANK = "fetch_and_rank"


class SQSMessageStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"


class UnifiedJobMessage(BaseModel):
    """Unified message for all job types (fetch, rank, partial rank)"""
    job_id: str = Field(..., description="Unique identifier for this job")
    message_type: SQSMessageType = Field(..., description="Type of job to process")
    keyword_ids: List[int] = Field(..., description="List of keyword IDs to process")
    user_id: int = Field(..., description="User ID who initiated the request")
    token_info: Dict[str, Any] = Field(..., description="Token information for authentication")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    retry_count: int = Field(default=0, description="Number of retry attempts")
    max_retries: int = Field(default=3, description="Maximum number of retries")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata")

    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                "message_type": "partial_rank",
                "keyword_ids": [1, 2, 3],
                "user_id": 123,
                "token_info": {
                    "user_id": 123,
                    "email": "user@example.com",
                    "hubspot_token": "token_here"
                },
                "timestamp": "2024-01-01T00:00:00Z",
                "retry_count": 0,
                "max_retries": 3
            }
        }


# Keep these as aliases for backward compatibility if needed
PartialRankMessage = UnifiedJobMessage
FullRankMessage = UnifiedJobMessage
FetchMessage = UnifiedJobMessage


class SQSJobStatus(BaseModel):
    job_id: str
    message_id: str = Field(..., description="SQS Message ID")
    status: SQSMessageStatus
    keyword_ids: List[int]
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    retry_count: int = 0

    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                "message_id": "sqs-message-id",
                "status": "processing",
                "keyword_ids": [1, 2, 3],
                "created_at": "2024-01-01T00:00:00Z",
                "started_at": "2024-01-01T00:01:00Z",
                "retry_count": 0
            }
        }