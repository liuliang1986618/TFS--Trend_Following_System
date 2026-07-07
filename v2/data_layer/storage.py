"""Market data storage for TFS v2."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .config import DATA_DIR, VALID_DTYPES


class MarketDataStore:
    """Read market parquet files from the v2 data directory."""

    def __init__(self, data_dir: str | Path | None = None):
        self.data_dir = Path(data_dir or DATA_DIR)

    def load_daily(self, dtype: str, code: str, end_date: str | None = None) -> pd.DataFrame:
        self._validate_dtype(dtype)
        path = self.data_dir / dtype / f"{code}.parquet"
        if not path.exists():
            raise FileNotFoundError(path)

        df = pd.read_parquet(path)
        if "date" not in df.columns:
            raise ValueError(f"missing date column: {path}")
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").drop_duplicates("date", keep="last").reset_index(drop=True)
        if end_date is not None:
            df = df[df["date"] <= pd.to_datetime(end_date)].reset_index(drop=True)
        self._validate_daily_schema(df, path)
        return df

    def load_universe(self, dtype: str) -> list[str]:
        self._validate_dtype(dtype)
        metadata = self._load_universe_metadata(dtype)
        if metadata is not None:
            return metadata
        data_dir = self.data_dir / dtype
        if not data_dir.exists():
            return []
        return sorted(path.stem for path in data_dir.glob("*.parquet"))

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
