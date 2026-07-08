"""AkShare Eastmoney provider for TFS v2 market data."""

from __future__ import annotations

import importlib
import re
from typing import Any

import pandas as pd
import requests


class AkshareEMProvider:
    """Fetch and normalize Eastmoney market data through AkShare."""

    def __init__(self, ak_module: Any | None = None):
        self.ak = ak_module or importlib.import_module("akshare")
        self._uses_default_ak = ak_module is None
        self._em_board_mapping_cache: dict[str, dict[str, str]] = {}

    def fetch_stock_universe(self) -> list[dict[str, str]]:
        df = self.ak.stock_zh_a_spot_em()
        return self._normalize_universe(df)

    def fetch_etf_universe(self) -> list[dict[str, str]]:
        df = self.ak.fund_etf_spot_em()
        return self._normalize_universe(df)

    def fetch_stock_daily(self, code: str, start_date: str, end_date: str) -> pd.DataFrame:
        df = self.ak.stock_zh_a_hist(
            symbol=code,
            period="daily",
            start_date=self._compact_date(start_date),
            end_date=self._compact_date(end_date),
            adjust="qfq",
            timeout=15,
        )
        return self._normalize_daily(df)

    def fetch_etf_daily(self, code: str, start_date: str, end_date: str) -> pd.DataFrame:
        df = self.ak.fund_etf_hist_em(
            symbol=code,
            period="daily",
            start_date=self._compact_date(start_date),
            end_date=self._compact_date(end_date),
            adjust="qfq",
        )
        return self._normalize_daily(df)

    def fetch_index_daily(self, code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """拉取指数日线（上证/科创/创业板/沪深300）。"""
        try:
            df = self.ak.stock_zh_index_daily_em(symbol=f"sh{code}" if code.startswith(("000", "688")) else f"sz{code}")
        except Exception:
            df = self.ak.index_zh_a_hist(symbol=code, period="daily",
                                         start_date=self._compact_date(start_date),
                                         end_date=self._compact_date(end_date))
        return self._normalize_daily(df)

    def fetch_sector_universe(self) -> list[dict[str, str]]:
        if self._uses_default_ak:
            return self.fetch_relation_universe("eastmoney", "sector")
        df = self.ak.stock_board_industry_name_ths()
        return self._normalize_relation_universe(df)

    def fetch_theme_universe(self) -> list[dict[str, str]]:
        if self._uses_default_ak:
            return self.fetch_relation_universe("eastmoney", "theme")
        df = self.ak.stock_board_concept_name_ths()
        return self._normalize_relation_universe(df)

    def fetch_sector_members(self, name: str) -> list[dict[str, str]]:
        if self._uses_default_ak:
            item = {"code": name, "name": name}
            return self.fetch_relation_members("eastmoney", "sector", item)
        df = self.ak.stock_board_industry_cons_em(symbol=name)
        return self._normalize_members(df)

    def fetch_theme_members(self, name: str) -> list[dict[str, str]]:
        if self._uses_default_ak:
            item = {"code": name, "name": name}
            return self.fetch_relation_members("eastmoney", "theme", item)
        df = self.ak.stock_board_concept_cons_em(symbol=name)
        return self._normalize_members(df)

    def fetch_relation_universe(self, source: str, kind: str) -> list[dict[str, str]]:
        if source == "eastmoney":
            fs = self._em_relation_fs(kind)
            rows = self._fetch_em_pages(fs=fs, fields="f12,f14")
            df = pd.DataFrame([{"code": row.get("f12"), "name": row.get("f14")} for row in rows])
            return self._normalize_relation_universe(df)
        if source == "ths":
            if kind == "sector":
                df = self.ak.stock_board_industry_name_ths()
            elif kind == "theme":
                df = self.ak.stock_board_concept_name_ths()
            else:
                raise ValueError(f"unsupported relation kind: {kind}")
            return self._normalize_relation_universe(df)
        raise ValueError(f"unsupported relation source: {source}")

    def fetch_relation_members(self, source: str, kind: str, item: dict) -> list[dict[str, str]]:
        if source == "eastmoney":
            code = str(item["code"])
            if not re.match(r"^BK\d+", code):
                code = self._resolve_em_board_code(str(item["name"]), kind)
            return self._fetch_em_members(code)
        if source == "ths":
            return self._fetch_ths_members(kind, str(item["name"]))
        raise ValueError(f"unsupported relation source: {source}")

    def _resolve_em_board_code(self, name: str, kind: str) -> str:
        if re.match(r"^BK\d+", str(name)):
            return str(name)
        mapping = self._fetch_em_board_mapping(self._em_relation_fs(kind))
        if name in mapping:
            return mapping[name]
        clean = str(name).replace("概念", "").replace("板块", "")
        if clean in mapping:
            return mapping[clean]
        for candidate in mapping:
            if candidate.startswith(str(name)) and len(candidate) <= len(str(name)) + 3:
                return mapping[candidate]
        raise ValueError(f"cannot resolve Eastmoney board code for {kind} {name}")

    @staticmethod
    def _em_relation_fs(kind: str) -> str:
        if kind == "sector":
            return "m:90 t:2 f:!50"
        if kind == "theme":
            return "m:90 t:3 f:!50"
        raise ValueError(f"unsupported relation kind: {kind}")

    def _fetch_ths_members(self, kind: str, name: str) -> list[dict[str, str]]:
        if kind == "sector" and hasattr(self.ak, "stock_board_industry_cons_ths"):
            return self._normalize_members(self.ak.stock_board_industry_cons_ths(symbol=name))
        if kind == "theme" and hasattr(self.ak, "stock_board_concept_cons_ths"):
            return self._normalize_members(self.ak.stock_board_concept_cons_ths(symbol=name))
        raise NotImplementedError(f"ths {kind} constituent API is unavailable in current AkShare")

    def _fetch_em_board_mapping(self, fs: str) -> dict[str, str]:
        if fs not in self._em_board_mapping_cache:
            rows = self._fetch_em_pages(fs=fs, fields="f12,f14")
            self._em_board_mapping_cache[fs] = {
                str(row["f14"]): str(row["f12"]) for row in rows if row.get("f12") and row.get("f14")
            }
        return self._em_board_mapping_cache[fs]

    @staticmethod
    def _fetch_em_members(board_code: str) -> list[dict[str, str]]:
        rows = AkshareEMProvider._fetch_em_pages(fs=f"b:{board_code}", fields="f12,f14", max_pages=5)
        df = pd.DataFrame([{"代码": row.get("f12"), "名称": row.get("f14")} for row in rows])
        return AkshareEMProvider._normalize_members(df)

    @staticmethod
    def _fetch_em_pages(fs: str, fields: str, max_pages: int = 10) -> list[dict]:
        url = "https://push2delay.eastmoney.com/api/qt/clist/get"
        rows: list[dict] = []
        with requests.Session() as session:
            session.headers.update({"User-Agent": "Mozilla/5.0", "Referer": "https://quote.eastmoney.com/"})
            for page in range(1, max_pages + 1):
                response = session.get(
                    url,
                    params={
                        "pn": str(page),
                        "pz": "100",
                        "po": "1",
                        "np": "1",
                        "fltt": "2",
                        "invt": "2",
                        "fid": "f3",
                        "fs": fs,
                        "fields": fields,
                    },
                    timeout=5,
                )
                response.raise_for_status()
                data = response.json().get("data") or {}
                batch = data.get("diff") or []
                rows.extend(batch)
                total = data.get("total", 0)
                if len(rows) >= total or len(batch) < 100:
                    break
        return rows

    @staticmethod
    def _normalize_universe(df: pd.DataFrame) -> list[dict[str, str]]:
        if df.empty:
            return []
        required = {"代码", "名称"}
        missing = sorted(required - set(df.columns))
        if missing:
            raise ValueError(f"missing universe columns: {missing}")
        result = df[["代码", "名称"]].copy()
        result.columns = ["code", "name"]
        result["code"] = result["code"].astype(str).str.zfill(6)
        result["name"] = result["name"].astype(str)
        if "最新价" in df.columns:
            result["latest_price"] = pd.to_numeric(df["最新价"], errors="coerce")
            result = result[result["latest_price"].notna() & (result["latest_price"] > 0)]
        if "成交量" in df.columns:
            result["volume"] = pd.to_numeric(df["成交量"], errors="coerce")
            result = result[result["volume"].notna() & (result["volume"] > 0)]
        name = result["name"]
        result = result[~name.str.contains("退|PT", na=False)]
        result = result.dropna(subset=["code"]).drop_duplicates("code", keep="last")
        return result[["code", "name"]].sort_values("code").to_dict("records")

    @staticmethod
    def _normalize_relation_universe(df: pd.DataFrame) -> list[dict[str, str]]:
        if df.empty:
            return []
        required = {"code", "name"}
        missing = sorted(required - set(df.columns))
        if missing:
            raise ValueError(f"missing relation universe columns: {missing}")
        result = df[["code", "name"]].copy()
        result["code"] = result["code"].astype(str)
        result["name"] = result["name"].astype(str)
        result = result.dropna(subset=["code", "name"]).drop_duplicates("code", keep="last")
        return result.sort_values("code").to_dict("records")

    @staticmethod
    def _normalize_members(df: pd.DataFrame) -> list[dict[str, str]]:
        if df.empty:
            return []
        required = {"代码", "名称"}
        missing = sorted(required - set(df.columns))
        if missing:
            raise ValueError(f"missing member columns: {missing}")
        result = df[["代码", "名称"]].copy()
        result.columns = ["code", "name"]
        result["code"] = result["code"].astype(str).str.zfill(6)
        result["name"] = result["name"].astype(str)
        result = result.dropna(subset=["code", "name"]).drop_duplicates("code", keep="last")
        return result.sort_values("code").to_dict("records")

    @staticmethod
    def _normalize_daily(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])
        columns = {
            "日期": "date",
            "开盘": "open",
            "最高": "high",
            "最低": "low",
            "收盘": "close",
            "成交量": "volume",
        }
        missing = sorted(set(columns) - set(df.columns))
        if missing:
            raise ValueError(f"missing daily columns: {missing}")
        result = df[list(columns)].rename(columns=columns).copy()
        result["date"] = pd.to_datetime(result["date"])
        for col in ["open", "high", "low", "close", "volume"]:
            result[col] = pd.to_numeric(result[col], errors="coerce")
        return result.sort_values("date").drop_duplicates("date", keep="last").reset_index(drop=True)

    @staticmethod
    def _compact_date(value: str) -> str:
        return value.replace("-", "")
