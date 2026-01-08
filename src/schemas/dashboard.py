from pydantic import BaseModel

class WeeklyContactItem(BaseModel):
    date: str
    inquiries: int
class DashboardOut(BaseModel):
    keyword_count: int
    serp_result_count: int
    batch_history_count: int
    weekly_contact_sending: list[WeeklyContactItem]
    