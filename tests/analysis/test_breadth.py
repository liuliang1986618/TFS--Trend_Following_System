import pytest
from src.analysis.breadth import MarketBreadth


class TestMarketBreadth:
    def test_empty_results(self):
        result = MarketBreadth.calculate({}, {}, {})
        assert result["uptrend_sectors"] == 0
        assert result["market_health"] == "弱势"
