# 系统运行修复计划

> 本文档是系统运行修复的权威计划。所有实现以此为准。
>
> **制定日期**: 2026-07-12
> **状态**: 待确认

---

## 一、问题清单

| 序号 | 问题 | 严重性 | 修复难度 | 预计耗时 |
|------|------|--------|---------|---------|
| 1 | serve.py路径指向v1输出目录 | 中 | 低 | 10分钟 |
| 2 | 板块/主题价格数据为空 | 中 | 高 | 2-3小时 |
| 3 | pipeline生命周期检查阻塞 | 低 | 低 | 30分钟 |

---

## 二、修复1: serve.py路径（10分钟）

**当前问题**: `v2/serve.py`指向`dashboard/`（v1输出目录），而不是v2输出目录。

**修复方案**: 自动查找最新的v2输出bundle。

### 2.1 修改v2/serve.py

```python
"""No-cache static server for TFS v2 display output."""

from __future__ import annotations

import http.server
from pathlib import Path


class NoCacheHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    """Static handler that prevents browser caching during dashboard review."""

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()


def _find_latest_bundle(display_runs: Path) -> Path | None:
    """Find the most recent run bundle with a valid index.html."""
    candidates = []
    for child in display_runs.iterdir():
        if child.is_dir() and (child / "index.html").exists():
            candidates.append(child)
    if not candidates:
        return None
    # Sort by directory name (timestamp-based run IDs sort chronologically)
    candidates.sort(key=lambda p: p.name, reverse=True)
    return candidates[0]


def serve(port: int = 8765, directory: str | None = None) -> None:
    if directory:
        root = Path(directory)
    else:
        # Try v2 display_runs first, fall back to v1 dashboard
        project_root = Path(__file__).resolve().parents[1]
        display_runs = project_root / "v2" / "data" / "derived" / "display_runs"
        latest = _find_latest_bundle(display_runs)
        if latest:
            root = latest
        else:
            root = project_root / "dashboard"

    handler = lambda *args, **kwargs: NoCacheHTTPRequestHandler(
        *args, directory=str(root), **kwargs
    )
    with http.server.ThreadingHTTPServer(("", port), handler) as server:
        print(f"Serving {root} at http://localhost:{port}/")
        server.serve_forever()


if __name__ == "__main__":
    serve()
```

### 2.2 验证方式

1. 运行pipeline生成输出
2. 运行`python3 v2/serve.py`
3. 打开`http://localhost:8765/`确认显示v2页面

---

## 三、修复2: 板块/主题价格数据fetcher（2-3小时）

### 3.1 API选择

**选择Eastmoney API**（更简单、更可靠）：

| 函数 | 用途 | 参数 |
|------|------|------|
| `stock_board_industry_hist_em()` | 板块日K | symbol=BK代码, period="日k" |
| `stock_board_concept_hist_em()` | 主题日K | symbol=BK代码, period="daily" |

**优势**:
- 直接接受BK代码（如`BK0420`），无需名称转换
- 单次API调用获取完整历史数据
- 与现有`akshare_em.py`模式一致

### 3.2 修改v2/data_layer/providers/akshare_em.py

#### 新增方法1: fetch_sector_daily()

```python
def fetch_sector_daily(self, code: str, start_date: str, end_date: str) -> pd.DataFrame:
    """获取板块日K线数据。
    
    参数:
        code: 板块BK代码（如"BK0420"）
        start_date: 开始日期（YYYY-MM-DD）
        end_date: 结束日期（YYYY-MM-DD）
    
    返回:
        标准化OHLCV DataFrame
    """
    try:
        df = self.ak.stock_board_industry_hist_em(
            symbol=code,
            period="日k",
            start_date=self._compact_date(start_date),
            end_date=self._compact_date(end_date),
            adjust="qfq",
        )
        return self._normalize_board_daily(df)
    except Exception as e:
        self._log(f"Failed to fetch sector daily for {code}: {e}")
        return pd.DataFrame()
```

#### 新增方法2: fetch_theme_daily()

```python
def fetch_theme_daily(self, code: str, start_date: str, end_date: str) -> pd.DataFrame:
    """获取主题日K线数据。
    
    参数:
        code: 主题BK代码（如"BK0715"）
        start_date: 开始日期（YYYY-MM-DD）
        end_date: 结束日期（YYYY-MM-DD）
    
    返回:
        标准化OHLCV DataFrame
    """
    try:
        df = self.ak.stock_board_concept_hist_em(
            symbol=code,
            period="daily",
            start_date=self._compact_date(start_date),
            end_date=self._compact_date(end_date),
            adjust="qfq",
        )
        return self._normalize_board_daily(df)
    except Exception as e:
        self._log(f"Failed to fetch theme daily for {code}: {e}")
        return pd.DataFrame()
```

#### 新增方法3: _normalize_board_daily()

