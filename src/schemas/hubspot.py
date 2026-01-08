from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, EmailStr

class HubspotBase(BaseModel):
    user_id: int
    hub_id: int
    hub_domain: str
    refresh_token: str
    access_token: str
    expires_at: Optional[datetime] = None
    scopes: Optional[str] = None
    

class HubspotCreate(HubspotBase):
    pass

class HubspotUpdate(HubspotBase):
    hub_id: Optional[int] = None
    hub_domain: Optional[str] = None
    refresh_token: Optional[str] = None
    access_token: Optional[str] = None
    scopes: Optional[str] = None

class HubspotInDBBase(HubspotBase):
    id: int
    created_at: datetime
    
class HubspotAuthBase(BaseModel):
    token_type: str
    refresh_token: str
    access_token: str
    expires_at: Optional[datetime]

class HubspotAuthResponse(HubspotAuthBase):
    hub_id: int

class HubDomainResponse(BaseModel):
    hub_id: Optional[int]
    hub_domain: Optional[str]
    
class ContactIn(BaseModel):
    email: EmailStr
    firstname: Optional[str] = None
    lastname: Optional[str] = None
    phone: Optional[str] = None
    properties: Dict[str, Any] = {}

class CompanyIn(BaseModel):
    name: str
    domain: Optional[str] = None
    properties: Dict[str, Any] = {}
