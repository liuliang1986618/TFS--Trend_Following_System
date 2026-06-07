# 增强「今日操作建议」面板 — 设计规格说明

> 日期：2026-06-07
> 状态：待审查

---

## 1. 目标

将「今日操作建议」面板从当前简陋的四列表格（标的、操作、仓位、原因），
升级为**多场景推演预测卡片**，让用户一眼看懂：
- 这只标的现在处于什么趋势？趋势形成了多久？趋势健康吗？
- 明天大概率怎么走？涨跌平的概率各多少？
- 在什么价位买最划算？什么价位卖最合适？
- 出现什么信号该动手？什么信号该等等？
- 如果连续出现某种情况，该怎么办？

---

## 2. 核心设计原则（不可违反）

### 2.1 趋势为纲 — 基于全量趋势数据判定（CRITICAL）

> **所有推演结论、操作建议、买卖区间、条件矩阵，必须基于标的已形成的完整趋势数据，
> 而非单一交易日或最近两三天的数据。**

具体含义：
- 概率推演：基于「上升趋势中缩量回调」这一完整趋势形态的回测统计，而非仅基于今天涨跌
- 条件矩阵：每个触发条件都是**趋势阶段 + 价格位置 + 成交量 + 动量 + 形态**的多维共振，
  且需**至少 3 个信号同时满足**才触发操作建议
- 买卖区间：结合布林带(60天)+MA20/MA60+近期高低点+历史回测，而非仅看今天价格
- 趋势背景：卡片顶部必须展示趋势已运行天数、趋势强度、当前处于趋势的什么阶段

同样的涨跌，在不同趋势阶段含义完全相反：
| 趋势阶段 | 今天跌了→怎么办？ | 今天涨了→怎么办？ |
|---------|-----------------|-----------------|
| 上升趋势 | 回调是加仓机会 | 顺势持有或加仓 |
| 震荡趋势 | 观望等待方向 | 观望等待方向 |
| 下跌趋势 | 继续回避或减仓 | 反弹是减仓机会 |

### 2.2 格式固定 — v4 卡片为唯一标准（CRITICAL）

> **每只标的的推演卡片，必须严格按照 v4 定稿的 6 个 Widget 顺序和结构渲染，
> 不得随意增减、调序、或改变每个 Widget 的内部布局。**

v4 定稿卡片结构（6 个 Widget，严格按此顺序）：
```
┌─────────────────────────────────────────────┐
│ 卡片头部：标的名 + 代码 + 建议操作徽章          │
├─────────────────────────────────────────────┤
│ Widget 0: 📈 趋势大背景判断                   │
│   趋势方向 + 运行天数 + 今日定位 + 策略总纲       │
├─────────────────────────────────────────────┤
│ Widget 1: 📊 明日行情推演                     │
│   概率分布条（绿/黄/红）+ 回测样本量 + 依据      │
├─────────────────────────────────────────────┤
│ Widget 2: 🎯 明日最佳买卖区间                  │
│   价格轴可视化 + 加仓区 + 减仓区 + 逻辑说明      │
├─────────────────────────────────────────────┤
│ Widget 3: ⚡ 盯盘指南                         │
│   5个场景(A→E)，每场景≥3个多维信号+逻辑+历史胜率  │
├─────────────────────────────────────────────┤
│ Widget 4: 📐 关键价位                         │
│   支撑/阻力/止损/止盈/昨收                     │
├─────────────────────────────────────────────┤
│ Widget 5: 🔁 连续操作预案                     │
│   连续N天触发+条件+操作+逻辑                   │
└─────────────────────────────────────────────┘
```

变更规则：
- 想**关闭**某个 Widget → 在配置中将 `enabled` 设为 `false`，其余 Widget 保持原有顺序
- 想**新增** Widget → 在配置中添加一行，指定 `order` 决定插入位置，写渲染函数
- 想**替换** Widget → 关闭旧的 + 新增新的
- **不允许**随意改变 Widget 渲染顺序或内部 HTML 结构，除非有明确的设计变更讨论

### 2.3 页面隔离

只允许修改「今日操作建议」这一个板块的内容和样式。页面上其他任何板块
（概览、特别关注、全市场扫描、龙头列表、侧边栏等）保持原样，一像素都不许动。

### 2.4 策略不动

系统的回测策略、状态机判定、融合层逻辑、趋势跟随核心算法一律不修改。
本次只做「展示增强」，不做「策略优化」。

