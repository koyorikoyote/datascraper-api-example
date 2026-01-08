from sqlalchemy import Column, Integer, String, Numeric

from src.config.database import Base

class WeightedMetric(Base):
    __tablename__ = "weighted_metric"

    id = Column(Integer, primary_key=True, autoincrement=True)
    label = Column(String(255), nullable=False, unique=True)
    value = Column(Numeric(3, 2), nullable=False)
