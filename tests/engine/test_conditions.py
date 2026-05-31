"""测试三条件判断器。"""
import pytest
import pandas as pd
import numpy as np
from src.engine.conditions import TrendConditions, ConditionResult
from tests.conftest import make_ohlcv


class TestTrendConditions:
    def test_structure_pass_uptrend(self, uptrend_daily):
        """上涨趋势数据应通过结构条件A。"""
        result = TrendConditions.check_structure(uptrend_daily)
        assert result.pass_ is True
        assert "更高高" in result.detail

    def test_structure_fail_downtrend(self, downtrend_daily):
        """下跌趋势数据应不通过结构条件A。"""
        result = TrendConditions.check_structure(downtrend_daily)
        assert result.pass_ is False

    def test_volume_pass_uptrend(self, uptrend_daily):
        """上涨趋势数据应通过量能条件B。"""
        result = TrendConditions.check_volume(uptrend_daily)
        assert result.pass_ is True
        assert "涨均量" in result.detail

    def test_volume_fail_downtrend(self, downtrend_daily):
        """下跌中缩量反弹不应通过量能条件。"""
        result = TrendConditions.check_volume(downtrend_daily)
        assert result.pass_ is False

    def test_persistence_pass_uptrend(self, uptrend_daily):
        """上涨趋势数据应通过持续性条件C。"""
        result = TrendConditions.check_persistence(uptrend_daily)
        assert result.pass_ is True
        assert "阳" in result.detail

    def test_persistence_fail_downtrend(self, downtrend_daily):
        """下跌趋势数据应不通过持续性条件C。"""
        result = TrendConditions.check_persistence(downtrend_daily)
        assert result.pass_ is False

    def test_three_conditions_all_independent(self, uptrend_daily):
        """三个条件验证三个独立维度——缺一不可。"""
        struct = TrendConditions.check_structure(uptrend_daily)
        volume = TrendConditions.check_volume(uptrend_daily)
        persist = TrendConditions.check_persistence(uptrend_daily)
        details = {struct.detail, volume.detail, persist.detail}
        assert len(details) == 3  # 三个维度的detail各不相同

    def test_insufficient_data_all_fail(self):
        """数据不足时所有条件都不通过。

        → 少亏钱：宁可错过不可做错。数据不足时不出信号=不冒无谓风险。
        """
        n = 15
        dates = pd.date_range("2026-05-01", periods=n, freq="B")
        closes = [10 + i * 0.1 for i in range(n)]
        volumes = [1000000] * n
        df = make_ohlcv(dates, closes, volumes)
        assert TrendConditions.check_structure(df).pass_ is False
        assert TrendConditions.check_volume(df).pass_ is False
        assert TrendConditions.check_persistence(df).pass_ is False

    def test_continuous_three_yang_detection(self):
        """检测到连续3日阳线——持续性C的核心条件。"""
        n = 30
        dates = pd.date_range("2026-04-01", periods=n, freq="B")
        closes = [10.0] * 10 + [10.2, 10.5, 10.8, 10.6, 10.4] + [10.0] * 15
        opens = [10.0] * 10 + [10.0, 10.3, 10.6, 10.8, 10.2] + [10.0] * 15
        volumes = [1000000] * n
        df = make_ohlcv(dates, closes, volumes, opens)
        result = TrendConditions.check_persistence(df)
        assert result.pass_ is True

    def test_check_all_returns_all_three(self, uptrend_daily):
        """check_all一次返回全部三个条件的结果。"""
        results = TrendConditions.check_all(uptrend_daily)
        assert "structure" in results
        assert "volume" in results
        assert "persistence" in results
        assert isinstance(results["structure"], ConditionResult)

    def test_structure_detail_includes_price(self, uptrend_daily):
        """结构的detail包含具体价格——Dashboard需要展示"为什么"。"""
        result = TrendConditions.check_structure(uptrend_daily)
        assert result.pass_ is True
        # detail应包含价格信息（如"12.50"这样的数字）
        import re
        assert re.search(r'\d+\.\d+', result.detail) is not None