### 2.5 数据独立

面板需要的新计算数据，必须新建一个独立的 Python 模块 (`src/enhanced_actions.py`)
来产出，单独存储为 `dashboard/data/enhanced_actions_{date}.json`。
不修改任何已有文件的数据结构和计算逻辑。新模块只读取已有产出，在此基础上做增强计算。

### 2.6 大白话呈现

所有文本内容必须用零基础股民能看懂的大白话。严禁出现：
- 状态码（状态1/2/3/4/5）
- 英文变量名（MACD 可以出现但要解释「MACD金叉=短期均线上穿长期均线，买入信号」）
- 内部术语（TFS、BB、RSI 等缩写必须翻译为「布林带」「强弱指标」并加解释）

---

## 3. 架构设计

### 3.1 数据流

```
pipeline.py (不动)
  ├── MarketScanner.scan_etfs()  → ETF 评分
  ├── MarketScanner.scan_stocks() → 个股评分
  └── save_actions()  → actions_{date}.json ✅

🆕 src/enhanced_actions.py (新文件)
  ├── 读取 actions_{date}.json
  ├── 读取 历史 actions_*.json (回测统计)
  ├── 读取 Scanner 技术指标原始数据
  ├── 为每只标的计算推演卡片全部字段
  └── 输出 enhanced_actions_{date}.json ✅

🆕 dashboard/data/enhanced_actions_config.json (新文件)
  └── 定义卡片显示哪些 Widget、顺序、开关

🔧 scripts/build_final.py (只改 build_action_panel 函数)
  ├── 读取 enhanced_actions_{date}.json
  ├── 读取 enhanced_actions_config.json
  └── 逐 Widget 渲染 → HTML ✅
```

### 3.2 文件清单

| 文件 | 类型 | 作用 |
|------|------|------|
| `src/enhanced_actions.py` | 🆕 新模块 | 独立计算推演数据 |
| `dashboard/data/enhanced_actions_{date}.json` | 🆕 数据文件 | 每日推演卡片数据 |
| `dashboard/data/enhanced_actions_config.json` | 🆕 配置文件 | Widget 开关/顺序/参数 |
| `scripts/build_final.py` | 🔧 修改 | 只改 `build_action_panel()` |

### 3.3 不动的文件（零改动）

`pipeline.py` · `src/fusion/scanner.py` · `src/engine/state_machine.py` ·
`src/fusion/orchestrator.py` · `src/display/snapshot.py` · `src/analysis/scenario.py` ·
`backtest/*` · `dashboard/index.html`

---

## 4. 配置驱动 Widget 系统

### 4.1 配置文件格式

```json
{
  "max_etf_cards": 5,
  "max_stock_cards": 5,

  "etf_widgets": [
    {
      "id": "trend_context",
      "label": "趋势大背景判断",
      "order": 0,
      "enabled": true
    },
    {
      "id": "probability_bar",
      "label": "明日行情推演",
      "order": 1,
      "enabled": true,
      "params": { "show_sample_count": true }
    },
    {
      "id": "buy_sell_zone",
      "label": "最佳买卖区间",
      "order": 2,
      "enabled": true
    },
    {
      "id": "condition_matrix",
      "label": "盯盘指南",
      "order": 3,
      "enabled": true,
      "params": { "max_scenarios": 5, "min_signals": 3 }
    },
    {
      "id": "key_levels",
      "label": "关键价位",
      "order": 4,
      "enabled": true
    },
    {
      "id": "consecutive_plan",
      "label": "连续操作预案",
      "order": 5,
      "enabled": true
    },
    {
      "id": "risk_warning",
      "label": "风险提示",
      "order": 6,
      "enabled": false
    },
    {
      "id": "volume_signal",
      "label": "成交量信号",
      "order": 7,
      "enabled": false
    }
  ],

  "stock_widgets": [ /* 同上结构，可独立配置 */ ],

  "market_regime": {
    "stop_loss_etf": 3,
    "stop_loss_stock": 8,
    "max_position": 80
  }
}
```

### 4.2 扩展方式

新增一个信息块只需 3 步，不影响已有代码：

1. 在配置中加一行 JSON
2. 写一个渲染函数（~10 行 Python，返回 HTML 字符串）
3. 在 WIDGET_RENDERERS 字典中注册

