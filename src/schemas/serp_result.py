from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

class CandidateKeyword(BaseModel):
    keyword: str
    volume: int
    
class SerpRequest(BaseModel):
    keyword_id: int

class SearchResult(BaseModel):
    title: str
    link: str
    snippet: Optional[str] = None
    position: int
    rank: Optional[str] = None
    status: Optional[str] = None
    total_weight: Optional[float] = None
    service_price: Optional[int] = None
    service_volume: Optional[int] = None
    site_size: Optional[int] = None
    metric_price: Optional[float] = None
    metric_volume: Optional[float] = None
    metric_site_size: Optional[float] = None
    candidate_keyword: Optional[list[CandidateKeyword]] = Field(default_factory=list)
    company_name: Optional[str] = None
    domain_name: Optional[str] = None
    contact_person: Optional[str] = None
    phone_number: Optional[str] = None
    url_corporate_site: Optional[str] = None
    url_service_site: Optional[str] = None
    email_address: Optional[str] = None
    has_column_section: Optional[bool] = None
    column_determination_reason: Optional[str] = None
    industry: Optional[str] = None
    has_own_product_service_offer: Optional[bool] = None
    own_product_service_determination_reason: Optional[str] = None
    notes: Optional[str] = None
    activity_date: Optional[datetime] = None
    is_hubspot_duplicate: Optional[bool] = None
    
class SearchResultUpdate(BaseModel):
    title: Optional[str] = None
    link: Optional[str] = None
    snippet: Optional[str] = None
    position: Optional[int] = None
    rank: Optional[str] = None
    status: Optional[str] = None
    total_weight: Optional[float] = None
    service_price: Optional[int] = None
    service_volume: Optional[int] = None
    site_size: Optional[int] = None
    metric_price: Optional[float] = None
    metric_volume: Optional[float] = None
    metric_site_size: Optional[float] = None
    candidate_keyword: Optional[list[CandidateKeyword]] = Field(default_factory=list)
    company_name: Optional[str] = None
    domain_name: Optional[str] = None
    contact_person: Optional[str] = None
    phone_number: Optional[str] = None
    url_corporate_site: Optional[str] = None
    url_service_site: Optional[str] = None
    email_address: Optional[str] = None
    has_column_section: Optional[bool] = None
    column_determination_reason: Optional[str] = None
    industry: Optional[str] = None
    has_own_product_service_offer: Optional[bool] = None
    own_product_service_determination_reason: Optional[str] = None
    notes: Optional[str] = None
    activity_date: Optional[datetime] = None
    is_hubspot_duplicate: Optional[bool] = None

class MonthlySearchVolume(BaseModel):
    year: int
    month: int
    searches: int


class SerpResponse(BaseModel):
    keyword_id: int
    keyword: str
    results: list[SearchResult]

# new classes for serp result CRUD
class SerpResultBase(BaseModel):
    title: str
    link: str
    snippet: Optional[str] = None
    position: int
    keyword_id: int
    rank: Optional[str] = None
    status: Optional[str] = None
    total_weight: Optional[float] = None
    service_price: Optional[int] = None
    service_volume: Optional[int] = None
    site_size: Optional[int] = None
    metric_price: Optional[float] = None
    metric_volume: Optional[float] = None
    metric_site_size: Optional[float] = None
    candidate_keyword: Optional[list[CandidateKeyword]] = Field(default_factory=list)
    company_name: Optional[str] = None
    domain_name: Optional[str] = None
    contact_person: Optional[str] = None
    phone_number: Optional[str] = None
    url_corporate_site: Optional[str] = None
    url_service_site: Optional[str] = None
    email_address: Optional[str] = None
    has_column_section: Optional[bool] = None
    column_determination_reason: Optional[str] = None
    industry: Optional[str] = None
    has_own_product_service_offer: Optional[bool] = None
    own_product_service_determination_reason: Optional[str] = None
    notes: Optional[str] = None
    activity_date: Optional[datetime] = None
    is_hubspot_duplicate: Optional[bool] = None
class SerpResultCreate(SerpResultBase):
    pass

class SerpResultUpdate(BaseModel):
    title: Optional[str] = None
    link: Optional[str] = None
    snippet: Optional[str] = None
    position: Optional[int] = None

class SerpResultInDBBase(SerpResultBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class SerpResultOut(SerpResultInDBBase):
    pass
    
class RankComputation(BaseModel):
    total_weight: float
    service_price: int
    service_volume: int
    site_size: int
    metric_price: float
    metric_volume: float
    metric_site_size: float
    candidate_keyword: list[CandidateKeyword] = Field(default_factory=list)
