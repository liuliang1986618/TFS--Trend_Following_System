# Phase 1 详细实施计划

> **最后更新**: 2026-07-12
> **目标**: 修复确定性bug，不改变策略逻辑

---

## 一、改动总览

| 序号 | 文件 | 改动类型 | 新增行数 | 修改行数 |
|------|------|---------|---------|---------|
| 1.1 | `v2/engine/indicators.py` | 修改RSI函数 | ~40 | ~10 |
| 1.2 | `v2/engine/levels.py` | 重写PivotDetector | ~200 | 0 |
| 1.3 | `v2/engine/analyzers.py` | 重写PullbackAnalyzer | ~120 | 0 |
| 1.4 | `v2/engine/params.py` | 补充参数 | ~5 | 0 |
| 1.5 | `v2/engine/filters.py` | 补充涨跌停过滤 | ~20 | ~10 |
| 1.6 | `v2/tests/test_engine.py` | 新增测试用例 | ~80 | 0 |

**预计总改动**: ~465行

---

## 二、具体改动详解

### 2.1 指标层：RSI算法标准化 (indicators.py)

**当前问题**: RSI使用简单平均，非标准Wilder平滑算法。

**改动方案**:

```python
# 当前实现（第32-40行）
def rsi(close: np.ndarray, period: int = 14) -> float:
    if len(close) < period + 1:
        return 50.0
    delta = np.diff(close[-period - 1:].astype(float))
    gain = np.maximum(delta, 0).sum() / period
    loss = np.maximum(-delta, 0).sum() / period
    if loss == 0:
        return 100.0
    return float(100.0 - 100.0 / (1.0 + gain / loss))

# 改为标准Wilder RSI
def rsi(close: np.ndarray, period: int = 14) -> float:
    """标准Wilder RSI（平滑RSI）。
    
    行业标准：使用指数移动平均而非简单平均。
    初始值 = 前period日的简单平均，之后用Wilder平滑。
    """
    if len(close) < period + 1:
        return 50.0
    
    deltas = np.diff(close.astype(float))
    gains = np.maximum(deltas, 0)
    losses = np.maximum(-deltas, 0)
    
    # 初始平均（简单平均）
    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])
    
    # Wilder平滑（从第period+1个数据开始）
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    
    if avg_loss == 0:
        return 100.0
    
    rs = avg_gain / avg_loss
    return float(100.0 - 100.0 / (1.0 + rs))
```

**影响范围**:
- `calculate_indicators()` 中的 `result["rsi"]` 调用
- `scoring.py` 中可能间接使用RSI值
- **风险**: RSI值会与之前不同，需要回归测试

**验证方式**:
1. 构造已知价格序列，手动计算Wilder RSI
2. 对比新旧算法输出差异
3. 验证RSI值在0-100范围内

---

### 2.2 枢轴点层：涨跌停处理 (levels.py)

**当前问题**: 
1. v2的`levels.py`只有13行，是空壳
2. v1的`pivots.py`没有处理涨跌停日

**改动方案**: 从v1迁移PivotDetector，加入涨跌停处理

```python
# 新增涨跌停检测函数
def _is_limit_day(df: pd.DataFrame, idx: int) -> bool:
    """判断某日是否为涨跌停日。
    
    A股涨跌停定义：
    - 普通股票：涨跌幅 > 9.5% 或 < -9.5%
    - ST股票：涨跌幅 > 4.5% 或 < -4.5%
    - 科创板/创业板(30x/68x)：涨跌幅 > 19.5% 或 < -19.5%
    
    注意：实际涨跌停判断需要考虑前收盘价，这里简化处理。
    """
    if idx < 0 or idx >= len(df):
        return False
    
    row = df.iloc[idx]
    open_price = row.get("open", 0)
    close_price = row.get("close", 0)
    
    if open_price <= 0:
        return False
    
    # 计算日内涨跌幅（简化版，实际应比较前收盘）
    change_pct = abs(close_price - open_price) / open_price * 100
    
    # 根据股票代码判断板块
    code = str(row.get("code", ""))
    if code.startswith(("30", "68")):  # 创业板/科创板
        return change_pct > 19.5
    else:  # 主板
        return change_pct > 9.5

# 修改find_highs和find_lows，跳过涨跌停日
@staticmethod
def find_highs(daily_df: pd.DataFrame, window: int = 3) -> pd.DataFrame:
    """找出所有局部高点（跳过涨跌停日）。"""
    highs = daily_df["high"].values
    n = len(highs)
    pivot_indices = []
    
    for i in range(window, n - window):
        # 跳过涨跌停日
        if _is_limit_day(daily_df, i):
            continue
        
        left_max = np.max(highs[i - window:i])
        right_max = np.max(highs[i + 1:i + window + 1])
        if highs[i] > left_max and highs[i] > right_max:
            pivot_indices.append(i)
    
    return daily_df.iloc[pivot_indices].copy()
```

