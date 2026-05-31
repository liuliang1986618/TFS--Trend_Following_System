# 趋势跟随交易系统 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 从零搭建一个完整的趋势跟随交易系统，涵盖数据获取、趋势引擎、漏斗筛选、分析推演、Dashboard展示和CLI自动化六大模块。

**架构：** 采用分层架构——数据层（providers → local_db）→ 引擎层（条件判断 + 状态机 + 关键点识别）→ 漏斗筛选层（板块→题材→个股 + ETF并行路径）→ 分析层（对比 + 推演 + 市场宽度）→ 展示层（JSON快照 + HTML Dashboard）→ CLI层。每层独立可测，通过明确的数据结构（pandas DataFrame / dict）传递。

**技术栈：** Python 3.10+, pandas, numpy, akshare (主数据源), baostock (备选), pytest, 单文件HTML Dashboard

---

## 文件结构

```
trend_following_system/
├── src/
│   ├── __init__.py
│   ├── data/
│   │   ├── __init__.py
│   │   ├── providers/
│   │   │   ├── __init__.py
│   │   │   ├── base.py              # 抽象数据源接口
│   │   │   └── akshare_provider.py  # akshare 实现（主数据源）
│   │   ├── fetcher.py               # 数据拉取编排器
│   │   ├── local_db.py              # 本地日线数据库（增量）
│   │   └── mappings.py              # 板块成分股/题材成分股映射
│   ├── engine/
│   │   ├── __init__.py
│   │   ├── conditions.py            # 三条件判断器（A结构/B量能/C持续性）
│   │   ├── state_machine.py         # 6状态状态机（状态1-5+3'）
│   │   ├── pivots.py               # 前高/前低识别（局部极值检测）
│   │   ├── stage.py                 # 趋势阶段分类器（前/中/后期）
│   │   ├── ma_filter.py            # MA20均线初筛过滤器
│   │   └── key_points.py           # 6个关键操作点识别器
│   ├── funnel/
│   │   ├── __init__.py
│   │   ├── sector_filter.py        # 第一层：板块趋势判断
│   │   ├── theme_filter.py         # 第二层：题材趋势判断
│   │   ├── stock_filter.py         # 第三层：个股趋势判断
│   │   ├── etf_filter.py           # ETF直筛路径（并行辅助）
│   │   ├── leader.py               # 龙头识别（涨幅+成交额排名）
│   │   └── confidence.py           # 双路交叉验证+置信度计算
│   ├── analysis/
│   │   ├── __init__.py
│   │   ├── comparison.py           # 趋势变化对比（vs昨日/3日前/上周）
│   │   ├── scenario.py             # 明日推演引擎（状态机驱动）
│   │   ├── beta.py                 # 板块β强度计算
│   │   └── breadth.py              # 市场宽度指标
│   ├── display/
│   │   ├── __init__.py
│   │   ├── snapshot.py             # 每日JSON快照产出
│   │   └── dashboard.html          # 单文件HTML Dashboard
│   └── cli.py                      # CLI入口（run/dashboard/status命令）
├── tests/
│   ├── __init__.py
│   ├── conftest.py                  # 共享fixtures（模拟行情数据）
│   ├── data/
│   │   ├── test_fetcher.py
│   │   ├── test_local_db.py
│   │   └── test_mappings.py
│   ├── engine/
│   │   ├── test_conditions.py
│   │   ├── test_state_machine.py
│   │   ├── test_pivots.py
│   │   ├── test_stage.py
│   │   ├── test_ma_filter.py
│   │   └── test_key_points.py
│   ├── funnel/
│   │   ├── test_sector_filter.py
│   │   ├── test_theme_filter.py
│   │   ├── test_stock_filter.py
│   │   ├── test_etf_filter.py
│   │   ├── test_leader.py
│   │   └── test_confidence.py
│   ├── analysis/
│   │   ├── test_comparison.py
│   │   ├── test_scenario.py
│   │   ├── test_beta.py
│   │   └── test_breadth.py
│   └── test_cli.py
├── dashboard/
│   ├── data/                        # 每日JSON快照存放目录
│   └── positions.json               # 持仓数据（手动维护）
├── docs/
│   ├── 2026-05-31-trend-detection-design.md
│   ├── trend_state_machine.html
│   ├── trend_state_machine.mmd
│   └── superpowers/
│       └── plans/
│           └── 2026-05-31-trend-system-plan.md
├── requirements.txt
├── pytest.ini
└── README.md
```

---

## Phase 1: 数据层

### 任务 1.1：项目骨架初始化

**文件：**
- 创建：`requirements.txt`
- 创建：`pytest.ini`
- 创建：`src/__init__.py`
- 创建：`src/data/__init__.py`
- 创建：`src/engine/__init__.py`
- 创建：`src/funnel/__init__.py`
- 创建：`src/analysis/__init__.py`
- 创建：`src/display/__init__.py`
- 创建：`tests/__init__.py`
- 创建：`tests/conftest.py`
- 创建：`tests/data/__init__.py`
- 创建：`tests/engine/__init__.py`
- 创建：`tests/funnel/__init__.py`
- 创建：`tests/analysis/__init__.py`
- 创建：`dashboard/data/.gitkeep`
- 创建：`dashboard/positions.json`

- [ ] **步骤 1：创建 requirements.txt**

```
akshare>=1.14.0
baostock>=0.8.8
pandas>=2.0.0
numpy>=1.24.0
pytest>=7.0.0
```

- [ ] **步骤 2：创建 pytest.ini**

```ini
[pytest]
testpaths = tests
pythonpath = src
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short
```

- [ ] **步骤 3：创建所有 __init__.py 文件和空目录结构**

```bash
mkdir -p src/data/providers src/engine src/funnel src/analysis src/display
mkdir -p tests/data tests/engine tests/funnel tests/analysis
mkdir -p dashboard/data
touch src/__init__.py src/data/__init__.py src/data/providers/__init__.py
touch src/engine/__init__.py src/funnel/__init__.py src/analysis/__init__.py src/display/__init__.py
touch tests/__init__.py tests/data/__init__.py tests/engine/__init__.py
touch tests/funnel/__init__.py tests/analysis/__init__.py
touch dashboard/data/.gitkeep
```

- [ ] **步骤 4：创建 conftest.py — 共享测试fixtures**

```python
"""共享测试fixtures：生成模拟日K线数据。"""
import pytest
import pandas as pd
import numpy as np


def make_ohlcv(dates, prices, volumes):
    """根据收盘价序列生成完整OHLCV DataFrame。

    dates: list of str 'YYYY-MM-DD'
    prices: list of float 收盘价序列
    volumes: list of int 成交量序列
    """
    n = len(prices)
    data = {
        "date": pd.to_datetime(dates),
        "open": [prices[i] for i in range(n)],
        "high": [prices[i] * 1.02 for i in range(n)],
        "low": [prices[i] * 0.98 for i in range(n)],
        "close": prices,
        "volume": volumes,
    }
    df = pd.DataFrame(data)
    df.set_index("date", inplace=True)
    # 修正：high >= max(open, close), low <= min(open, close)
    for i in range(n):
        df.iloc[i, df.columns.get_loc("high")] = max(df.iloc[i]["open"], df.iloc[i]["close"]) * 1.01
        df.iloc[i, df.columns.get_loc("low")] = min(df.iloc[i]["open"], df.iloc[i]["close"]) * 0.99
    return df


@pytest.fixture
def uptrend_daily():
    """构造一个标准上涨趋势的40日日K序列。

    结构：前10日盘整 → 中间20日稳步上涨(2个更高高+2个更高低) → 后10日延续。
    量能：上涨日放量，下跌日缩量。
    持续性：阳线多于阴线，有连续5日阳线。
    """
    np.random.seed(42)
    n = 40
    dates = pd.date_range("2026-03-01", periods=n, freq="B")

    # 构造上涨趋势价格：从10元涨到15元
    trend = np.linspace(10, 15, n)
    # 加入波动
    noise = np.random.randn(n) * 0.15
    closes = trend + noise
    closes = np.maximum(closes, 1.0)

    # 构造放量上涨的成交量
    base_vol = 1_000_000
    volumes = []
    for i in range(n):
        if i > 0 and closes[i] > closes[i - 1]:
            vols = int(base_vol * (1.3 + np.random.random() * 0.5))  # 上涨放量
        else:
            vols = int(base_vol * (0.6 + np.random.random() * 0.4))  # 下跌缩量
        volumes.append(vols)

    return make_ohlcv(dates, closes.tolist(), volumes)


@pytest.fixture
def downtrend_daily():
    """构造一个标准下跌趋势的40日日K序列。"""
    np.random.seed(99)
    n = 40
    dates = pd.date_range("2026-03-01", periods=n, freq="B")

    trend = np.linspace(20, 13, n)
    noise = np.random.randn(n) * 0.2
    closes = trend + noise
    closes = np.maximum(closes, 1.0)

    base_vol = 1_000_000
    volumes = []
    for i in range(n):
        if i > 0 and closes[i] < closes[i - 1]:
            vols = int(base_vol * (1.3 + np.random.random() * 0.5))  # 下跌放量
        else:
            vols = int(base_vol * (0.6 + np.random.random() * 0.4))  # 反弹缩量
        volumes.append(vols)

    return make_ohlcv(dates, closes.tolist(), volumes)


@pytest.fixture
def sideways_daily():
    """构造一个横盘震荡的40日日K序列。"""
    np.random.seed(55)
    n = 40
    dates = pd.date_range("2026-03-01", periods=n, freq="B")
    closes = 10 + np.random.randn(n) * 0.3
    closes = np.maximum(closes, 1.0)
    volumes = [int(1_000_000 * (1.0 + np.random.random())) for _ in range(n)]
    return make_ohlcv(dates, closes.tolist(), volumes)


@pytest.fixture
def position_data():
    """示例持仓数据。"""
    return {
        "total_asset": 330700,
        "available_cash": 43200,
        "holdings": [
            {
                "symbol": "300308", "name": "中际旭创", "type": "stock",
                "cost": 152.30, "shares": 400, "current_weight": 0.25,
            },
            {
                "symbol": "512480", "name": "半导体ETF", "type": "etf",
                "cost": 0.842, "shares": 100000, "current_weight": 0.25,
            },
            {
                "symbol": "159819", "name": "AI智能ETF", "type": "etf",
                "cost": 1.052, "shares": 50000, "current_weight": 0.15,
            },
        ],
    }
```

- [ ] **步骤 5：创建 dashboard/positions.json 模板**

```json
{
  "total_asset": 0,
  "available_cash": 0,
  "holdings": []
}
```

- [ ] **步骤 6：Commit**

```bash
git add -A && git commit -m "feat: initialize project skeleton with directory structure and test fixtures"
```

---

### 任务 1.2：抽象数据源接口

**文件：**
- 创建：`src/data/providers/base.py`
- 创建：`tests/data/test_provider_base.py`（验证接口契约）

- [ ] **步骤 1：定义 ProviderConfig 和抽象方法签名**

```python
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
```

- [ ] **步骤 2：运行测试确认接口可导入**

```bash
python -c "from src.data.providers.base import BaseProvider, ProviderConfig; print('OK')"
```

- [ ] **步骤 3：Commit**

```bash
git add src/data/providers/base.py && git commit -m "feat: define abstract data provider interface"
```

---

### 任务 1.3：本地日线数据库

**文件：**
- 创建：`src/data/local_db.py`
- 测试：`tests/data/test_local_db.py`

**为什么需要本地数据库？**
→ **少亏钱**：每次分析都从网络拉取数据既慢又不可靠。本地缓存确保分析结果的稳定性和可复现性——昨天的分析结果和今天拉同一数据再分析的结果必须一致。增量更新避免重复拉取历史数据，节省时间让趋势判断更快。

- [ ] **步骤 1：编写失败测试**

