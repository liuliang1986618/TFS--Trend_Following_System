"""测试ETF直筛路径。"""
import pytest
from src.funnel.etf_filter import ETFFilter


class TestETFFilter:
    def test_eligible_types_are_a_and_b(self):
        assert ETFFilter.ELIGIBLE_TYPES == {"A", "B"}

    def test_filter_uptrend_etf_passes(self, uptrend_daily):
        data = {"512480": uptrend_daily}
        result = ETFFilter.filter(data)
        assert "512480" in result
