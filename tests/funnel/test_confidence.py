"""测试置信度计算。"""
import pytest
from src.funnel.confidence import ConfidenceCalculator


class TestConfidenceCalculator:
    def test_dual_confirmation_highest(self):
        """双路确认置信度最高。"""
        result = ConfidenceCalculator.calculate_etf("512480", {"512480"}, {"512480"})
        assert result["confidence"] > 0.85
        assert "双路确认" in result["source"]

    def test_direct_only_lower_confidence(self):
        """仅直筛命中置信度较低。"""
        result = ConfidenceCalculator.calculate_etf("159819", set(), {"159819"})
        assert result["confidence"] < 0.65
        assert result["position_multiplier"] == 0.5

    def test_no_signal_zero_confidence(self):
        result = ConfidenceCalculator.calculate_etf("000000", set(), set())
        assert result["confidence"] == 0.0
