"""数据拉取编排器 — 管理数据获取的完整流程。

编排逻辑:
  1. init_db(): 初始化，全量拉取近2年历史数据
  2. update_daily(target_date): 每日增量更新，仅拉当日数据

为什么历史数据取2年？
→ 多赚钱：前高/前低检测需要至少60个交易日的历史数据（设计文档§2.3），
  加上MA20计算和量能对比需要更多数据建立基准，2年足够覆盖所有计算需求。
  取更久没有额外收益——参数和结构都只关注近期。
"""
from datetime import datetime, timedelta
from typing import List, Optional
import pandas as pd

from .providers.base import BaseProvider, ProviderConfig
from .providers.akshare_provider import AkshareProvider
from .local_db import LocalDB
from .mappings import ConstituentMapping


class DataFetcher:
    """数据拉取编排器。

    管理：
      - provider: 数据源适配器
      - local_db: 本地数据库
      - mapping: 成分股映射关系

    为什么需要编排器？
    → 少亏钱：数据拉取有多步依赖（先拉板块列表→再拉板块日K→再拉成分股），
      如果某步失败需要有重试和降级策略。编排器统一管理：初始化时全量拉取历史数据，
      日常运行时仅增量更新当日数据。失败时自动回退到本地缓存。
    """

    def __init__(
        self,
        provider: Optional[BaseProvider] = None,
        local_db: Optional[LocalDB] = None,
        mapping: Optional[ConstituentMapping] = None,
    ):
        self.provider = provider or AkshareProvider()
        self.local_db = local_db or LocalDB()
        self.mapping = mapping or ConstituentMapping()

    def init_db(self, end_date: str = None) -> dict:
        """初始化本地数据库：全量拉取近2年历史数据。

        Returns:
            dict: {"sectors": N, "themes": M, "stocks": K, "errors": [...]}
        """
        if end_date is None:
            end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.strptime(end_date, "%Y-%m-%d") - timedelta(days=730)).strftime("%Y-%m-%d")

        errors = []
        stats = {"sectors": 0, "themes": 0, "stocks": 0, "etfs": 0, "errors": errors}

        # 1. 拉取板块指数 + 板块日K
        try:
            sectors_df = self.provider.fetch_sector_indices()
            stats["sectors"] = len(sectors_df)
            self._save_sector_index_list(sectors_df)

            for _, row in sectors_df.iterrows():
                try:
                    bk = row["bk_code"]
                    daily = self.provider.fetch_sector_daily(bk, start_date, end_date)
                    self.local_db.save_daily("sector", bk, daily)

                    constituents = self.provider.fetch_sector_constituents(bk)
                    self.mapping.add_sector_constituents(bk, constituents.to_dict("records"))
                except Exception as e:
                    errors.append(f"sector {row.get('bk_code', '?')}: {e}")
        except Exception as e:
            errors.append(f"fetch_sector_indices: {e}")

        # 2. 拉取题材指数 + 题材日K
        try:
            themes_df = self.provider.fetch_theme_indices()
            stats["themes"] = len(themes_df)
            self._save_theme_index_list(themes_df)

            for _, row in themes_df.iterrows():
                try:
                    gn = row["gn_code"]
                    daily = self.provider.fetch_theme_daily(gn, start_date, end_date)
                    self.local_db.save_daily("theme", gn, daily)

                    constituents = self.provider.fetch_theme_constituents(gn)
                    self.mapping.add_theme_constituents(gn, constituents.to_dict("records"))
                except Exception as e:
                    errors.append(f"theme {row.get('gn_code', '?')}: {e}")
        except Exception as e:
            errors.append(f"fetch_theme_indices: {e}")

        # 3. 拉取ETF列表
        try:
            etfs_df = self.provider.fetch_etf_list()
            stats["etfs"] = len(etfs_df)
            self._save_etf_list(etfs_df)

            # 只拉取A类和B类ETF的日K（C类宽基不适用本策略）
            # → 少亏钱：不浪费时间和存储在不适用策略的标的上
            ab_etfs = etfs_df[etfs_df["etf_type"].isin(["A", "B"])]
            for _, row in ab_etfs.iterrows():
                try:
                    daily = self.provider.fetch_etf_daily(row["symbol"], start_date, end_date)
                    self.local_db.save_daily("etf", row["symbol"], daily)
                except Exception as e:
                    errors.append(f"etf {row['symbol']}: {e}")
        except Exception as e:
            errors.append(f"fetch_etf_list: {e}")

        return stats

    def update_daily(self, target_date: str = None) -> dict:
        """每日增量更新：仅拉取目标日期的数据。

        逻辑：
          1. 检查本地数据库最新日期
          2. 只拉取本地没有的交易日数据
          3. 增量追加到本地数据库

        → 少亏钱：增量更新只拉新数据，避免重复请求被封IP。
        → 多赚钱：增量更新速度快，1-2秒内完成，更快开始分析。
        """
        if target_date is None:
            target_date = datetime.now().strftime("%Y-%m-%d")

        errors = []
        updated = {"sectors": 0, "themes": 0, "stocks": 0, "etfs": 0, "errors": errors}

        # 增量更新已存储的板块
        for bk_code in self.local_db.list_symbols("sector"):
            try:
                _, last_date = self.local_db.get_date_range("sector", bk_code)
                if last_date and pd.Timestamp(target_date) <= last_date:
                    continue
                start = (pd.Timestamp(target_date) - timedelta(days=30)).strftime("%Y-%m-%d")
                daily = self.provider.fetch_sector_daily(bk_code, start, target_date)
                self.local_db.incremental_update("sector", bk_code, daily)
                updated["sectors"] += 1
            except Exception as e:
                errors.append(f"sector {bk_code}: {e}")

        # 增量更新ETF
        for etf_code in self.local_db.list_symbols("etf"):
            try:
                _, last_date = self.local_db.get_date_range("etf", etf_code)
                if last_date and pd.Timestamp(target_date) <= last_date:
                    continue
                start = (pd.Timestamp(target_date) - timedelta(days=30)).strftime("%Y-%m-%d")
                daily = self.provider.fetch_etf_daily(etf_code, start, target_date)
                self.local_db.incremental_update("etf", etf_code, daily)
                updated["etfs"] += 1
            except Exception as e:
                errors.append(f"etf {etf_code}: {e}")

        return updated

    def load_all_sectors(self) -> dict:
        """从本地数据库加载所有板块日K数据。

        → 多赚钱：从本地加载比网络拉取快100倍，批量分析的基础。
        """
        result = {}
        for bk in self.local_db.list_symbols("sector"):
            df = self.local_db.load_daily("sector", bk)
            if df is not None and len(df) > 20:
                result[bk] = df
        return result

    def load_all_themes(self) -> dict:
        """从本地数据库加载所有题材日K数据。"""
        result = {}
        for gn in self.local_db.list_symbols("theme"):
            df = self.local_db.load_daily("theme", gn)
            if df is not None and len(df) > 20:
                result[gn] = df
        return result

    def _save_sector_index_list(self, df: pd.DataFrame):
        """保存板块指数列表到本地。"""
        import json, os
        path = os.path.join(self.local_db.data_dir, "sector_list.json")
        df.to_json(path, orient="records", force_ascii=False)

    def _save_theme_index_list(self, df: pd.DataFrame):
        """保存题材指数列表到本地。"""
        import json, os
        path = os.path.join(self.local_db.data_dir, "theme_list.json")
        df.to_json(path, orient="records", force_ascii=False)

    def _save_etf_list(self, df: pd.DataFrame):
        """保存ETF列表到本地。"""
        import json, os
        path = os.path.join(self.local_db.data_dir, "etf_list.json")
        df.to_json(path, orient="records", force_ascii=False)
