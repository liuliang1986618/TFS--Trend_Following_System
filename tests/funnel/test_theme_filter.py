"""测试漏斗第二层：题材趋势判断。"""
import pytest
from src.funnel.theme_filter import ThemeFilter


class TestThemeFilter:
    def test_filter_uptrend_theme_passes(self, uptrend_daily):
        """上涨趋势题材通过筛选。"""
        data = {"GN300308": uptrend_daily}
        result = ThemeFilter.filter(data)
        assert "GN300308" in result

    def test_filter_downtrend_theme_fails(self, downtrend_daily):
        """下跌趋势题材不通过。"""
        data = {"GN_TEST": downtrend_daily}
        result = ThemeFilter.filter(data)
        assert "GN_TEST" not in result

    def test_target_states_only_3_and_4(self):
        """题材只关注状态3和4。"""
        assert ThemeFilter.TARGET_STATES == {3, 4}
