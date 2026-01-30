from sqlalchemy.orm import Session
from sqlalchemy import update
from typing import Optional, List, Dict

from src.models import SerpResult
from src.schemas import SearchResult, SearchResultUpdate
from src.utils.constants import StatusConst


class SerpResultRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, serp_id: int) -> Optional[SerpResult]:
        return self.db.query(SerpResult).filter(SerpResult.id == serp_id).first()

    def list(
        self, keyword_id: int, skip: int = 0, limit: int | None = None
    ) -> List[SerpResult]:
        query = (
            self.db.query(SerpResult)
            .filter(SerpResult.keyword_id == keyword_id)
            .offset(skip)
        )
        if limit is not None:
            query = query.limit(limit)
        return query.all()
        
    def list_pending_failed_or_partial(
        self, keyword_id: int, skip: int = 0, limit: int | None = None
    ) -> List[SerpResult]:
        """
        List SERP results for a keyword with status PENDING or FAILED.
        """
        query = (
            self.db.query(SerpResult)
            .filter(SerpResult.keyword_id == keyword_id)
            .filter(SerpResult.status.in_(
                [StatusConst.PENDING, StatusConst.FAILED, StatusConst.PARTIAL, StatusConst.PROCESSING]))
            .order_by(SerpResult.position)
            .offset(skip)
        )
        if limit is not None:
            query = query.limit(limit)
        return query.all()

    def get_by_keyword_and_link(
        self, keyword_id: int, link: str
    ) -> Optional[SerpResult]:
        return (
            self.db.query(SerpResult)
            .filter(SerpResult.keyword_id == keyword_id, SerpResult.link == link)
            .first()
        )

    def create(self, keyword_id: int, result_in: SearchResult) -> SerpResult:
        db_obj = SerpResult(**result_in.model_dump(exclude_none=True), keyword_id=keyword_id)
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def create_bulk_unique(self, keyword_id: int, results: List[SearchResult]) -> None:
        for result_in in results:
            if self.get_by_keyword_and_link(keyword_id, result_in.link):
                continue
            db_obj = SerpResult(**result_in.model_dump(exclude_none=True), keyword_id=keyword_id)
            self.db.add(db_obj)
        self.db.commit()

    def upsert_bulk_hubspot_duplicate(self, keyword_id: int, results: List[SearchResult]) -> None:
        for result_in in results:
            existing = self.get_by_keyword_and_link(keyword_id, result_in.link)
            if existing:
                # update only specific fields
                existing.is_hubspot_duplicate = result_in.is_hubspot_duplicate
            else:
                # insert new
                db_obj = SerpResult(**result_in.model_dump(exclude_none=True), keyword_id=keyword_id)
                self.db.add(db_obj)
        self.db.commit()

    def update(self, db_result: SerpResult, result_in: SearchResultUpdate) -> SerpResult:
        update_data = result_in.model_dump(exclude_none=True)
        for field, value in update_data.items():
            setattr(db_result, field, value)
        self.db.commit()
        self.db.refresh(db_result)
        return db_result

    def update_no_commit(self, db_result: SerpResult, result_in: SearchResultUpdate) -> SerpResult:
        """Update SERP result without committing - for use within transactions"""
        update_data = result_in.model_dump(exclude_none=True)
        for field, value in update_data.items():
            setattr(db_result, field, value)
        self.db.flush()  # Flush changes to DB but don't commit
        return db_result

    def delete(self, db_result: SerpResult) -> None:
        self.db.delete(db_result)
        self.db.commit()
        
    def update_processing_to_pending(self, keyword_id: int = None) -> Dict[str, int]:
        """
        Update SERP results with 'processing' status to 'pending'.
        
        Args:
            keyword_id: Optional keyword ID to update only SERP results for a specific keyword.
                       If None, updates all SERP results with processing status.
        
        Returns:
            Dictionary with count of updated records
        """
        # Base condition
        condition = (SerpResult.status == StatusConst.PROCESSING)
        
        # Add keyword_id filter if provided
        if keyword_id is not None:
            condition = condition & (SerpResult.keyword_id == keyword_id)
        
        query = (
            update(SerpResult)
            .where(condition)
            .values(status=StatusConst.PENDING)
            .execution_options(synchronize_session=False)
        )
        result = self.db.execute(query)
        count = result.rowcount
        
        self.db.commit()
        
        return {"status_updated": count}

    def update_failed_to_pending(self, keyword_id: int) -> int:
        """
        Update FAILED SERP results to PENDING for a specific keyword.
        Used to reset status when manually re-running a job.
        
        Args:
            keyword_id: The keyword ID to update
        
        Returns:
            Count of updated records
        """
        if keyword_id is None:
            return 0
            
        condition = (SerpResult.status == StatusConst.FAILED) & (SerpResult.keyword_id == keyword_id)
        
        query = (
            update(SerpResult)
            .where(condition)
            .values(status=StatusConst.PENDING)
            .execution_options(synchronize_session=False)
        )
        result = self.db.execute(query)
        count = result.rowcount
        
        self.db.commit()
        return count

    def count_failed_by_keyword(self, keyword_id: int) -> int:
        """
        Count the number of FAILED SERP results for a given keyword.
        """
        return (
            self.db.query(SerpResult)
            .filter(SerpResult.keyword_id == keyword_id)
            .filter(SerpResult.status == StatusConst.FAILED)
            .count()
        )

    def count_by_keyword(self, keyword_id: int) -> int:
        """
        Count the total number of SERP results for a given keyword.
        """
        return (
            self.db.query(SerpResult)
            .filter(SerpResult.keyword_id == keyword_id)
            .count()
        )

    def update_processing_to_failed(self, keyword_ids: List[int]) -> int:
        """
        Update SERP results with 'processing' status to 'failed' for specific keywords.
        """
        if not keyword_ids:
            return 0
            
        condition = (SerpResult.status == StatusConst.PROCESSING) & (SerpResult.keyword_id.in_(keyword_ids))
        
        query = (
            update(SerpResult)
            .where(condition)
            .values(status=StatusConst.FAILED)
            .execution_options(synchronize_session=False)
        )
        result = self.db.execute(query)
        count = result.rowcount
        self.db.commit()
        return count