```python
def _normalize_board_daily(self, df: pd.DataFrame) -> pd.DataFrame:
    """标准化板块/主题日K线数据。
    
    注意：EM板块API返回的列顺序与股票API不同：
    股票API: 开盘, 最高, 最低, 收盘
    板块API: 开盘, 收盘, 最高, 最低
    """
    if df is None or df.empty:
        return pd.DataFrame()
    
    # 列名映射（板块API格式）
    column_map = {
        "日期": "date",
        "开盘": "open",
        "收盘": "close",
        "最高": "high",
        "最低": "low",
        "成交量": "volume",
        "成交额": "amount",
        "振幅": "amplitude",
        "涨跌幅": "pct_change",
        "涨跌额": "change",
        "换手率": "turnover",
    }
    
    df = df.rename(columns=column_map)
    
    # 选择需要的列
    required_cols = ["date", "open", "high", "low", "close", "volume"]
    available_cols = [c for c in required_cols if c in df.columns]
    df = df[available_cols].copy()
    
    # 转换日期
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
    
    # 转换数值列
    for col in ["open", "high", "low", "close", "volume"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    
    # 移除空值
    df = df.dropna(subset=["close"])
    
    # 移除重复日期
    if "date" in df.columns:
        df = df.drop_duplicates(subset=["date"], keep="last")
        df = df.sort_values("date").reset_index(drop=True)
    
    return df
```

#### 新增方法4: _compact_date()

```python
def _compact_date(self, date_str: str) -> str:
    """将YYYY-MM-DD转换为YYYYMMDD格式。"""
    return date_str.replace("-", "")
```

### 3.3 修改v2/data_layer/fetcher.py

#### 新增方法: update_sector_theme_daily()

```python
def update_sector_theme_daily(self, target_date: str | None = None) -> dict:
    """获取板块和主题的日K线数据。
    
    参数:
        target_date: 目标日期（YYYY-MM-DD），默认今天
    
    返回:
        {"sectors_ok": int, "sectors_fail": int, "themes_ok": int, "themes_fail": int}
    """
    if target_date is None:
        target_date = datetime.now().strftime("%Y-%m-%d")
    
    # 读取关系数据获取BK代码
    relations = self._load_relations()
    if not relations:
        self._log("No relations data found, skipping sector/theme daily update")
        return {"sectors_ok": 0, "sectors_fail": 0, "themes_ok": 0, "themes_fail": 0}
    
    sector_codes = [s["code"] for s in relations.get("sectors", [])]
    theme_codes = [t["code"] for t in relations.get("themes", [])]
    
    # 计算日期范围（回溯1年）
    start_date = (datetime.strptime(target_date, "%Y-%m-%d") - timedelta(days=365)).strftime("%Y-%m-%d")
    
    sectors_ok = 0
    sectors_fail = 0
    themes_ok = 0
    themes_fail = 0
    
    # 获取板块数据
    for code in sector_codes:
        try:
            df = self.provider.fetch_sector_daily(code, start_date, target_date)
            if df is not None and not df.empty:
                self._save_parquet("sector", code, df)
                sectors_ok += 1
            else:
                sectors_fail += 1
            time.sleep(0.3)  # 限速
        except Exception as e:
            self._log(f"Failed to fetch sector {code}: {e}")
            sectors_fail += 1
    
    # 获取主题数据
    for code in theme_codes:
        try:
            df = self.provider.fetch_theme_daily(code, start_date, target_date)
            if df is not None and not df.empty:
                self._save_parquet("theme", code, df)
                themes_ok += 1
            else:
                themes_fail += 1
            time.sleep(0.3)  # 限速
        except Exception as e:
            self._log(f"Failed to fetch theme {code}: {e}")
            themes_fail += 1
    
    return {
        "sectors_ok": sectors_ok,
        "sectors_fail": sectors_fail,
        "themes_ok": themes_ok,
        "themes_fail": themes_fail,
    }
```

### 3.4 修改v2/data_layer/__init__.py

#### 新增方法: update_sector_theme_daily()

```python
def update_sector_theme_daily(self, target_date: str | None = None) -> dict:
    """获取板块和主题的日K线数据。"""
    return self.fetcher.update_sector_theme_daily(target_date)
```

### 3.5 修改v2/pipeline/runner.py

#### 在数据健康检查后添加板块/主题数据获取

```python
def _run_data_health(self, target_date: str | None) -> StageResult:
    # 现有逻辑...
    
    # 新增：如果板块/主题数据不足，尝试获取
    if not health.get("allowed", {}).get("sector_confirmation", True):
        self._log("Sector data incomplete, attempting to fetch...")
        try:
            result = self.data_layer.update_sector_theme_daily(target_date)
            self._log(f"Sector/theme fetch result: {result}")
            # 重新检查健康状态
            health = self.data_layer.check_market_health(target_date)
        except Exception as e:
            self._log(f"Failed to fetch sector/theme data: {e}")
    
    # 继续现有逻辑...
```

### 3.6 验证方式

1. 运行`python3 -c "from v2.data_layer import DataLayer; dl = DataLayer(); print(dl.update_sector_theme_daily('2026-07-10'))"`
2. 检查`v2/data/sector/`和`v2/data/theme/`目录是否有parquet文件
3. 运行pipeline验证板块/主题数据正常

