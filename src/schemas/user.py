from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr
from .user_role import UserRoleOut


class UserBase(BaseModel):
    email: EmailStr
    full_name: str = None
    role_id: int


class UserCreate(UserBase):
    password: Optional[str] = None


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    password: Optional[str] = None
    role_id: Optional[int] = None
    last_login_at: Optional[datetime] = None
    model_config = ConfigDict(extra="ignore")

class UserInDBBase(UserBase):
    id: int
    created_at: datetime
    last_login_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserOut(UserInDBBase):
    role: UserRoleOut


class UserInDB(UserBase):
    id: Optional[int] = None
    email: Optional[str] = None
    created_at: Optional[datetime] = None
    last_login_at: Optional[datetime] = None
    password_hash: Optional[str] = None
    
class TokenInfo(BaseModel):
    email: EmailStr
    id: int
    role_id: Optional[int] = None