from sqlalchemy.orm import Session, selectinload
from typing import Optional, List

from src.models import BatchHistory, Keyword
from src.schemas.batch_history import BatchHistoryCreate, BatchHistoryUpdate


class BatchHistoryRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, batch_id: int) -> Optional[BatchHistory]:
        return (
            self.db.query(BatchHistory)
            .options(selectinload(BatchHistory.details))
            .options(selectinload(BatchHistory.user))
            .filter(BatchHistory.id == batch_id)
            .first()
        )

    def list(self, execution_id_list: list[int], skip: int = 0, limit: int | None = None) -> List[BatchHistory]:
        query = (
            self.db.query(BatchHistory)
            .filter(BatchHistory.execution_type_id.in_(execution_id_list))
            .options(
                selectinload(BatchHistory.details),
                selectinload(BatchHistory.user),
            )
            .order_by(BatchHistory.created_at.desc())
            .offset(skip)
        )
        if limit is not None:
            query = query.limit(limit)
        return query.all()

    def create(self, batch_in: BatchHistoryCreate) -> BatchHistory:
        db_batch = BatchHistory(**batch_in.model_dump(exclude_none=True))
        self.db.add(db_batch)
        self.db.commit()
        self.db.refresh(db_batch)
        return db_batch

    def update(self, db_batch: BatchHistory, batch_in: BatchHistoryUpdate) -> BatchHistory:
        update_data = batch_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_batch, field, value)
        self.db.commit()
        self.db.refresh(db_batch)
        return db_batch

    def delete(self, db_batch: BatchHistory) -> None:
        self.db.delete(db_batch)
        self.db.commit()
