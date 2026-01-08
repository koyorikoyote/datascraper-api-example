from typing import List
from pydantic import BaseModel

from .weighted_metric import WeightedMetricOut
from .score_threshold import ScoreThresholdOut


class ScoreSetting(BaseModel):
    weighted_metrics: List[WeightedMetricOut]
    score_thresholds: List[ScoreThresholdOut]
