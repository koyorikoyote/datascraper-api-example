from enum import Enum
from typing import Optional

from pydantic import BaseModel


class RoleName(str, Enum):
    sales_manager = 'sales_manager'
    sales_rep = 'sales_rep'
    system = 'system'


class UserRoleBase(BaseModel):
    role_name: RoleName
    typical_title: Optional[str] = None
    responsibilities: Optional[str] = None


class UserRoleCreate(UserRoleBase):
    pass


class UserRoleUpdate(BaseModel):
    typical_title: Optional[str] = None
    responsibilities: Optional[str] = None


class UserRoleOut(UserRoleBase):
    id: int

    class Config:
        from_attributes = True
