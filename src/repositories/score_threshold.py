from sqlalchemy.orm import Session
from typing import Optional, List

from src.models import ScoreThreshold
from src.schemas.score_threshold import ScoreThresholdCreate, ScoreThresholdUpdate


class ScoreThresholdRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, threshold_id: int) -> Optional[ScoreThreshold]:
        return self.db.query(ScoreThreshold).filter(ScoreThreshold.id == threshold_id).first()

    def get_by_label(self, label: str) -> Optional[ScoreThreshold]:
        return self.db.query(ScoreThreshold).filter(ScoreThreshold.label == label).first()

    def list(self, skip: int = 0, limit: int | None = None) -> List[ScoreThreshold]:
        query = self.db.query(ScoreThreshold).offset(skip)
        if limit is not None:
            query = query.limit(limit)
        return query.all()

    def create(self, threshold_in: ScoreThresholdCreate) -> ScoreThreshold:
        db_obj = ScoreThreshold(**threshold_in.model_dump(exclude_none=True))
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def update(self, db_obj: ScoreThreshold, threshold_in: ScoreThresholdUpdate) -> ScoreThreshold:
        update_data = threshold_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_obj, field, value)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def delete(self, db_obj: ScoreThreshold) -> None:
        self.db.delete(db_obj)
        self.db.commit()
