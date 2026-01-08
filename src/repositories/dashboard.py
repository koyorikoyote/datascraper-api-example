from sqlalchemy import func
from sqlalchemy.orm import Session

from src.models import Keyword, SerpResult, BatchHistory
from src.models.batch_history_detail import BatchHistoryDetail
from src.schemas.dashboard import DashboardOut

from sqlalchemy import func
from datetime import date, timedelta

from src.utils.constants import ExecutionTypeConst

class DashboardRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_dashboard(self, user_id: int) -> DashboardOut:
        keyword_count = (
            self.db.query(func.count(Keyword.id))
            .filter(Keyword.created_by_user_id == user_id)
            .scalar()
        ) or 0

        serp_result_count = (
            self.db.query(func.count(SerpResult.id))
            .join(Keyword, SerpResult.keyword_id == Keyword.id)
            .filter(Keyword.created_by_user_id == user_id)
            .scalar()
        ) or 0

        batch_history_count = (
            self.db.query(func.count(BatchHistory.id))
            .filter(BatchHistory.user_id == user_id)
            .scalar()
        ) or 0

        today = date.today()
        start_date = today - timedelta(days=6)

        batch_detail_logs = (
            self.db.query(
                func.date(BatchHistoryDetail.created_at).label("date"),
                func.count(BatchHistoryDetail.id).label("inquiries")
            )
            .join(BatchHistory, BatchHistoryDetail.batch_id == BatchHistory.id)
            .filter(
                BatchHistory.user_id == user_id,
                BatchHistory.execution_type_id == ExecutionTypeConst.CONTACT_SENDING.value,
                func.date(BatchHistoryDetail.created_at) >= start_date,
            )
            .group_by(func.date(BatchHistoryDetail.created_at))
            .order_by(func.date(BatchHistoryDetail.created_at))
            .all()
        )
        print(batch_detail_logs)
        # Convert query results to a dict
        date_to_count = {
            log.date.isoformat(): log.inquiries for log in batch_detail_logs
        }

        # Ensure all 7 days are included in output
        weekly_contact_sending = [
            {
                "date": (start_date + timedelta(days=i)).isoformat(),
                "inquiries": date_to_count.get((start_date + timedelta(days=i)).isoformat(), 0)
            }
            for i in range(7)
        ]

        return DashboardOut(
            keyword_count=keyword_count,
            serp_result_count=serp_result_count,
            batch_history_count=batch_history_count,
            weekly_contact_sending=weekly_contact_sending
        )