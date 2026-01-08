from sqlalchemy.orm import Session

from src.repositories import DashboardRepository
from src.schemas.dashboard import DashboardOut

class DashboardService:
    def __init__(self, db: Session):
        self.repo = DashboardRepository(db)

    def get_dashboard(self, user_id: int) -> DashboardOut:
        return self.repo.get_dashboard(user_id)
