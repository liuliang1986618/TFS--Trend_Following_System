# 趋势跟随交易系统

> 📖 **总览手册：** [系统手册.md](系统手册.md) — 规则、脚本、技能、触发词、构建序列、红线，一个文档全部看懂。

## ⚠️ 模型行为约束（最高优先级）

**在执行任何操作前，必须先执行 `/model-discipline-prime` 进行自我约束检查。**

五条铁律：禁止未经确认改代码 | 设计先行 | 验证后完成 | 用户优先 | skill门禁

## 项目规则

本项目规则存储在 `.claude/rules/` 目录，每个会话自动加载。详细触发条件和红线见 [系统手册.md](系统手册.md)。

- [侧边栏日期导航保护规则](.claude/rules/sidebar-date-nav-protection.md) — **CRITICAL**，任何改动后必须验证
- [标的筛选质量门禁](.claude/rules/stock-screening-quality-gate.md) — **CRITICAL**，任何进入面板的标的必须通过多维趋势审查
- [全量市场数据完整性](.claude/rules/full-market-data-integrity.md) — 必须基于全市场数据，禁止部分数据
- [数据真实性最高准则](.claude/rules/data-authenticity-prime-directive.md) — **最高优先级**，禁止假数据/人造数据/Parquet缓存
- [数据目录结构标准](.claude/rules/data-directory-standard.md) — 按日期组织6层数据，/dates/{date}/ 自包含快照
- [全量市场数据下载最高准则](.claude/rules/full-market-download-prime-directive.md) — **最高优先级**，禁止硬编码ETF列表/设置任何下载上限/臆想数量
- [展示层最高准则](.claude/rules/display-layer-prime-directive.md) — **最高优先级**，参考模板+数据替换，禁止重新生成HTML，禁止动build_final

## 关键架构

- `dashboard/index.html` — 侧边栏壳页面（iframe），由 `build_nav_index.py` 独占生成
- `dashboard/trend_dashboard_{date}.html` — 每日仪表板，由 `build_final.py` 生成
- `src/enhanced_actions.py` — 增强操作建议数据模块（6 Widget）
- `pipeline.py` — 主数据管道

## 入口页面

用户查看的是 `http://localhost:8765/index.html`（侧边栏壳 + iframe），不是 `trend_dashboard_*.html`。
