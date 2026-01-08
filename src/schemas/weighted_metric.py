from typing import Optional
from pydantic import BaseModel


class WeightedMetricBase(BaseModel):
    label: str
    value: float


class WeightedMetricCreate(WeightedMetricBase):
    pass


class WeightedMetricUpdate(BaseModel):
    label: Optional[str] = None
    value: Optional[float] = None


class WeightedMetricInDBBase(WeightedMetricBase):
    id: int

    class Config:
        from_attributes = True


class WeightedMetricOut(WeightedMetricInDBBase):
    pass


class WeightedMetricInDB(WeightedMetricBase):
    id: Optional[int] = None
