"""测试漏斗第三层：个股趋势判断。"""
import pytest
from src.funnel.stock_filter import StockFilter


class TestStockFilter:
    def test_filter_uptrend_stock_passes(self, uptrend_daily):
        data = {"000001": uptrend_daily}
        result = StockFilter.filter(data)
        assert "000001" in result

    def test_filter_downtrend_stock_fails(self, downtrend_daily):
        data = {"000001": downtrend_daily}
        result = StockFilter.filter(data)
        assert "000001" not in result

    def test_target_states_include_3_4_5(self):
        assert StockFilter.TARGET_STATES == {3, 4, 5}
