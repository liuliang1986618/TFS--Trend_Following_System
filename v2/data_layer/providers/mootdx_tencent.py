"""Mootdx (通达信 TCP) + Tencent (腾讯财经 HTTP) provider for TFS v2.

不封 IP，批量拉日K无限制。mootdx 负责K线，腾讯负责实时行情/PE/PB。
"""

from __future__ import annotations

import socket
import urllib.request
from pathlib import Path
from typing import Any

import pandas as pd


_TDX_SERVERS = [
    ("119.97.185.59", 7709),
    ("124.70.133.119", 7709),
    ("116.205.183.150", 7709),
    ("123.60.73.44", 7709),
    ("116.205.163.254", 7709),
    ("121.36.225.169", 7709),
    ("123.60.70.228", 7709),
    ("124.71.9.153", 7709),
    ("110.41.147.114", 7709),
    ("124.71.187.122", 7709),
]


def _probe(ip: str, port: int, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except Exception:
        return False


def _tdx_client(market: str = "std"):
    """创建 mootdx 客户端。直接 factory（bestip=True 会卡住，不用）。"""
    from mootdx.quotes import Quotes

    try:
        return Quotes.factory(market=market)
    except Exception as e:
        raise RuntimeError(
            "mootdx 连接失败。请确认网络可访问国内 7709 端口。"
            f"原始错误: {e}"
        )


def _get_prefix(code: str) -> str:
    if code.startswith(("6", "9")):
        return "sh"
    if code.startswith("8"):
        return "bj"
    return "sz"


class MootdxTencentProvider:
    """通达信 K线 + 腾讯实时行情 Provider。不封 IP。"""

    def __init__(self, data_dir: str | Path | None = None):
        self._client = None  # lazy init
        self._data_dir = Path(data_dir) if data_dir else None

    @property
    def client(self):
        if self._client is None:
            self._client = _tdx_client()
        return self._client

    # ── 股票列表：从本地 parquet 读 ──────────────────────────────────
    def fetch_stock_universe(self) -> list[dict[str, str]]:
        """从本地 stock/ 目录读股票列表（最快，无网络）。"""
        if self._data_dir is None:
            raise ValueError("data_dir required for universe fetch")
        stock_dir = self._data_dir / "stock"
        if not stock_dir.exists():
            return []
        items = []
        for f in sorted(stock_dir.glob("*.parquet")):
            code = f.stem
            name = code  # 暂用代码当名称，后续可从 meta 补
            items.append({"code": code, "name": name})
        return items

    def fetch_etf_universe(self) -> list[dict[str, str]]:
        """从本地 etf/ 目录读ETF列表。"""
        if self._data_dir is None:
            raise ValueError("data_dir required for universe fetch")
        etf_dir = self._data_dir / "etf"
        if not etf_dir.exists():
            return []
        items = []
        for f in sorted(etf_dir.glob("*.parquet")):
            code = f.stem
            items.append({"code": code, "name": code})
        return items

    # ── 日K数据：mootdx TCP ──────────────────────────────────────────
    def fetch_stock_daily(self, code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """拉股票日K（不封IP，mootdx TCP）。"""
        return self._fetch_daily(code, start_date, end_date)

    def fetch_etf_daily(self, code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """拉ETF日K（不封IP，mootdx TCP）。"""
        return self._fetch_daily(code, start_date, end_date)

    def fetch_index_daily(self, code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """拉指数日K。"""
        return self._fetch_daily(code, start_date, end_date)

    def _fetch_daily(self, code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """通过 mootdx 拉日K，返回标准格式 DataFrame。"""
        # mootdx bars 返回最近 N 根，我们拉足够多再按日期过滤
        # 730天 ≈ 2年交易日
        try:
            klines = self.client.bars(symbol=code, frequency=9, offset=730)
        except Exception:
            # 有些代码可能不存在，返回空
            return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])

        if klines is None or klines.empty:
            return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])

        df = klines[["open", "close", "high", "low", "vol", "datetime"]].copy()
        df.columns = ["open", "close", "high", "low", "volume", "date"]
        df["date"] = pd.to_datetime(df["date"]).dt.normalize()

        # 日期过滤
        start = pd.to_datetime(start_date)
        end = pd.to_datetime(end_date)
        df = df[(df["date"] >= start) & (df["date"] <= end)]

        # 排序去重
        df = df.sort_values("date").drop_duplicates("date", keep="last").reset_index(drop=True)
        return df[["date", "open", "high", "low", "close", "volume"]]

    # ── 实时行情：腾讯 HTTP ──────────────────────────────────────────
    def fetch_tencent_quotes(self, codes: list[str]) -> dict[str, dict]:
        """批量拉腾讯实时行情（PE/PB/市值/换手率等）。"""
        prefixed = []
        for c in codes:
            prefixed.append(f"{_get_prefix(c)}{c}")
        url = "https://qt.gtimg.cn/q=" + ",".join(prefixed)
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "Mozilla/5.0")
        resp = urllib.request.urlopen(req, timeout=15)
        data = resp.read().decode("gbk")

        result = {}
        for line in data.strip().split(";"):
            if not line.strip() or "=" not in line or '"' not in line:
                continue
            key = line.split("=")[0].split("_")[-1]
            vals = line.split('"')[1].split("~")
            if len(vals) < 53:
                continue
            code = key[2:]
            result[code] = {
                "name": vals[1],
                "price": float(vals[3]) if vals[3] else 0,
                "last_close": float(vals[4]) if vals[4] else 0,
                "open": float(vals[5]) if vals[5] else 0,
                "change_pct": float(vals[32]) if vals[32] else 0,
                "pe_ttm": float(vals[39]) if vals[39] else 0,
                "mcap_yi": float(vals[44]) if vals[44] else 0,
                "float_mcap_yi": float(vals[45]) if vals[45] else 0,
                "pb": float(vals[46]) if vals[46] else 0,
                "turnover_pct": float(vals[38]) if vals[38] else 0,
            }
        return result

    # ── 兼容 AkshareEMProvider 接口（让 DataFetcher 无缝切换）──────
    def fetch_sector_universe(self) -> list[dict[str, str]]:
        raise NotImplementedError("mootdx provider 不支持板块列表，请用 akshare_em")

    def fetch_theme_universe(self) -> list[dict[str, str]]:
        raise NotImplementedError("mootdx provider 不支持题材列表，请用 akshare_em")

    def fetch_sector_members(self, name: str) -> list[dict[str, str]]:
        raise NotImplementedError("mootdx provider 不支持板块成分，请用 akshare_em")

    def fetch_theme_members(self, name: str) -> list[dict[str, str]]:
        raise NotImplementedError("mootdx provider 不支持题材成分，请用 akshare_em")

    def fetch_relation_universe(self, source: str, kind: str) -> list[dict[str, str]]:
        raise NotImplementedError("mootdx provider 不支持关系数据，请用 akshare_em")

    def fetch_relation_members(self, source: str, kind: str, item: dict) -> list[dict[str, str]]:
        raise NotImplementedError("mootdx provider 不支持关系数据，请用 akshare_em")
