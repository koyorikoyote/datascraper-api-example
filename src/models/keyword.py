from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Index, text
from sqlalchemy.orm import relationship

from src.config.database import Base


class Keyword(Base):
    __tablename__ = 'keyword'
    __table_args__ = (
        Index('idx_keyword_term', 'keyword'),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    keyword = Column(String(100), nullable=False, unique=True, index=True)
    fetch_status = Column(String(20), nullable=False, server_default=text("'pending'"))
    partial_rank_status = Column(String(20), nullable=False, server_default=text("'pending'"))
    rank_status = Column(String(20), nullable=False, server_default=text("'pending'"))
    execution_date = Column(DateTime, nullable=True)
    is_scheduled = Column(Boolean, nullable=False, server_default=text('0'))
    created_by_user_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    updated_at = Column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'))

    user = relationship('User')
    serp_results = relationship(
        'SerpResult',
        back_populates='keyword',
        cascade='all, delete-orphan',
        passive_deletes=True
    )
