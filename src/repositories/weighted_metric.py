from sqlalchemy.orm import Session
from typing import Optional, List

from src.models import WeightedMetric
from src.schemas.weighted_metric import WeightedMetricCreate, WeightedMetricUpdate


class WeightedMetricRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, metric_id: int) -> Optional[WeightedMetric]:
        return self.db.query(WeightedMetric).filter(WeightedMetric.id == metric_id).first()

    def get_by_label(self, label: str) -> Optional[WeightedMetric]:
        return self.db.query(WeightedMetric).filter(WeightedMetric.label == label).first()

    def list(self, skip: int = 0, limit: int | None = None) -> List[WeightedMetric]:
        query = self.db.query(WeightedMetric).offset(skip)
        if limit is not None:
            query = query.limit(limit)
        return query.all()

    def create(self, metric_in: WeightedMetricCreate) -> WeightedMetric:
        db_obj = WeightedMetric(**metric_in.model_dump(exclude_none=True))
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def update(self, db_obj: WeightedMetric, metric_in: WeightedMetricUpdate) -> WeightedMetric:
        update_data = metric_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_obj, field, value)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def delete(self, db_obj: WeightedMetric) -> None:
        self.db.delete(db_obj)
        self.db.commit()
