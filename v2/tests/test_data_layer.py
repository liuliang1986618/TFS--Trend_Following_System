from pathlib import Path

import pandas as pd
import pytest

from v2.data_layer import DataLayer
from v2.data_layer.lifecycle import LifecycleManager
from v2.data_layer.relations import RelationStore
from v2.data_layer.storage import MarketDataStore


def test_market_data_store_load_daily_returns_sorted_frame(tmp_path):
    stock_dir = tmp_path / "stock"
    stock_dir.mkdir()
    pd.DataFrame(
        [
            {"date": "2026-06-12", "open": 2.0, "high": 2.2, "low": 1.9, "close": 2.1, "volume": 20},
            {"date": "2026-06-10", "open": 1.0, "high": 1.2, "low": 0.9, "close": 1.1, "volume": 10},
            {"date": "2026-06-11", "open": 1.5, "high": 1.7, "low": 1.4, "close": 1.6, "volume": 15},
        ]
    ).to_parquet(stock_dir / "300308.parquet")

    df = MarketDataStore(tmp_path).load_daily("stock", "300308", end_date="2026-06-11")

    assert list(df["date"].dt.strftime("%Y-%m-%d")) == ["2026-06-10", "2026-06-11"]
    assert list(df["close"]) == [1.1, 1.6]


def test_market_data_store_load_universe_uses_metadata_then_files(tmp_path):
    universe_dir = tmp_path / "meta" / "universe"
    universe_dir.mkdir(parents=True)
    (tmp_path / "stock").mkdir()
    pd.DataFrame(
        [{"date": "2026-06-10", "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1}]
    ).to_parquet(tmp_path / "stock" / "300308.parquet")
    (universe_dir / "stock_list.json").write_text('[{"code": "000001"}, {"code": "300308"}]', encoding="utf-8")

    assert MarketDataStore(tmp_path).load_universe("stock") == ["000001", "300308"]
    assert MarketDataStore(tmp_path).load_universe("etf") == []


def test_market_data_store_rejects_empty_daily_file(tmp_path):
    stock_dir = tmp_path / "stock"
    stock_dir.mkdir()
    pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"]).to_parquet(stock_dir / "300308.parquet")

    with pytest.raises(ValueError, match="empty daily data"):
        MarketDataStore(tmp_path).load_daily("stock", "300308")


def test_relation_store_get_constituents_reads_current_relation_version(tmp_path):
    relations_dir = tmp_path / "meta" / "relations"
    relations_dir.mkdir(parents=True)
    (relations_dir / "current.json").write_text(
        '{"version": "2026-W26", "sector_members": {"sector-a": ["300308"]}, "theme_members": {"theme-a": ["300308", "000001"]}}',
        encoding="utf-8",
    )

    store = RelationStore(tmp_path)

    assert store.get_constituents("sector", "sector-a") == ["300308"]
    assert store.get_constituents("theme", "theme-a") == ["300308", "000001"]
    assert store.get_constituents("sector", "missing") == []


def test_lifecycle_manager_check_market_health_returns_structured_result(tmp_path):
    stock_dir = tmp_path / "stock"
    stock_dir.mkdir()
    pd.DataFrame(
        [{"date": "2026-06-12", "open": 1, "high": 1.1, "low": 0.9, "close": 1, "volume": 1}]
    ).to_parquet(stock_dir / "300308.parquet")

    result = LifecycleManager(tmp_path).check_market_health("2026-06-12")

    assert result["date"] == "2026-06-12"
    assert result["checks"]["stock"]["actual_count"] == 1
    assert result["checks"]["stock"]["latest_date_ok"] is True
    assert result["checks"]["stock"]["status"] == "warning"
    assert result["allowed"]["stock_recommendation"] is False
    assert "issues" in result
    assert "allowed" in result


def test_data_layer_facade_delegates_to_stores(tmp_path):
    stock_dir = tmp_path / "stock"
    stock_dir.mkdir()
    pd.DataFrame(
        [{"date": "2026-06-12", "open": 1, "high": 1.1, "low": 0.9, "close": 1, "volume": 1}]
    ).to_parquet(stock_dir / "300308.parquet")

    layer = DataLayer(tmp_path)

    assert layer.list_symbols("stock") == ["300308"]
    assert layer.get_date_range("stock", "300308") == ("2026-06-12", "2026-06-12")
    assert layer.check_market_health("2026-06-12")["checks"]["stock"]["actual_count"] == 1
