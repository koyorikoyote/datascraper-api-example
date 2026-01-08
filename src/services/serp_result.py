from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.schemas import SearchResult
from src.repositories import SerpResultRepository, KeywordRepository

class SerpResultService:
    def __init__(self, db: Session):
        self.repo = SerpResultRepository(db)
        self.keyword_repo = KeywordRepository(db)

    def create_result(self, keyword_id: int, result_in: SearchResult):
        keyword = self.keyword_repo.get(keyword_id)
        if not keyword:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Keyword does not exist",
            )
        return self.repo.create(keyword_id, result_in)

    def get_result(self, serp_id: int):
        return self.repo.get(serp_id)

    def list_results(self, keyword_id: int, skip: int = 0, limit: int | None = None):
        return self.repo.list(keyword_id, skip, limit)

    def update_result(self, serp_id: int, result_in: SearchResult):
        db_result = self.repo.get(serp_id)
        if not db_result:
            return None
        return self.repo.update(db_result, result_in)

    def delete_result(self, serp_id: int) -> bool:
        db_result = self.repo.get(serp_id)
        if not db_result:
            return False
        self.repo.delete(db_result)
        return True