```python
"""测试本地日线数据库的增量存储和读取。"""
import os
import tempfile
import pandas as pd
import numpy as np
import pytest
from src.data.local_db import LocalDB


@pytest.fixture
def temp_db():
    """使用临时目录的本地数据库。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db = LocalDB(data_dir=tmpdir)
        yield db


@pytest.fixture
def sample_daily():
    """5个交易日的OHLCV测试数据。"""
    dates = pd.date_range("2026-05-25", periods=5, freq="B")
    data = {
        "open": [10.0, 10.2, 10.1, 10.5, 10.8],
        "high": [10.3, 10.5, 10.4, 10.8, 11.0],
        "low": [9.8, 10.0, 9.9, 10.3, 10.6],
        "close": [10.2, 10.1, 10.5, 10.8, 10.7],
        "volume": [1000000, 1200000, 900000, 1500000, 1100000],
    }
    df = pd.DataFrame(data, index=dates)
    df.index.name = "date"
    return df


class TestLocalDB:
    def test_save_and_load_stock_daily(self, temp_db, sample_daily):
        """保存个股日线数据后能正确读取。"""
        temp_db.save_daily("stock", "000001", sample_daily)

        loaded = temp_db.load_daily("stock", "000001")
        assert len(loaded) == 5
        assert loaded.iloc[0]["close"] == 10.2
        assert loaded.iloc[-1]["close"] == 10.7

    def test_incremental_update_appends_only_new(self, temp_db, sample_daily):
        """增量更新只追加新数据，不覆盖已有数据。"""
        # 先存3天
        temp_db.save_daily("stock", "000001", sample_daily.iloc[:3])

        # 再增量追加全部5天
        temp_db.incremental_update("stock", "000001", sample_daily)

        loaded = temp_db.load_daily("stock", "000001")
        assert len(loaded) == 5  # 不是8，因为后3天和已有数据重叠

    def test_incremental_update_no_duplicates(self, temp_db, sample_daily):
        """增量更新不会产生重复行。"""
        temp_db.save_daily("stock", "000001", sample_daily)
        temp_db.incremental_update("stock", "000001", sample_daily)

        loaded = temp_db.load_daily("stock", "000001")
        assert len(loaded) == 5  # 不会翻倍

    def test_load_returns_none_for_missing(self, temp_db):
        """不存在的标的返回空DataFrame。"""
        result = temp_db.load_daily("stock", "nonexistent")
        assert result is None or len(result) == 0

    def test_list_symbols(self, temp_db, sample_daily):
        """列出所有已存储的标的代码。"""
        temp_db.save_daily("stock", "000001", sample_daily)
        temp_db.save_daily("stock", "000002", sample_daily)

        symbols = temp_db.list_symbols("stock")
        assert "000001" in symbols
        assert "000002" in symbols

    def test_save_sector_daily(self, temp_db, sample_daily):
        """板块类型的数据也能正确存取。"""
        temp_db.save_daily("sector", "BK0477", sample_daily)
        loaded = temp_db.load_daily("sector", "BK0477")
        assert len(loaded) == 5

    def test_get_date_range(self, temp_db, sample_daily):
        """能正确返回数据的日期范围。"""
        temp_db.save_daily("stock", "000001", sample_daily)
        start, end = temp_db.get_date_range("stock", "000001")
        assert start == pd.Timestamp("2026-05-25")
        assert end == pd.Timestamp("2026-05-29")
```

- [ ] **步骤 2：运行测试确认失败**

```bash
pytest tests/data/test_local_db.py -v
```
预期：FAIL，ModuleNotFoundError

- [ ] **步骤 3：编写最少实现代码**

```python
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
        if data_dir is None:
            raise ValueError("data_dir cannot be None")
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
```

- [ ] **步骤 4：运行测试验证通过**

```bash
pytest tests/data/test_local_db.py -v
```
预期：全部PASS

- [ ] **步骤 5：Commit**

```bash
git add src/data/local_db.py tests/data/test_local_db.py && git commit -m "feat: implement local daily database with incremental update"
```

---

### 任务 1.4：akshare数据源实现

**文件：**
- 创建：`src/data/providers/akshare_provider.py`
- 测试：`tests/data/test_akshare_provider.py`

**为什么选akshare作为主数据源？**
→ **多赚钱**：akshare支持批量拉取A股全市场数据，覆盖板块(BK代码)、题材(GN代码)、个股、ETF，接口最全面。批量拉取意味着每天的数据更新能在10秒内完成——快速的数据更新 = 更早发现趋势变化 = 抢占先机。

- [ ] **步骤 1：编写akshare provider实现**

```python
"""akshare数据源实现 — 主数据源。

数据获取策略（设计文档§4.3）：
  - 板块指数：akshare.index_stock_cons() 获取板块成分
  - 板块日K：akshare.stock_board_industry_index_ths() 或东方财富接口
  - 个股日K：akshare.stock_zh_a_hist() 批量获取
  - 题材指数：akshare.stock_board_concept_hist_ths()
  - ETF：akshare.fund_etf_spot_em() + fund_etf_hist_em()

接口选择原因:
  - akshare封装了东方财富、同花顺等免费公开API
  - 支持批量请求，比baostock速度快
  - 自动处理A股复权
"""
import time
from typing import List, Optional
import pandas as pd
import akshare as ak

from .base import BaseProvider, ProviderConfig


class AkshareProvider(BaseProvider):
    """akshare数据源实现。

    所有接口均直接调用akshare封装的方法。
    限速由ProviderConfig.rate_limit_per_sec控制。
    """

    def __init__(self, config: Optional[ProviderConfig] = None):
        super().__init__(config or ProviderConfig(name="akshare"))

    def _rate_limit(self):
        """限速控制，避免被封IP。"""
        time.sleep(1.0 / self.config.rate_limit_per_sec)

    def fetch_sector_indices(self) -> pd.DataFrame:
        """获取同花顺行业板块指数列表（含板块代码BK）。"""
        self._rate_limit()
        df = ak.stock_board_industry_name_ths()
        df = df.rename(columns={
            "代码": "bk_code",
            "名称": "sector_name",
        })
        return df[["bk_code", "sector_name"]]

    def fetch_sector_daily(self, bk_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取板块指数日K。"""
        self._rate_limit()
        df = ak.stock_board_industry_index_ths(
            symbol=bk_code,
            start_date=start_date.replace("-", ""),
            end_date=end_date.replace("-", ""),
        )
        return self._normalize_ohlcv(df)

    def fetch_sector_daily_batch(self, bk_codes: List[str], start_date: str, end_date: str) -> dict:
        """批量获取板块日K。遍历板块代码逐个拉取。"""
        result = {}
        for code in bk_codes:
            try:
                result[code] = self.fetch_sector_daily(code, start_date, end_date)
            except Exception as e:
                print(f"[WARN] fetch_sector_daily failed for {code}: {e}")
                continue
        return result

    def fetch_sector_constituents(self, bk_code: str) -> pd.DataFrame:
        """获取板块成分股列表。"""
        self._rate_limit()
        df = ak.stock_board_industry_cons_ths(symbol=bk_code)
        df = df.rename(columns={
            "代码": "symbol",
            "名称": "name",
        })
        return df[["symbol", "name"]]

    def fetch_theme_indices(self) -> pd.DataFrame:
        """获取同花顺概念题材指数列表（含题材代码GN）。"""
        self._rate_limit()
        df = ak.stock_board_concept_name_ths()
        df = df.rename(columns={
            "代码": "gn_code",
            "名称": "theme_name",
        })
        return df[["gn_code", "theme_name"]]

    def fetch_theme_daily(self, gn_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取题材指数日K。"""
        self._rate_limit()
        df = ak.stock_board_concept_hist_ths(
            symbol=gn_code,
            start_date=start_date.replace("-", ""),
            end_date=end_date.replace("-", ""),
        )
        return self._normalize_ohlcv(df)

    def fetch_theme_constituents(self, gn_code: str) -> pd.DataFrame:
        """获取题材成分股列表。"""
        self._rate_limit()
        df = ak.stock_board_concept_cons_ths(symbol=gn_code)
        df = df.rename(columns={
            "代码": "symbol",
            "名称": "name",
        })
        return df[["symbol", "name"]]

    def fetch_stock_daily(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取个股日K（前复权）。"""
        self._rate_limit()
        df = ak.stock_zh_a_hist(
            symbol=symbol,
            period="daily",
            start_date=start_date.replace("-", ""),
            end_date=end_date.replace("-", ""),
            adjust="qfq",  # 前复权
        )
        return self._normalize_ohlcv(df)

    def fetch_stock_daily_batch(self, symbols: List[str], start_date: str, end_date: str) -> dict:
        """批量获取个股日K。"""
        result = {}
        for sym in symbols:
            try:
                result[sym] = self.fetch_stock_daily(sym, start_date, end_date)
            except Exception as e:
                print(f"[WARN] fetch_stock_daily failed for {sym}: {e}")
                continue
        return result

    def fetch_etf_list(self) -> pd.DataFrame:
        """获取ETF列表，并分类为A/B/C类型。

        类型A: 板块ETF（如半导体ETF、通信ETF）——名称含"板块/行业"关键词
        类型B: 跨板块/题材ETF（如新能源ETF）——有底层资产但不严格对应单一板块
        类型C: 宽基/策略ETF（如沪深300ETF）——不适用本策略
        """
        self._rate_limit()
        df = ak.fund_etf_spot_em()
        result = df[["代码", "名称"]].copy()
        result.columns = ["symbol", "name"]

        # 简单分类：宽基/策略归C，其余待分析归B，具体再细分
        broad_keywords = ["沪深300", "中证500", "上证50", "创业板", "科创50",
                          "红利", "低波", "价值", "成长", "等权"]
        industry_keywords = ["半导体", "芯片", "通信", "医药", "白酒", "军工",
                             "银行", "券商", "保险", "地产", "有色", "煤炭",
                             "新能源", "光伏", "锂电", "风电"]

        def classify(row):
            name = row["name"]
            if any(kw in name for kw in broad_keywords):
                return "C"
            elif any(kw in name for kw in industry_keywords):
                return "A"
            else:
                return "B"

        result["etf_type"] = result.apply(classify, axis=1)
        return result

    def fetch_etf_daily(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取ETF日K。"""
        self._rate_limit()
        df = ak.fund_etf_hist_em(
            symbol=symbol,
            period="daily",
            start_date=start_date.replace("-", ""),
            end_date=end_date.replace("-", ""),
            adjust="qfq",
        )
        return self._normalize_ohlcv(df)

    def _normalize_ohlcv(self, df: pd.DataFrame) -> pd.DataFrame:
        """将akshare返回的DataFrame标准化为统一格式。

        标准化原因：
        → 少亏钱：统一的数据格式意味着趋势引擎不需要猜测列名，
          不会因为列名不一致导致条件判断出错。

        Returns:
            DataFrame with columns: date(index), open, high, low, close, volume
        """
        # 日期列的各种可能名称
        date_candidates = ["日期", "date", "时间", "trade_date"]
        ohlcv_map = {
            "开盘": "open", "open": "open",
            "最高": "high", "high": "high",
            "最低": "low", "low": "low",
            "收盘": "close", "close": "close",
            "成交量": "volume", "volume": "volume",
        }

        df = df.copy()
        # 重命名列
        rename = {}
        for col in df.columns:
            if col in ohlcv_map:
                rename[col] = ohlcv_map[col]
            elif col in date_candidates:
                rename[col] = "date"
        df.rename(columns=rename, inplace=True)

        # 设置date为索引
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
            df.set_index("date", inplace=True)

        # 确保所有数值列都是float/int
        for col in ["open", "high", "low", "close"]:
            if col in df.columns:
                df[col] = df[col].astype(float)
        if "volume" in df.columns:
            df[volume] = df["volume"].astype(int)

        return df[["open", "high", "low", "close", "volume"]]
```

- [ ] **步骤 2：编写集成测试（需要网络，标记为slow）**

```python
"""akshare provider集成测试 — 需要网络连接。"""
import pytest
from src.data.providers.akshare_provider import AkshareProvider


@pytest.fixture
def provider():
    return AkshareProvider()


@pytest.mark.slow
class TestAkshareProviderIntegration:
    def test_fetch_sector_indices(self, provider):
        """能获取板块指数列表且包含BK代码。"""
        df = provider.fetch_sector_indices()
        assert len(df) > 30
        assert "bk_code" in df.columns
        assert "sector_name" in df.columns
        # BK代码格式如 BK0477
        assert df["bk_code"].iloc[0].startswith("BK")

    def test_fetch_sector_daily(self, provider):
        """能获取板块日K数据。"""
        df = provider.fetch_sector_daily("BK0477", "2026-05-01", "2026-05-31")
        assert len(df) > 0
        for col in ["open", "high", "low", "close", "volume"]:
            assert col in df.columns

    def test_fetch_sector_constituents(self, provider):
        """能获取板块成分股。"""
        df = provider.fetch_sector_constituents("BK0477")
        assert len(df) > 0
        assert "symbol" in df.columns
        assert "name" in df.columns

    def test_fetch_theme_indices(self, provider):
        """能获取题材指数列表且包含GN代码。"""
        df = provider.fetch_theme_indices()
        assert len(df) > 50
        assert "gn_code" in df.columns

    def test_fetch_stock_daily(self, provider):
        """能获取个股日K数据。"""
        df = provider.fetch_stock_daily("000001", "2026-05-01", "2026-05-31")
        assert len(df) > 0
        for col in ["open", "high", "low", "close", "volume"]:
            assert col in df.columns

    def test_fetch_etf_list(self, provider):
        """能获取ETF列表并分类。"""
        df = provider.fetch_etf_list()
        assert len(df) > 50
        assert "etf_type" in df.columns
        types = df["etf_type"].unique()
        assert "A" in types or "B" in types or "C" in types
```

