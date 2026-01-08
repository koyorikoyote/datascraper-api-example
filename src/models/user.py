from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, text
from sqlalchemy.orm import relationship

from src.config.database import Base


class User(Base):
    __tablename__ = 'user'

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    full_name = Column(String(100), nullable=True)
    password_hash = Column(String(60), nullable=True)
    role_id = Column(Integer, ForeignKey('user_role.id'), nullable=False)
    created_at = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False)
    last_login_at = Column(DateTime, nullable=True)

    role = relationship('UserRole', back_populates='users')
    hubspot_integrations = relationship(
        "HubspotIntegration",
        back_populates="user",
        cascade="all, delete-orphan",
    )