**影响范围**:
- `PullbackAnalyzer.analyze()` 中的 `PivotDetector.recent_low()` 调用
- `TrendConditions.check_structure()` 中的 `PivotDetector.get_last_n_highs/lows()` 调用
- **风险**: 低。涨跌停日产生的枢轴点本身就不应作为支撑/阻力

**验证方式**:
1. 构造包含涨跌停日的数据，验证枢轴点不包含这些日
2. 对比修复前后茅台/平安的枢轴点位置

---

### 2.3 分析层：回调分析修复 (analyzers.py)

**当前问题**: 
1. v2的`analyzers.py`只有32行，是空壳
2. v1的`pullback.py`中 `broke_prev_low` 默认False（当PivotDetector失败时）

**改动方案**: 从v1迁移PullbackAnalyzer，修复默认值问题

```python
# 修改PivotDetector失败时的处理
try:
    from v2.engine.levels import PivotDetector
    pd_obj = PivotDetector()
    prev_low = pd_obj.recent_low(daily_df)
    broke_prev_low = prev_low is not None and price < prev_low["low"]
except Exception:
    # 修复：不再默认False，而是标记为"unknown"
    broke_prev_low = None  # 或者用字符串"unknown"
    # 在is_healthy判断中，unknown视为不健康
    pass

# 修改is_healthy判断逻辑
is_healthy = (
    volume_pattern == "shrinking"
    and broke_prev_low is not False  # None或True都不健康
    and not touched_ma60
    and depth_pct > -10
)
```

**影响范围**:
- `analyze_trend_context()` 中的回调分析
- **风险**: 中。可能影响部分股票的回调健康判断

**验证方式**:
1. 构造PivotDetector失败的场景（如数据不足）
2. 验证`broke_prev_low`不再默认False
3. 对比修复前后回调健康判断

---

### 2.4 参数层：补充参数 (params.py)

**当前问题**: 缺少涨跌停阈值等参数

**改动方案**: 新增涨跌停相关参数

```python
@dataclass
class StrategyParams:
    # 现有参数...
    ma_periods: tuple[int, ...] = (5, 10, 20, 60, 120, 250)
    rsi_period: int = 14
    # ...
    
    # 新增参数
    limit_up_threshold: float = 9.5  # 普通股票涨跌停阈值（%）
    limit_up_threshold_gem: float = 19.5  # 创业板/科创板涨跌停阈值（%）
    limit_up_threshold_st: float = 4.5  # ST股票涨跌停阈值（%）
```

**影响范围**: 无。仅新增参数，不改变现有逻辑

---

### 2.5 过滤层：涨跌停过滤 (filters.py)

**当前问题**: 没有涨跌停日过滤

**改动方案**: 在趋势过滤中加入涨跌停日检查

```python
def apply_trend_filters(state, indicators: dict, daily_df=None) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    
    # 现有过滤...
    if state in (1, 2, "3'"):
        reasons.append("defensive_state")
    
    # 新增：检查当日是否为涨跌停日
    if daily_df is not None and len(daily_df) > 0:
        from v2.engine.levels import _is_limit_day
        if _is_limit_day(daily_df, len(daily_df) - 1):
            reasons.append("limit_up_down_day")
    
    return len(reasons) == 0, reasons
```

