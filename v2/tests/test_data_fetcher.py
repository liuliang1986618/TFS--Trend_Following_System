import json
from pathlib import Path

import pandas as pd

from v2.data_layer import DataLayer
from v2.data_layer.fetcher import DataFetcher
from v2.data_layer.providers.akshare_em import AkshareEMProvider


class FakeAkshare:
    @staticmethod
    def stock_zh_a_spot_em():
        return pd.DataFrame(
            [
                {"代码": "000001", "名称": "平安银行", "最新价": 12.3, "成交量": 10000},
                {"代码": "300308", "名称": "中际旭创", "最新价": 88.8, "成交量": 20000},
                {"代码": "688121", "名称": "卓然股份", "最新价": 6.48, "成交量": None},
                {"代码": "000003", "名称": "PT金田A", "最新价": 0.0, "成交量": 0},
                {"代码": "000004", "名称": "国华退", "最新价": 0.28, "成交量": 100},
                {"代码": "688555", "名称": "退市泽达", "最新价": None, "成交量": None},
            ]
        )

    @staticmethod
    def fund_etf_spot_em():
        return pd.DataFrame(
            [
                {"代码": "159915", "名称": "创业板ETF", "成交量": 10000},
                {"代码": "560000", "名称": "智能电车ETF浦银", "成交量": None},
            ]
        )

    @staticmethod
    def stock_zh_a_hist(symbol, period, start_date, end_date, adjust, timeout=None):
        assert period == "daily"
        assert adjust == "qfq"
        assert timeout == 15
        return pd.DataFrame(
            [
                {"日期": "2026-06-10", "开盘": 10, "最高": 11, "最低": 9, "收盘": 10.5, "成交量": 100},
                {"日期": "2026-06-11", "开盘": 11, "最高": 12, "最低": 10, "收盘": 11.5, "成交量": 110},
            ]
        )

    @staticmethod
    def fund_etf_hist_em(symbol, period, start_date, end_date, adjust):
        assert period == "daily"
        assert adjust == "qfq"
        return pd.DataFrame(
            [
                {"日期": "2026-06-10", "开盘": 1, "最高": 1.1, "最低": 0.9, "收盘": 1.05, "成交量": 1000},
                {"日期": "2026-06-11", "开盘": 1.1, "最高": 1.2, "最低": 1.0, "收盘": 1.15, "成交量": 1100},
            ]
        )


def test_akshare_em_provider_normalizes_universe_and_daily_data():
    provider = AkshareEMProvider(ak_module=FakeAkshare)

    stocks = provider.fetch_stock_universe()
    etfs = provider.fetch_etf_universe()
    daily = provider.fetch_stock_daily("000001", start_date="20260601", end_date="20260612")

    assert stocks == [{"code": "000001", "name": "平安银行"}, {"code": "300308", "name": "中际旭创"}]
    assert etfs == [{"code": "159915", "name": "创业板ETF"}]
    assert list(daily.columns) == ["date", "open", "high", "low", "close", "volume"]
    assert list(daily["date"].dt.strftime("%Y-%m-%d")) == ["2026-06-10", "2026-06-11"]


def test_data_fetcher_update_market_daily_writes_v2_market_files_and_universe(tmp_path):
    provider = AkshareEMProvider(ak_module=FakeAkshare)
    fetcher = DataFetcher(data_dir=tmp_path, provider=provider)

    result = fetcher.update_market_daily(start_date="20260601", end_date="20260612", dtypes=("stock", "etf"))

    assert result["status"] == "completed"
    assert result["checks"]["stock"]["total"] == 2
    assert result["checks"]["stock"]["success"] == 2
    assert result["checks"]["stock"]["skipped"] == 0
    assert result["checks"]["etf"]["total"] == 1
    assert result["checks"]["etf"]["success"] == 1
    assert (tmp_path / "stock" / "000001.parquet").exists()
    assert (tmp_path / "stock" / "300308.parquet").exists()
    assert (tmp_path / "etf" / "159915.parquet").exists()

    stock_universe = json.loads((tmp_path / "meta" / "universe" / "stock_list.json").read_text(encoding="utf-8"))
    assert stock_universe == [{"code": "000001", "name": "平安银行"}, {"code": "300308", "name": "中际旭创"}]
    assert DataLayer(tmp_path).load_daily("stock", "000001")["close"].tolist() == [10.5, 11.5]


def test_data_layer_update_market_daily_uses_fetcher_boundary(tmp_path):
    provider = AkshareEMProvider(ak_module=FakeAkshare)
    layer = DataLayer(tmp_path, fetcher=DataFetcher(data_dir=tmp_path, provider=provider))

    result = layer.update_market_daily(start_date="20260601", end_date="20260612", dtypes=("stock",))

    assert result["checks"]["stock"]["success"] == 2
    assert result["checks"]["stock"]["skipped"] == 0
    assert layer.list_symbols("stock") == ["000001", "300308"]


def test_data_fetcher_skips_existing_valid_market_file_by_default(tmp_path):
    stock_dir = tmp_path / "stock"
    stock_dir.mkdir()
    pd.DataFrame(
        [
            {"date": "2026-06-11", "open": 10, "high": 11, "low": 9, "close": 10.5, "volume": 100},
            {"date": "2026-06-12", "open": 11, "high": 12, "low": 10, "close": 11.5, "volume": 110},
        ]
    ).to_parquet(stock_dir / "000001.parquet")
    provider = AkshareEMProvider(ak_module=FakeAkshare)
    fetcher = DataFetcher(data_dir=tmp_path, provider=provider)

    result = fetcher.update_market_daily(start_date="20260601", end_date="20260612", dtypes=("stock",))

    assert result["checks"]["stock"]["total"] == 2
    assert result["checks"]["stock"]["skipped"] == 1
    assert result["checks"]["stock"]["success"] == 1


def test_data_fetcher_treats_friday_file_as_current_for_sunday_end_date(tmp_path):
    stock_dir = tmp_path / "stock"
    stock_dir.mkdir()
    pd.DataFrame(
        [
            {"date": "2026-06-25", "open": 10, "high": 11, "low": 9, "close": 10.5, "volume": 100},
            {"date": "2026-06-26", "open": 11, "high": 12, "low": 10, "close": 11.5, "volume": 110},
        ]
    ).to_parquet(stock_dir / "000001.parquet")
    provider = AkshareEMProvider(ak_module=FakeAkshare)
    fetcher = DataFetcher(data_dir=tmp_path, provider=provider)

    result = fetcher.update_market_daily(start_date="20260601", end_date="20260628", dtypes=("stock",))

    assert result["checks"]["stock"]["skipped"] == 1
