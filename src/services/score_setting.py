from sqlalchemy.orm import Session

from src.repositories.weighted_metric import WeightedMetricRepository
from src.repositories.score_threshold import ScoreThresholdRepository
from src.schemas.score_setting import ScoreSetting
from src.schemas.weighted_metric import WeightedMetricUpdate
from src.schemas.score_threshold import ScoreThresholdUpdate


class ScoreSettingService:
    def __init__(self, db: Session):
        self.metric_repo = WeightedMetricRepository(db)
        self.threshold_repo = ScoreThresholdRepository(db)

    def list_settings(self) -> ScoreSetting:
        metrics = self.metric_repo.list()
        thresholds = self.threshold_repo.list()
        return ScoreSetting(weighted_metrics=metrics, score_thresholds=thresholds)

    def update_settings(self, settings: ScoreSetting) -> ScoreSetting:
        for metric in settings.weighted_metrics:
            db_obj = self.metric_repo.get(metric.id)
            if db_obj:
                update_in = WeightedMetricUpdate(label=metric.label, value=metric.value)
                self.metric_repo.update(db_obj, update_in)
        for threshold in settings.score_thresholds:
            db_obj = self.threshold_repo.get(threshold.id)
            if db_obj:
                update_in = ScoreThresholdUpdate(label=threshold.label, value=threshold.value)
                self.threshold_repo.update(db_obj, update_in)
        return self.list_settings()