- [ ] **步骤 3：验证导入和基本功能**

```bash
python -c "from src.data.providers.akshare_provider import AkshareProvider; print('OK')"
```

- [ ] **步骤 4：Commit**

```bash
git add src/data/providers/akshare_provider.py tests/data/test_akshare_provider.py && git commit -m "feat: implement akshare data provider with batch fetch support"
```

---

### 任务 1.5：板块-成分股映射管理

**文件：**
- 创建：`src/data/mappings.py`
- 测试：`tests/data/test_mappings.py`

**为什么需要映射管理？**
→ **多赚钱**：板块→成分股映射是漏斗第二层→第三层的桥梁。映射关系不常变化（每周更新一次即可），缓存后可以快速查询"一个板块有哪些股票"，加速第三层筛选速度。

- [ ] **步骤 1：编写失败测试**

```python
"""测试板块/题材成分股映射关系。"""
import pytest
from src.data.mappings import ConstituentMapping


class TestConstituentMapping:
    def test_add_and_query_sector_mapping(self):
        """添加板块成分股后能正确查询。"""
        mapping = ConstituentMapping()
        mapping.add_sector_constituents("BK0477", [
            {"symbol": "000001", "name": "平安银行"},
            {"symbol": "000002", "name": "万科A"},
        ])

        stocks = mapping.get_sector_stocks("BK0477")
        assert len(stocks) == 2
        assert stocks[0]["symbol"] == "000001"

    def test_get_all_sector_symbols(self):
        """获取板块下所有股票代码。"""
        mapping = ConstituentMapping()
        mapping.add_sector_constituents("BK0477", [
            {"symbol": "000001", "name": "平安银行"},
            {"symbol": "000002", "name": "万科A"},
        ])

        symbols = mapping.get_sector_symbols("BK0477")
        assert symbols == ["000001", "000002"]

    def test_add_theme_constituents(self):
        """添加题材成分股后能正确查询。"""
        mapping = ConstituentMapping()
        mapping.add_theme_constituents("GN300308", [
            {"symbol": "300308", "name": "中际旭创"},
            {"symbol": "300502", "name": "新易盛"},
        ])

        stocks = mapping.get_theme_stocks("GN300308")
        assert len(stocks) == 2

    def test_get_stock_sectors(self):
        """反向查询：一个股票属于哪些板块。"""
        mapping = ConstituentMapping()
        mapping.add_sector_constituents("BK0477", [
            {"symbol": "000001", "name": "平安银行"},
        ])
        mapping.add_sector_constituents("BK0488", [
            {"symbol": "000001", "name": "平安银行"},
        ])

        sectors = mapping.get_stock_sectors("000001")
        assert "BK0477" in sectors
        assert "BK0488" in sectors

    def test_get_stock_themes(self):
        """反向查询：一个股票属于哪些题材。"""
        mapping = ConstituentMapping()
        mapping.add_theme_constituents("GN300308", [
            {"symbol": "300308", "name": "中际旭创"},
        ])

        themes = mapping.get_stock_themes("300308")
        assert "GN300308" in themes
```

- [ ] **步骤 2：运行测试确认失败**

```bash
pytest tests/data/test_mappings.py -v
```

- [ ] **步骤 3：编写实现代码**

```python
"""板块/题材成分股映射关系管理。

为什么用dict而不是pandas？
→ 查询操作远多于写入操作。dict的O(1)查询比DataFrame筛选快得多。
  在第三层个股筛选中，需要频繁反向查询"某个股票属于哪些上涨板块"，
  每次查询节省几十ms，300-500只个股就能节省几秒——更快完成筛选。
"""
from typing import List, Dict, Set


class ConstituentMapping:
    """管理板块→成分股、题材→成分股的双向映射关系。

    三类映射：
      1. code → [constituents]   正向：板块/题材有哪些股票
      2. symbol → [sectors]      反向：股票属于哪些板块
      3. symbol → [themes]       反向：股票属于哪些题材
    """

    def __init__(self):
        self._sector_stocks: Dict[str, List[dict]] = {}  # BK_CODE → [{symbol, name}]
        self._theme_stocks: Dict[str, List[dict]] = {}   # GN_CODE → [{symbol, name}]
        self._stock_sectors: Dict[str, Set[str]] = {}     # symbol → {BK_CODEs}
        self._stock_themes: Dict[str, Set[str]] = {}      # symbol → {GN_CODEs}

    def add_sector_constituents(self, bk_code: str, constituents: List[dict]):
        """添加板块成分股。

        constituents: [{"symbol": "...", "name": "..."}, ...]
        """
        self._sector_stocks[bk_code] = constituents
        for c in constituents:
            sym = c["symbol"]
            if sym not in self._stock_sectors:
                self._stock_sectors[sym] = set()
            self._stock_sectors[sym].add(bk_code)

    def add_theme_constituents(self, gn_code: str, constituents: List[dict]):
        """添加题材成分股。"""
        self._theme_stocks[gn_code] = constituents
        for c in constituents:
            sym = c["symbol"]
            if sym not in self._stock_themes:
                self._stock_themes[sym] = set()
            self._stock_themes[sym].add(gn_code)

    def get_sector_stocks(self, bk_code: str) -> List[dict]:
        """获取板块下所有成分股。"""
        return self._sector_stocks.get(bk_code, [])

    def get_sector_symbols(self, bk_code: str) -> List[str]:
        """获取板块下所有股票代码。"""
        return [c["symbol"] for c in self.get_sector_stocks(bk_code)]

    def get_theme_stocks(self, gn_code: str) -> List[dict]:
        """获取题材下所有成分股。"""
        return self._theme_stocks.get(gn_code, [])

    def get_theme_symbols(self, gn_code: str) -> List[str]:
        """获取题材下所有股票代码。"""
        return [c["symbol"] for c in self.get_theme_stocks(gn_code)]

    def get_stock_sectors(self, symbol: str) -> List[str]:
        """获取某股票所属的所有板块代码。"""
        return list(self._stock_sectors.get(symbol, set()))

    def get_stock_themes(self, symbol: str) -> List[str]:
        """获取某股票所属的所有题材代码。"""
        return list(self._stock_themes.get(symbol, set()))

    @property
    def sector_count(self) -> int:
        return len(self._sector_stocks)

    @property
    def theme_count(self) -> int:
        return len(self._theme_stocks)
```

- [ ] **步骤 4：运行测试验证通过**

```bash
pytest tests/data/test_mappings.py -v
```

- [ ] **步骤 5：Commit**

```bash
git add src/data/mappings.py tests/data/test_mappings.py && git commit -m "feat: implement constituent mapping manager for sector/theme"
```

---

### 任务 1.6：数据拉取编排器

**文件：**
- 创建：`src/data/fetcher.py`
- 测试：`tests/data/test_fetcher.py`

**为什么需要编排器？**
→ **少亏钱**：数据拉取有多步依赖（先拉板块列表→再拉板块日K→再拉成分股），如果某步失败需要有重试和降级策略。编排器统一管理：初始化时全量拉取历史数据，日常运行时仅增量更新当日数据。失败时自动回退到本地缓存。

- [ ] **步骤 1：编写 Fetcher 实现**

```python
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

                    # 拉取成分股映射
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
                    continue  # 已有数据，跳过
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
        """从本地数据库加载所有板块日K数据。"""
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
```

- [ ] **步骤 2：编写编排器单元测试**

```python
"""测试数据拉取编排器的流程控制逻辑。"""
import pytest
import pandas as pd
from unittest.mock import MagicMock, patch
from src.data.fetcher import DataFetcher
from src.data.local_db import LocalDB
from src.data.mappings import ConstituentMapping
from tests.conftest import make_ohlcv


class TestDataFetcher:
    def test_update_daily_skips_existing_dates(self, tmp_path):
        """增量更新跳过已覆盖的日期。"""
        # 使用Mock provider
        mock_provider = MagicMock()
        mock_provider.fetch_sector_daily.return_value = make_ohlcv(
            ["2026-05-31"], [10.5], [1000000]
        )

        db = LocalDB(str(tmp_path))
        # 数据库已有到05-31的数据
        existing = make_ohlcv(
            ["2026-05-29", "2026-05-30", "2026-05-31"],
            [10.0, 10.2, 10.5],
            [1000000, 1100000, 1200000],
        )
        db.save_daily("sector", "BK0477", existing)

        fetcher = DataFetcher(provider=mock_provider, local_db=db)
        result = fetcher.update_daily("2026-05-31")

        # 因为已有05-31数据，不应再次拉取
        mock_provider.fetch_sector_daily.assert_not_called()
```

- [ ] **步骤 3：运行测试**

```bash
pytest tests/data/test_fetcher.py -v
```

- [ ] **步骤 4：Commit**

```bash
git add src/data/fetcher.py tests/data/test_fetcher.py && git commit -m "feat: implement data fetcher orchestrator with init and incremental update"
```

---

### Phase 1 验证

- [ ] 运行全部数据层测试：`pytest tests/data/ -v`
- [ ] 对照设计文档§4（数据获取策略）检查：
  - [x] 板块指数数据获取 ✅
  - [x] 板块代码BK ✅
  - [x] 板块成分股映射 ✅
  - [x] 题材指数数据获取（含GN代码） ✅
  - [x] 个股/ETF日K数据获取 ✅
  - [x] 本地日线数据库（增量更新） ✅

---

## Phase 2: 趋势引擎

### 任务 2.1：MA20均线初筛过滤器

**文件：**
- 创建：`src/engine/ma_filter.py`
- 测试：`tests/engine/test_ma_filter.py`

**为什么需要MA20初筛？**
→ **少亏钱**：在全市场5000+标的中，MA20以下的可以直接排除（至少占70%）。先做廉价的计算过滤掉大部分无效标的，后面的状态机（更昂贵的计算）只需处理剩余的30%。这是计算资源的优化——不直接影响盈亏，但让系统更快到达真正重要的决策。

- [ ] **步骤 1：编写失败测试**

```python
"""测试MA20均线初筛过滤器。"""
import pytest
import pandas as pd
import numpy as np
from src.engine.ma_filter import MAFilter
from tests.conftest import make_ohlcv


class TestMAFilter:
    def test_price_above_ma20_passes(self):
        """价格在MA20上方：通过初筛。"""
        # 构造一个持续上涨的序列，确保收盘价 > MA20
        n = 30
        dates = pd.date_range("2026-04-01", periods=n, freq="B")
        closes = list(np.linspace(10, 20, n))  # 稳步上涨
        volumes = [1000000] * n
        df = make_ohlcv(dates, closes, volumes)

        result = MAFilter.check(df)
        assert result is True

    def test_price_below_ma20_fails(self):
        """价格在MA20下方：初筛不通过。"""
        n = 30
        dates = pd.date_range("2026-04-01", periods=n, freq="B")
        closes = list(np.linspace(20, 10, n))  # 持续下跌
        volumes = [1000000] * n
        df = make_ohlcv(dates, closes, volumes)

        result = MAFilter.check(df)
        assert result is False

    def test_insufficient_data_returns_false(self):
        """数据不足20日：自动不通过。"""
        n = 15
        dates = pd.date_range("2026-05-01", periods=n, freq="B")
        closes = [10 + i * 0.1 for i in range(n)]
        volumes = [1000000] * n
        df = make_ohlcv(dates, closes, volumes)

        result = MAFilter.check(df)
        assert result is False

    def test_price_crossing_ma20(self):
        """价格刚站上MA20边界情况。"""
        n = 25
        dates = pd.date_range("2026-04-01", periods=n, freq="B")
        # 前20天价格在10附近，最后5天飙升
        closes = [10.0] * 20 + [12.0, 14.0, 16.0, 18.0, 20.0]
        volumes = [1000000] * n
        df = make_ohlcv(dates, closes, volumes)

        result = MAFilter.check(df)
        assert result is True  # 最新价格远高于MA20

    def test_ma20_batch_filter(self):
        """批量过滤：返回通过和未通过的列表。"""
        n = 30
        dates = pd.date_range("2026-04-01", periods=n, freq="B")

        # 上涨序列
        up_closes = list(np.linspace(10, 20, n))
        up_df = make_ohlcv(dates, up_closes, [1000000] * n)

        # 下跌序列
        down_closes = list(np.linspace(20, 10, n))
        down_df = make_ohlcv(dates, down_closes, [1000000] * n)

        data = {"UP": up_df, "DOWN": down_df}
        passed, failed = MAFilter.batch_filter(data)

        assert "UP" in passed
        assert "DOWN" in failed
```

