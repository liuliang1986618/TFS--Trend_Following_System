"""数据层集中配置。

所有路径、阈值、参数一处定义，修改时只需改这里。
"""

import os

# ── 存储路径 ────────────────────────────────────────────────

# v2 独立数据目录根（与旧系统 dashboard/data 隔离）
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

# v1 旧系统数据目录（fallback 数据源，真实积累数据，过渡期复用）
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
V1_DATA_DIR = os.path.join(_PROJECT_ROOT, "dashboard", "data")
V1_LEGACY_DIR = os.path.join(_PROJECT_ROOT, "data")

# 元数据 JSON 目录
META_DIR = os.path.join(DATA_DIR, "meta")

# 指数代码白名单（侧边栏指数涨跌用）
INDEX_CODES = {
    "000001": "上证综指",
    "399006": "创业板指",
    "000688": "科创50",
    "000300": "沪深300",
}

# 子目录模板：{data_dir}/{dtype}/{code}.parquet
PARQUET_PATH_TEMPLATE = "{data_dir}/{dtype}/{code}.parquet"

# 元数据文件名
META_STOCK_NAMES = "stock_names.json"
META_ETF_NAMES = "etf_names.json"
META_STOCK_SECTORS = "stock_sectors.json"
META_CONSTITUENT_MAP = "constituent_map.json"
META_SECTOR_LIST = "sector_list.json"
META_THEME_LIST = "theme_list.json"
META_ETF_LIST = "etf_list.json"
META_ETF_HOLDINGS = "etf_holdings.json"
META_THEME_HOLDINGS = "theme_holdings.json"

# ── 合法数据类型 ────────────────────────────────────────────

VALID_DTYPES = frozenset({"stock", "sector", "theme", "etf", "index"})

# ── 数据保留 ────────────────────────────────────────────────

RETENTION_DAYS = 730       # 约2年
RETENTION_YEARS = 2

# ── 数据完整性阈值 ──────────────────────────────────────────

COMPLETENESS = {
    "sector_min": 80, "sector_max": 100,
    "theme_min": 180, "theme_max": 220,
    "stock_min": 4300, "stock_max": 4700,
    "etf_min": 600, "etf_max": 900,
    "min_trading_days": 700,
    "min_rows_for_load": 20,
}

# ── 增量更新 ────────────────────────────────────────────────

INCREMENTAL_LOOKBACK_DAYS = 30

# ── 防封参数 ────────────────────────────────────────────────

ANTI_BAN = {
    "jitter_min_s": 0.5,
    "jitter_max_s": 2.0,
    "batch_size": 50,
    "batch_cooldown_s": (3.0, 8.0),
    "max_retries": 3,
    "backoff_s": (2.0, 5.0, 15.0),
}

# ── 断点续传 ────────────────────────────────────────────────

MIN_ROWS_FOR_COMPLETE = 500
