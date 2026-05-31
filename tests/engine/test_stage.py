"""测试趋势阶段分类器。"""
import pytest
import pandas as pd
import numpy as np
from src.engine.stage import StageClassifier
from tests.conftest import make_ohlcv


class TestStageClassifier:
    def test_state3_is_early(self, uptrend_daily):
        """状态3判定为前期。"""
        result = StageClassifier.classify(3, uptrend_daily)
        assert result.stage == "early"

    def test_state4_over_10_days_is_mid(self, uptrend_daily):
        """状态4超过10日判定为中期。"""
        result = StageClassifier.classify(4, uptrend_daily, days_in_state=15)
        assert result.stage == "mid"

    def test_state1_no_stage(self, downtrend_daily):
        """状态1不适用阶段分类。"""
        result = StageClassifier.classify(1, downtrend_daily)
        assert result.stage == ""

    def test_late_signals_slope_steepening(self):
        """检测斜率加速的晚期信号。

        构造数据：前20日横盘10元，中15日缓慢爬升至11元，末5日加速飙升至22元。
        近5日均涨幅(20%) > 近20日均涨幅(6%) * 3 = 触发斜率变陡信号。
        """
        dates = pd.date_range("2026-03-01", periods=40, freq="B")
        closes = [10.0] * 20
        for i in range(15):
            closes.append(10.0 + i * (1.0 / 14.0))
        closes.extend([14.0, 16.0, 18.0, 20.0, 22.0])
        volumes = [1000000] * 40
        df = make_ohlcv(dates, closes, volumes)
        signals = StageClassifier._check_late_signals(df)
        assert len(signals) >= 1  # 至少检测到斜率变陡
