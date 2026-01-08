from sqlalchemy import Column, Integer, String, Numeric

from src.config.database import Base

class ScoreThreshold(Base):
    __tablename__ = "score_threshold"

    id = Column(Integer, primary_key=True, autoincrement=True)
    label = Column(String(1), nullable=False, unique=True)
    value = Column(Numeric(4, 2), nullable=False)
