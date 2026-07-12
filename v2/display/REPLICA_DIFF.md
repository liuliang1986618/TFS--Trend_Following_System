# 0622_full 一比一复刻 — 区块差异清单

> 阶段 64 输出。基线:`v2/0622_full.png`(1440x16944,index.html 入口完整截图,含 240 sidebar + 1200 iframe)。
> v2 当前样本:`v2/data/derived/display_runs/weekly_2026-06-22_2026-06-26/`(2026-06-22 daily + 5 日 weekly index)。
> 颜色取色:用 PIL 抽样参考图关键像素。

---

## A. 参考图整体结构(8 region,从上到下)

| # | y 范围(全图) | iframe y 范围 | region 名称 | 边框强调色 | 布局 |
|---|---|---|---|---|---|
| 0 | 0-50 | 0-50 | header(全图):侧栏标题 + 右上"弱势"红徽 | 红 | 侧栏 240 / iframe 1200 |
| 1 | 80-2700 | 80-2700 | 强势板块深度穿透·漏斗精选(2x3 = 6 板块) | 橙 #f59e0b | 2 列 |
| 2 | 2750-8000 | 2750-8000 | 稳健推荐·趋势初期·全量直扫(2 列) | 绿 #4ade80 | 左 ETF 6 / 右 个股 6,各 6 段 widget |
| 3 | 8000-9100 | 8000-9100 | 强势追踪·拐强过热·等回调再进(2 列) | 橙红 | 左 ETF 5 / 右 个股 6,各 6 段 widget |
| 4 | 9200-10500 | 9200-10500 | 焦点板块·全量直扫(2x2+1 = 5 板块 SectorFocusCard) | 蓝 | 2 列 + 1 独占 |
| 5 | 10500-12000 | 10500-12000 | 观察区(反弹中接近突破)(2x2+1 = 5 板块 SectorFocusCard) | 粉/红 | 2 列 + 1 独占 |
| 6 | 12100-16000 | 12100-16000 | 趋势个股·全量直扫 表格(148 行) | 紫 | 宽表 + 搜索框 |
| 7 | 16050-16700 | 16050-16700 | ETF 直筛 表格(20 行) | 金 | 宽表 |
| 8 | 16750-16944 | 16750-16944 | 底部模块:推演准确率面板 + 反思闭环仪表 + footer | — | 单行 |

> **侧栏(sidebar 240):** 顶部 50px 标题区"趋势跟随交易系统"(青色文字),y=50-16944 全黑,**没有任何日期导航项**。参考图 sidebar 是空骨架。

---

## B. v2 当前输出结构(对照样本 weekly_2026-06-22_2026-06-26)

| v2 region | v2 实际渲染 | 关键问题 |
|---|---|---|
| shell | 280 sidebar + 1fr iframe(min-height 100vh) | sidebar **280 ≠ 240**,shell 无 max-width,iframe 宽度非 1200 |
| sidebar header | `<h1>趋势跟随</h1>`(单行) | 标题样式差异;**没有副标题"{n} 个交易日"** |
| sidebar list | 5 个 `date_nav_card` button(已实现 3 行) | 参考图 sidebar 是空的,v2 多出 5 项;**这意味着 v2 已超过参考图,需要决定保留/移除** |
| iframe daily | `<main class="daily-dashboard">` + 6 region | iframe 实际内容**只有 6 region,而参考图 8 region**;且每张 card body 显示 `{'label': ...}` 字典 repr |
| overview region | 2 张 metric_card(市场状态 + 候选数量) | **参考图没有 overview region**;iframe 顶部直接是漏斗 |
| action_panel region | 40 张 action_card 横向流 | **每张只显示"持有"两字**,6 段 widget 完全没有展开(plan 67) |
| signal_groups region | 20 张 signal_card | v2 的 signal_groups 在参考图中不存在(signal 信息已并入 ActionCard 6 段) |
| funnel/sector_focus/observation | v2 有 funnel_deep_dive_card / sector_focus_card / observation_card 模板 | **模板存在但渲染没输出这些 region**(实际 daily 区域只有 overview/action_panel/signal_groups/tables/evaluation 6 个) |
| tables | stock_table_card / etf_table_card | 有实现但格式简陋(待看 daily 完整渲染确认) |
| evaluation | 评估 metric 卡片 | 渲染但视觉差异大 |