关闭一个块 → `"enabled": false`，其余块自动上移。
调整顺序 → 改 `"order"` 数字。

### 4.3 Widget 渲染流程

```
build_action_panel(date_str, actions):
  1. 加载 enhanced_actions_{date}.json → card_data
  2. 加载 enhanced_actions_config.json → config
  3. 渲染面板头部（市场环境、止损线）
  4. 对每只 ETF / 个股:
     a. 渲染卡片头部（标的名+代码+建议操作徽章）
     b. 按 order 排序的 enabled widgets
     c. 逐 widget 调用 WIDGET_RENDERERS[id](card_data, widget_params)
     d. 拼接为完整卡片 HTML
  5. 包裹面板容器 → 返回完整 HTML
```

---

## 5. Widget 详细设计

### 5.1 Widget 0: 趋势大背景判断 (trend_context)

**位置：** 卡片最顶部（order=0），所有其他 Widget 的「纲」

**固定内容结构：**
- 趋势方向图标 + 趋势方向描述（如「📈 处于上升趋势，今天是正常回调」）
- 趋势数据段落（均线排列状态、今日涨跌、成交量特征、趋势累计涨幅、当前所处阶段）
- 策略总纲条（彩色左边框，一句话给出操作方向）

**⚠️ 趋势为纲约束：**
所有表述基于全量趋势数据。如「均线多头排列保持完好」基于60天数据，
「不是趋势反转」基于多周期分析，「处于休整阶段」基于趋势阶段判定。

**数据来源（全量趋势数据）：**
- `state`（TFS 状态，映射为大白话标签）
- `ma_deviation`（偏离MA20的幅度）
- `ret_20d`（近20日收益）
- `ma_bullish`、`ma_mid_bullish`（均线多头排列状态）
- 趋势持续时间（从近期高低点推算）
- `pct_5d`、`pct_20d`（多周期涨跌幅）

### 5.2 Widget 1: 明日行情推演 (probability_bar)

**固定内容结构：**
- Widget 标题：「📊 明日行情推演」
- 回测样本描述（如「基于 18,432 次相似走势（上升趋势中缩量回调）的回测统计」）
- 概率分布条：绿色=上涨/回升 | 黄色=震荡/继续 | 红色=下跌/反转
- 每种行情的简要说明段落

**⚠️ 趋势为纲约束：**
概率不是基于今天一天算的，而是基于**完整趋势形态**的回测统计。
样本描述必须是具体的趋势形态，而非单日涨跌。

**数据来源：**
- 回测统计：扫描所有历史数据中相似趋势形态的后续走势分布
- 相似形态定义：趋势方向相同 + 价格位置相似 + 成交量特征相似 + 动量状态相似

### 5.3 Widget 2: 最佳买卖区间 (buy_sell_zone)

**固定内容结构：**
- Widget 标题：「🎯 明日最佳买卖区间」
- 价格标尺（止损 ← 昨收 → 止盈）
- 可视化价格轴（渐变色彩条，标注加仓区和减仓区）
- 左栏：买入区间 + 具体价格 + 买入逻辑
- 右栏：卖出区间 + 具体价格 + 卖出逻辑
- 底部数据来源说明

**⚠️ 趋势为纲约束：**
买卖区间不是固定数值，而是**趋势阶段 + 技术指标 + 历史统计**的综合产物。
- 上升趋势：买入区 = 回调支撑位（布林下轨+MA20），卖出区 = 前期高点+布林上轨
- 下跌趋势：买入区 = 不适用（不建议买入），卖出区 = 反弹压力位
- 震荡趋势：买入区 = 区间下沿，卖出区 = 区间上沿

**数据来源（全量趋势数据）：**
- 布林带上下轨（基于60天数据）
- MA20/MA60（基于60天数据）
- 近期高低点（基于20-60天数据）
- 成交量加权均价 VWAP
- 历史回测：相似趋势中在这些价位操作的胜率

### 5.4 Widget 3: 盯盘指南 (condition_matrix)

**⚠️ 这是最重要的 Widget，体现「趋势为纲」的核心思想。**

**固定内容结构：**
- Widget 标题：「⚡ 明天盯盘指南 — 多维信号共振判定」
- 5 个操作场景（加仓A、加仓B、不动C、减仓D、清仓E）
- 每个场景卡片包含：操作标签 + 目标仓位 + 触发类型说明 + 信号列表 + 逻辑解释

