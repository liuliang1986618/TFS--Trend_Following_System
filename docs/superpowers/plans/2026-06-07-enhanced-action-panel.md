# 增强「今日操作建议」面板 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers-zh:subagent-driven-development（推荐）或 superpowers-zh:executing-plans 逐任务实现此计划。

**目标：** 将「今日操作建议」面板从简陋四列表格升级为 6-Widget 推演预测卡片

**架构：** 新建 `src/enhanced_actions.py` 独立数据模块 + `enhanced_actions_config.json` 配置 + 修改 `build_final.py` 的 `build_action_panel()`

**技术栈：** Python 3 + numpy + pandas + HTML/CSS（内联样式）

**设计规格：** `docs/superpowers/specs/2026-06-07-enhanced-action-panel-design.md`

---

## 文件结构

| 文件 | 操作 | 职责 |
|------|------|------|
| `dashboard/data/enhanced_actions_config.json` | 🆕 创建 | Widget 开关/顺序/参数 |
| `src/enhanced_actions.py` | 🆕 创建 | 独立推演数据生成模块 |
| `scripts/build_final.py` | 🔧 修改 (仅 build_action_panel) | 卡片 HTML 渲染 |
| `tests/test_enhanced_actions.py` | 🆕 创建 | 数据模块单元测试 |

---

### 任务 1：创建 Widget 配置文件

**文件：** 创建 `dashboard/data/enhanced_actions_config.json`

```
{"max_etf_cards":5,"max_stock_cards":5,"etf_widgets":[{"id":"trend_context","label":"📈 趋势大背景判断","order":0,"enabled":true},{"id":"probability_bar","label":"📊 明日行情推演","order":1,"enabled":true,"params":{"show_sample_count":true}},{"id":"buy_sell_zone","label":"🎯 明日最佳买卖区间","order":2,"enabled":true},{"id":"condition_matrix","label":"⚡ 明天盯盘指南","order":3,"enabled":true,"params":{"max_scenarios":5,"min_signals":3}},{"id":"key_levels","label":"📐 关键价位","order":4,"enabled":true},{"id":"consecutive_plan","label":"🔁 连续操作预案","order":5,"enabled":true},{"id":"risk_warning","label":"⚠️ 风险提示","order":6,"enabled":false},{"id":"volume_signal","label":"📈 成交量信号","order":7,"enabled":false}],"stock_widgets":[{"id":"trend_context","label":"📈 趋势大背景判断","order":0,"enabled":true},{"id":"probability_bar","label":"📊 明日行情推演","order":1,"enabled":true,"params":{"show_sample_count":true}},{"id":"buy_sell_zone","label":"🎯 明日最佳买卖区间","order":2,"enabled":true},{"id":"condition_matrix","label":"⚡ 明天盯盘指南","order":3,"enabled":true,"params":{"max_scenarios":5,"min_signals":3}},{"id":"key_levels","label":"📐 关键价位","order":4,"enabled":true},{"id":"consecutive_plan","label":"🔁 连续操作预案","order":5,"enabled":true},{"id":"risk_warning","label":"⚠️ 风险提示","order":6,"enabled":false},{"id":"volume_signal","label":"📈 成交量信号","order":7,"enabled":false}],"market_regime":{"stop_loss_etf":3,"stop_loss_stock":8,"max_position":80}}
```

验证：`python3 -c "import json; json.load(open('dashboard/data/enhanced_actions_config.json')); print('OK')"`

---

### 任务 2：创建 enhanced_actions.py — 趋势背景计算

**文件：** 创建 `src/enhanced_actions.py` + `tests/test_enhanced_actions.py`

核心实现 `EnhancedActionGenerator` 类：

1. `_calc_trend_context(close, state, volume)` — 基于≥60天全量数据：
   - 趋势方向（上升/下跌/震荡）+ emoji + 运行天数 + 累计涨跌幅 + 所处阶段
   - 均线排列大白话描述
   - 今日涨跌在趋势中的含义（8种场景覆盖：上升趋势中缩量回调/放量回调/顺势上涨/横盘，下跌趋势中缩量反弹/放量反弹/延续下跌/横盘，震荡中方向不明）
   - 策略总纲（对应8种场景的操作方向）

2. `trend_direction_text(state, ma_bullish, ma_mid_bullish, ret_20d, close)` — 趋势方向大白话映射
3. `_count_trend_days(close, direction)` — 从MA20/MA60交叉点推算趋势运行天数

**测试覆盖：** 上升/下跌/震荡各方向判定，趋势回调=加仓机会，反弹=减仓机会

---

### 任务 3：概率条 + 买卖区间 + 关键价位 + 连续预案

**文件：** 修改 `src/enhanced_actions.py`

1. `_calc_probability(close, ctx, state)` — 3种行情概率分布：
   - 基于趋势方向+价格位置(BB位置)+动量(RSI)综合分配概率
   - 每种行情：标签、百分比、预估涨跌幅、大白话解释
   - 概率之和≈100%