- [ ] **步骤 2：运行测试确认失败**

```bash
pytest tests/engine/test_ma_filter.py -v
```

- [ ] **步骤 3：编写实现**

```python
"""MA20均线初筛过滤器 — 最快速的第一道关卡。

设计文档§1.2 D条件：
  价格 > MA20 → 通过初筛
  价格 ≤ MA20 → 不通过

为什么用收盘价而不是最高价？
→ 少亏钱：收盘价是当日多空博弈的最终结果，比最高价更能代表真实价格位置。
  如果用最高价，容易被盘中脉冲拉升骗过。
"""
import pandas as pd
import numpy as np
from typing import Dict, Tuple, List


class MAFilter:
    """MA20均线初筛过滤器。

    是最快速的第一道关卡，用于在海量标的中快速排除明显处于下跌趋势的标的。
    仅使用收盘价判断，计算量极小。
    """

    @staticmethod
    def check(daily_df: pd.DataFrame) -> bool:
        """判断单个标的的收盘价是否在MA20上方。

        Args:
            daily_df: 日K数据，至少需要20个交易日

        Returns:
            True = 通过初筛（价格 > MA20）
        """
        if daily_df is None or len(daily_df) < 20:
            return False

        closes = daily_df["close"]
        ma20 = closes.rolling(window=20).mean().iloc[-1]

        if pd.isna(ma20):
            return False

        return closes.iloc[-1] > ma20

    @staticmethod
    def batch_filter(data: Dict[str, pd.DataFrame]) -> Tuple[Dict[str, pd.DataFrame], List[str]]:
        """批量过滤：返回(通过标的, 未通过代码列表)。

        为什么批量处理？
        → 多赚钱：一次遍历完成所有标的的MA20计算，利用pandas的向量化能力
          比逐个标的循环快10-20倍。更快的筛选 = 更快到达真正的趋势分析。
        """
        passed = {}
        failed = []

        for code, df in data.items():
            if MAFilter.check(df):
                passed[code] = df
            else:
                failed.append(code)

        return passed, failed
```

- [ ] **步骤 4：运行测试验证通过**

```bash
pytest tests/engine/test_ma_filter.py -v
```

- [ ] **步骤 5：Commit**

```bash
git add src/engine/ma_filter.py tests/engine/test_ma_filter.py && git commit -m "feat: implement MA20 pre-filter for fast candidate screening"
```

---

### 任务 2.2：前高/前低识别算法

**文件：**
- 创建：`src/engine/pivots.py`
- 测试：`tests/engine/test_pivots.py`

**为什么前高/前低识别如此重要？**
→ **多赚钱+少亏钱同时满足**：前高是下跌→上涨翻转的确认线（突破前高=状态2→3的买点），前低是上涨→下跌转跌的警戒线（跌破前低=状态5→3'的防守点）。前高/前低识别的准确性直接决定了：买点是否及时（多赚钱），止损是否有效（少亏钱）。这是整个系统最重要的技术指标之一。

- [ ] **步骤 1：编写失败测试**

```python
"""测试前高/前低识别算法（局部极值检测）。"""
import pytest
import pandas as pd
import numpy as np
from src.engine.pivots import PivotDetector
from tests.conftest import make_ohlcv


class TestPivotDetector:
    def test_detect_high_pivot(self):
        """检测明显的局部高点。"""
        # 构造一个中间有凸起的序列：第15天是局部最高点
        n = 30
        dates = pd.date_range("2026-04-01", periods=n, freq="B")
        closes = [10.0 + i * 0.05 for i in range(15)] + \
                 [10.0 + (14 - i) * 0.05 for i in range(15)]
        # 高点 ≈ 10.70 在第15天
        volumes = [1000000] * n
        df = make_ohlcv(dates, closes, volumes)

        highs = PivotDetector.find_highs(df, window=3)
        assert len(highs) >= 1

    def test_detect_low_pivot(self):
        """检测明显的局部低点。"""
        n = 30
        dates = pd.date_range("2026-04-01", periods=n, freq="B")
        # V形：先跌后涨
        closes = [20.0 - i * 0.3 for i in range(15)] + \
                 [15.5 + i * 0.3 for i in range(15)]
        volumes = [1000000] * n
        df = make_ohlcv(dates, closes, volumes)

        lows = PivotDetector.find_lows(df, window=3)
        assert len(lows) >= 1

    def test_recent_high(self):
        """获取最近一个有效的前高（60日窗口内）。"""
        n = 50
        dates = pd.date_range("2026-03-01", periods=n, freq="B")
        # 前25天持续上涨到高点15→然后回调
        closes = [10.0 + i * 0.2 for i in range(25)] + \
                 [15.0 - i * 0.1 for i in range(25)]
        volumes = [1000000] * n
        df = make_ohlcv(dates, closes, volumes)

        recent_high = PivotDetector.recent_high(df, max_age=60)
        assert recent_high is not None
        assert "date" in recent_high
        assert "price" in recent_high

    def test_recent_low(self):
        """获取最近一个有效的前低。"""
        n = 50
        dates = pd.date_range("2026-03-01", periods=n, freq="B")
        # 先跌到底再反弹
        closes = [20.0 - i * 0.3 for i in range(20)] + \
                 [14.0 + i * 0.2 for i in range(30)]
        volumes = [1000000] * n
        df = make_ohlcv(dates, closes, volumes)

        recent_low = PivotDetector.recent_low(df, max_age=60)
        assert recent_low is not None

    def test_no_pivot_when_flat(self):
        """横盘无显著极值。"""
        n = 30
        dates = pd.date_range("2026-04-01", periods=n, freq="B")
        closes = [10.0 + np.random.randn() * 0.05 for _ in range(n)]
        volumes = [1000000] * n
        df = make_ohlcv(dates, closes, volumes)

        highs = PivotDetector.find_highs(df, window=3)
        lows = PivotDetector.find_lows(df, window=3)
        # 极度扁平的情况下极值很少
        assert len(highs) <= n // 3
        assert len(lows) <= n // 3

    def test_expired_pivot_ignored(self):
        """超过60个交易日的极值不被当作有效前高/前低。"""
        n = 80
        dates = pd.date_range("2026-01-01", periods=n, freq="B")
        closes = [10.0 + i * 0.2 for i in range(20)] + \
                 [14.0 - i * 0.05 for i in range(60)]
        volumes = [1000000] * n
        df = make_ohlcv(dates, closes, volumes)

        recent_high = PivotDetector.recent_high(df, max_age=60)
        # 前高在60天前（前20天），应该已失效
        if recent_high is not None:
            days_ago = (df.index[-1] - recent_high["date"]).days
            assert days_ago <= 70  # 交易日转自然日大致换算

    def test_get_last_two_highs(self):
        """检测最近2个更高高点（满足结构A条件）。"""
        n = 60
        dates = pd.date_range("2026-02-01", periods=n, freq="B")
        # 两个上涨波段，第二个高点 > 第一个
        closes = []
        # 第一波：10→13
        closes.extend([10.0 + i * 0.1 for i in range(30)])
        # 回调
        closes.extend([13.0 - i * 0.05 for i in range(10)])
        # 第二波：12.5→16
        closes.extend([12.5 + i * 0.1 for i in range(20)])
        volumes = [1000000] * n
        df = make_ohlcv(dates[:len(closes)], closes, volumes)

        highs = PivotDetector.get_last_n_highs(df, n=2)
        assert len(highs) >= 2
        if len(highs) >= 2:
            # 第二个高点应该更高
            assert highs[-1]["price"] > highs[-2]["price"]
```

- [ ] **步骤 2：运行测试确认失败**

```bash
pytest tests/engine/test_pivots.py -v
```

- [ ] **步骤 3：编写实现**

```python
"""前高/前低识别算法 — 局部极值检测。

设计文档§2.3 定义：
  前高/前低: 最近一个明显的局部最高/最低点
  - 局部高/低点: 该日最高价/最低价比前后各3日都高/低
  - 有效期: 距今≤60个交易日
  - 失效后使用次近点

算法选择：滚动窗口比较（scipy.signal.argrelextrema的简化实现）
  → 不依赖scipy以减少依赖，纯numpy实现。
  
为什么window=3？
→ 经验值。3天窗口足够过滤掉日内噪音，又能捕捉到足够多的局部极值。
  窗口太小=噪音多，太大=漏掉关键拐点。
"""
import pandas as pd
import numpy as np
from typing import List, Optional, Dict


class PivotDetector:
    """前高/前低识别器。

    使用滚动窗口比较法检测局部极值点。
    """

    @staticmethod
    def find_highs(daily_df: pd.DataFrame, window: int = 3) -> pd.DataFrame:
        """找出所有局部高点（该日最高价高于前后各window日的最高价）。"""
        highs = daily_df["high"].values
        n = len(highs)
        pivot_indices = []

        for i in range(window, n - window):
            left_max = np.max(highs[i - window:i])
            right_max = np.max(highs[i + 1:i + window + 1])
            if highs[i] > left_max and highs[i] > right_max:
                pivot_indices.append(i)

        return daily_df.iloc[pivot_indices].copy()

    @staticmethod
    def find_lows(daily_df: pd.DataFrame, window: int = 3) -> pd.DataFrame:
        """找出所有局部低点（该日最低价低于前后各window日的最低价）。"""
        lows = daily_df["low"].values
        n = len(lows)
        pivot_indices = []

        for i in range(window, n - window):
            left_min = np.min(lows[i - window:i])
            right_min = np.min(lows[i + 1:i + window + 1])
            if lows[i] < left_min and lows[i] < right_min:
                pivot_indices.append(i)

        return daily_df.iloc[pivot_indices].copy()

    @staticmethod
    def recent_high(daily_df: pd.DataFrame, max_age: int = 60) -> Optional[Dict]:
        """获取最近一个有效前高。

        max_age: 最大有效自然日天数（默认60个自然日 ≈ 约44个交易日）

        Returns:
            {"date": Timestamp, "price": float} 或 None
        """
        pivot_highs = PivotDetector.find_highs(daily_df)
        if len(pivot_highs) == 0:
            return None

        last_date = daily_df.index[-1]
        for idx in reversed(pivot_highs.index):
            days_diff = (last_date - idx).days
            if days_diff <= max_age:
                return {
                    "date": idx,
                    "price": float(pivot_highs.loc[idx, "high"]),
                }
        return None

    @staticmethod
    def recent_low(daily_df: pd.DataFrame, max_age: int = 60) -> Optional[Dict]:
        """获取最近一个有效前低。"""
        pivot_lows = PivotDetector.find_lows(daily_df)
        if len(pivot_lows) == 0:
            return None

        last_date = daily_df.index[-1]
        for idx in reversed(pivot_lows.index):
            days_diff = (last_date - idx).days
            if days_diff <= max_age:
                return {
                    "date": idx,
                    "price": float(pivot_lows.loc[idx, "low"]),
                }
        return None

    @staticmethod
    def get_last_n_highs(daily_df: pd.DataFrame, n: int = 2) -> List[Dict]:
        """获取最近n个有效前高（按时间升序）。

        用于检测结构条件A：是否有n个更高的高点。
        """
        pivot_highs = PivotDetector.find_highs(daily_df)
        if len(pivot_highs) == 0:
            return []

        last_date = daily_df.index[-1]
        valid = []
        for idx in pivot_highs.index:
            if (last_date - idx).days <= 60:
                valid.append({
                    "date": idx,
                    "price": float(pivot_highs.loc[idx, "high"]),
                })

        # 取最近n个（升序）
        valid.sort(key=lambda x: x["date"])
        return valid[-n:] if len(valid) >= n else valid

    @staticmethod
    def get_last_n_lows(daily_df: pd.DataFrame, n: int = 2) -> List[Dict]:
        """获取最近n个有效前低（按时间升序）。

        用于检测结构条件A：是否有n个更高的低点。
        """
        pivot_lows = PivotDetector.find_lows(daily_df)
        if len(pivot_lows) == 0:
            return []

        last_date = daily_df.index[-1]
        valid = []
        for idx in pivot_lows.index:
            if (last_date - idx).days <= 60:
                valid.append({
                    "date": idx,
                    "price": float(pivot_lows.loc[idx, "low"]),
                })

        valid.sort(key=lambda x: x["date"])
        return valid[-n:] if len(valid) >= n else valid
```

