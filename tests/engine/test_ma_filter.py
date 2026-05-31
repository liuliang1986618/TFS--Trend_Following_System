"""测试MA20均线初筛过滤器。"""
import pytest
import pandas as pd
import numpy as np
from src.engine.ma_filter import MAFilter
from tests.conftest import make_ohlcv


class TestMAFilter:
    def test_price_above_ma20_passes(self):
        """价格在MA20上方：通过初筛。"""
        n = 30
        dates = pd.date_range("2026-04-01", periods=n, freq="B")
        closes = list(np.linspace(10, 20, n))
        volumes = [1000000] * n
        df = make_ohlcv(dates, closes, volumes)
        result = MAFilter.check(df)
        assert result is True

    def test_price_below_ma20_fails(self):
        """价格在MA20下方：初筛不通过。"""
        n = 30
        dates = pd.date_range("2026-04-01", periods=n, freq="B")
        closes = list(np.linspace(20, 10, n))
        volumes = [1000000] * n
        df = make_ohlcv(dates, closes, volumes)
        result = MAFilter.check(df)
        assert result is False

    def test_insufficient_data_returns_false(self):
        """数据不足20日：自动不通过。"""
        n = 15
        dates = pd.date_range("2026-05-01", periods=n, freq="B")
        closes = [10 + i * 0.1 for i in range(n)]
        volumes = [1000000] * n
        df = make_ohlcv(dates, closes, volumes)
        result = MAFilter.check(df)
        assert result is False

    def test_price_crossing_ma20(self):
        """价格刚站上MA20边界情况。"""
        n = 25
        dates = pd.date_range("2026-04-01", periods=n, freq="B")
        closes = [10.0] * 20 + [12.0, 14.0, 16.0, 18.0, 20.0]
        volumes = [1000000] * n
        df = make_ohlcv(dates, closes, volumes)
        result = MAFilter.check(df)
        assert result is True

    def test_ma20_batch_filter(self):
        """批量过滤：返回通过和未通过的列表。"""
        n = 30
        dates = pd.date_range("2026-04-01", periods=n, freq="B")
        up_closes = list(np.linspace(10, 20, n))
        up_df = make_ohlcv(dates, up_closes, [1000000] * n)
        down_closes = list(np.linspace(20, 10, n))
        down_df = make_ohlcv(dates, down_closes, [1000000] * n)

        data = {"UP": up_df, "DOWN": down_df}
        passed, failed = MAFilter.batch_filter(data)

        assert "UP" in passed
        assert "DOWN" in failed