**关键问题(plan 67 对应):**v2 当前 `action_card.html` 模板只有 15 行,渲染时只输出"持有"等短文本,**完全没有 6 段 widget**(趋势大背景/今日定位/策略总纲/明日推演/买卖区间/关键价位/盯盘场景/仓位管理)。

---

## C. ActionCard 6 段 widget 字段清单(参考图,与 plan 67.1 一致)

| 段号 | widget 标题 | 字段 |
|---|---|---|
| 0 | header 评分 | 股票/ETF 名 · 代码 · 评分 125.0 · 状态徽标(持续上涨·拿筹别动) |
| 1 | 简评 | 一行 markdown 文本(底部用 ~D 标识来源 + ~半导体 等题材) |
| 2 | 趋势大背景 + 上升趋势 | 标题(已运行 N 天 · 累计+XX.X%) + 均线状态多行 + 今日定位 chip + 策略总纲多行 |
| 3 | 明日行情推演 | 标题(基于 N 次相似走势回测统计) + 3 段概率按钮(止跌回升 X% / 继续回调 Y% / 趋势反转 Z%) + 每段说明 |
| 4 | 明日最佳买卖实区间 + 关键价位 | 2 列(左买入区间 + 卖出区间,右支撑位/阻力位/止损位) |
| 5 | 昨天灯盘指南 — 5 场景多维信号共振 | 5 个子段(A 加仓/B 加仓/C 不动/D 减仓/E 清),每段含概率、信号含义、胜率、MACD/KDJ 状态说明 |
| 6 | 仓位管理 | 3 条规则(连续 3 天量价突破 20 日均线 → 每次回调加仓 3%-5% / 连续 2 天 → 减一半仓位,观望 / 连续 3 天量价放量过大 → 全部清仓,保护本金) |

> v2 模板 `action_card.html` 当前仅 15 行,不包含任何上述字段。需要重写。

---

## D. SectorFocusCard 字段清单(参考图)

| 字段 | 位置 | 备注 |
|---|---|---|
| 板块名 + 代码 (电子化学品 881172) | 标题 | 文字 + 圆形色点(state 颜色) |
| 标签徽标(持续上涨·拿筹别动 / 趋势转好,突破买入·可以买了 / 下跌中的反弹) | 标题右侧 | 5 段 5d 状态条 + 5 分评分 |
| 板块状态行(阴跌 / 持续整理 / 1阴天继续整理 77%) | 状态区 | 文字+数字 |
| 关键标志行(1次5日均值上穿 / 突破上涨 32%) | 标志区 | 文字+百分比 |
| A 结构(1更更高+1更高低)/ B 量能(健康)/ C 持续性 | 三行 | ✅/❌ + 文字描述 |
| MA20+20日/10日/5日 + 正负 + 5d 走势均值 | 数据行 | 数字 + sparkline |
| 龙头个股(近20日涨幅排名)表 | 表格 | 5 行,列:个股 / 涨幅 / 入选原因 |
| 相关 ETF 表(部分卡) | 表格 | 2-3 行,列:ETF / 状态 / 代码 |

---

## E. 三个桶差异分类

### 桶 ① 视觉比例(轻量,改 CSS tokens + 模板栅格)

