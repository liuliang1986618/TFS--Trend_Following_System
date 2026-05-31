"""测试前高/前低识别算法（局部极值检测）。"""
import pytest
import pandas as pd
import numpy as np
from src.engine.pivots import PivotDetector
from tests.conftest import make_ohlcv


class TestPivotDetector:
    def test_detect_high_pivot(self):
        """检测明显的局部高点。"""
        n = 30
        dates = pd.date_range("2026-04-01", periods=n, freq="B")
        # 避免双重顶：第二段从略低于峰值的价格开始下降
        closes = [10.0 + i * 0.1 for i in range(15)] + \
                 [11.3 - i * 0.1 for i in range(15)]
        volumes = [1000000] * n
        df = make_ohlcv(dates, closes, volumes)
        highs = PivotDetector.find_highs(df, window=3)
        assert len(highs) >= 1

    def test_detect_low_pivot(self):
        """检测明显的局部低点。"""
        n = 30
        dates = pd.date_range("2026-04-01", periods=n, freq="B")
        closes = [20.0 - i * 0.3 for i in range(15)] + \
                 [15.5 + i * 0.3 for i in range(15)]
        volumes = [1000000] * n
        df = make_ohlcv(dates, closes, volumes)
        lows = PivotDetector.find_lows(df, window=3)
        assert len(lows) >= 1

    def test_recent_high(self):
        """获取最近一个有效的前高（60日窗口内）。"""
        n = 50
        dates = pd.date_range("2026-03-01", periods=n, freq="B")
        closes = [10.0 + i * 0.2 for i in range(25)] + \
                 [15.0 - i * 0.1 for i in range(25)]
        volumes = [1000000] * n
        df = make_ohlcv(dates, closes, volumes)
        recent_high = PivotDetector.recent_high(df, max_age=60)
        assert recent_high is not None
        assert "date" in recent_high
        assert "price" in recent_high

    def test_recent_low(self):
        """获取最近一个有效的前低。"""
        n = 50
        dates = pd.date_range("2026-03-01", periods=n, freq="B")
        closes = [20.0 - i * 0.3 for i in range(20)] + \
                 [14.0 + i * 0.2 for i in range(30)]
        volumes = [1000000] * n
        df = make_ohlcv(dates, closes, volumes)
        recent_low = PivotDetector.recent_low(df, max_age=60)
        assert recent_low is not None

    def test_no_pivot_when_flat(self):
        """横盘无显著极值——震荡市正确识别。

        → 少亏钱：横盘不产生假突破信号，避免频繁交易亏损。
        """
        n = 30
        dates = pd.date_range("2026-04-01", periods=n, freq="B")
        closes = [10.0 + np.random.randn() * 0.05 for _ in range(n)]
        volumes = [1000000] * n
        df = make_ohlcv(dates, closes, volumes)
        highs = PivotDetector.find_highs(df, window=3)
        lows = PivotDetector.find_lows(df, window=3)
        assert len(highs) <= n // 3
        assert len(lows) <= n // 3

    def test_expired_pivot_ignored(self):
        """超过60个交易日的极值不被当作有效前高/前低。

        → 少亏钱：过期的支撑/阻力位已失去技术意义，参考它们
          会导致错误的止损/止盈位置。
        """
        n = 100
        dates = pd.date_range("2026-01-01", periods=n, freq="B")
        closes = [10.0 + i * 0.2 for i in range(20)] + \
                 [14.0 - i * 0.05 for i in range(80)]
        volumes = [1000000] * n
        df = make_ohlcv(dates, closes, volumes)
        recent_high = PivotDetector.recent_high(df, max_age=60)
        # 极值在79个交易日之外(>60)，应被过滤——返回None
        assert recent_high is None

    def test_get_last_two_highs(self):
        """检测最近2个更高高点（满足结构A条件）。

        → 多赚钱：2个更高高=完整上涨结构确认，这是状态3→4的关键条件。
        """
        n = 60
        dates = pd.date_range("2026-02-01", periods=n, freq="B")
        closes = []
        # 背景微涨
        closes.extend([9.0 + i * 0.05 for i in range(18)])
        # 峰值1: 上升→峰值→下降(V形)
        closes.extend([10.1, 10.3, 10.5, 10.7, 10.9, 11.1, 10.9, 10.7, 10.5, 10.3])
        # 回升+更高的峰值2(V形)
        closes.extend([10.5, 10.7, 10.9, 11.1, 11.3, 11.5, 11.7,
                       12.0, 12.3, 12.6, 12.4, 12.2, 12.0, 11.8,
                       11.6, 11.4, 11.2, 11.0])
        # 尾部走势
        closes.extend([10.8, 10.6, 10.4, 10.2, 10.0, 9.8, 9.6,
                       9.4, 9.2, 9.0, 8.8, 8.6, 8.4, 8.2])
        volumes = [1000000] * len(closes)
        df = make_ohlcv(dates[:len(closes)], closes, volumes)
        highs = PivotDetector.get_last_n_highs(df, n=2)
        assert len(highs) >= 2
        if len(highs) >= 2:
            assert highs[-1]["price"] > highs[-2]["price"]
