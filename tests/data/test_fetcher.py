"""测试数据拉取编排器的流程控制逻辑。"""
import pytest
import pandas as pd
from unittest.mock import MagicMock
from src.data.fetcher import DataFetcher
from src.data.local_db import LocalDB
from src.data.mappings import ConstituentMapping
from tests.conftest import make_ohlcv


class TestDataFetcher:
    def test_update_daily_skips_existing_dates(self, tmp_path):
        """增量更新跳过已覆盖的日期——避免重复拉取。

        → 少亏钱：重复请求 = 浪费API配额 = 增加被封风险。
        """
        mock_provider = MagicMock()
        sample = make_ohlcv(
            ["2026-05-31"], [10.5], [1000000]
        )
        mock_provider.fetch_sector_daily.return_value = sample

        db = LocalDB(str(tmp_path))
        existing = make_ohlcv(
            ["2026-05-29", "2026-05-30", "2026-05-31"],
            [10.0, 10.2, 10.5],
            [1000000, 1100000, 1200000],
        )
        db.save_daily("sector", "BK0477", existing)

        fetcher = DataFetcher(provider=mock_provider, local_db=db)
        result = fetcher.update_daily("2026-05-31")

        # 因为已有05-31数据，不应再次拉取
        mock_provider.fetch_sector_daily.assert_not_called()

    def test_load_all_sectors_filters_short_data(self, tmp_path):
        """数据不足20日的板块被自动过滤。

        → 少亏钱：数据不足无法计算MA20和量能基准，
          强行分析会产出不可靠的信号。
        """
        db = LocalDB(str(tmp_path))
        # 只有10天数据的板块
        short = make_ohlcv(
            pd.date_range("2026-05-20", periods=10, freq="B").tolist(),
            [10 + i * 0.1 for i in range(10)],
            [1000000] * 10,
        )
        db.save_daily("sector", "BK_SHORT", short)

        # 有30天数据的板块
        long = make_ohlcv(
            pd.date_range("2026-05-01", periods=30, freq="B").tolist(),
            [10 + i * 0.1 for i in range(30)],
            [1000000] * 30,
        )
        db.save_daily("sector", "BK_LONG", long)

        fetcher = DataFetcher(local_db=db)
        result = fetcher.load_all_sectors()

        assert "BK_SHORT" not in result  # 数据不足
        assert "BK_LONG" in result       # 数据充足

    def test_init_db_skips_type_c_etfs(self, tmp_path):
        """init_db只拉取A和B类ETF，C类宽基跳过。

        → 少亏钱：C类宽基不适用趋势跟随策略，
          不浪费时间和存储在不适用策略的标的上。
        """
        mock_provider = MagicMock()
        # Mock sector data
        mock_provider.fetch_sector_indices.return_value = pd.DataFrame({
            "bk_code": ["BK0477"], "sector_name": ["半导体"]
        })
        mock_provider.fetch_sector_daily.return_value = make_ohlcv(
            pd.date_range("2024-06-01", periods=500, freq="B").tolist(),
            [10 + i * 0.01 for i in range(500)],
            [1000000] * 500,
        )
        mock_provider.fetch_sector_constituents.return_value = pd.DataFrame({
            "symbol": ["000001"], "name": ["测试股"]
        })
        mock_provider.fetch_theme_indices.return_value = pd.DataFrame({
            "gn_code": [], "theme_name": []
        })

        # ETF列表：A类1只，B类1只，C类1只
        mock_provider.fetch_etf_list.return_value = pd.DataFrame({
            "symbol": ["512480", "159819", "510300"],
            "name": ["半导体ETF", "新能源ETF", "沪深300ETF"],
            "etf_type": ["A", "B", "C"],
        })

        db = LocalDB(str(tmp_path))
        fetcher = DataFetcher(provider=mock_provider, local_db=db)

        result = fetcher.init_db("2026-05-31")
        # C类ETF不应被拉取
        assert len(result["errors"]) == 0
