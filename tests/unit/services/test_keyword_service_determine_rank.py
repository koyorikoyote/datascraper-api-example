import unittest
from unittest.mock import MagicMock, patch
import math
from sqlalchemy.orm import Session

from src.services.keyword import KeywordService
from src.schemas import ScoreSetting, ScoreThresholdOut, WeightedMetricOut
from src.utils.constants import RankConst


class TestKeywordServiceDetermineRank(unittest.TestCase):
    """Unit tests for the _determine_rank method in KeywordService."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_db = MagicMock(spec=Session)
        self.service = KeywordService(self.mock_db)

    def test_determine_rank_basic_matching(self):
        """Test basic rank determination with standard thresholds."""
        score_setting = ScoreSetting(
            weighted_metrics=[],
            score_thresholds=[
                ScoreThresholdOut(id=1, label="A", value=80.0),
                ScoreThresholdOut(id=2, label="B", value=60.0),
                ScoreThresholdOut(id=3, label="C", value=40.0),
            ]
        )

        # Test various weights
        self.assertEqual(self.service._determine_rank(90.0, score_setting), "A")
        self.assertEqual(self.service._determine_rank(80.0, score_setting), "A")
        self.assertEqual(self.service._determine_rank(70.0, score_setting), "B")
        self.assertEqual(self.service._determine_rank(60.0, score_setting), "B")
        self.assertEqual(self.service._determine_rank(50.0, score_setting), "C")
        self.assertEqual(self.service._determine_rank(40.0, score_setting), "C")
        self.assertEqual(self.service._determine_rank(30.0, score_setting), "D")
        self.assertEqual(self.service._determine_rank(20.0, score_setting), "D")

    def test_determine_rank_below_all_thresholds(self):
        """Test when weight is below all thresholds - should return lowest threshold label."""
        score_setting = ScoreSetting(
            weighted_metrics=[],
            score_thresholds=[
                ScoreThresholdOut(id=1, label="A", value=80.0),
                ScoreThresholdOut(id=2, label="B", value=60.0),
                ScoreThresholdOut(id=3, label="C", value=40.0),
                ScoreThresholdOut(id=4, label="D", value=20.0),
            ]
        )

        # Weight below all thresholds should return label with lowest threshold
        self.assertEqual(self.service._determine_rank(10.0, score_setting), "D")
        self.assertEqual(self.service._determine_rank(0.0, score_setting), "D")
        self.assertEqual(self.service._determine_rank(-10.0, score_setting), "D")

    def test_determine_rank_unsorted_thresholds(self):
        """Test with unsorted thresholds - should still work correctly."""
        score_setting = ScoreSetting(
            weighted_metrics=[],
            score_thresholds=[
                ScoreThresholdOut(id=1, label="C", value=40.0),
                ScoreThresholdOut(id=2, label="A", value=80.0),
                ScoreThresholdOut(id=4, label="B", value=60.0),
            ]
        )

        self.assertEqual(self.service._determine_rank(85.0, score_setting), "A")
        self.assertEqual(self.service._determine_rank(65.0, score_setting), "B")
        self.assertEqual(self.service._determine_rank(45.0, score_setting), "C")
        self.assertEqual(self.service._determine_rank(25.0, score_setting), "D")

    def test_determine_rank_duplicate_thresholds(self):
        """Test with duplicate threshold values - should pick deterministically."""
        score_setting = ScoreSetting(
            weighted_metrics=[],
            score_thresholds=[
                ScoreThresholdOut(id=1, label="A", value=60.0),
                ScoreThresholdOut(id=2, label="B", value=60.0),
                ScoreThresholdOut(id=3, label="C", value=30.0),
            ]
        )

        # With same thresholds, should pick based on alphabetical order (deterministic)
        self.assertEqual(self.service._determine_rank(60.0, score_setting), "A")
        self.assertEqual(self.service._determine_rank(30.0, score_setting), "C")

    def test_determine_rank_empty_thresholds(self):
        """Test with empty score_thresholds list - should return default rank."""
        score_setting = ScoreSetting(
            weighted_metrics=[],
            score_thresholds=[]
        )

        self.assertEqual(self.service._determine_rank(50.0, score_setting), RankConst.D_RANK)

    def test_determine_rank_none_thresholds(self):
        """Test when score_thresholds attribute is None or missing."""
        # Create a ScoreSetting without score_thresholds
        score_setting = MagicMock(spec=ScoreSetting)
        score_setting.score_thresholds = None

        self.assertEqual(self.service._determine_rank(50.0, score_setting), RankConst.D_RANK)

        # Test with missing attribute entirely
        del score_setting.score_thresholds
        self.assertEqual(self.service._determine_rank(50.0, score_setting), RankConst.D_RANK)

    def test_determine_rank_invalid_values(self):
        """Test with invalid threshold values (NaN, non-numeric)."""
        score_setting = ScoreSetting(
            weighted_metrics=[],
            score_thresholds=[
                ScoreThresholdOut(id=1, label="A", value=float('nan')),
                ScoreThresholdOut(id=2, label="B", value=60.0),
                ScoreThresholdOut(id=3, label="C", value=40.0),
            ]
        )

        # Should skip NaN values
        self.assertEqual(self.service._determine_rank(70.0, score_setting), "B")
        self.assertEqual(self.service._determine_rank(50.0, score_setting), "C")

    def test_determine_rank_negative_thresholds(self):
        """Test with negative threshold values."""
        score_setting = ScoreSetting(
            weighted_metrics=[],
            score_thresholds=[
                ScoreThresholdOut(id=1, label="A", value=50.0),
                ScoreThresholdOut(id=2, label="B", value=0.0),
                ScoreThresholdOut(id=3, label="C", value=-25.0),
                ScoreThresholdOut(id=4, label="D", value=-50.0),
            ]
        )

        self.assertEqual(self.service._determine_rank(60.0, score_setting), "A")
        self.assertEqual(self.service._determine_rank(25.0, score_setting), "B")
        self.assertEqual(self.service._determine_rank(0.0, score_setting), "B")
        self.assertEqual(self.service._determine_rank(-10.0, score_setting), "C")
        self.assertEqual(self.service._determine_rank(-30.0, score_setting), "D")
        self.assertEqual(self.service._determine_rank(-60.0, score_setting), "D")

    def test_determine_rank_float_precision(self):
        """Test with floating point precision edge cases."""
        score_setting = ScoreSetting(
            weighted_metrics=[],
            score_thresholds=[
                ScoreThresholdOut(id=1, label="A", value=80.00000001),
                ScoreThresholdOut(id=2, label="B", value=60.0),
                ScoreThresholdOut(id=3, label="C", value=39.99999999),
            ]
        )

        self.assertEqual(self.service._determine_rank(80.00000001, score_setting), "A")
        self.assertEqual(self.service._determine_rank(80.0, score_setting), "B")
        self.assertEqual(self.service._determine_rank(40.0, score_setting), "C")
        self.assertEqual(self.service._determine_rank(39.99999999, score_setting), "C")

    def test_determine_rank_empty_labels(self):
        """Test with empty string labels."""
        score_setting = ScoreSetting(
            weighted_metrics=[],
            score_thresholds=[
                ScoreThresholdOut(id=1, label="", value=80.0),
                ScoreThresholdOut(id=2, label="B", value=60.0),
            ]
        )

        # Empty labels should be skipped
        self.assertEqual(self.service._determine_rank(70.0, score_setting), "B")

    def test_determine_rank_none_labels(self):
        """Test with None labels."""
        score_setting = ScoreSetting(
            weighted_metrics=[],
            score_thresholds=[
                MagicMock(spec=ScoreThresholdOut, id=1, label=None, value=80.0),
                ScoreThresholdOut(id=2, label="B", value=60.0),
            ]
        )

        # None labels should be skipped
        self.assertEqual(self.service._determine_rank(70.0, score_setting), "B")

    def test_get_metric_value_with_thresholds(self):
        """Test helper method _get_metric_value with ScoreThresholdOut objects."""
        metrics = [
            ScoreThresholdOut(id=1, label="A", value=80.0),
            ScoreThresholdOut(id=2, label="B", value=60.0),
            ScoreThresholdOut(id=3, label="C", value=40.0),
        ]

        self.assertEqual(self.service._get_metric_value(metrics, "A"), 80.0)
        self.assertEqual(self.service._get_metric_value(metrics, "B"), 60.0)
        self.assertEqual(self.service._get_metric_value(metrics, "C"), 40.0)
        self.assertEqual(self.service._get_metric_value(metrics, "NonExistent"), 0.0)

    def test_get_metric_value_with_weighted_metrics(self):
        """Test helper method _get_metric_value with WeightedMetricOut objects."""
        metrics = [
            WeightedMetricOut(id=1, label="service_price", value=0.5),
            WeightedMetricOut(id=2, label="service_volume", value=0.3),
            WeightedMetricOut(id=3, label="site_size", value=0.2),
        ]

        self.assertEqual(self.service._get_metric_value(metrics, "service_price"), 0.5)
        self.assertEqual(self.service._get_metric_value(metrics, "service_volume"), 0.3)
        self.assertEqual(self.service._get_metric_value(metrics, "site_size"), 0.2)
        self.assertEqual(self.service._get_metric_value(metrics, "unknown"), 0.0)

if __name__ == '__main__':
    unittest.main()