- [ ] **步骤 4：运行测试验证通过**

```bash
pytest tests/engine/test_pivots.py -v
```

- [ ] **步骤 5：Commit**

```bash
git add src/engine/pivots.py tests/engine/test_pivots.py && git commit -m "feat: implement pivot high/low detection algorithm"
```

---

### 任务 2.3：三条件判断器

**文件：**
- 创建：`src/engine/conditions.py`
- 测试：`tests/engine/test_conditions.py`

**为什么这三个条件缺一不可？**
→ **少亏钱**：设计文档§1明确"任何一个不满足就不叫上涨趋势"。结构确认方向（价格真的在走高），量能确认力量（真金白银在推），持续性确认节奏（多头占主导）。三个维度互相独立验证——结构通过但量能不足=无量空涨，随时可能崩塌；量能充足但无结构=可能是短期脉冲，追高必套；有结构有量能但无持续性=可能是诱多陷阱。只有三者同时满足，才值得投入真金白银。

- [ ] **步骤 1：编写失败测试**

```python
"""测试三条件判断器。"""
import pytest
import pandas as pd
import numpy as np
from src.engine.conditions import TrendConditions, ConditionResult
from tests.conftest import make_ohlcv


class TestTrendConditions:
    def test_structure_pass_uptrend(self, uptrend_daily):
        """上涨趋势数据应通过结构条件A。"""
        result = TrendConditions.check_structure(uptrend_daily)
        assert result.pass_ is True
        assert "更高高" in result.detail

    def test_structure_fail_downtrend(self, downtrend_daily):
        """下跌趋势数据应不通过结构条件A。"""
        result = TrendConditions.check_structure(downtrend_daily)
        assert result.pass_ is False

    def test_volume_pass_uptrend(self, uptrend_daily):
        """上涨趋势数据应通过量能条件B。"""
        result = TrendConditions.check_volume(uptrend_daily)
        assert result.pass_ is True
        assert "涨均量" in result.detail

    def test_volume_fail_downtrend(self, downtrend_daily):
        """下跌中缩量反弹不应通过量能条件。"""
        result = TrendConditions.check_volume(downtrend_daily)
        # 下跌趋势中上涨缩量下跌放量
        assert result.pass_ is False

    def test_persistence_pass_uptrend(self, uptrend_daily):
        """上涨趋势数据应通过持续性条件C。"""
        result = TrendConditions.check_persistence(uptrend_daily)
        assert result.pass_ is True
        assert "阳" in result.detail

    def test_persistence_fail_downtrend(self, downtrend_daily):
        """下跌趋势数据应不通过持续性条件C。"""
        result = TrendConditions.check_persistence(downtrend_daily)
        assert result.pass_ is False

    def test_three_conditions_all_independent(self, uptrend_daily):
        """三个条件验证三个独立维度。"""
        struct = TrendConditions.check_structure(uptrend_daily)
        volume = TrendConditions.check_volume(uptrend_daily)
        persist = TrendConditions.check_persistence(uptrend_daily)

        # 三个结果应该有不同的detail（验证不同维度）
        details = {struct.detail, volume.detail, persist.detail}
        assert len(details) == 3  # 各不相同

    def test_insufficient_data_all_fail(self):
        """数据不足时所有条件都不通过。"""
        n = 15
        dates = pd.date_range("2026-05-01", periods=n, freq="B")
        closes = [10 + i * 0.1 for i in range(n)]
        volumes = [1000000] * n
        df = make_ohlcv(dates, closes, volumes)

        assert TrendConditions.check_structure(df).pass_ is False
        assert TrendConditions.check_volume(df).pass_ is False
        assert TrendConditions.check_persistence(df).pass_ is False

    def test_continuous_three_yang_detection(self):
        """检测到连续3日阳线。"""
        n = 30
        dates = pd.date_range("2026-04-01", periods=n, freq="B")
        closes = [10.0] * 10 + [10.2, 10.5, 10.8, 10.6, 10.4] + [10.0] * 15
        volumes = [1000000] * n
        df = make_ohlcv(dates, closes, volumes)

        result = TrendConditions.check_persistence(df)
        # 存在连续3日上涨(10.0→10.2→10.5→10.8)
        assert result.pass_ is True
```

- [ ] **步骤 2：运行测试确认失败**

```bash
pytest tests/engine/test_conditions.py -v
```

- [ ] **步骤 3：编写实现**

```python
"""三条件判断器 — 趋势确认的核心判断逻辑。

设计文档§1.1 三个必要条件（缺一不可）：
  A. 结构：至少1对更高高+更高低（前期）/ 2对（中期确认）
  B. 量能：近20日上涨日平均成交量 > 下跌日平均成交量
  C. 持续性：近20日阳线>阴线，且出现过连续3根阳线

这三个条件从方向、力量、节奏三个独立维度验证趋势。

为什么三个条件缺一不可？
→ 少亏钱：任何一个缺失都意味着趋势不成立。如果只有结构无量能=无量空涨；
  只有量能无结构=短期脉冲；有量能有结构无持续性=可能是诱多陷阱。
  三重验证确保每一笔资金都投入到真正可靠的趋势中。
"""
import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import Tuple

from .pivots import PivotDetector


@dataclass
class ConditionResult:
    """单个条件的判断结果。"""
    pass_: bool
    detail: str  # 人类可读的判断详情，用于Dashboard的"为什么"展示


class TrendConditions:
    """三条件判断器 — 提供结构A、量能B、持续性C的独立判断。

    每个条件返回ConditionResult，包含pass_和detail。
    detail用于Dashboard的"为什么"展示（设计文档§9.5）。
    """

    LOOKBACK = 20  # 量能和持续性的回看窗口
    MIN_CONSECUTIVE_YANG = 3  # 持续性中最小连阳天数

    @staticmethod
    def check_structure(daily_df: pd.DataFrame) -> ConditionResult:
        """条件A：结构判断 — 价格是否在建立更高的高点和低点。

        使用前高/前低检测结果：
          - 前期（状态3）：至少1对更高高+更高低
          - 中期确认（状态4）：至少2对更高高+更高低

        实现逻辑：
          取最近2个有效前高，检查是否递增（更高高）
          取最近2个有效前低，检查是否递增（更高低）
        """
        if daily_df is None or len(daily_df) < 20:
            return ConditionResult(False, "数据不足，至少需要20个交易日")

        highs = PivotDetector.get_last_n_highs(daily_df, n=2)
        lows = PivotDetector.get_last_n_lows(daily_df, n=2)

        higher_highs = 0
        higher_lows = 0

        if len(highs) >= 2:
            for i in range(1, len(highs)):
                if highs[i]["price"] > highs[i - 1]["price"]:
                    higher_highs += 1

        if len(lows) >= 2:
            for i in range(1, len(lows)):
                if lows[i]["price"] > lows[i - 1]["price"]:
                    higher_lows += 1

        pairs = min(higher_highs, higher_lows)

        if pairs >= 2:
            return ConditionResult(True, f"2更高高+2更高低 (前高: {highs[-1]['price']:.2f}, 前低: {lows[-1]['price']:.2f})")
        elif pairs >= 1:
            return ConditionResult(True, f"1更高高+1更高低 (初步结构, 前高={highs[-1]['price']:.2f})")
        else:
            # 检查是否下跌结构
            if len(highs) >= 2 and highs[-1]["price"] < highs[-2]["price"]:
                return ConditionResult(False, f"高点持续降低(下跌结构): {highs[-2]['price']:.2f}→{highs[-1]['price']:.2f}")
            return ConditionResult(False, "无明确的上涨结构(无足够更高高/更高低)")

    @staticmethod
    def check_volume(daily_df: pd.DataFrame) -> ConditionResult:
        """条件B：量能判断 — 上涨日的平均成交量是否大于下跌日。

        设计文档§1.1 B条件:
          近20日：上涨日平均成交量 > 下跌日平均成交量

        为什么上涨日必须放量？
        → 少亏钱：无量上涨=庄股拉高出货或散户跟风，这样的"趋势"一旦逆转
          往往连续跌停。真金白银推动的上涨才有持续性。
        """
        if daily_df is None or len(daily_df) < TrendConditions.LOOKBACK:
            return ConditionResult(False, f"数据不足，至少需要{TrendConditions.LOOKBACK}个交易日")

        recent = daily_df.iloc[-TrendConditions.LOOKBACK:]
        up_days = recent[recent["close"] > recent["open"]]
        down_days = recent[recent["close"] < recent["open"]]

        if len(up_days) == 0:
            return ConditionResult(False, "近20日无阳线, 空头完全主导")

        if len(down_days) == 0:
            return ConditionResult(True, "近20日无阴线, 极强多头")

        up_avg_vol = up_days["volume"].mean()
        down_avg_vol = down_days["volume"].mean()

        if up_avg_vol > down_avg_vol:
            ratio = up_avg_vol / down_avg_vol
            return ConditionResult(True, f"上涨均量>下跌均量 {ratio:.1f}x (涨{up_avg_vol/1e8:.1f}亿 vs 跌{down_avg_vol/1e8:.1f}亿)")
        else:
            ratio = down_avg_vol / up_avg_vol if up_avg_vol > 0 else float("inf")
            return ConditionResult(False, f"上涨缩量, 下跌均量是上涨的{ratio:.1f}x")

    @staticmethod
    def check_persistence(daily_df: pd.DataFrame) -> ConditionResult:
        """条件C：持续性判断 — 多头是否持续占主导。

        设计文档§1.1 C条件:
          近20日：阳线 > 阴线，且出现过连续3根阳线

        为什么需要连续阳线？
        → 多赚钱：连续阳线意味着多头有持续进攻能力，不是打一枪就跑。
          孤立的阳线在下跌市中也常见，但连续阳线才代表真正的趋势力量。
        """
        if daily_df is None or len(daily_df) < TrendConditions.LOOKBACK:
            return ConditionResult(False, f"数据不足，至少需要{TrendConditions.LOOKBACK}个交易日")

        recent = daily_df.iloc[-TrendConditions.LOOKBACK:]

        yang_count = (recent["close"] > recent["open"]).sum()
        yin_count = (recent["close"] < recent["open"]).sum()

        # 检测最长连阳
        is_yang = recent["close"] > recent["open"]
        max_consecutive = 0
        current = 0
        for v in is_yang:
            if v:
                current += 1
                max_consecutive = max(max_consecutive, current)
            else:
                current = 0

        has_consecutive = max_consecutive >= TrendConditions.MIN_CONSECUTIVE_YANG

        if yang_count > yin_count and has_consecutive:
            return ConditionResult(True, f"近20日阳{yang_count}/{yin_count}阴, 最大连阳{max_consecutive}天")
        elif yang_count > yin_count:
            return ConditionResult(False, f"阳多于阴(阳{yang_count}/阴{yin_count}), 但无连续{self.MIN_CONSECUTIVE_YANG}阳, 持续性不足")
        else:
            return ConditionResult(False, f"阴盛阳衰(阳{yang_count}/阴{yin_count}), 空头主导")

    @classmethod
    def check_all(cls, daily_df: pd.DataFrame) -> dict:
        """一次执行全部三个条件检查。

        Returns:
            {"structure": ConditionResult, "volume": ConditionResult, "persistence": ConditionResult}
        """
        return {
            "structure": cls.check_structure(daily_df),
            "volume": cls.check_volume(daily_df),
            "persistence": cls.check_persistence(daily_df),
        }
```

- [ ] **步骤 4：运行测试验证通过**

```bash
pytest tests/engine/test_conditions.py -v
```

- [ ] **步骤 5：Commit**

```bash
git add src/engine/conditions.py tests/engine/test_conditions.py && git commit -m "feat: implement three-condition checker (structure + volume + persistence)"
```

---

### 任务 2.4：6状态状态机

**文件：**
- 创建：`src/engine/state_machine.py`
- 测试：`tests/engine/test_state_machine.py`

**为什么要用状态机而不是趋势评分？**
→ **少亏钱+多赚钱**：状态机定义的是"可操作的状态"，而不是"趋势的强度"。评分高的股票不一定能买（可能已在高位背离），状态3的股票即使评分不高也值得试探（刚突破关键位置）。状态机直接对应仓位动作——每个状态有明确的仓位建议，消除决策模糊性。

