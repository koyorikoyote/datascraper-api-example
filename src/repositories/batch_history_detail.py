from sqlalchemy.orm import Session
from typing import Optional, List

from src.models import BatchHistoryDetail
from src.schemas.batch_history_detail import (
    BatchHistoryDetailCreate,
    BatchHistoryDetailUpdate,
)


class BatchHistoryDetailRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, detail_id: int) -> Optional[BatchHistoryDetail]:
        return (
            self.db.query(BatchHistoryDetail)
            .filter(BatchHistoryDetail.id == detail_id)
            .first()
        )

    def list(
        self, batch_id: Optional[int] = None, skip: int = 0, limit: int | None = None
    ) -> List[BatchHistoryDetail]:
        query = self.db.query(BatchHistoryDetail)
        if batch_id is not None:
            query = query.filter(BatchHistoryDetail.batch_id == batch_id)
        query = query.offset(skip)
        if limit is not None:
            query = query.limit(limit)
        return query.all()

    def create(self, detail_in: BatchHistoryDetailCreate) -> BatchHistoryDetail:
        db_detail = BatchHistoryDetail(**detail_in.model_dump(exclude_none=True))
        self.db.add(db_detail)
        self.db.commit()
        self.db.refresh(db_detail)
        return db_detail

    def update(
        self, db_detail: BatchHistoryDetail, detail_in: BatchHistoryDetailUpdate
    ) -> BatchHistoryDetail:
        update_data = detail_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_detail, field, value)
        self.db.commit()
        self.db.refresh(db_detail)
        return db_detail

    def delete(self, db_detail: BatchHistoryDetail) -> None:
        self.db.delete(db_detail)
        self.db.commit()
