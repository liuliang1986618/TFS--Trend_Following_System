"""测试漏斗第一层：板块趋势判断。"""
import pytest
import pandas as pd
import numpy as np
from src.funnel.sector_filter import SectorFilter
from tests.conftest import make_ohlcv


class TestSectorFilter:
    def test_filter_uptrend_sector_passes(self, uptrend_daily):
        """上涨趋势板块通过筛选。"""
        data = {"BK0477": uptrend_daily}
        result = SectorFilter.filter(data)
        assert "BK0477" in result

    def test_filter_downtrend_sector_fails(self, downtrend_daily):
        """下跌趋势板块不通过筛选。"""
        data = {"BK_TEST": downtrend_daily}
        result = SectorFilter.filter(data)
        assert "BK_TEST" not in result

    def test_rank_prefers_state4_over_state3(self):
        """状态4板块排在状态3前面。"""
        np.random.seed(42)
        n = 60
        dates = pd.date_range("2026-03-01", periods=n, freq="B")
        # 上涨趋势（状态4）：正弦波 + 上升趋势，阳线为主
        trend = np.linspace(10, 16, n)
        wave = np.sin(np.linspace(0, 3 * 2 * np.pi, n)) * 0.8
        noise = np.random.randn(n) * 0.08
        up_closes = trend + wave + noise
        up_closes = np.maximum(up_closes, 1.0)
        up_opens = up_closes - np.abs(np.random.randn(n) * 0.10) - 0.02
        up = make_ohlcv(dates, up_closes.tolist(), [1000000] * n, opens=up_opens.tolist())

        # 刚翻转（状态3）：相同价格序列，但最后20天转为阴线
        mid_opens = up_closes - np.abs(np.random.randn(n) * 0.10) - 0.02
        for i in range(n - 20, n):
            mid_opens[i] = up_closes[i] + np.abs(np.random.randn() * 0.10) + 0.02
        mid = make_ohlcv(dates, up_closes.tolist(), [1000000] * n, opens=mid_opens.tolist())

        from src.engine.state_machine import StateMachine
        s4 = StateMachine.classify(up)
        s3 = StateMachine.classify(mid)

        # 验证数据构造正确
        assert s4.state == 4, f"期望状态4，实际{s4.state}"
        assert s3.state == 3, f"期望状态3，实际{s3.state}"

        ranked = SectorFilter.rank({"UP": s4, "MID": s3})
        # 状态4的排在状态3前面
        assert ranked[0][0] == "UP"
