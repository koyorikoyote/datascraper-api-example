from datetime import datetime, time
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, computed_field

from src.schemas import KeywordOut, UserOut
from src.utils.constants import ExecutionTypeConst, StatusConst 
from .batch_history_detail import BatchHistoryDetailOut

class BatchHistoryBase(BaseModel):
    execution_type_id: int
    user_id: int
    status: Optional[str] = None
    duration: Optional[time] = None

class BatchHistoryCreate(BatchHistoryBase):
    pass

class BatchHistoryUpdate(BaseModel):
    execution_type_id: Optional[int] = None
    user_id: Optional[int] = None
    status: Optional[str] = None
    duration: Optional[time] = None

class BatchHistoryInDBBase(BatchHistoryBase):
    id: int
    created_at: datetime

class BatchHistoryOut(BatchHistoryBase):
    id: int
    created_at: datetime
    
    # relationships
    user: Optional[UserOut] = None
    details: List[BatchHistoryDetailOut] = []

    model_config = ConfigDict(from_attributes=True)
    
    @computed_field(return_type=str)
    def execution_type_code_str(self) -> str:
        return ExecutionTypeConst(self.execution_type_id).code_str

    @computed_field(return_type=str)
    def execution_type_jp_name(self) -> str:
        return ExecutionTypeConst(self.execution_type_id).jp_name
    
    @computed_field(return_type=int)
    def total_url(self) -> int:
        if self.details is None:
            return 0
        return len(self.details)
    
    @computed_field(return_type=int)
    def total_success_url(self) -> int:
        return sum(
            1
            for d in (self.details or [])
            if d.status == StatusConst.SUCCESS
        )
        

class BatchHistoryExecutionParams(BaseModel):
    execution_id_list: list[int]
        
    
    