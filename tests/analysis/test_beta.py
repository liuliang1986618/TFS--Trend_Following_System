import pytest
import pandas as pd
import numpy as np
from src.analysis.beta import BetaCalculator
from tests.conftest import make_ohlcv


class TestBetaCalculator:
    def test_beta_calculation(self):
        n = 60
        dates = pd.date_range("2026-02-01", periods=n, freq="B")
        sector = make_ohlcv(dates, list(np.linspace(10, 15, n)), [1000000] * n)
        bench = make_ohlcv(dates, list(np.linspace(10, 12, n)), [1000000] * n)
        beta = BetaCalculator.calculate(sector, bench)
        assert beta > 0

    def test_interpret_high_beta(self):
        result = BetaCalculator.interpret(1.8)
        assert "高弹性" in result