**影响范围**:
- `TrendEngine.analyze_symbol()` 中的过滤调用
- **风险**: 低。涨跌停日本身就不应产生信号

**验证方式**:
1. 构造涨跌停日数据，验证被过滤
2. 验证非涨跌停日不受影响

---

### 2.6 测试层：新增测试用例

**新增测试**:

```python
# test_engine.py 新增

def test_rsi_matches_wilder_standard():
    """验证RSI符合Wilder标准算法。"""
    # 构造已知价格序列
    close = np.array([44, 44.34, 44.09, 43.61, 44.33, 44.83, 45.10, 45.42, 45.84, 46.08,
                      45.89, 46.03, 45.61, 46.28, 46.28, 46.00, 46.03, 46.41, 46.22, 45.64])
    rsi_val = rsi(close, period=14)
    # 手动计算Wilder RSI（初始avg_gain=0.0871, avg_loss=0.0586）
    # 期望RSI ≈ 59.88
    assert 55 < rsi_val < 65  # 允许一定误差

def test_pivot_detector_skips_limit_days():
    """验证枢轴点检测跳过涨跌停日。"""
    # 构造包含涨跌停日的数据
    dates = pd.date_range("2026-01-01", periods=20, freq="B")
    # 第10日涨10%（涨停）
    closes = [10 + i * 0.1 for i in range(10)] + [20] + [20 - i * 0.1 for i in range(9)]
    opens = [10 + i * 0.1 for i in range(10)] + [18] + [20 - i * 0.1 for i in range(9)]
    
    df = make_ohlcv(dates, closes, [1000000] * 20, opens)
    highs = PivotDetector.find_highs(df, window=3)
    
    # 涨停日（第10日）不应成为枢轴点
    limit_day_idx = df.index[10]
    assert limit_day_idx not in highs.index

def test_pullback_unknown_pivot_is_unhealthy():
    """验证PivotDetector失败时回调标记为不健康。"""
    # 构造数据不足的场景（<60日）
    dates = pd.date_range("2026-01-01", periods=30, freq="B")
    closes = [10 + i * 0.1 for i in range(30)]
    df = make_ohlcv(dates, closes, [1000000] * 30)
    
    profile = PullbackAnalyzer.analyze(df)
    # 数据不足返回None，不会产生错误
    assert profile is None

def test_trend_filters_limit_day():
    """验证涨跌停日被趋势过滤。"""
    # 构造涨跌停日数据
    # 需要在analyze_symbol层面测试
    pass
```

---

## 三、执行顺序

```
Step 1: 修改indicators.py (RSI算法)
    ↓
Step 2: 修改params.py (新增参数)
    ↓
Step 3: 重写levels.py (PivotDetector + 涨跌停)
    ↓
Step 4: 重写analyzers.py (PullbackAnalyzer)
    ↓
Step 5: 修改filters.py (涨跌停过滤)
    ↓
Step 6: 新增测试用例
    ↓
Step 7: 运行测试验证
```

---

## 四、风险控制

| 风险 | 概率 | 缓解措施 |
|------|------|---------|
| RSI算法改变导致评分变化 | 高 | 回归测试对比前后排序 |
| 涨跌停处理可能漏掉有效信号 | 低 | 只跳过涨跌停日的枢轴，不跳过其他分析 |
| PivotDetector失败处理影响回调判断 | 中 | 新增unknown状态，明确标记 |

---

## 五、验证清单

- [ ] RSI值符合Wilder标准（初始值=前14日平均涨跌幅）
- [ ] 涨跌停日枢轴点识别正确
- [ ] PivotDetector失败时不再默认"健康"
- [ ] 用3只股票验证修复效果（茅台、平安、宁德时代）
- [ ] 所有现有测试通过
- [ ] 新增测试用例通过

---

*本计划最后更新：2026-07-12*
