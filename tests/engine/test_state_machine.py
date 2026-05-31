"""测试6状态状态机。"""
import pytest
import pandas as pd
import numpy as np
from src.engine.state_machine import StateMachine, TrendState
from tests.conftest import make_ohlcv


class TestStateMachine:
    def test_uptrend_classifies_as_state4(self, uptrend_daily):
        """完整上涨趋势应判定为状态4。"""
        result = StateMachine.classify(uptrend_daily)
        assert result.state == 4

    def test_downtrend_classifies_as_state1(self, downtrend_daily):
        """持续下跌趋势应判定为状态1。"""
        result = StateMachine.classify(downtrend_daily)
        assert result.state == 1

    def test_state_transition_2to3(self):
        """状态2→3=买点1: 放量突破前高。

        → 多赚钱：这是第一个买点，提前埋伏。
        """
        event = {
            "broke_prev_high": True,
            "volume_surge": True,
        }
        new_state = StateMachine.transition(2, event)
        assert new_state == 3

    def test_state_transition_3to1(self):
        """状态3→1=止损: 假突破跌破新低。

        → 少亏钱：发现假突破立即止损，保住本金。
        """
        event = {
            "broke_prev_low": True,
            "volume_surge": True,
        }
        new_state = StateMachine.transition(3, event)
        assert new_state == 1

    def test_state_transition_4to5(self):
        """状态4→5: 上涨中的正常回调（缩量未破前低）。

        → 少亏钱：区分正常回调vs趋势结束，避免错误清仓。
        """
        event = {
            "consecutive_drop": True,
            "broke_prev_low": False,
            "volume_shrink": True,
        }
        new_state = StateMachine.transition(4, event)
        assert new_state == 5

    def test_state_transition_5to3prime(self):
        """状态5→3': 放量跌破前低=防守。

        → 少亏钱：上涨结构被破坏，减仓防守保住利润。
        """
        event = {
            "broke_prev_low": True,
            "volume_surge": True,
        }
        new_state = StateMachine.transition(5, event)
        assert new_state == "3'"

    def test_state_transition_3prime_to_1(self):
        """状态3'→1=退场: 再破新低清仓。

        → 少亏钱：趋势彻底结束，不清仓就是放任亏损扩大。
        """
        event = {
            "broke_new_low": True,
        }
        new_state = StateMachine.transition("3'", event)
        assert new_state == 1

    def test_position_suggestion(self):
        """每个状态都有明确的仓位建议——消除决策模糊性。

        → 多赚钱+少亏钱：状态4满仓=充分享受主升浪。
          状态1空仓=熊市不亏就是赚。
        """
        assert StateMachine.position_suggestion(1) == 0.0   # 空仓
        assert StateMachine.position_suggestion(2) == 0.0   # 观望
        pos3 = StateMachine.position_suggestion(3)
        assert 0.16 <= pos3 <= 0.34  # 试探仓1/6~1/3
        assert StateMachine.position_suggestion(4) == 1.0   # 标准仓
        assert StateMachine.position_suggestion(5) == 1.0   # 持股等加仓
        assert StateMachine.position_suggestion("3'") == 0.333  # 防守

    def test_all_six_states_accessible(self):
        """验证所有6种状态都有定义——缺一不可。"""
        states = StateMachine.ALL_STATES
        assert 1 in states
        assert 2 in states
        assert 3 in states
        assert 4 in states
        assert 5 in states
        assert "3'" in states
        assert len(states) == 6

    def test_state_labels_readable(self):
        """状态标签人类可读——Dashboard展示需要。"""
        assert StateMachine.STATE_LABELS[1] == "下跌趋势"
        assert StateMachine.STATE_LABELS[3] == "翻转确认中"
        assert StateMachine.STATE_LABELS["3'"] == "转跌确认中"

    def test_transition_3to4_buy_point_2(self):
        """状态3→4=买点2: 再创新高结构完整，加至标准仓。

        → 多赚钱：这是最重要的加仓信号——结构从初步变成完整。
        """
        event = {
            "broke_prev_high": True,
            "volume_surge": True,
        }
        new_state = StateMachine.transition(3, event)
        assert new_state == 4
