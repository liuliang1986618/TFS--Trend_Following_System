"""本地日线数据库 — 增量更新，Parquet格式存储。

为什么用Parquet而不是SQLite？
→ 多赚钱：A股数据是典型的宽表结构（日期×标的），Parquet的列式存储
  在按日期范围查询时比SQLite快3-5倍。且pandas原生支持，零依赖。
  更快的分析 = 更早做出交易决策 = 更好的入场时机。

为什么每个标的存一个文件？
→ 少亏钱：增量更新时只需读写单个文件，不会因一个标的的数据错误
  影响到整个数据库。隔离故障 = 降低风险。
"""
import os
import pandas as pd
from typing import Optional, List, Tuple


class LocalDB:
    """本地日线数据库，按类型/标的存储为 Parquet 文件。

    目录结构:
        {data_dir}/
        ├── stock/
        │   ├── 000001.parquet
        │   └── 000002.parquet
        ├── sector/
        │   └── BK0477.parquet
        ├── theme/
        │   └── GN300308.parquet
        └── etf/
            └── 510050.parquet
    """

    VALID_TYPES = {"stock", "sector", "theme", "etf"}

    def __init__(self, data_dir: str = "dashboard/data"):
        self.data_dir = data_dir
        for t in self.VALID_TYPES:
            os.makedirs(os.path.join(data_dir, t), exist_ok=True)

    def _filepath(self, dtype: str, symbol: str) -> str:
        """返回某个标的的parquet文件路径。"""
        return os.path.join(self.data_dir, dtype, f"{symbol}.parquet")

    def save_daily(self, dtype: str, symbol: str, df: pd.DataFrame):
        """全量保存（覆盖）日线数据。"""
        if dtype not in self.VALID_TYPES:
            raise ValueError(f"Invalid dtype: {dtype}, must be one of {self.VALID_TYPES}")
        df = df.copy()
        df.index.name = "date"
        df.to_parquet(self._filepath(dtype, symbol))

    def load_daily(self, dtype: str, symbol: str) -> Optional[pd.DataFrame]:
        """加载某个标的的全部日线数据。不存在则返回None。"""
        path = self._filepath(dtype, symbol)
        if not os.path.exists(path):
            return None
        df = pd.read_parquet(path)
        if df.index.name != "date":
            df.index.name = "date"
        return df

    def incremental_update(self, dtype: str, symbol: str, new_df: pd.DataFrame):
        """增量更新：只追加本地不存在的日期数据。"""
        existing = self.load_daily(dtype, symbol)
        if existing is None:
            self.save_daily(dtype, symbol, new_df)
            return

        # 找到新数据中本地没有的日期
        new_dates = set(new_df.index)
        existing_dates = set(existing.index)
        to_add = new_dates - existing_dates

        if to_add:
            new_rows = new_df.loc[list(sorted(to_add))]
            merged = pd.concat([existing, new_rows])
            merged = merged[~merged.index.duplicated(keep="first")]
            merged.sort_index(inplace=True)
            self.save_daily(dtype, symbol, merged)

    def list_symbols(self, dtype: str) -> List[str]:
        """列出某类型下所有已存储的标的代码。"""
        dir_path = os.path.join(self.data_dir, dtype)
        if not os.path.exists(dir_path):
            return []
        return sorted([
            f.replace(".parquet", "")
            for f in os.listdir(dir_path)
            if f.endswith(".parquet")
        ])

    def get_date_range(self, dtype: str, symbol: str) -> Optional[Tuple[pd.Timestamp, pd.Timestamp]]:
        """返回数据的起止日期。"""
        df = self.load_daily(dtype, symbol)
        if df is None or len(df) == 0:
            return None
        return (df.index.min(), df.index.max())