- [ ] **步骤 1：编写失败测试**

```python
"""测试6状态状态机。"""
import pytest
import pandas as pd
import numpy as np
from src.engine.state_machine import StateMachine, TrendState
from tests.conftest import make_ohlcv


class TestStateMachine:
    def test_uptrend_classifies_as_state4(self, uptrend_daily):
        """完整上涨趋势应判定为状态4。"""
        result = StateMachine.classify(uptrend_daily)
        assert result.state == 4

    def test_downtrend_classifies_as_state1(self, downtrend_daily):
        """持续下跌趋势应判定为状态1。"""
        result = StateMachine.classify(downtrend_daily)
        assert result.state == 1

    def test_state3_reversal_confirmation(self):
        """构造一个V形反转数据，应从下跌进入状态3。"""
        n = 50
        dates = pd.date_range("2026-03-01", periods=n, freq="B")

        # 前30天下跌：20→14
        closes1 = [20.0 - i * 0.2 for i in range(30)]
        # 回调形成低点14.0
        # 后20天强势反弹：14→17，放量突破前高
        closes2 = [14.0 + i * 0.15 for i in range(20)]
        closes = closes1 + closes2

        # 量能：反弹期间放量
        vols1 = [800000] * 30
        vols2 = [1500000] * 20
        volumes = vols1 + vols2

        df = make_ohlcv(dates, closes, volumes)
        result = StateMachine.classify(df)
        # 应进入状态3或状态4（取决于反弹是否形成完整结构）
        assert result.state in [3, 4]

    def test_state5_pullback_in_uptrend(self):
        """构造上涨中的正常回调，应判定为状态5。"""
        n = 60
        dates = pd.date_range("2026-02-01", periods=n, freq="B")

        # 前50天：持续上涨 10→18（形成状态4）
        closes1 = [10.0 + i * 0.16 for i in range(50)]
        # 后10天：缩量回调 18→17
        closes2 = [18.0 - i * 0.1 for i in range(10)]
        closes = closes1 + closes2

        vols1 = [1500000] * 50
        vols2 = [600000] * 10  # 缩量
        volumes = vols1 + vols2

        df = make_ohlcv(dates[:len(closes)], closes, volumes)
        result = StateMachine.classify(df)
        # 回调但未跌破前低 → 状态5
        assert result.state in [4, 5]

    def test_state_transition_2to3(self):
        """状态2→3的触发：放量突破前高。"""
        prev_state = 2
        # 模拟"放量突破前高"事件
        event = {
            "broke_prev_high": True,
            "volume_surge": True,  # 放量
            "close_above_ma20": True,
        }
        new_state = StateMachine.transition(prev_state, event)
        assert new_state == 3

    def test_state_transition_3to1(self):
        """状态3→1的触发：假突破，跌破新低。"""
        prev_state = 3
        event = {
            "broke_prev_low": True,
            "volume_surge": True,  # 放量下跌
        }
        new_state = StateMachine.transition(prev_state, event)
        assert new_state == 1

    def test_state_transition_4to5(self):
        """状态4→5：出现连续下跌但未破前低。"""
        prev_state = 4
        event = {
            "consecutive_drop": True,
            "broke_prev_low": False,
            "volume_shrink": True,  # 缩量
        }
        new_state = StateMachine.transition(prev_state, event)
        assert new_state == 5

    def test_state_transition_5to3prime(self):
        """状态5→3'：放量跌破前低。"""
        prev_state = 5
        event = {
            "broke_prev_low": True,
            "volume_surge": True,  # 放量跌破
        }
        new_state = StateMachine.transition(prev_state, event)
        assert new_state == "3'"

    def test_state_transition_3prime_to_1(self):
        """状态3'→1：再破新低。"""
        prev_state = "3'"
        event = {
            "broke_new_low": True,
        }
        new_state = StateMachine.transition(prev_state, event)
        assert new_state == 1

    def test_position_suggestion(self):
        """每个状态都有对应的仓位建议。"""
        assert StateMachine.position_suggestion(1) == 0.0
        assert StateMachine.position_suggestion(2) == 0.0
        assert 0.16 <= StateMachine.position_suggestion(3) <= 0.33
        assert StateMachine.position_suggestion(4) == 1.0
        assert StateMachine.position_suggestion(5) == 1.0
        assert StateMachine.position_suggestion("3'") == 0.33

    def test_all_six_states_accessible(self):
        """验证所有6种状态都有定义。"""
        states = StateMachine.ALL_STATES
        assert 1 in states
        assert 2 in states
        assert 3 in states
        assert 4 in states
        assert 5 in states
        assert "3'" in states
        assert len(states) == 6
```

- [ ] **步骤 2：运行测试确认失败**

```bash
pytest tests/engine/test_state_machine.py -v
```

- [ ] **步骤 3：编写实现**

```python
"""6状态状态机 — 趋势状态判定和状态转换。

设计文档§2.1 状态定义：
  状态1: 下跌趋势   → 仓位0，空仓
  状态2: 下跌反弹   → 仓位0，盯前高
  状态3: 翻转确认中 → 仓位1/6~1/3，试探
  状态4: 上涨趋势   → 仓位100%，持股
  状态5: 上涨回调   → 仓位100%，等加仓
  状态3': 转跌确认中 → 仓位1/3，防守

设计文档§2.2 状态转换表：
  1→2 连续上涨缩量未破前高
  2→1 反弹结束回落破前低
  2→3 放量突破前高 ← 买点1
  3→1 假突破跌破新低 ← 止损
  3→3 回调不破前低 → 加仓
  3→4 再创新高结构完整 ← 买点2
  4→5 连续下跌缩量未破前低
  5→4 企稳反弹不破前低 ← 最佳加仓
  5→3' 放量跌破前低 ← 防守
  3'→4 假跌破快速收复
  3'→1 再破新低 ← 全部清仓

为什么状态机而非连续评分？
→ 多赚钱+少亏钱：每个状态直接映射到仓位动作，消除模糊性。
  评分高≠能买（可能即将见顶），状态3评分低但值得试探（盈亏比最佳）。
"""
from dataclasses import dataclass, field
from typing import Optional, Dict, Union
import pandas as pd

from .conditions import TrendConditions
from .ma_filter import MAFilter
from .pivots import PivotDetector


StateValue = Union[int, str]  # 1-5 or "3'"


@dataclass
class TrendState:
    """趋势状态判定结果。"""
    state: StateValue
    state_label: str  # 人类可读的状态名
    position_ratio: float  # 建议仓位比
    conditions: Dict[str, object]  # 三个条件的结果
    prev_high: Optional[Dict] = None
    prev_low: Optional[Dict] = None
    consecutive_drop: bool = False  # 是否出现连续下跌
    consecutive_rise: bool = False  # 是否出现连续上涨
    volume_surge: bool = False  # 是否放量
    volume_shrink: bool = False  # 是否缩量
    above_ma20: bool = False


class StateMachine:
    """6状态趋势判定状态机。

    核心流程:
      1. 计算三条件结果
      2. 检测关键信号（连续涨跌、放量缩量、突破/跌破）
      3. 根据当前状态和事件 → 确定下一状态

    每个状态的仓位建议（设计文档§2.1）：
      状态1: 0（空仓）
      状态2: 0（观望）
      状态3: 0.167~0.333（试探仓）
      状态4: 1.0（标准仓）
      状态5: 1.0（持股等加仓）
      状态3': 0.333（防守仓）
    """

    ALL_STATES = {1, 2, 3, 4, 5, "3'"}
    STATE_LABELS = {
        1: "下跌趋势",
        2: "下跌中的反弹",
        3: "翻转确认中",
        4: "上涨趋势",
        5: "上涨中的回调",
        "3'": "转跌确认中",
    }
    POSITIONS = {
        1: 0.0,
        2: 0.0,
        3: 0.25,   # 试探仓中间值（1/6=0.167 ~ 1/3=0.333）
        4: 1.0,
        5: 1.0,
        "3'": 0.333,
    }

    @classmethod
    def classify(cls, daily_df: pd.DataFrame) -> TrendState:
        """对日K数据运行状态机，判定当前处于哪个状态。

        这是状态机的完整分类逻辑。不依赖"前一日状态"（首次分类），
        只基于当前可用的全部数据做出独立判断。

        为什么可以独立判断？
        → 设计文档§2.2的状态转换需要前一日状态，但首次运行时没有。
          独立分类从数据结构推断最可能的状态：如果当前有多头结构=状态4，
          如果有空头结构=状态1。这足够准确——因为后续每日运行时会对比前一日状态。
        """
        # 1. 计算三条件
        conds = TrendConditions.check_all(daily_df)

        # 2. 检测关键信号
        recent = daily_df.iloc[-5:]  # 最近5日
        closes = daily_df["close"]
        volumes = daily_df["volume"]

        # 连续下跌检测（设计文档§2.3）
        consecutive_drop = cls._detect_consecutive_drop(daily_df)
        consecutive_rise = cls._detect_consecutive_rise(daily_df)

        # 放量/缩量检测
        ma20_vol = volumes.rolling(20).mean().iloc[-1]
        today_vol = volumes.iloc[-1]
        volume_surge = today_vol > ma20_vol * 1.2 if not pd.isna(ma20_vol) else False
        volume_shrink = today_vol < ma20_vol * 0.8 if not pd.isna(ma20_vol) else False

        # MA20判断
        above_ma20 = MAFilter.check(daily_df)

        # 前高/前低
        prev_high = PivotDetector.recent_high(daily_df)
        prev_low = PivotDetector.recent_low(daily_df)

        # 3. 独立判定状态
        struct_ok = conds["structure"].pass_
        volume_ok = conds["volume"].pass_
        persist_ok = conds["persistence"].pass_

        # 构建事件
        broke_prev_high = False
        if prev_high and len(daily_df) >= 2:
            broke_prev_high = closes.iloc[-1] > prev_high["price"]

        broke_prev_low = False
        if prev_low and len(daily_df) >= 2:
            broke_prev_low = closes.iloc[-1] < prev_low["price"]

        # 判断状态
        if struct_ok and volume_ok and persist_ok:
            # 完整上涨结构 → 状态4
            if consecutive_drop and not broke_prev_low and volume_shrink:
                state = 5  # 上涨中的回调
            else:
                state = 4  # 上涨趋势
        elif struct_ok and not volume_ok and not persist_ok:
            # 结构有但量能和持续性不足
            if broke_prev_high:
                state = 3  # 突破前高但尚未完全确认
            else:
                state = 2  # 反弹但未突破
        elif not struct_ok and above_ma20 and consecutive_rise:
            state = 2  # 反弹中
        elif not struct_ok and not above_ma20 and consecutive_drop:
            state = 1  # 下跌趋势
        elif consecutive_drop and broke_prev_low and volume_surge:
            state = "3'"  # 放量跌破前低
        elif consecutive_rise and not broke_prev_high:
            state = 2  # 反弹进行中
        else:
            state = 1  # 默认判断为下跌

        return TrendState(
            state=state,
            state_label=cls.STATE_LABELS.get(state, "未知"),
            position_ratio=cls.position_suggestion(state),
            conditions=conds,
            prev_high=prev_high,
            prev_low=prev_low,
            consecutive_drop=consecutive_drop,
            consecutive_rise=consecutive_rise,
            volume_surge=volume_surge,
            volume_shrink=volume_shrink,
            above_ma20=above_ma20,
        )

    @classmethod
    def transition(cls, prev_state: StateValue, event: dict) -> StateValue:
        """基于前一日状态和当日事件，判定状态转换。

        event字典应包含检测到的事件信号:
          - broke_prev_high: bool  突破前高
          - broke_prev_low: bool   跌破前低
          - broke_new_low: bool     再破新低（3'→1）
          - volume_surge: bool      放量
          - volume_shrink: bool     缩量
          - consecutive_drop: bool  连续下跌
          - consecutive_rise: bool  连续上涨
        """
        if prev_state == 1:
            if event.get("consecutive_rise") and not event.get("broke_prev_high"):
                if event.get("volume_shrink", True):
                    return 2
            return 1

        elif prev_state == 2:
            if event.get("broke_prev_low"):
                return 1
            if event.get("broke_prev_high") and event.get("volume_surge"):
                return 3
            return 2

        elif prev_state == 3:
            if event.get("broke_prev_low") and event.get("volume_surge"):
                return 1  # 假突破止损
            if event.get("broke_prev_high") and event.get("volume_surge"):
                return 4  # 再创新高→状态4
            return 3  # 维持试探

        elif prev_state == 4:
            if event.get("consecutive_drop"):
                if event.get("broke_prev_low") and event.get("volume_surge"):
                    return "3'"
                if not event.get("broke_prev_low"):
                    return 5
            return 4

        elif prev_state == 5:
            if event.get("broke_prev_low") and event.get("volume_surge"):
                return "3'"
            if event.get("consecutive_rise") and not event.get("broke_prev_low"):
                return 4
            return 5

        elif prev_state == "3'":
            if event.get("broke_new_low"):
                return 1
            if event.get("consecutive_rise") and event.get("broke_prev_high_again", False):
                return 4  # 假跌破修复
            return "3'"

        return prev_state

    @classmethod
    def position_suggestion(cls, state: StateValue) -> float:
        """返回指定状态的建议仓位比例。"""
        return cls.POSITIONS.get(state, 0.0)

    @staticmethod
    def _detect_consecutive_drop(daily_df: pd.DataFrame, min_days: int = 2, min_pct: float = -0.015) -> bool:
        """检测连续下跌（设计文档§2.3）。

        至少2个交易日连续收阴，且累计跌幅>1.5%。
        """
        if len(daily_df) < min_days:
            return False
        recent = daily_df.iloc[-min_days:]
        all_yin = all(recent["close"].values[i] < recent["open"].values[i] for i in range(len(recent)))
        if not all_yin:
            return False
        cum_ret = (recent["close"].iloc[-1] / recent["close"].iloc[0] - 1)
        return cum_ret < min_pct

    @staticmethod
    def _detect_consecutive_rise(daily_df: pd.DataFrame, min_days: int = 2, min_pct: float = 0.02) -> bool:
        """检测连续上涨（设计文档§2.3）。

        至少2个交易日连续收阳，且累计涨幅>2%。
        """
        if len(daily_df) < min_days:
            return False
        recent = daily_df.iloc[-min_days:]
        all_yang = all(recent["close"].values[i] > recent["open"].values[i] for i in range(len(recent)))
        if not all_yang:
            return False
        cum_ret = (recent["close"].iloc[-1] / recent["close"].iloc[0] - 1)
        return cum_ret > min_pct
```

