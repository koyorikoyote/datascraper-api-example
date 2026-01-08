from sqlalchemy.orm import Session
from typing import List, Optional

from src.schemas import BatchHistoryOut, BatchHistoryCreate, BatchHistoryUpdate, BatchHistoryOut
from src.repositories import BatchHistoryRepository


class BatchHistoryService:
    def __init__(self, db: Session):
        self.repo = BatchHistoryRepository(db)

    def get_batch(self, batch_id: int) -> Optional[BatchHistoryOut]:
        return self.repo.get(batch_id)

    def list_batches(self, execution_id_list: list[int], skip: int = 0, limit: int | None = None) -> List[BatchHistoryOut]:
        return self.repo.list(execution_id_list, skip, limit)

    def update_batch(self, batch_id: int, batch_in: BatchHistoryUpdate) -> Optional[BatchHistoryOut]:
        db_batch = self.repo.get(batch_id)
        if not db_batch:
            return None
        return self.repo.update(db_batch, batch_in)

    def delete_batch(self, batch_id: int) -> bool:
        db_batch = self.repo.get(batch_id)
        if not db_batch:
            return False
        self.repo.delete(db_batch)
        return True
