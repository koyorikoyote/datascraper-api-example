from sqlalchemy import Column, BigInteger, Integer, String, DateTime, ForeignKey, Enum, text
from sqlalchemy.orm import relationship

from src.config.database import Base

class HubspotIntegration(Base):
    __tablename__ = 'hubspot_integration'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    hub_id = Column(BigInteger, nullable=False)
    hub_domain = Column(String(100), nullable=False)
    refresh_token = Column(String(512), nullable=False)
    access_token = Column(String(512))
    expires_at = Column(DateTime(timezone=True))
    scopes = Column(String(512))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))

    user = relationship("User", back_populates="hubspot_integrations")