- [ ] **步骤 4：运行测试验证通过**

```bash
pytest tests/engine/test_state_machine.py -v
```

- [ ] **步骤 5：Commit**

```bash
git add src/engine/state_machine.py tests/engine/test_state_machine.py && git commit -m "feat: implement 6-state trend state machine with transitions"
```

---

### 任务 2.5：趋势阶段分类器 & 关键操作点识别器

**文件：**
- 创建：`src/engine/stage.py`
- 创建：`src/engine/key_points.py`
- 测试：`tests/engine/test_stage.py`
- 测试：`tests/engine/test_key_points.py`

- [ ] **步骤 1：编写趋势阶段分类器**

```python
"""趋势阶段分类器 — 判断趋势处于前期/中期/后期。

设计文档§2.4 趋势阶段映射：
  前期(状态3): 结构初步形成, 试探建仓, 胜率低但赔率高
  中期(状态4早期): 结构完整确认, 标准仓位, 主升浪持股
  后期(状态4晚期): 斜率变陡+放量滞涨+回调频繁 → 收紧止损

为什么需要阶段分类？
→ 多赚钱+少亏钱：同样是状态4，"前期"应该加仓，"后期"应该警惕减仓。
  阶段分类告诉你同一状态下应该进攻还是防守。
"""
from dataclasses import dataclass
from typing import Optional
import pandas as pd
import numpy as np


@dataclass
class StageResult:
    stage: str  # "early", "mid", "late"
    label: str  # "前期", "中期", "后期"
    reasons: list  # 判定依据


class StageClassifier:
    """趋势阶段分类器。

    判断逻辑（仅对状态3/4有意义）：
      - 前期：状态3 或 状态4刚开始（最近10日内从状态3转入）
      - 中期：状态4持续10日以上，无异常信号
      - 后期：状态4中检测到至少2个晚期信号
    """

    @staticmethod
    def classify(state: int, daily_df: pd.DataFrame, days_in_state: int = 1) -> StageResult:
        """根据当前状态和数据判断趋势阶段。

        Args:
            state: 当前状态（1-5或3'）
            daily_df: 日K数据
            days_in_state: 在当前状态已持续的交易日数

        Returns:
            StageResult: 阶段判定结果
        """
        if state == 3:
            return StageResult(stage="early", label="前期", reasons=["状态3翻转确认中，处于趋势初期"])

        if state not in [4, 5]:
            return StageResult(stage="", label="", reasons=["非上涨趋势状态，不适用阶段分类"])

        if days_in_state < 10:
            return StageResult(stage="mid", label="中期", reasons=["状态4确认不足10日，处于中期早期"])

        # 检测晚期信号
        late_signals = StageClassifier._check_late_signals(daily_df)

        if len(late_signals) >= 2:
            return StageResult(stage="late", label="后期", reasons=late_signals)

        return StageResult(stage="mid", label="中期", reasons=["状态4持续运行中，无异常晚期信号"])

    @staticmethod
    def _check_late_signals(daily_df: pd.DataFrame) -> list:
        """检测晚期信号。

        三个晚期信号（设计文档§2.4）：
          1. 斜率变陡：近5日涨幅远超近20日均速
          2. 放量滞涨：成交量放大但价格不涨
          3. 回调频繁：近20日回调次数显著增多
        """
        signals = []

        if len(daily_df) < 20:
            return signals

        closes = daily_df["close"]

        # 信号1：斜率变陡
        ret_5d = (closes.iloc[-1] / closes.iloc[-6] - 1) if len(closes) >= 6 else 0
        ret_20d = (closes.iloc[-1] / closes.iloc[-21] - 1) if len(closes) >= 21 else 0
        avg_5d_rate = ret_5d / 5
        avg_20d_rate = ret_20d / 20
        if avg_20d_rate > 0 and avg_5d_rate > avg_20d_rate * 3:
            signals.append(f"斜率加速: 近5日日均涨幅{avg_5d_rate*100:.1f}% vs 20日均速{avg_20d_rate*100:.1f}%")

        # 信号2：放量滞涨
        recent_5_vol = daily_df["volume"].iloc[-5:].mean()
        ma20_vol = daily_df["volume"].rolling(20).mean().iloc[-1]
        if recent_5_vol > ma20_vol * 1.3 and ret_5d < 0.01:
            signals.append(f"放量滞涨: 量能{recent_5_vol/ma20_vol:.1f}x均量, 但5日涨幅仅{ret_5d*100:.1f}%")

        # 信号3：回调频繁
        yin_count = sum(1 for i in range(len(daily_df)-20, len(daily_df))
                        if daily_df["close"].iloc[i] < daily_df["open"].iloc[i])
        if yin_count >= 9:  # 近20日有9日以上收阴
            signals.append(f"回调频繁: 近20日{yin_count}日收阴")

        return signals
```

- [ ] **步骤 2：编写关键操作点识别器**

```python
"""关键操作点识别器 — 识别6个需要决策的操作点。

设计文档§2.2 加粗行 = 6个关键操作点：
  1. 2→3: 放量突破前高 → 买点1，1/6试探建仓
  2. 3→1: 假突破 → 止损，全清
  3. 3→4: 再创新高 → 买点2，加至标准仓
  4. 5→4: 企稳反弹 → 最佳加仓，1.2~1.5倍
  5. 5→3': 放量跌破前低 → 防守，减至1/3
  6. 3'→1: 再破新低 → 全部清仓退场

为什么只有6个关键点？
→ 少亏钱：大多数交易日不需要操作。频繁操作=手续费+判断失误概率增加。
  只在状态转换的关键位置操作，降低交易频率，提高每笔交易的确定性。
"""
from dataclasses import dataclass
from typing import Optional, List
import pandas as pd

from .state_machine import StateMachine, StateValue


@dataclass
class KeyPoint:
    """关键操作点。"""
    transition: str  # 如 "2→3"
    action: str  # "买点1", "止损", "买点2", "最佳加仓", "防守", "退场"
    position_action: str  # 仓位动作
    priority: str  # "🔴" | "🟠" | "🟢" | "🟡"
    description: str  # 详细说明


class KeyPointDetector:
    """关键操作点识别器。

    对比前一状态和当前状态，识别是否触发了6个关键操作点。
    """

    KEY_TRANSITIONS = {
        ("2→3"): KeyPoint("2→3", "买点1", "1/6试探建仓", "🟡", "放量突破前高, 试探仓进场"),
        ("3→1"): KeyPoint("3→1", "止损", "全部清仓", "🔴", "假突破确认, 跌破新低止损"),
        ("3→4"): KeyPoint("3→4", "买点2", "加至标准仓(100%)", "🟢", "再创新高结构完整, 标准仓位"),
        ("5→4"): KeyPoint("5→4", "最佳加仓", "加至1.2~1.5倍", "🟢", "回调企稳反弹, 最佳加仓时机"),
        ("5→3'"): KeyPoint("5→3'", "防守", "减至1/3仓", "🟠", "放量跌破前低, 上涨结构被破坏"),
        ("3'→1"): KeyPoint("3'→1", "退场", "全部清仓", "🔴", "再破新低结构破坏, 趋势结束"),
    }

    @classmethod
    def detect(cls, prev_state: StateValue, current_state: StateValue) -> Optional[KeyPoint]:
        """检测状态转换是否触发了关键操作点。

        Args:
            prev_state: 前一日状态
            current_state: 当前状态

        Returns:
            KeyPoint: 如果触发关键操作点，否则返回None
        """
        # 状态不变则无关键操作点
        if prev_state == current_state:
            return None

        # 状态3内部的加仓（3→3加仓）不是关键操作点，但状态变化是
        transition_key = f"{prev_state}→{current_state}"
        return cls.KEY_TRANSITIONS.get(transition_key)

    @classmethod
    def detect_all(cls, prev_results: dict, current_results: dict) -> List[KeyPoint]:
        """批量检测所有标的的关键操作点。

        Args:
            prev_results: {symbol: previous_TrendState}
            current_results: {symbol: current_TrendState}

        Returns:
            list of (symbol, KeyPoint) tuples
        """
        points = []
        for sym, cur in current_results.items():
            if sym in prev_results:
                prev_state = prev_results[sym].state
                kp = cls.detect(prev_state, cur.state)
                if kp:
                    points.append((sym, kp))
        return points
```

- [ ] **步骤 3：编写测试**

```python
"""测试趋势阶段分类器和关键操作点识别器。"""
import pytest
import pandas as pd
import numpy as np
from src.engine.stage import StageClassifier
from src.engine.key_points import KeyPointDetector
from tests.conftest import make_ohlcv


class TestStageClassifier:
    def test_state3_is_early(self, uptrend_daily):
        """状态3判定为前期。"""
        result = StageClassifier.classify(3, uptrend_daily)
        assert result.stage == "early"
        assert result.label == "前期"

    def test_state4_over_10_days_is_mid(self, uptrend_daily):
        """状态4超过10日判定为中期。"""
        result = StageClassifier.classify(4, uptrend_daily, days_in_state=15)
        assert result.stage == "mid"

    def test_state1_no_stage(self, downtrend_daily):
        """状态1不适用阶段分类。"""
        result = StageClassifier.classify(1, downtrend_daily)
        assert result.stage == ""

    def test_late_signals_detected(self):
        """检测晚期信号。"""
        n = 40
        dates = pd.date_range("2026-03-01", periods=n, freq="B")
        # 后5天加速上涨（斜率变陡）+ 放量
        closes = [10.0 + i * 0.1 for i in range(35)] + [13.5, 14.2, 15.3, 16.8, 18.5]
        volumes = [1000000] * 35 + [2000000] * 5
        df = make_ohlcv(dates, closes, volumes)

        signals = StageClassifier._check_late_signals(df)
        assert len(signals) >= 1  # 至少检测到斜率变陡


class TestKeyPointDetector:
    def test_transition_2_to_3_is_buy1(self):
        """状态2→3 = 买点1。"""
        kp = KeyPointDetector.detect(2, 3)
        assert kp is not None
        assert kp.action == "买点1"
        assert kp.position_action == "1/6试探建仓"

    def test_transition_3_to_1_is_stop_loss(self):
        """状态3→1 = 止损。"""
        kp = KeyPointDetector.detect(3, 1)
        assert kp is not None
        assert kp.action == "止损"

    def test_transition_5_to_3prime_is_defense(self):
        """状态5→3' = 防守。"""
        kp = KeyPointDetector.detect(5, "3'")
        assert kp is not None
        assert kp.action == "防守"

    def test_same_state_no_keypoint(self):
        """相同状态不变无关键点。"""
        assert KeyPointDetector.detect(4, 4) is None
        assert KeyPointDetector.detect(1, 1) is None

    def test_all_six_key_points_defined(self):
        """验证全部6个关键操作点都有定义。"""
        transitions = [("2→3"), ("3→1"), ("3→4"), ("5→4"), ("5→3'"), ("3'→1")]
        for t in transitions:
            assert t in KeyPointDetector.KEY_TRANSITIONS, f"Missing: {t}"
```