**固定场景模板：**

| 场景 | 操作 | 仓位 | 信号数量 | 性质 |
|------|------|------|---------|------|
| A | 加仓 | 15% | ≥3 | 最佳买点（回调支撑+动量衰竭） |
| B | 加仓 | 12% | ≥3 | 回调结束确认（安全性更高） |
| C | 不动 | 维持 | — | 方向不明，等待信号 |
| D | 减仓 | 3% | ≥3 | 关键支撑破位，风险控制 |
| E | 清仓 | 0% | ≥3 | 长期趋势破坏，保本第一 |

每个信号必须包含：✅/❌ 标记 + 大白话描述 + 技术原理标注

**⚠️ 趋势为纲约束（CRITICAL）：**

信号不能是简单的「明天涨3%」「明天跌5%」。每个信号必须是多维度共振：

- ❌ 错误示例：「放量涨超3%」→ 这只是明天一天的数据
- ✅ 正确示例：「价格回踩到MA20附近（基于过去60天均线计算），
  成交量缩到20日均量一半以下（与过去20天对比，说明抛压衰竭），
  MACD绿柱开始缩短（动量改善），
  出现长下影线（今日K线形态显示多头反击）」
  → 4个信号同时满足 = 「在上升趋势中，缩量回调到关键支撑且抛压衰竭 = 回调结束的经典信号，历史5日盈利概率68%」

### 5.5 Widget 4: 关键价位 (key_levels)

**固定内容结构：**
- Widget 标题：「📐 关键价位」
- 水平排列的价格标签：支撑位 + 阻力位 + 止损位 + 止盈位 + 昨收价
- 每个标签注明来源（MA20/MA60/布林上轨/布林下轨/前期高点等）

### 5.6 Widget 5: 连续操作预案 (consecutive_plan)

**固定内容结构：**
- Widget 标题：「🔁 连续操作预案」
- 3 条阶梯式预案，每条包含：连续天数 + 触发条件 + 操作动作 + 逻辑解释
- 按风险从低到高排列（加仓→减仓→清仓）

**固定模板：**
- 连续N天站稳关键均线 + 量能配合 → 加仓
- 连续N天跌破中期均线 → 减仓
- 连续N天跌破长期均线 → 清仓

---

## 6. 数据模块: enhanced_actions.py

### 6.1 核心类

```python
class EnhancedActionGenerator:
    """独立推演数据生成器 — 读取已有产出，增强计算。

    核心原则（趋势为纲）：
      所有推演基于完整趋势数据判定，而非单日信号。
      每个输出字段的数据来源必须覆盖 ≥20 个交易日。
    """

    def __init__(self, data_dir: str = "dashboard/data"):
        ...

    def generate(self, date_str: str) -> dict:
        """为指定日期生成增强操作建议。

        返回格式：
        {
          "date": "2026-06-05",
          "market_regime": "strong_bear",
          "etf_cards": [ { card_data }, ... ],
          "stock_cards": [ { card_data }, ... ]
        }
        """
        ...

    def _calc_trend_context(self, code, daily_data, state) -> dict:
        """计算趋势大背景（基于全量趋势数据）。"""
        ...

    def _calc_probability(self, code, daily_data, trend_context) -> dict:
        """计算明日行情概率分布（基于相似趋势形态回测）。"""
        ...

    def _calc_buy_sell_zone(self, code, daily_data, trend_context) -> dict:
        """计算最佳买卖区间（趋势阶段+技术指标+历史统计）。"""
        ...

    def _calc_scenarios(self, code, daily_data, trend_context) -> list:
        """生成5个操作场景（多维信号共振，每场景≥3信号）。"""
        ...

    def _calc_key_levels(self, code, daily_data) -> dict:
        """计算关键价位。"""
        ...

    def _calc_consecutive_plan(self, code, daily_data, trend_context, state) -> list:
        """生成连续操作预案。"""
        ...
```

### 6.2 单张卡片数据结构