2. `_calc_buy_sell_zone(close, state)` — 买卖区间：
   - 买入区 = min(布林下轨, MA20) × 0.98 ~ (布林下轨+MA20)/2
   - 卖出区 = (布林上轨+20日高点)/2 ~ max(布林上轨, 20日高点) × 1.02
   - 止损 = MA60 × 0.97，止盈 = 布林上轨 × 1.05

3. `_calc_key_levels(close)` — 5个关键价位（支撑/阻力/止损/止盈/昨收）
4. `_calc_consecutive_plan(close, state)` — 3条阶梯预案（3天/2天/3天）

**测试覆盖：** 概率之和≈100%，上升趋势止跌回升概率最高，买卖区间含必需字段

---

### 任务 4：条件矩阵 — 5场景多维共振

**文件：** 修改 `src/enhanced_actions.py`

`_calc_scenarios(close, ctx, volume, state)` — 三类趋势各一套定制场景：

**上升趋势场景：**
- A: 加仓→15% 回踩MA20+量缩一半+MACD绿柱缩短+长下影 = 回调结束信号 (胜率68%)
- B: 加仓→12% 站上5日线+量放大1.2倍+MACD金叉 = 回调结束确认 (胜率62%)
- C: 不动→8% 方向不明，等待
- D: 减仓→3% 跌破MA20+放量+MA5死叉MA10 = 趋势可能转弱 (胜率55%)
- E: 清仓→0% 跌破MA60+MA20死叉MA60+回撤超15% = 趋势破坏 (胜率72%)

**下跌趋势场景：** A:减仓反弹 B/C:不动观望 D/E:清仓（加速下跌/阴跌不止）

**震荡趋势场景：** A:区间下沿买入 B/C:不动 D:跌破下沿减仓 E:转下跌清仓

每个信号必须是大白话，严禁状态码/变量名，至少3个信号才触发。

**测试覆盖：** 5个场景输出，每场景≥3个信号(除C外)，所有信号大白话无状态码

---

### 任务 5：generate() 主方法 + pkl 数据加载

**文件：** 修改 `src/enhanced_actions.py`

1. `generate(date_str)` — 主方法：
   - 读取 `actions_{date}.json`
   - 对每只ETF/个股调用 `_build_card()` 组装6个Widget
   - 输出 `enhanced_actions_{date}.json`
   
2. `_build_card(r, date_str, is_etf)` — 单只标的完整卡片组装

3. `_load_price_data(code, is_etf)` — 从 `data/etf_stocks/` 或 `data/massive_stocks/` 加载pkl

**测试覆盖：** 集成测试（模拟 actions JSON + pkl 数据），每张卡片含6个Widget

---

### 任务 6：修改 build_final.py — build_action_panel 升级

**文件：** 修改 `scripts/build_final.py`（仅 `build_action_panel` 函数及新增辅助函数）

核心变更：
1. `build_action_panel()` — 读取 `enhanced_actions_{date}.json` + config，按Widget系统渲染
2. `load_enhanced_actions()` / `load_enhanced_config()` — 数据加载
3. 6个Widget渲染函数：`_render_trend_context/_probability_bar/_buy_sell_zone/_condition_matrix/_key_levels/_consecutive_plan`
4. 2个备用渲染函数（暂返回空）：`_render_risk_warning/_render_volume_signal`
5. `_render_card()` — 卡片组装（头部+Widget遍历）
6. `_build_legacy_action_panel()` — 降级方案（enhanced数据不可用时回退旧版表格）
7. `_color_to_rgba()` — 工具函数

**关键约束：**
- 仅修改 build_action_panel 函数及其辅助函数（原行295-389）
- build_watchlist_panel 及之后的所有函数一字不动
- 页面其他板块对应的代码零改动

---

### 任务 7：端到端验证

1. `pytest tests/test_enhanced_actions.py -v` — 全部PASS
2. `python3 -c "from src.enhanced_actions import EnhancedActionGenerator; gen.generate('2026-06-05')"` — 成功产出JSON
3. `python3 scripts/build_final.py 2026-06-05` — 成功生成HTML
4. `grep -c "趋势大背景\|盯盘指南\|连续预案" dashboard/trend_dashboard_2026-06-05.html` — 每种≥5次
5. `open dashboard/trend_dashboard_2026-06-05.html` — 浏览器目视检查
6. 确认 pipeline.py, scanner.py, state_machine.py, orchestrator.py 零改动

---

## 完成检查清单

- [ ] pytest 全部通过
- [ ] enhanced_actions.py 独立运行产出 valid JSON
- [ ] 现有策略文件零改动
- [ ] 所有Widget大白话，无状态码/变量名
- [ ] 条件矩阵每场景≥3信号
- [ ] 页面其他板块不变
- [ ] HTML卡片浏览器正常渲染
- [ ] 配置文件驱动，关闭/新增Widget只需改JSON
