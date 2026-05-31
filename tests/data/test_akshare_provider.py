"""akshare provider集成测试 — 需要网络连接。"""
import pytest
from src.data.providers.akshare_provider import AkshareProvider


@pytest.fixture
def provider():
    return AkshareProvider()


@pytest.mark.slow
class TestAkshareProviderIntegration:
    def test_fetch_sector_indices(self, provider):
        """能获取板块指数列表且包含BK代码。"""
        df = provider.fetch_sector_indices()
        assert len(df) > 30
        assert "bk_code" in df.columns
        assert "sector_name" in df.columns
        assert df["bk_code"].iloc[0].startswith("BK")

    def test_fetch_sector_daily(self, provider):
        """能获取板块日K数据。"""
        df = provider.fetch_sector_daily("BK0477", "2026-05-01", "2026-05-31")
        assert len(df) > 0
        for col in ["open", "high", "low", "close", "volume"]:
            assert col in df.columns

    def test_fetch_sector_constituents(self, provider):
        """能获取板块成分股。"""
        df = provider.fetch_sector_constituents("BK0477")
        assert len(df) > 0
        assert "symbol" in df.columns
        assert "name" in df.columns

    def test_fetch_theme_indices(self, provider):
        """能获取题材指数列表且包含GN代码。"""
        df = provider.fetch_theme_indices()
        assert len(df) > 50
        assert "gn_code" in df.columns

    def test_fetch_stock_daily(self, provider):
        """能获取个股日K数据（前复权）。"""
        df = provider.fetch_stock_daily("000001", "2026-05-01", "2026-05-31")
        assert len(df) > 0
        for col in ["open", "high", "low", "close", "volume"]:
            assert col in df.columns

    def test_fetch_etf_list(self, provider):
        """能获取ETF列表并分类。"""
        df = provider.fetch_etf_list()
        assert len(df) > 50
        assert "etf_type" in df.columns
        types = df["etf_type"].unique()
        assert "A" in types or "B" in types or "C" in types