| 编号 | 差异 | 改造成本 | 涉及文件 |
|---|---|---|---|
| V1 | shell 总宽 1440(参考图) vs v2 无 max-width | 轻量 | display.css `.display-shell` |
| V2 | sidebar 240(参考图) vs 280(v2) | 轻量 | display.css `.display-sidebar` width |
| V3 | iframe 宽度 1200(参考图) vs 1fr(v2,实际 ~1640) | 轻量 | display.css `.display-shell` grid-template-columns |
| V4 | ActionCard 内 6 段 widget 内部栅格(2 列买卖区 / 2 列概率条) | 轻量 | action_card.html + display.css |
| V5 | SectorFocusCard 三段式分区(标题/数据/龙头表)高度比例 350-400px | 中量 | focus_sector_card.html + display.css |
| V6 | 趋势个股表 + ETF 直筛表 表格列宽比例(sticky header) | 中量 | stock_table_card.html / etf_table_card.html + display.css |
| V7 | 区域间距(20px vs v2 当前可能 16px) | 轻量 | display.css `--region-gap` |
| V8 | 卡内 4px 强调线(left border)在漏斗/稳健/强势三色 | 轻量 | display.css 各 region header |

### 桶 ② 内容缺失(中/重量,改 builder + 模板,部分需 Evaluation 产出)

| 编号 | 缺失内容 | 改造成本 | 涉及文件 |
|---|---|---|---|
| M1 | **ActionCard 6 段 widget 全部未渲染**(显示"持有") | 重量 | action_card.html + renderer + builder(pay attention to plan 67) |
| M2 | ActionCard 5 场景多维信号共振(盯盘场景 chip) | 重量 | action_card.html + Evaluation 输出 |
| M3 | ActionCard 仓位管理(3 条规则) | 重量 | action_card.html + Evaluation 输出 |
| M4 | ActionCard 明日最佳买卖实区间 + 关键价位(2 列) | 中量 | action_card.html + Evaluation 区间字段 |
| M5 | ActionCard 明日行情推演概率按钮(止跌/回调/反转 3 段) | 中量 | action_card.html + ProjectionValidation |
| M6 | SectorFocusCard 5d 状态条(5 色点) + 5 分评分 | 中量 | focus_sector_card.html + builder 派生 |
| M7 | SectorFocusCard sparkline(5d 折线) | 中量 | focus_sector_card.html + 新增 svg/canvas |
| M8 | SectorFocusCard 龙头个股表(5 行) | 中量 | focus_sector_card.html + relation provider |
| M9 | 漏斗区(2x3 板块 6 张)整体未在 v2 daily 渲染输出 | 重量 | funnel.html partial + renderer 接入 |
| M10 | "稳健推荐"和"强势追踪"两组 ActionCard 标题/分组的 sub-region 划分 | 中量 | builder 增加 group by state_family/strategy_track |
| M11 | 趋势个股表格(state∈{3,4,5})148 行 + 5d 圆点列 | 中量 | stock_table_card.html + builder(已有 stock_table_card 模板,但需确认渲染) |
| M12 | ETF 直筛 表格 20 行 + MA20 偏离/20日涨幅列 | 中量 | etf_table_card.html + builder |
| M13 | 观察区(反弹中接近突破)state==2 单独成区 | 中量 | observation_card.html + builder group by state |
| M14 | 底部模块:推演准确率面板 + 反思闭环仪表 + footer | 中量 | templates 底部新增 partial + Evaluation 产出 |
| M15 | 顶部"弱势"红徽标(state 文本) | 轻量 | index.html header 区域新增徽标 |
| M16 | 漏斗区 2x3 = 6 板块(state≥3) | 重量 | funnel_deep_dive_card.html + 新建 funnel 区域渲染 |

### 桶 ③ 色阶与质感(轻量,改 CSS tokens)

