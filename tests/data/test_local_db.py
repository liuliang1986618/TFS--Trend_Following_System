"""测试本地日线数据库的增量存储和读取。"""
import os
import tempfile
import pandas as pd
import numpy as np
import pytest
from src.data.local_db import LocalDB


@pytest.fixture
def temp_db():
    """使用临时目录的本地数据库。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db = LocalDB(data_dir=tmpdir)
        yield db


@pytest.fixture
def sample_daily():
    """5个交易日的OHLCV测试数据。"""
    dates = pd.date_range("2026-05-25", periods=5, freq="B")
    data = {
        "open": [10.0, 10.2, 10.1, 10.5, 10.8],
        "high": [10.3, 10.5, 10.4, 10.8, 11.0],
        "low": [9.8, 10.0, 9.9, 10.3, 10.6],
        "close": [10.2, 10.1, 10.5, 10.8, 10.7],
        "volume": [1000000, 1200000, 900000, 1500000, 1100000],
    }
    df = pd.DataFrame(data, index=dates)
    df.index.name = "date"
    return df


class TestLocalDB:
    def test_save_and_load_stock_daily(self, temp_db, sample_daily):
        """保存个股日线数据后能正确读取。"""
        temp_db.save_daily("stock", "000001", sample_daily)
        loaded = temp_db.load_daily("stock", "000001")
        assert len(loaded) == 5
        assert loaded.iloc[0]["close"] == 10.2
        assert loaded.iloc[-1]["close"] == 10.7

    def test_incremental_update_appends_only_new(self, temp_db, sample_daily):
        """增量更新只追加新数据，不覆盖已有数据。"""
        temp_db.save_daily("stock", "000001", sample_daily.iloc[:3])
        temp_db.incremental_update("stock", "000001", sample_daily)
        loaded = temp_db.load_daily("stock", "000001")
        assert len(loaded) == 5

    def test_incremental_update_no_duplicates(self, temp_db, sample_daily):
        """增量更新不会产生重复行。"""
        temp_db.save_daily("stock", "000001", sample_daily)
        temp_db.incremental_update("stock", "000001", sample_daily)
        loaded = temp_db.load_daily("stock", "000001")
        assert len(loaded) == 5

    def test_load_returns_none_for_missing(self, temp_db):
        """不存在的标的返回None。"""
        result = temp_db.load_daily("stock", "nonexistent")
        assert result is None or len(result) == 0

    def test_list_symbols(self, temp_db, sample_daily):
        """列出所有已存储的标的代码。"""
        temp_db.save_daily("stock", "000001", sample_daily)
        temp_db.save_daily("stock", "000002", sample_daily)
        symbols = temp_db.list_symbols("stock")
        assert "000001" in symbols
        assert "000002" in symbols

    def test_save_sector_daily(self, temp_db, sample_daily):
        """板块类型的数据也能正确存取。"""
        temp_db.save_daily("sector", "BK0477", sample_daily)
        loaded = temp_db.load_daily("sector", "BK0477")
        assert len(loaded) == 5

    def test_get_date_range(self, temp_db, sample_daily):
        """能正确返回数据的日期范围。"""
        temp_db.save_daily("stock", "000001", sample_daily)
        start, end = temp_db.get_date_range("stock", "000001")
        assert start == pd.Timestamp("2026-05-25")
        assert end == pd.Timestamp("2026-05-29")
