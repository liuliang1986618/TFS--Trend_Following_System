# 趋势交易系统 — 完整实现

## 项目背景

我是一个趋势交易者。唯一准则是跟随趋势操作。每一个功能、每一个实现
都必须服务于"多赚钱或少亏钱"。本项目目标是构建一个完整的 A 股趋势
跟踪决策系统。

## 第一步：阅读设计文档

在写任何代码前，请完整阅读以下文件：
- `docs/2026-05-31-trend-detection-design.md` — 唯一规格来源
- `docs/trend_state_machine.html`（浏览器打开）
- `docs/trend_state_machine.mmd`（VSCode Mermaid 预览）

## 技术栈

- Python 3.10+
- 数据获取：akshare（首选）→ baostock（备选）→ 本地缓存（兜底）
- 计算：numpy, pandas
- 测试：pytest（覆盖率目标 80%+）
- Dashboard：单文件 HTML + JSON 数据源，无后端
- 日志：Python logging，模块级 logger，INFO 为默认级别

## 工程约束

1. 当前项目已有骨架（`src/`、`tests/`、`docs/`），在现有结构上增量实现
2. 遵循「先固化设计 → 参数用经验值 → 后续回测迭代」路线
3. 代码模块化，每个模块单一职责、可独立测试
4. 每个模块的每个判断逻辑，必须能回答「这个能帮我多赚钱还是少亏钱？」
5. 每 Phase 完成后，使用 trend-review agent 做准则合规审查

## 数据降级策略（全局约定）

1. 优先 akshare → 失败降级 baostock → 仍失败用本地缓存
2. 缓存超过 1 天标记为 stale，日志 WARNING
3. 两个数据源均失败且无缓存 → 该标的跳过，不阻塞整体流程
4. 跳过率超过 20% → 终止并报错，建议人工介入

## 审查 Agent 约定

- `trend-review` agent：每 Phase 完成后审查，检查标准为设计文档的决策准则
- 自动检查规则：数据完整性校验、状态机状态转换合法性校验（pytest 覆盖）
- 审查输出：Pass / Warn / Fail 三级，Fail 阻断进入下一 Phase

## 实现范围

### Phase 1: 数据层 ← 当前先做这个
- 板块指数批量日K获取（含 BK 代码映射）
- 板块成分股映射关系
- 题材指数数据获取（含 GN 代码）
- 个股/ETF 日K数据获取
- 本地日线数据库增量更新
- **验收标准：**
  - `fetch_all` 命令 30s 内返回完整板块列表（沪深两市主要板块全覆盖）
  - 增量更新不重复拉取已有数据
  - pytest 覆盖：数据源切换逻辑、增量更新去重、BK/GN 代码映射完整性

### Phase 2: 趋势引擎
- 三条件判断器（结构A + 量能B + 持续性C）
- 6状态状态机（状态1-5 + 状态3'）→ 严格按设计文档状态转移图
- 趋势阶段分类器（前/中/后期）
- 前高/前低识别算法（局部极值检测，窗口参数取经验值，注释标记 TODO 回测优化）
- MA20 初筛过滤器
- 关键操作点识别器
- **验收标准：**
  - 状态机所有合法转移路径有 pytest 参数化测试
  - 非法转移路径被明确拒绝（抛异常或日志 ERROR）
  - 状态转移逻辑与设计文档流程图 100% 一致（逐条对照审查）

### Phase 3: 漏斗筛选
- 四层漏斗：板块趋势 → 题材趋势 → 个股趋势（ETF 并行直筛）
- 龙头识别：题材内涨幅 + 成交额排名（参数经验值，标记 TODO）
- 双路交叉验证 + 置信度计算
- **验收标准：**
  - 输入：某日全市场数据 → 输出：筛选结果列表 + 每层过滤原因
  - 龙头识别有可复现的排序逻辑
  - 置信度 0-100 分，计算因子可追溯

### Phase 4: 分析与推演
- 趋势变化对比（vs 昨日/3日前/上周）
- 明日推演引擎（状态机驱动的场景推演，输出概率加权情景）
- 板块 β 强度计算
- 市场宽度指标
- **验收标准：**
  - 推演引擎至少覆盖 3 种情景（乐观/中性/悲观），每种有触发条件
  - 趋势对比支持任意两个日期之间的 diff

### Phase 5: 展示层
- 每日 JSON 快照 → `data/snapshots/YYYY-MM-DD.json`
- HTML Dashboard 单文件（`dashboard/index.html`）
  - 日期导航、概览面板
  - 板块/题材/个股/ETF 详情面板（含展开行的「为什么」解释）
  - 趋势对比、关键操作点、明日推演
  - 持仓管理（`dashboard/positions.json` 手动维护）
  - 观察列表、外部落地页链接
- **验收标准：**
  - 浏览器打开 index.html 即可使用，无后端依赖
  - 展开行显示 3W：What（当前状态）、Why（判断依据）、What Next（操作建议）
  - 切換日期 < 1 秒

### Phase 6: CLI & 自动化
- `python -m src.cli run` — 一次完整分析 → 产出 JSON 快照
- `python -m src.cli dashboard` — 启动本地文件服务打开 Dashboard
- `python -m src.cli status` — 文本概要（持仓 + 今日操作点）
- `python -m src.cli run --date 2026-01-15` — 回测模式
  - 回测数据路径：`data/backtest/`，不污染实盘缓存
  - 回测报告：`data/backtest/reports/{date}.json`，记录每步决策和结果
- **验收标准：**
  - 4 条命令均可独立运行
  - 回测模式不修改任何实盘数据文件

## 工作流（每 Phase）

1. Write Plan — 使用 superpowers-zh:write-plan 生成该 Phase 的详细实现计划
2. TDD — 使用 superpowers-zh:test-driven-development，先写失败测试再实现
3. Implement — 实现代码，保持 commit 原子化
4. Code Review — 使用 code-reviewer agent 做代码审查
5. Criteria Review — 使用 trend-review agent，逐条对照设计文档的决策准则
6. Self Test — pytest + 手动验证该 Phase 的验收标准
7. Show & Confirm — 展示完成情况，确认后进入下一 Phase

## 每 Phase 完成后的自检清单

- [ ] pytest 全部通过（含新增和已有）
- [ ] 对照设计文档逐条核实，无遗漏
- [ ] trend-review agent 审查结果为 Pass
- [ ] 每个判断逻辑有「赚钱/少亏钱」注释说明
- [ ] 日志输出可追溯关键决策路径

## 不要做

- ❌ 不要实现设计文档之外的交易策略变体
- ❌ 不要引入设计文档未指定的新数据源
- ❌ 不要优化性能直到功能先跑通（先正确，后快速）
- ❌ 不要跳过 TDD 和审查直接写实现
- ❌ 不要在没有回测验证的情况下调整参数经验值

## 核心原则（每次实现前自问）

「这个设计/实现，能帮我赚更多钱，还是能帮我少亏钱？」
如果两者都不满足，则不做。
