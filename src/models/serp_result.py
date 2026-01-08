from sqlalchemy import Column, Integer, String, DateTime, BigInteger, ForeignKey, Index, Text, text, Numeric, JSON, Boolean
from sqlalchemy.orm import relationship

from src.config.database import Base

class SerpResult(Base):
    __tablename__ = "serp_result"
    __table_args__ = (
        Index("ux_keyword_link", "keyword_id", "link", unique=True, mysql_length={"link": 191},),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    keyword_id = Column(Integer, ForeignKey("keyword.id", ondelete='CASCADE'), nullable=False)

    rank = Column(String(1), nullable=True, comment="Rank of the result in SERP (A, B, C)")
    status = Column(String(20), nullable=False, server_default=text("'pending'"))
    
    total_weight = Column(Numeric(5, 2), nullable=True)
    
    service_price = Column(BigInteger, nullable=True)
    service_volume = Column(BigInteger, nullable=True)
    site_size = Column(BigInteger, nullable=True)
    
    metric_price = Column(Numeric(3, 2), nullable=True)
    metric_volume = Column(Numeric(3, 2), nullable=True)
    metric_site_size = Column(Numeric(3, 2), nullable=True)
    
    candidate_keyword = Column(JSON, nullable=True)

    title = Column(String(255), nullable=False)
    link = Column(String(2083), nullable=False)
    snippet = Column(Text, nullable=True)
    position = Column(Integer, nullable=False, comment="Position in SERP, 1-based")
    
    company_name = Column(String(255), nullable=True)
    domain_name = Column(String(255), nullable=True)
    contact_person = Column(String(255), nullable=True)
    phone_number = Column(String(32), nullable=True)
    url_corporate_site = Column(String(2083), nullable=True)
    url_service_site = Column(String(2083), nullable=True)
    email_address = Column(String(320), nullable=True)
    has_column_section = Column(Boolean, nullable=True)
    column_determination_reason = Column(Text, nullable=True)
    industry = Column(String(255), nullable=True)
    has_own_product_service_offer = Column(Boolean, nullable=True)
    own_product_service_determination_reason = Column(Text, nullable=True)
    contact_send_success = Column(Boolean, nullable=True)
    notes = Column(Text, nullable=True)
    activity_date = Column(DateTime(timezone=True), nullable=True, server_default=text('CURRENT_TIMESTAMP'))
    
    is_hubspot_duplicate = Column(Boolean, nullable=False, server_default=text('0'))
    
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))

    keyword = relationship("Keyword", back_populates="serp_results")
