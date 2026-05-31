"""数据源抽象接口 — 定义所有provider必须实现的方法契约。"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional
import pandas as pd


@dataclass
class ProviderConfig:
    """数据源配置。"""
    name: str = "akshare"
    cache_dir: str = "dashboard/data"
    rate_limit_per_sec: int = 3  # 限速：每秒最多请求数


class BaseProvider(ABC):
    """数据源抽象基类。

    为什么需要这个接口？
    → 少亏钱：当主数据源不可用时，可无缝切换到备选数据源（baostock），
      避免因数据缺失导致的错误交易决策。
    """

    def __init__(self, config: ProviderConfig):
        self.config = config

    @abstractmethod
    def fetch_sector_indices(self) -> pd.DataFrame:
        """获取全市场行业板块指数列表。

        Returns:
            DataFrame columns: bk_code, sector_name, 含板块代码BK
        """
        ...

    @abstractmethod
    def fetch_sector_daily(self, bk_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取单个板块指数的日K线数据。

        Returns:
            DataFrame columns: date, open, high, low, close, volume
        """
        ...

    @abstractmethod
    def fetch_sector_daily_batch(self, bk_codes: List[str], start_date: str, end_date: str) -> dict:
        """批量获取板块日K数据。

        Returns:
            dict: {bk_code: DataFrame(columns: date, open, high, low, close, volume)}
        """
        ...

    @abstractmethod
    def fetch_sector_constituents(self, bk_code: str) -> pd.DataFrame:
        """获取板块成分股列表。

        Returns:
            DataFrame columns: symbol, name
        """
        ...

    @abstractmethod
    def fetch_theme_indices(self) -> pd.DataFrame:
        """获取全市场题材（概念）指数列表。

        Returns:
            DataFrame columns: gn_code, theme_name, 含题材代码GN
        """
        ...

    @abstractmethod
    def fetch_theme_daily(self, gn_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取单个题材指数的日K线数据。"""
        ...

    @abstractmethod
    def fetch_theme_constituents(self, gn_code: str) -> pd.DataFrame:
        """获取题材成分股列表。"""
        ...

    @abstractmethod
    def fetch_stock_daily(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取个股日K线数据。"""
        ...

    @abstractmethod
    def fetch_stock_daily_batch(self, symbols: List[str], start_date: str, end_date: str) -> dict:
        """批量获取个股日K数据。"""
        ...

    @abstractmethod
    def fetch_etf_list(self) -> pd.DataFrame:
        """获取ETF列表。

        Returns:
            DataFrame columns: symbol, name, etf_type (A/B/C)
        """
        ...

    @abstractmethod
    def fetch_etf_daily(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取ETF日K线数据。"""
        ...
