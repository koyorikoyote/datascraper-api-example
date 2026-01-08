from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict

from .keyword import KeywordBase

class BatchHistoryDetailBase(BaseModel):
    batch_id: int
    keyword_id: Optional[int] = None
    target: str
    status: Optional[str] = None
    error_message: Optional[str] = None


class BatchHistoryDetailCreate(BatchHistoryDetailBase):
    pass


class BatchHistoryDetailUpdate(BaseModel):
    target: Optional[str] = None
    status: Optional[str] = None
    error_message: Optional[str] = None


class BatchHistoryDetailInDBBase(BatchHistoryDetailBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class BatchHistoryDetailOut(BatchHistoryDetailInDBBase):
    # relationships
    keyword: Optional[KeywordBase] = None

    model_config = ConfigDict(from_attributes=True)
