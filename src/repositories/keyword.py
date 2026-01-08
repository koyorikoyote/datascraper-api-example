from datetime import datetime, timezone
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import update, text
from typing import Optional, List, Dict, Any

from src.models import Keyword
from src.schemas import KeywordInDB, KeywordUpdate, TokenInfo
from src.utils.constants import StatusConst
import logging
import re
import pytz

class KeywordRepository:
    def __init__(self, db: Session):
        self.db = db
        self._norm_cache = None  # populated on first exists_normalized() call

    def get(self, keyword_id: int) -> Optional[Keyword]:
        return self.db.query(Keyword).filter(Keyword.id == keyword_id).first()

    def get_by_keyword(self, term: str) -> Optional[Keyword]:
        return self.db.query(Keyword).filter(Keyword.keyword == term).first()

    def _normalize_py(self, s: str) -> str:
        # Match DB behavior by truncating to 100 chars before normalization
        s = (s or "")[:100]
        return re.sub(r"\s+", "", s).replace("\u3000", "").replace("\u200b", "").replace("\ufeff", "").replace("\u00A0", "").lower()
    
    def exists_normalized(self, term: str) -> bool:
        # Cache normalized existing values once per request to make repeated checks fast and consistent
        if self._norm_cache is None:
            rows = self.db.query(Keyword.keyword).all()
            self._norm_cache = {self._normalize_py(r[0]) for r in rows if r and r[0]}
        return self._normalize_py(term) in self._norm_cache

    def list(self, skip: int = 0, limit: int | None = None) -> List[Keyword]:
        query = (
            self.db.query(Keyword)
            .options(selectinload(Keyword.user))
            .options(selectinload(Keyword.serp_results))
            .order_by(Keyword.updated_at.desc())
            .offset(skip)
        )
        if limit is not None:
            query = query.limit(limit)
        return query.all()
        
    def list_all_values(self) -> List[str]:
        return [row[0] for row in self.db.query(Keyword.keyword).all()]
        
    def list_scheduled(self) -> List[Keyword]:
        """Get all keywords that are scheduled for execution"""
        return (
            self.db.query(Keyword)
            .filter(Keyword.is_scheduled == True)
            .options(selectinload(Keyword.user))
            .options(selectinload(Keyword.serp_results))
            .all()
        )

    def create(self, keyword_in: KeywordInDB, token: TokenInfo) -> Keyword:
        db_keyword = Keyword(
            keyword=keyword_in.keyword,
            fetch_status=keyword_in.fetch_status,
            rank_status=keyword_in.rank_status,
            execution_date=keyword_in.execution_date or datetime.now(timezone.utc),
            is_scheduled=keyword_in.is_scheduled,
            created_by_user_id=token.id,
        )
        self.db.add(db_keyword)
        self.db.commit()
        self.db.refresh(db_keyword)
        return db_keyword

    def update(self, db_keyword: Keyword, keyword_in: KeywordUpdate) -> Keyword:
        update_data = keyword_in.model_dump(exclude_none=True)
        for field, value in update_data.items():
            setattr(db_keyword, field, value)
        self.db.commit()
        self.db.refresh(db_keyword)
        return db_keyword

    def update_no_commit(self, db_keyword: Keyword, keyword_in: KeywordUpdate) -> Keyword:
        """Update keyword without committing - for use within transactions"""
        update_data = keyword_in.model_dump(exclude_none=True)
        for field, value in update_data.items():
            setattr(db_keyword, field, value)
        self.db.flush()  # Flush changes to DB but don't commit
        return db_keyword

    def delete(self, db_keyword: Keyword) -> None:
        self.db.delete(db_keyword)
        self.db.commit()

    def delete_bulk(self, ids: List[int]) -> int:
        if not ids:
            return 0
        result = (
            self.db.query(Keyword)
            .filter(Keyword.id.in_(ids))
            .delete(synchronize_session=False)
        )
        self.db.commit()
        return result
        
    def bulk_insert_ignore(self, keywords: List[str], user_id: int, is_scheduled: bool = False) -> int:
        if not keywords:
            return 0
        utc_now = datetime.utcnow().replace(tzinfo=pytz.UTC)
        now = utc_now.astimezone(pytz.timezone('Asia/Tokyo'))
        params = [
            {
                "keyword": kw,
                "execution_date": now,
                "is_scheduled": 1 if is_scheduled else 0,
                "user_id": user_id,
            }
            for kw in keywords
        ]
        sql = text("""
            INSERT IGNORE INTO keyword (keyword, execution_date, is_scheduled, created_by_user_id)
            VALUES (:keyword, :execution_date, :is_scheduled, :user_id)
        """)
        total = 0
        chunk_size = 200
        for i in range(0, len(params), chunk_size):
            chunk = params[i:i+chunk_size]
            res = self.db.execute(sql, chunk)
            total += res.rowcount or 0
            # Commit per chunk to avoid long-running transactions/timeouts on very large imports
            self.db.commit()
        return total
         
    def update_processing_to_pending(self, keyword_id: int = None) -> Dict[str, int]:
        """
        Update keywords with 'processing' status to 'pending'.
        
        Args:
            keyword_id: Optional keyword ID to update only a specific keyword.
                       If None, updates all keywords with processing status.
        
        Returns:
            Dictionary with counts of updated records for fetch_status and rank_status
        """
        # Base conditions for both queries
        fetch_status_condition = (Keyword.fetch_status == StatusConst.PROCESSING)
        rank_status_condition = (Keyword.rank_status == StatusConst.PROCESSING)
        partial_rank_status_condition = (Keyword.partial_rank_status == StatusConst.PROCESSING)
        
        # Add keyword_id filter if provided
        if keyword_id is not None:
            fetch_status_condition = fetch_status_condition & (Keyword.id == keyword_id)
            rank_status_condition = rank_status_condition & (Keyword.id == keyword_id)
            partial_rank_status_condition = partial_rank_status_condition & (Keyword.id == keyword_id)
        
        # Update fetch_status
        fetch_status_query = (
            update(Keyword)
            .where(fetch_status_condition)
            .values(fetch_status=StatusConst.PENDING)
            .execution_options(synchronize_session=False)
        )
        fetch_status_result = self.db.execute(fetch_status_query)
        fetch_status_count = fetch_status_result.rowcount
        
        # Update rank_status
        rank_status_query = (
            update(Keyword)
            .where(rank_status_condition)
            .values(rank_status=StatusConst.PENDING)
            .execution_options(synchronize_session=False)
        )
        rank_status_result = self.db.execute(rank_status_query)
        rank_status_count = rank_status_result.rowcount
        
        # Update partial_rank_status
        partial_rank_status_query = (
            update(Keyword)
            .where(partial_rank_status_condition)
            .values(partial_rank_status=StatusConst.PENDING)
            .execution_options(synchronize_session=False)
        )
        partial_rank_status_result = self.db.execute(partial_rank_status_query)
        partial_rank_status_count = partial_rank_status_result.rowcount
        
        self.db.commit()
        
        return {
            "fetch_status_updated": fetch_status_count,
            "rank_status_updated": rank_status_count,
            "partial_rank_status_updated": partial_rank_status_count
        }