---

## 四、修复3: 生命周期检查配置（30分钟）

### 4.1 修改v2/data_layer/config.py

```python
import os as _os

# 现有COMPLETENESS定义...

# 允许环境变量覆盖
for _key in list(COMPLETENESS.keys()):
    _env = _os.environ.get(f"TFS_{_key.upper()}")
    if _env is not None:
        try:
            COMPLETENESS[_key] = int(_env)
        except ValueError:
            pass

# 跳过健康检查标志
SKIP_HEALTH_CHECK = _os.environ.get("TFS_SKIP_HEALTH", "0") == "1"
```

### 4.2 修改v2/data_layer/lifecycle.py

```python
class LifecycleManager:
    def __init__(self, data_dir=None, skip: bool = False):
        self.data_dir = Path(data_dir or DATA_DIR)
        self.store = MarketDataStore(self.data_dir)
        self.skip = skip
    
    def check_market_health(self, date=None):
        if self.skip:
            return {
                "date": date,
                "status": "complete",
                "checks": {},
                "allowed": {
                    "stock_recommendation": True,
                    "etf_recommendation": True,
                    "sector_confirmation": True,
                    "theme_confirmation": True,
                },
                "issues": [],
            }
        # 现有逻辑...
```

### 4.3 修改v2/data_layer/__init__.py

```python
class DataLayer:
    def __init__(self, data_dir=None, fetcher=None, skip_health: bool = False):
        # 现有逻辑...
        self.lifecycle = LifecycleManager(self.data_dir, skip=skip_health)
```

### 4.4 修改v2/pipeline/cli.py

```python
# 在add_arguments函数中添加：
daily.add_argument("--skip-health", action="store_true", default=False,
                   help="Skip data health check (for development/testing)")
```

### 4.5 修改v2/pipeline/runner.py

```python
class PipelineRunner:
    def __init__(self, ..., skip_health_check: bool | None = None):
        # 现有逻辑...
        self.skip_health_check = skip_health_check
    
    def _run_data_health(self, target_date: str | None) -> StageResult:
        if self.skip_health_check:
            return StageResult(
                name="data_health",
                status=StageStatus.SUCCESS,
                started_at=datetime.now(),
                finished_at=datetime.now(),
                inputs={"target_date": target_date},
                outputs={"skipped": True},
            )
        # 现有逻辑...
```

### 4.6 验证方式

1. 运行`TFS_SKIP_HEALTH=1 python3 -m v2.run daily --date 2026-07-10`
2. 确认pipeline跳过健康检查并继续运行

---

## 五、执行顺序

```
Step 1: 修改v2/serve.py（修复1）
    ↓
Step 2: 修改v2/data_layer/config.py（修复3）
    ↓
Step 3: 修改v2/data_layer/lifecycle.py（修复3）
    ↓
Step 4: 修改v2/data_layer/__init__.py（修复2+3）
    ↓
Step 5: 修改v2/data_layer/providers/akshare_em.py（修复2）
    ↓
Step 6: 修改v2/data_layer/fetcher.py（修复2）
    ↓
Step 7: 修改v2/pipeline/cli.py（修复3）
    ↓
Step 8: 修改v2/pipeline/runner.py（修复2+3）
    ↓
Step 9: 运行测试验证
    ↓
Step 10: 运行pipeline验证
```

---

## 六、文件改动清单

| 文件 | 改动类型 | 预计行数 |
|------|---------|---------|
| `v2/serve.py` | 重写 | ~50 |
| `v2/data_layer/config.py` | 新增环境变量支持 | ~15 |
| `v2/data_layer/lifecycle.py` | 新增skip参数 | ~20 |
| `v2/data_layer/__init__.py` | 新增方法+参数 | ~15 |
| `v2/data_layer/providers/akshare_em.py` | 新增4个方法 | ~120 |
| `v2/data_layer/fetcher.py` | 新增1个方法 | ~60 |
| `v2/pipeline/cli.py` | 新增CLI参数 | ~10 |
| `v2/pipeline/runner.py` | 新增skip逻辑 | ~20 |

**预计总改动**: ~310行

---

## 七、风险评估

| 风险 | 概率 | 缓解措施 |
|------|------|---------|
| Eastmoney API变更 | 中 | 添加异常处理，失败时跳过 |
| 板块/主题数量过多导致超时 | 低 | 限速0.3s，分批获取 |
| AkShare版本不兼容 | 中 | 检查已安装版本，必要时升级 |
| 环境变量配置错误 | 低 | 添加验证和默认值 |

---

## 八、成功标准

- [ ] serve.py能正确服务v2输出目录
- [ ] 板块/主题数据fetcher能正常工作
- [ ] v2/data/sector/和v2/data/theme/有parquet文件
- [ ] pipeline能完整运行（含板块/主题数据）
- [ ] 浏览器能打开dashboard页面
- [ ] 所有现有测试通过

---

*本计划最后更新：2026-07-12*
