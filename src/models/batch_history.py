from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Time, text
from sqlalchemy.orm import relationship

from src.config.database import Base


class BatchHistory(Base):
    __tablename__ = 'batch_history'

    id = Column(Integer, primary_key=True, autoincrement=True)
    execution_type_id = Column(Integer, nullable=False)
    user_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    status = Column(String(20), nullable=False, server_default=text("'pending'"))
    duration = Column(
        Time,
        nullable=False,
        server_default=text("'00:00:00'"),
        comment="Duration (hh:mm:ss)",
    )
    created_at = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False)

    details          = relationship("BatchHistoryDetail", back_populates="batch", cascade="all, delete-orphan")
    user             = relationship("User")