```json
{
  "code": "515030",
  "name": "新能车ETF",
  "link": "https://fund.eastmoney.com/515030.html",
  "action": "加仓",
  "position_pct": 12,
  "score": 3.3,

  "trend_context": {
    "direction": "上升趋势",
    "direction_emoji": "📈",
    "days_running": 48,
    "total_return_pct": 18.3,
    "ma_status": "多头排列（短期均线在上，长期均线在下，典型的上升趋势）",
    "today_position": "正常回调",
    "today_narrative": "今天虽然跌了0.74%，但这是上升趋势中的正常回调。均线多头排列保持完好，成交量萎缩说明抛压不大，不是趋势反转信号。",
    "strategy_summary": "上升趋势中的回调 = 加仓机会。等回调企稳信号出现就动手。"
  },

  "probability": {
    "sample_count": 18432,
    "sample_desc": "上升趋势中缩量回调到MA20附近的相似走势",
    "scenarios": [
      {"label": "止跌回升", "pct": 55, "range": "涨2%~5%", "detail": "上升趋势中回调结束后的反弹力度通常较强"},
      {"label": "继续回调", "pct": 30, "range": "跌不破MA20(0.830)", "detail": "缩量回调是健康的回调方式"},
      {"label": "趋势反转", "pct": 15, "range": "需放量跌破MA60确认", "detail": "目前没有反转信号，概率很低"}
    ]
  },

  "buy_sell_zone": {
    "buy_zone": {"low": 0.865, "high": 0.885, "logic": "布林下轨+MA20双重支撑，上升趋势中回调至此买入历史胜率68%"},
    "sell_zone": {"low": 0.990, "high": 1.015, "logic": "前期高点压力位+布林上轨，反弹至此可分批止盈等回调"},
    "stop_loss": 0.790,
    "take_profit": 1.025,
    "last_close": 0.950
  },

  "scenarios": [
    {
      "action": "加仓", "position": 15, "level": "A",
      "min_signals": 3,
      "signals": [
        {"text": "价格回踩到0.865~0.885（MA20+布林下轨双重支撑）", "type": "price"},
        {"text": "成交量缩到20日均量一半以下（抛压衰竭，没人愿意卖了）", "type": "volume"},
        {"text": "MACD绿柱开始缩短（下跌动能减弱）", "type": "momentum"},
        {"text": "出现长下影线或小阳线（多头开始反击）", "type": "pattern"}
      ],
      "logic": "上升趋势中缩量回踩支撑+动量衰竭=回调结束经典信号",
      "history_win_rate": 68
    }
  ],

  "key_levels": [
    {"label": "支撑位", "price": 0.830, "source": "MA20均线"},
    {"label": "阻力位", "price": 1.015, "source": "前期高点"},
    {"label": "止损位", "price": 0.790, "source": "MA60均线"},
    {"label": "止盈位", "price": 1.025, "source": "布林上轨"},
    {"label": "昨收", "price": 0.950, "source": ""}
  ],

  "consecutive_plan": [
    {"days": 3, "condition": "站稳MA20且成交量逐步放大", "action": "每次加仓3%", "logic": "回调结束确认，趋势恢复"},
    {"days": 2, "condition": "收盘低于MA20", "action": "减半仓观望", "logic": "趋势可能转弱"},
    {"days": 3, "condition": "收盘低于MA60", "action": "全部清仓", "logic": "上升趋势大概率结束"}
  ]
}
```

---

## 7. 验收标准

- [ ] 页面其他部分完全不变，diff 确认只有「今日操作建议」板块被修改
- [ ] 现有策略文件（`pipeline.py`, `scanner.py`, `state_machine.py`, `orchestrator.py` 等）零改动
- [ ] 新数据模块 `enhanced_actions.py` 独立运行，独立输出 JSON
- [ ] v4 定稿的 6 个 Widget 严格按固定顺序和结构渲染，每个 Widget 内部布局与设计一致
- [ ] 所有推演结论基于全量趋势数据（≥20 交易日），而非单日信号
- [ ] 条件矩阵每个场景至少 3 个多维共振信号，含逻辑解释和历史胜率
- [ ] 所有术语都是大白话，零基础股民能看懂
- [ ] ETF 和个股各展示 5 只标的
- [ ] 配置文件驱动，新增/关闭/排序 Widget 只需改 JSON
- [ ] 生成一天数据，浏览器中面板正常渲染

---

## 8. 非目标（不做的事）

- 不修改回测策略、状态机、融合层任何逻辑
- 不改变页面其他板块
- 不修改 `pipeline.py` 流程
- 不新增依赖包（仅使用 numpy, pandas 等已有依赖）
- 不改变现有数据文件格式
- 不随意改变 v4 定稿的 Widget 顺序和内部结构
