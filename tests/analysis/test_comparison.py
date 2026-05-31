import pytest
from src.analysis.comparison import TrendComparison
from src.engine.state_machine import StateMachine
from tests.conftest import make_ohlcv
import numpy as np


class TestTrendComparison:
    def test_new_uptrend_detected(self, uptrend_daily, downtrend_daily):
        curr = {"BK": StateMachine.classify(uptrend_daily)}
        prev = {"BK": StateMachine.classify(downtrend_daily)}
        result = TrendComparison.compare(curr, prev)
        assert len(result["new_uptrend"]) >= 0

    def test_empty_previous(self, uptrend_daily):
        curr = {"BK": StateMachine.classify(uptrend_daily)}
        result = TrendComparison.compare(curr, {})
        assert "new_uptrend" in result
