from typing import Optional
from pydantic import BaseModel


class ScoreThresholdBase(BaseModel):
    label: str
    value: float


class ScoreThresholdCreate(ScoreThresholdBase):
    pass


class ScoreThresholdUpdate(BaseModel):
    label: Optional[str] = None
    value: Optional[float] = None


class ScoreThresholdInDBBase(ScoreThresholdBase):
    id: int

    class Config:
        from_attributes = True


class ScoreThresholdOut(ScoreThresholdInDBBase):
    pass


class ScoreThresholdInDB(ScoreThresholdBase):
    id: Optional[int] = None
