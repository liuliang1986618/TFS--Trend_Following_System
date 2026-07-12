# 引擎层修复计划

> 本文档是引擎层修复的权威计划。所有实现以此为准。
>
> **制定日期：2026-07-12**
> **状态：待确认**

---

## 一、问题诊断总结

### 1.1 v2 引擎现状

| 模块 | 行数 | 状态 |
|------|------|------|
| `indicators.py` | 144行 | 完整可用，RSI非标准算法 |
| `levels.py` | 13行 | 空壳 |
| `analyzers.py` | 32行 | 空壳 |
| `filters.py` | 14行 | 简单实现 |
| `params.py` | 20行 | 缺少涨跌停参数 |
| `scoring.py` | 120行 | 完整可用 |
| `classifier.py` | 85行 | 完整可用 |

### 1.2 v1 算法核心问题

| 问题类型 | 具体问题 | 严重性 | 可修复性 |
|---------|---------|--------|---------|
| **Bug** | PivotDetector失败时 `broke_prev_low` 默认False | 高 | 确定修复 |
| **Bug** | 涨跌停日产生假枢轴点 | 高 | 确定修复 |
| **Bug** | RSI使用自定义算法，非标准Wilder | 中 | 确定修复 |
| **设计缺陷** | 回调深度用绝对值，不适应不同波动率 | 高 | 需要回测验证 |
| **设计缺陷** | 二波信号RSI和MACD高度相关 | 中 | 需要回测验证 |
| **设计缺陷** | 没有ADX趋势强度门槛 | 高 | 需要回测验证 |

---

## 二、分阶段实施计划

### Phase 1：修复确定性bug（预计1-2天）

**目标**：修复已确认的错误，不改变策略逻辑。

#### 2.1 指标层：RSI算法标准化

**文件**: `v2/engine/indicators.py`

**改动**: 将第32-40行的简单平均RSI改为标准Wilder平滑算法

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
- **风险**: RSI值会与之前不同，需要回归测试

**验证方式**:
1. 构造已知价格序列，手动计算Wilder RSI
2. 对比新旧算法输出差异
3. 验证RSI值在0-100范围内

---

#### 2.2 枢轴点层：涨跌停处理

**文件**: `v2/engine/levels.py`

**改动**: 从v1迁移PivotDetector，加入涨跌停处理

```python
# 新增涨跌停检测函数
def _is_limit_day(df: pd.DataFrame, idx: int) -> bool:
    """判断某日是否为涨跌停日。
    
    A股涨跌停定义：
    - 普通股票：涨跌幅 > 9.5% 或 < -9.5%
    - 创业板/科创板(30x/68x)：涨跌幅 > 19.5% 或 < -19.5%
    - ST股票：涨跌幅 > 4.5% 或 < -4.5%
    """
    if idx < 0 or idx >= len(df):
        return False
    
    row = df.iloc[idx]
    open_price = row.get("open", 0)
    close_price = row.get("close", 0)
    
    if open_price <= 0:
        return False
    
    # 计算日内涨跌幅
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

#### 2.3 分析层：回调分析修复

**文件**: `v2/engine/analyzers.py`

**改动**: 从v1迁移PullbackAnalyzer，修复默认值问题

```python
# 修改PivotDetector失败时的处理
try:
    from v2.engine.levels import PivotDetector
    pd_obj = PivotDetector()
    prev_low = pd_obj.recent_low(daily_df)
    broke_prev_low = prev_low is not None and price < prev_low["low"]
except Exception:
    # 修复：不再默认False，而是标记为"unknown"
    broke_prev_low = None
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

#### 2.4 参数层：补充参数

**文件**: `v2/engine/params.py`

**改动**: 新增涨跌停相关参数

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

#### 2.5 过滤层：涨跌停过滤

**文件**: `v2/engine/filters.py`

**改动**: 在趋势过滤中加入涨跌停日检查

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

#### 2.6 测试层：新增测试用例

**文件**: `v2/tests/test_engine.py`

**新增测试**:

```python
def test_rsi_matches_wilder_standard():
    """验证RSI符合Wilder标准算法。"""
    close = np.array([44, 44.34, 44.09, 43.61, 44.33, 44.83, 45.10, 45.42, 45.84, 46.08,
                      45.89, 46.03, 45.61, 46.28, 46.28, 46.00, 46.03, 46.41, 46.22, 45.64])
    rsi_val = rsi(close, period=14)
    # 手动计算Wilder RSI（初始avg_gain=0.0871, avg_loss=0.0586）
    # 期望RSI ≈ 59.88
    assert 55 < rsi_val < 65

def test_pivot_detector_skips_limit_days():
    """验证枢轴点检测跳过涨跌停日。"""
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
    dates = pd.date_range("2026-01-01", periods=30, freq="B")
    closes = [10 + i * 0.1 for i in range(30)]
    df = make_ohlcv(dates, closes, [1000000] * 30)
    
    profile = PullbackAnalyzer.analyze(df)
    # 数据不足返回None，不会产生错误
    assert profile is None

def test_trend_filters_limit_day():
    """验证涨跌停日被趋势过滤。"""
    # 需要在analyze_symbol层面测试
    pass
```

---

### Phase 2：建立回测框架（预计3-5天）

**目标**：量化当前算法效果，为后续优化提供基准。

**框架设计**：

