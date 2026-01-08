from datetime import datetime
from typing import Optional
from src.utils.constants import StatusConst, RankConst
from pydantic import BaseModel, ConfigDict, computed_field, Field
from .user import UserOut
from .serp_result import SearchResult


class KeywordBase(BaseModel):
    keyword: str
    fetch_status: StatusConst = StatusConst.PENDING
    partial_rank_status: StatusConst = StatusConst.PENDING
    rank_status: StatusConst = StatusConst.PENDING
    execution_date: Optional[datetime] = None
    is_scheduled: bool = False


class KeywordCreate(KeywordBase):
    pass


class KeywordUpdate(BaseModel):
    fetch_status: Optional[str] = None
    partial_rank_status: Optional[str] = None
    rank_status: Optional[str] = None
    execution_date: Optional[datetime] = None
    is_scheduled: Optional[bool] = None


class KeywordInDBBase(KeywordBase):
    id: int
    updated_at: datetime

    class Config:
        from_attributes = True


class KeywordOut(KeywordInDBBase):
    user: Optional[UserOut]
    
    class Config:
        from_attributes = True


class KeywordComputedOut(KeywordInDBBase):
    user: Optional[UserOut]
    serp_results: Optional[list["SearchResult"]] = Field(
        default_factory=list,
        exclude=True,
        repr=False,
    )
    
    model_config = ConfigDict(from_attributes=True)
    
    @computed_field(return_type=int)
    def total_items(self) -> int:
        if self.serp_results is None:
            return 0
        return sum(d.rank is not None for d in self.serp_results)
    
    @computed_field(return_type=int)
    def total_a_rank(self) -> int:
        return sum(d.rank == RankConst.A_RANK for d in (self.serp_results or []))
    
    @computed_field(return_type=int)
    def total_b_rank(self) -> int:
        return sum(d.rank == RankConst.B_RANK for d in (self.serp_results or []))

    @computed_field(return_type=int)
    def total_c_rank(self) -> int:
        return sum(d.rank == RankConst.C_RANK for d in (self.serp_results or []))
    
    @computed_field(return_type=int)
    def total_d_rank(self) -> int:
        return sum(d.rank == RankConst.D_RANK for d in (self.serp_results or []))

class KeywordInDB(KeywordBase):
    id: Optional[int] = None
    updated_at: Optional[datetime] = None


class KeywordBulk(BaseModel):
    ids: list[int]


class RankGPTResponse(BaseModel):
    keyword: list[str]
    price: int
    company_name: str
    phone_number: str
    url_corporate_site: str
    url_service_site: str
    email_address: str
    has_column_section: bool = False
    column_determination_reason: str = ""
    industry: str = ""
    has_own_product_service_offer: bool = False
    own_product_service_determination_reason: str = ""

class LinkGPTResponse(BaseModel):
    about: str
    contact: str
