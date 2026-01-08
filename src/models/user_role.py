from sqlalchemy import Column, Integer, String, Text, Enum
from sqlalchemy.orm import relationship

from src.config.database import Base

class UserRole(Base):
    __tablename__ = 'user_role'

    id = Column(Integer, primary_key=True, autoincrement=True)
    role_name = Column(
        Enum('sales_manager', 'sales_rep', 'system', name='role_name_enum'),
        nullable=False,
        unique=True,
    )
    typical_title = Column(String(100), nullable=True)
    responsibilities = Column(Text, nullable=True)

    users = relationship('User', back_populates='role')