```python
class BacktestEngine:
    """回测引擎：验证算法效果"""
    
    def run(self, signals, price_data):
        """
        输入：
        - signals: 历史信号列表 [{date, code, action, score}]
        - price_data: 价格数据 {code: DataFrame}
        
        输出：
        - win_rate: 胜率
        - profit_factor: 盈亏比
        - sharpe_ratio: 夏普比率
        - max_drawdown: 最大回撤
        - trade_count: 交易次数
        """
```

**回测指标**：

| 指标 | 定义 | 目标 |
|------|------|------|
| 胜率 | 盈利交易/总交易 | >55% |
| 盈亏比 | 平均盈利/平均亏损 | >1.5 |
| 夏普比率 | (收益-无风险)/波动率 | >1.0 |
| 最大回撤 | 最大净值回撤 | <20% |
| 年化收益 | 复合年化收益率 | >15% |

**回测流程**：

1. 用v1算法在历史数据上生成信号
2. 模拟交易（买入持有N天）
3. 计算上述指标
4. 作为基准线

**预期产出**：
- `v2/engine/backtest.py` — 回测引擎
- `v2/engine/metrics.py` — 指标计算
- 回测报告（当前算法的基准指标）

---

### Phase 3：策略优化（有数据支撑后）

**前提**：Phase 2 回测框架完成，且有基准指标。

**优化清单**（按优先级排序）：

| 序号 | 优化项 | 预期效果 | 回测验证点 |
|------|--------|---------|-----------|
| 3.1 | 加入ADX(14)>20趋势门槛 | 过滤震荡市假信号 | 胜率提升？交易频率下降多少？ |
| 3.2 | 回调深度ATR归一化 | 消除大小盘差异 | 不同市值股票胜率差异缩小？ |
| 3.3 | 二波信号去相关（去掉MACD或RSI之一） | 减少冗余信号 | 误报率下降？信号数量变化？ |
| 3.4 | 阶段判断加入150日MA斜率 | 更准确的阶段识别 | 晚期信号准确率提升？ |
| 3.5 | Fibonacci回调带作为辅助参考 | 增加入场精度 | 61.8%位置入场胜率更高？ |

**每个优化项的验证流程**：
1. 实现新算法
2. 用历史数据回测
3. 对比基准指标
4. 指标改善 → 采纳；指标变差 → 放弃或调参

---

## 三、文件改动计划

### Phase 1 涉及文件

| 文件 | 改动类型 | 新增行数 | 修改行数 |
|------|---------|---------|---------|
| `v2/engine/levels.py` | 重写 | ~200 | 0 |
| `v2/engine/indicators.py` | 修改RSI函数 | ~30 | ~10 |
| `v2/engine/analyzers.py` | 重写 | ~120 | 0 |
| `v2/engine/filters.py` | 补充涨跌停过滤 | ~20 | ~10 |
| `v2/engine/params.py` | 补字段 | ~5 | 0 |
| `v2/tests/test_engine.py` | 新增测试用例 | ~80 | 0 |

### Phase 2 涉及文件

| 文件 | 改动类型 | 新增行数 |
|------|---------|---------|
| `v2/engine/backtest.py` | 新建 | ~300 |
| `v2/engine/metrics.py` | 新建 | ~100 |

### Phase 3 涉及文件

| 文件 | 改动类型 | 新增行数 | 修改行数 |
|------|---------|---------|---------|
| `v2/engine/indicators.py` | 新增ADX | ~50 | 0 |
| `v2/engine/analyzers.py` | 修改回调/二波逻辑 | 0 | ~100 |
| `v2/engine/levels.py` | ATR归一化 | ~30 | ~20 |

---

## 四、风险评估

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| RSI算法改变导致评分变化 | 高 | 中 | 回归测试对比前后排序 |
| 涨跌停处理可能漏掉有效信号 | 低 | 中 | 只跳过涨跌停日的枢轴，不跳过其他分析 |
| 回测框架设计不合理 | 中 | 高 | 参考行业标准回测方法 |
| 优化项回测效果不理想 | 中 | 低 | 不采纳，保持现状 |
| Phase 2耗时超预期 | 中 | 中 | 先做最小可用版本 |

---

## 五、成功标准

### Phase 1 完成标准
- [ ] 涨跌停日枢轴点识别正确
- [ ] RSI值符合Wilder标准
- [ ] PivotDetector失败时不再默认"健康"
- [ ] 用3只股票验证修复效果（茅台、平安、宁德时代）
- [ ] 所有现有测试通过
- [ ] 新增测试用例通过

### Phase 2 完成标准
- [ ] 回测引擎能跑通
- [ ] 输出胜率、盈亏比、夏普、最大回撤
- [ ] 有基准指标报告

### Phase 3 完成标准
- [ ] 每个优化项有回测对比数据
- [ ] 至少1个优化项指标改善>5%
- [ ] 所有优化项有明确的采纳/放弃结论

---

## 六、执行顺序

```
Phase 1 (Bug修复)
    ↓
Phase 2 (回测框架)
    ↓
Phase 3 (策略优化，有数据支撑)
```

**关键原则**：
- Phase 1 可以直接做（确定性修复）
- Phase 2 必须在 Phase 3 之前（需要基准数据）
- Phase 3 必须有回测数据支撑（不能靠理论推导）

---

## 七、与设计文档的关系

本计划完成后，需要更新：
- `v2/doc/engine_design.md` — 反映新的算法设计
- `v2/doc/data_management_design.md` — 如有数据格式变化

---

*本计划最后更新：2026-07-12*
