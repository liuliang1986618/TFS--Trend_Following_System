"""测试龙头识别。"""
import pytest
import numpy as np
import pandas as pd
from src.funnel.leader import LeaderIdentifier
from src.engine.state_machine import StateMachine
from tests.conftest import make_ohlcv


class TestLeaderIdentifier:
    def test_identify_ranks_by_return(self):
        """涨幅最高的排在龙头第一位。"""
        n = 40
        dates = pd.date_range("2026-03-01", periods=n, freq="B")
        # 龙头: 涨幅最大
        leader_df = make_ohlcv(dates, list(np.linspace(10, 20, n)), [2000000]*n)
        # 跟风: 涨幅较小
        follower_df = make_ohlcv(dates, list(np.linspace(10, 15, n)), [1000000]*n)

        stock_states = {
            "LEADER": StateMachine.classify(leader_df),
            "FOLLOWER": StateMachine.classify(follower_df),
        }
        stock_daily = {"LEADER": leader_df, "FOLLOWER": follower_df}

        ranked = LeaderIdentifier.identify("GN_TEST", stock_states, stock_daily)
        assert len(ranked) == 2
        assert ranked[0][0] == "LEADER"  # 涨幅最大的排第一
