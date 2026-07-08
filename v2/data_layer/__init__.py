"""DataLayer facade for TFS v2."""

from __future__ import annotations

import json
from pathlib import Path

from .config import DATA_DIR, META_ETF_LIST
from .fetcher import DataFetcher
from .history import HistoryStore
from .lifecycle import LifecycleManager
from .relations import RelationStore
from .storage import MarketDataStore


class DataLayer:
    """Single data access facade for upper layers."""

    def __init__(self, data_dir: str | Path | None = None, fetcher: DataFetcher | None = None):
        self.data_dir = Path(data_dir or DATA_DIR)
        self.market = MarketDataStore(self.data_dir)
        self.relations = RelationStore(self.data_dir)
        self.lifecycle = LifecycleManager(self.data_dir)
        self.history = HistoryStore(self.data_dir)
        self.fetcher = fetcher or DataFetcher(self.data_dir)

    def load_daily(self, dtype: str, code: str, end_date: str | None = None):
        return self.market.load_daily(dtype, code, end_date=end_date)

    def list_symbols(self, dtype: str) -> list[str]:
        return self.market.load_universe(dtype)

    def get_date_range(self, dtype: str, code: str):
        return self.market.get_date_range(dtype, code)

    def check_market_health(self, date: str | None = None) -> dict:
        return self.lifecycle.check_market_health(date)

    def update_market_daily(self, date: str | None = None, **kwargs) -> dict:
        return self.fetcher.update_market_daily(date=date, **kwargs)

    def update_relations_weekly(self, week: str | None = None, **kwargs) -> dict:
        return self.fetcher.update_relations_weekly(week=week, **kwargs)

    def get_relation_version(self) -> str | None:
        return self.relations.get_relation_version()

    def get_stock_profile(self, code: str, relation_version: str | None = None) -> dict:
        return self.relations.get_stock_profile(code)

    def get_sector_members(self, sector_id: str, relation_version: str | None = None) -> list[str]:
        return self.relations.get_constituents("sector", sector_id)

    def get_theme_members(self, theme_id: str, relation_version: str | None = None) -> list[str]:
        return self.relations.get_constituents("theme", theme_id)

    def get_relation_names(self, relation_version: str | None = None) -> dict:
        return self.relations.get_relation_names()

    def get_etf_names(self) -> dict[str, str]:
        path = self.data_dir / "meta" / "universe" / META_ETF_LIST
        if path.exists():
            try:
                items = json.loads(path.read_text(encoding="utf-8"))
                return {item.get("code"): item.get("name") for item in items if item.get("code") and item.get("name")}
            except Exception:
                pass
        # v1 fallback
        from .config import V1_DATA_DIR, V1_LEGACY_DIR
        for v1_path in [Path(V1_DATA_DIR) / "etf_names.json", Path(V1_LEGACY_DIR) / "etf_names.json"]:
            if v1_path.exists():
                try:
                    data = json.loads(v1_path.read_text(encoding="utf-8"))
                    if isinstance(data, dict):
                        return data
                except Exception:
                    pass
        return {}

    def get_stock_names(self) -> dict[str, str]:
        """个股名称映射，fallback 读 v1 stock_names.json。"""
        path = self.data_dir / "meta" / "stock_names.json"
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return data
            except Exception:
                pass
        from .config import V1_DATA_DIR, V1_LEGACY_DIR
        for v1_path in [Path(V1_DATA_DIR) / "stock_names.json", Path(V1_LEGACY_DIR) / "stock_names.json"]:
            if v1_path.exists():
                try:
                    data = json.loads(v1_path.read_text(encoding="utf-8"))
                    if isinstance(data, dict):
                        return data
                except Exception:
                    pass
        return {}

    def get_symbol_name(self, code: str, dtype: str = "stock") -> str:
        """取单个标的名称。"""
        names = self.get_etf_names() if dtype == "etf" else self.get_stock_names()
        return names.get(code, code)

    def check_relation_health(self, relation_version: str | None = None) -> dict:
        return self.lifecycle.check_relation_health(relation_version)


__all__ = ["DataLayer", "DATA_DIR"]