| 编号 | 差异 | 改造成本 | 涉及文件 |
|---|---|---|---|
| C1 | 漏斗区边框 #f59e0b(amber-500)与背景渐变 | 轻量 | display.css `--color-funnel-border` |
| C2 | 稳健推荐区边框 #4ade80(green) | 轻量 | display.css `--color-steady-border` |
| C3 | 强势追踪区边框橙红 | 轻量 | display.css `--color-strong-border` |
| C4 | 焦点板块边框蓝 | 轻量 | display.css `--color-focus-border` |
| C5 | 观察区边框粉/红 | 轻量 | display.css `--color-observe-border` |
| C6 | 趋势个股表头深紫 + ETF 直筛表头金/橙 | 轻量 | display.css `--color-table-header` |
| C7 | 标题前缀 emoji(🔥 ⚡ 🎯 👀 📋 🪙 📌 🍀) | 轻量 | 各 partial 模板 |
| C8 | 5d 状态条 5 色映射(5/5=绿,4/5=黄,3/5=橙,2/5=红,1/5=灰) | 轻量 | display.css `.dot-5d` |
| C9 | 板块卡圆形色点(state 颜色映射) | 轻量 | display.css `.sector-state-dot` |
| C10 | 概率按钮 3 色(止跌回升绿 / 继续回调黄 / 趋势反转红) | 轻量 | display.css `.prob-pill` |
| C11 | 评分块 125.0 右上角 + 边框 | 轻量 | display.css `.score-pill` |
| C12 | 顶部右侧"弱势"红徽标 + 红边框圆角 | 轻量 | display.css `.market-state-badge` |

---

## F. 改造成本汇总(按 plan 64.4 标注)

| 类别 | 数量 | 备注 |
|---|---|---|
| 轻量(CSS tokens) | 12(C1-C12) | 仅改 display.css |
| 轻量(模板微调) | 4(V4/V5/V7/V8,M15) | 改 templates/cards/*.html |
| 中量(renderer 调整) | 6(M4/M5/M6/M7/M8/M10/M11/M12/M13/M14) | 改 builder.py 派生 + renderer 输出 |
| 重量(新增 card 类型或重写) | 5(M1/M2/M3/M9/M16) | 6 段 widget 全部要重写 action_card.html;漏斗区 2x3 板块要新建 funnel 区域 |

**总评估:** M1(6 段 widget 全部) 和 M9(漏斗 2x3 板块) 是两个最大缺口,其他差异在视觉比例桶 ① 和色阶桶 ③ 都是轻量 CSS 调整。

---

## G. 结论(阶段 64)

1. 参考图与 v2 当前输出**信息架构差异大**:
   - 参考图:8 region(漏斗/2 组 ActionCard/2 组 SectorFocus/2 表/底部)
   - v2 当前:6 region(overview/action_panel/signal_groups/tables/evaluation/...)| 但 plan 71.4 说 6 region,可能 v2 当前数对得上,但内容缺失
2. **最大差异是 ActionCard 6 段 widget 完全没有展开**(plan 67 的全部 5 个子项),这是 17.76% 像素差异的核心来源。
3. 侧栏差异是**反向差异**:v2 已经实现 DateNavCard 3 行(plan 70.1 完成),参考图 sidebar 反而是空的(可能是参考图截屏时间早于 v2 DateNavCard 实现)。
4. 色阶/比例差异是轻量 CSS 调整,改造成本最低;可与 ActionCard 6 段 widget 同步推进。
5. 建议下一阶段(65)先做 CSS tokens(V1-V3 + C1-C12),(66)做概览(已部分存在,只需新增右上"弱势"徽标),(67)做 ActionCard 6 段 widget 重写(最重)。

---

## H. 阶段 64 完成标志

- [x] 64.1: 8 region 切片 + 区块名/卡片类型/字段/配色/布局比例
- [x] 64.2: v2 当前输出与参考图逐区块对比
- [x] 64.3: 差异分类到 3 桶(视觉比例/内容缺失/色阶质感)
- [x] 64.4: 产出本文档 `v2/display/REPLICA_DIFF.md`

> **下一步候选:**
> - 阶段 65:视觉比例与栅格收敛(V1-V8)
> - 阶段 66:顶部概览区精修(M15 + overview 微调)
> - 阶段 67:ActionCard 6 段 widget 重写(M1-M5,**最重**)
