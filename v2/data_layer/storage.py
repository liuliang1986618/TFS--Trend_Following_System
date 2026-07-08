"""Market data storage for TFS v2."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .config import DATA_DIR, VALID_DTYPES, V1_DATA_DIR


class MarketDataStore:
    """Read market parquet files from the v2 data directory."""

    def __init__(self, data_dir: str | Path | None = None):
        self.data_dir = Path(data_dir or DATA_DIR)
        # v1 fallback 仅在生产默认数据目录启用（测试自定义目录不触发，保证隔离）
        self._enable_v1_fallback = self.data_dir.resolve() == Path(DATA_DIR).resolve()

    def load_daily(self, dtype: str, code: str, end_date: str | None = None) -> pd.DataFrame:
        self._validate_dtype(dtype)
        path = self._resolve_daily_path(dtype, code)
        if path is None:
            raise FileNotFoundError(f"{dtype}/{code} not found in v2 or v1 fallback")

        df = pd.read_parquet(path)
        # v1 parquet 可能将 date 作为 index，统一 reset 为列
        if "date" not in df.columns and df.index.name == "date":
            df = df.reset_index()
        if "date" not in df.columns:
            raise ValueError(f"missing date column: {path}")
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").drop_duplicates("date", keep="last").reset_index(drop=True)
        if end_date is not None:
            df = df[df["date"] <= pd.to_datetime(end_date)].reset_index(drop=True)
        self._validate_daily_schema(df, path)
        return df

    def _resolve_daily_path(self, dtype: str, code: str) -> Path | None:
        """先找 v2/data/{dtype}/{code}.parquet，找不到 fallback 读 v1 dashboard/data。"""
        v2_path = self.data_dir / dtype / f"{code}.parquet"
        if v2_path.exists():
            return v2_path
        if not self._enable_v1_fallback:
            return None
        v1 = Path(V1_DATA_DIR)
        candidates = []
        if dtype == "stock":
            candidates = [v1 / "stock" / f"{code}.parquet", v1 / f"stock_{code}.parquet"]
        elif dtype == "etf":
            candidates = [v1 / "etf" / f"{code}.parquet", v1 / f"etf_{code}.parquet"]
        elif dtype == "sector":
            candidates = [v1 / f"sector_{code}.parquet"]
        elif dtype == "theme":
            candidates = [v1 / f"theme_{code}.parquet"]
        elif dtype == "index":
            candidates = [self.data_dir / "index" / f"{code}.parquet"]
        for c in candidates:
            if c.exists():
                return c
        return None

    def load_universe(self, dtype: str) -> list[str]:
        self._validate_dtype(dtype)
        metadata = self._load_universe_metadata(dtype)
        if metadata is not None:
            return metadata
        # v2 目录扫描
        data_dir = self.data_dir / dtype
        if data_dir.exists():
            v2_codes = sorted(path.stem for path in data_dir.glob("*.parquet"))
            if v2_codes:
                return v2_codes
        # v1 fallback：仅生产默认目录启用，扫描 v1 dashboard/data
        if not self._enable_v1_fallback:
            return []
        return self._load_v1_universe(dtype)

    def _load_v1_universe(self, dtype: str) -> list[str]:
        v1 = Path(V1_DATA_DIR)
        codes: list[str] = []
        if dtype == "stock":
            stock_dir = v1 / "stock"
            codes_set = set()
            if stock_dir.exists():
                codes_set.update(p.stem for p in stock_dir.glob("*.parquet"))
            codes_set.update(p.stem.replace("stock_", "") for p in v1.glob("stock_*.parquet"))
            codes = sorted(codes_set)
        elif dtype == "etf":
            etf_dir = v1 / "etf"
            codes_set = set()
            if etf_dir.exists():
                codes_set.update(p.stem for p in etf_dir.glob("*.parquet"))
            codes_set.update(p.stem.replace("etf_", "") for p in v1.glob("etf_*.parquet"))
            codes = sorted(codes_set)
        elif dtype == "sector":
            codes = sorted(p.stem.replace("sector_", "") for p in v1.glob("sector_*.parquet"))
        elif dtype == "theme":
            codes = sorted(p.stem.replace("theme_", "") for p in v1.glob("theme_*.parquet"))
        elif dtype == "index":
            idx_dir = self.data_dir / "index"
            if idx_dir.exists():
                codes = sorted(p.stem for p in idx_dir.glob("*.parquet"))
        return codes

    def get_date_range(self, dtype: str, code: str) -> tuple[str | None, str | None]:
        df = self.load_daily(dtype, code)
        if df.empty:
            return None, None
        dates = df["date"].dt.strftime("%Y-%m-%d")
        return dates.iloc[0], dates.iloc[-1]

    def _load_universe_metadata(self, dtype: str) -> list[str] | None:
        candidates = [
            self.data_dir / "meta" / "universe" / f"{dtype}_list.json",
            self.data_dir / "meta" / f"{dtype}_list.json",
        ]
        for path in candidates:
            if not path.exists():
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                data = data.get("data") or data.get("items") or data.get(dtype) or []
            symbols: list[str] = []
            for item in data:
                if isinstance(item, str):
                    symbols.append(item)
                elif isinstance(item, dict) and item.get("code"):
                    symbols.append(str(item["code"]))
            return sorted(dict.fromkeys(symbols))
        return None

    @staticmethod
    def _validate_dtype(dtype: str) -> None:
        if dtype not in VALID_DTYPES:
            raise ValueError(f"unsupported dtype: {dtype}")

    @staticmethod
    def _validate_daily_schema(df: pd.DataFrame, path: Path) -> None:
        required = {"date", "open", "high", "low", "close", "volume"}
        missing = sorted(required - set(df.columns))
        if missing:
            raise ValueError(f"missing columns in {path}: {missing}")
        if df["date"].isna().any():
            raise ValueError(f"empty date in {path}")
        if df["date"].duplicated().any():
            raise ValueError(f"duplicate date in {path}")
        if df.empty:
            raise ValueError(f"empty daily data in {path}")
        if df[["open", "high", "low", "close"]].isna().any().any():
            raise ValueError(f"empty OHLC value in {path}")
        if (df["close"] <= 0).any():
            raise ValueError(f"non-positive close in {path}")
        if (df["volume"] < 0).any():
            raise ValueError(f"negative volume in {path}")
