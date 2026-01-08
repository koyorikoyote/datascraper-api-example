from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Time, text
from sqlalchemy.orm import relationship

from src.config.database import Base


class BatchHistoryDetail(Base):
    __tablename__ = "batch_history_detail"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    batch_id      = Column(Integer, ForeignKey("batch_history.id"), nullable=False)
    keyword_id    = Column(Integer, ForeignKey('keyword.id', ondelete='CASCADE'), nullable=True)
    target        = Column(String(10000), nullable=False)
    status        = Column(String(20), nullable=False, server_default=text("'pending'"))
    error_message = Column(String(1000), nullable=True)
    created_at    = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"), nullable=False)

    batch = relationship("BatchHistory", back_populates="details")
    keyword          = relationship("Keyword")