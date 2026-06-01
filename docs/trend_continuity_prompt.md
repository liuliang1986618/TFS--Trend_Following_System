# 趋势连续性功能 — 新会话启动

## 项目背景
趋势跟随交易系统，代码在 `/Users/liuliang19/Desktop/project/trend_following_system`。
已有功能：每日快照Dashboard（10天历史），90板块+800个股的状态机分析。

## 核心需求：趋势连续性可视化

当前每个日期的Dashboard是独立的快照，无法看出趋势的演变过程。需要实现：

### 功能1：板块/个股的趋势轨迹
- 选中任意板块或个股，展示过去5-10天的状态变化轨迹
- 例如：白酒 5/18状态2 → 5/20状态3 → 5/22状态4 → 5/25状态5 → 5/29状态1
- 可视化：时间轴 + 状态颜色条 + 三条件变化（结构/量能/持续性）

### 功能2：今日视角下的历史对比
- 在今天的板块卡片中，显示"过去5天状态变化"小条
- 一眼看出这个板块是在加速上涨（2→3→4）还是衰退（4→3→1）
- 龙头个股同样显示状态轨迹

### 功能3：趋势强度变化
- 每个板块得分的历史曲线（迷你sparkline）
- 上涨板块总数的变化趋势（市场宽度演变）

## 已有数据
- 10个交易日完整快照：`dashboard/trend_dashboard_{date}.html`
- 每日快照JSON：`dashboard/data/trend_snapshot_{date}.json`（板块状态+得分）
- 完整分析数据：`dashboard/data/dashboard_data.json`
- 每个日期的板块状态存于 `daily_states` 变量中（回测脚本里有）

## 设计约束
1. 必须在现有Dashboard页面内实现，不能另起页面
2. 用前端JS实现——从多个JSON文件加载历史数据
3. 性能要好，不能一次加载10天全量数据（太慢）
4. 交互自然：点击板块卡片上的"趋势轨迹"按钮，弹出一个轻量面板

## 现有架构速查
- Dashboard: `scripts/build_final.py` 生成，`dashboard/index.html`
- 状态机: `src/engine/state_machine.py`（6状态+三条件）
- 数据管道: `scripts/daily_run.py` → `pull_all_data.py` → `generate_all_data.py` → `build_final.py`
- 每日快照JSON格式见 `dashboard/data/dashboard_data.json`

## 要求
1. 先快速探索现有代码和数据，确认设计可行性
2. 设计小步迭代：先做板块轨迹 → 再做个股 → 再做趋势强度
3. 所有实现必须通过测试和审查
4. 最终效果：用户能在Dashboard上直观看到任意标的的趋势演变
