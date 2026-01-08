from pydantic import BaseModel, EmailStr
from typing import Optional

class ContactTemplateBase(BaseModel):
    last: Optional[str] = None
    first: Optional[str] = None
    last_kana: Optional[str] = None
    first_kana: Optional[str] = None
    last_hira: Optional[str] = None
    first_hira: Optional[str] = None
    email: Optional[EmailStr] = None
    company: Optional[str] = None
    department: Optional[str] = None
    url: Optional[str] = None
    phone1: Optional[str] = None
    phone2: Optional[str] = None
    phone3: Optional[str] = None
    zip1: Optional[str] = None
    zip2: Optional[str] = None
    address1: Optional[str] = None
    address2: Optional[str] = None
    address3: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None

class ContactTemplateCreate(ContactTemplateBase):
    pass

class ContactTemplateUpdate(ContactTemplateBase):
    pass

class ContactTemplateInDBBase(ContactTemplateBase):
    id: int

    class Config:
        from_attributes = True

class ContactTemplateOut(ContactTemplateInDBBase):
    pass

class ContactTemplateInDB(ContactTemplateBase):
    id: Optional[int] = None