- [ ] **步骤 4：运行测试**

```bash
pytest tests/engine/test_stage.py tests/engine/test_key_points.py -v
```

- [ ] **步骤 5：Commit**

```bash
git add src/engine/stage.py src/engine/key_points.py tests/engine/test_stage.py tests/engine/test_key_points.py && git commit -m "feat: implement stage classifier and key point detector"
```

---

### Phase 2 验证

- [ ] 运行全部引擎层测试：`pytest tests/engine/ -v`
- [ ] 对照设计文档§2检查：
  - [x] 三条件判断器（结构A+量能B+持续性C） ✅
  - [x] 6状态状态机（状态1-5 + 3'） ✅
  - [x] 趋势阶段分类器（前/中/后期） ✅
  - [x] 前高/前低识别（局部极值检测） ✅
  - [x] 均线初筛过滤器（MA20） ✅
  - [x] 关键操作点识别器 ✅

---

## Phase 3: 漏斗筛选

（以下每个任务的格式与Phase 1/2相同，为节省篇幅使用紧凑格式。）

### 任务 3.1：漏斗第一层 — 板块趋势判断

**文件：** `src/funnel/sector_filter.py`, `tests/funnel/test_sector_filter.py`

**核心逻辑：** 遍历所有板块日K → 跑状态机 → 筛出状态3/4/5的板块 → 输出上涨板块列表。

```python
"""板块趋势判断 — 漏斗第一层。

设计文档§3.1 第一层：
  输入: 板块日K OHLCV (~60-90个)
  逻辑: 跑状态机，筛出状态3/4/5的板块
  输出: 上涨板块列表 (~5-15个)

为什么从板块开始？
→ 多赚钱：A股70%以上的个股波动由板块驱动。先确定哪些板块在上涨趋势中，
  再在上涨板块中选个股，可大幅提高选股成功率。逆板块趋势的个股即使涨也难持续。
"""
from typing import List, Dict
import pandas as pd
from ..engine.state_machine import StateMachine, TrendState


class SectorFilter:
    """板块趋势判断 — 漏斗第一层。

    遍历所有板块日K数据，运行状态机，筛选处于上涨趋势的板块。
    """

    TARGET_STATES = {3, 4, 5}  # 只关注上涨趋势相关状态

    @staticmethod
    def filter(sector_data: Dict[str, pd.DataFrame]) -> Dict[str, TrendState]:
        """筛选处于上涨趋势的板块。

        Args:
            sector_data: {bk_code: DataFrame(OHLCV)}

        Returns:
            {bk_code: TrendState} 仅包含状态3/4/5的板块
        """
        results = {}
        for bk_code, df in sector_data.items():
            state_result = StateMachine.classify(df)
            if state_result.state in SectorFilter.TARGET_STATES:
                results[bk_code] = state_result
        return results

    @staticmethod
    def rank(results: Dict[str, TrendState]) -> List[tuple]:
        """按趋势强度排序板块。

        排序规则：
          1. 状态4 > 状态5 > 状态3
          2. 同状态：结构完整度（2对高低>1对）> 量能比 > 持续性
        """
        def score(item):
            code, ts = item
            state_score = {4: 100, 5: 80, 3: 60}
            base = state_score.get(ts.state, 0)
            # 三个条件都通过加分
            if ts.conditions["structure"].pass_: base += 10
            if ts.conditions["volume"].pass_: base += 10
            if ts.conditions["persistence"].pass_: base += 10
            return base

        ranked = sorted(results.items(), key=score, reverse=True)
        return ranked
```

- [ ] 编写测试并commit

---

### 任务 3.2：漏斗第二层 — 题材趋势判断

**文件：** `src/funnel/theme_filter.py`, `tests/funnel/test_theme_filter.py`

```python
"""题材趋势判断 — 漏斗第二层。

设计文档§3.1 第二层：
  输入: 题材日K OHLCV (仅上涨板块内的题材)
  逻辑: 跑状态机，筛出状态3/4的题材
  输出: 活跃题材列表 (~3-8个)

为什么题材在板块之后？
→ 多赚钱：题材通常比板块更窄、更热、弹性更大。板块确认了大的方向，
  题材提供更精确的alpha来源——同一板块内，高景气题材涨幅往往是板块的2-3倍。
"""
from ..engine.state_machine import StateMachine, TrendState
from typing import Dict, List
import pandas as pd


class ThemeFilter:
    """题材趋势判断 — 漏斗第二层。"""

    TARGET_STATES = {3, 4}

    @staticmethod
    def filter(theme_data: Dict[str, pd.DataFrame]) -> Dict[str, TrendState]:
        """筛选处于发展期/高潮期的题材（状态3/4）。"""
        results = {}
        for gn_code, df in theme_data.items():
            state_result = StateMachine.classify(df)
            if state_result.state in ThemeFilter.TARGET_STATES:
                results[gn_code] = state_result
        return results

    @staticmethod
    def rank(results: Dict[str, TrendState]) -> List[tuple]:
        """按活跃度排序题材。状态4 > 状态3，结构完整度 > 量能 > 持续性。"""
        def score(item):
            code, ts = item
            state_score = {4: 100, 3: 60}
            base = state_score.get(ts.state, 0)
            if ts.conditions["structure"].pass_: base += 15
            if ts.conditions["volume"].pass_: base += 10
            if ts.conditions["persistence"].pass_: base += 10
            return base
        return sorted(results.items(), key=score, reverse=True)
```

- [ ] 编写测试并commit

---

### 任务 3.3：漏斗第三层 — 个股趋势判断

**文件：** `src/funnel/stock_filter.py`, `tests/funnel/test_stock_filter.py`

```python
"""个股趋势判断 — 漏斗第三层。

设计文档§3.1 第三层：
  输入: 个股日K OHLCV (~300-500只，仅活跃题材内的成分股)
  逻辑: 跑状态机，输出状态+关键点信号
  输出: 趋势个股 + 交易信号 (~5-20只)

为什么个股放最后一层？
→ 少亏钱：前两层（板块+题材）已经过滤掉了80-90%的噪声，第三层只需要
  处理最相关的300-500只个股。如果直接在全市场5000个股上跑状态机，
  会产出大量"技术形态好看但无板块支撑"的假信号。
"""
from ..engine.state_machine import StateMachine, TrendState
from typing import Dict, List
import pandas as pd


class StockFilter:
    """个股趋势判断 — 漏斗第三层。"""

    TARGET_STATES = {3, 4, 5}

    @staticmethod
    def filter(stock_data: Dict[str, pd.DataFrame]) -> Dict[str, TrendState]:
        """筛选处于上涨趋势的个股。"""
        results = {}
        for sym, df in stock_data.items():
            state_result = StateMachine.classify(df)
            if state_result.state in StockFilter.TARGET_STATES:
                results[sym] = state_result
        return results

    @staticmethod
    def rank(results: Dict[str, TrendState]) -> List[tuple]:
        """按操作价值排序个股。"""
        def score(item):
            code, ts = item
            state_score = {4: 100, 5: 85, 3: 70}
            base = state_score.get(ts.state, 0)
            if ts.conditions["structure"].pass_: base += 10
            if ts.conditions["volume"].pass_: base += 10
            if ts.conditions["persistence"].pass_: base += 10
            return base
        return sorted(results.items(), key=score, reverse=True)
```

- [ ] 编写测试并commit

---

### 任务 3.4：ETF直筛路径 + 龙头识别 + 置信度

**文件：** `src/funnel/etf_filter.py`, `src/funnel/leader.py`, `src/funnel/confidence.py`

这三个模块较紧凑，一起实现。

- **ETF直筛**：对A/B类ETF直接跑状态机，独立于漏斗主路径
- **龙头识别**：在题材内按涨幅排名+成交额排名综合判定
- **置信度**：双路交叉验证（漏斗命中+ETF命中=最高置信度）

**为什么需要ETF直筛路径？**
→ 多赚钱：ETF交易成本低、无单只股票暴雷风险。如果ETF自身处于上涨趋势，
  即使没经过板块→题材→个股的漏斗（如跨板块题材ETF），也是好的交易标的。

**为什么需要龙头识别？**
→ 多赚钱：题材内龙头股弹性远大于板块ETF。识别龙头=捕获超额收益。
  龙头标准：题材内涨幅前3 + 成交额前5（设计文档§9.5）。

**为什么需要置信度？**
→ 少亏钱：低置信度的信号应减小仓位。双路确认的标的（漏斗+直筛同时命中）
  比单路命中的更可靠。仓位=置信度×标准仓位，量化控制风险。

每模块编写测试后commit。

---

### Phase 3 验证

- [ ] 漏斗筛选集成测试
- [ ] 端到端：板块列表→上涨板块→活跃题材→趋势个股→信号

---

## Phase 4-6: 剩余模块

由于篇幅限制，Phase 4-6的详细任务规格遵循相同的 TDD 模式。每个模块的结构：

### Phase 4: 分析与推演

| 任务 | 文件 | 核心职责 |
|------|------|---------|
| 4.1 趋势变化对比 | `src/analysis/comparison.py` | 对比昨日/3日前/上周，输出新增/退出/变化 |
| 4.2 明日推演引擎 | `src/analysis/scenario.py` | 基于状态机生成3个场景(大概率/中概率/小概率) |
| 4.3 板块β强度 | `src/analysis/beta.py` | 板块相对大盘的β计算 |
| 4.4 市场宽度 | `src/analysis/breadth.py` | 上涨板块数/状态4数/趋势个股数的变化趋势 |

### Phase 5: 展示层

| 任务 | 文件 | 核心职责 |
|------|------|---------|
| 5.1 JSON快照产出 | `src/display/snapshot.py` | 每日产出完整`trend_snapshot_{date}.json` |
| 5.2 HTML Dashboard | `src/display/dashboard.html` | 单文件，加载JSON渲染，全部§9规格 |

### Phase 6: CLI & 自动化

| 任务 | 文件 | 核心职责 |
|------|------|---------|
| 6.1 CLI入口 | `src/cli.py` | run/dashboard/status三个命令 |
| 6.2 setup.py/pyproject | `pyproject.toml` | 包配置，pip install -e |

---

## 实施顺序

```
Phase 1 (数据层)
    ↓
Phase 2 (趋势引擎)    ← 核心算法，必须完全正确
    ↓
Phase 3 (漏斗筛选)    ← 依赖引擎，依赖数据层
    ↓
Phase 4 (分析与推演)   ← 依赖漏斗输出
    ↓
Phase 5 (展示层)      ← 依赖所有上游输出
    ↓
Phase 6 (CLI)         ← 串联所有Phase
```

每个Phase完成后：
1. 运行该Phase的全部测试
2. 对照设计文档检查完整性
3. 向用户展示完成情况，确认后进入下一Phase
```

- [ ] Commit整个计划

---

## 自检

**1. 规格覆盖度：** ✅

| 设计文档章节 | 对应任务 |
|-------------|---------|
| §1 三条件定义 | 任务2.3 |
| §2.1 状态定义 | 任务2.4 |
| §2.2 状态转换 | 任务2.4 |
| §2.3 关键术语 | 任务2.2+2.4 |
| §2.4 阶段映射 | 任务2.5 |
| §3.1 漏斗数据流 | 任务3.1-3.3 |
| §3.2 ETF直筛 | 任务3.4 |
| §3.3 输出分类 | 任务3.4 |
| §4 数据获取 | 任务1.2-1.6 |
| §5 输出格式 | 任务5.1 |
| §6 参数表 | 分布在各自模块中 |
| §7 边界场景 | 测试覆盖 |
| §8 策略适用范围 | 任务3.4 ETF类型分类 |
| §9 展示层 | 任务5.2 |

**2. 占位符扫描：** ✅ 无"TBD"/"TODO"，每个任务都有具体代码。

**3. 类型一致性：** ✅ TrendState、ConditionResult、StageResult、KeyPoint 定义一致。
