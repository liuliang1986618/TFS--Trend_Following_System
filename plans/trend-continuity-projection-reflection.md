# Blueprint: 趋势连续性可视化 + 推演验证 + 反思闭环

**目标:** 为趋势跟踪系统增加趋势连续性可视化、明日推演面板、推演验证回测、反思闭环引擎四大功能。

**技术约束:** Python 3, 纯静态HTML Dashboard (file:// 打开), 不引入新依赖, 不修改状态机核心逻辑, 不修改Dashboard布局结构。

**数据规模:** 822天历史数据, 90板块, 每日快照JSON已就绪。

---

## 阶段依赖图

```
Phase A (趋势连续性可视化)
  └→ Phase B (明日推演面板) [依赖A的状态缓存]
      └→ Phase C (推演验证回测) [依赖B的推演引擎]
          └→ Phase D (反思闭环引擎) [依赖C的准确率数据]
```

所有阶段串行执行，每阶段内部包含: Plan → TDD → Implement → Verify → TrendReview。

---

## Phase A: 趋势连续性可视化 [Day 1-2]

### 目标
展示板块/个股过去5-10天的状态变化轨迹，看清趋势演变过程。

### 新增/修改文件

| 文件 | 操作 | 说明 |
|------|------|------|
| `src/display/history.py` | **新增** | HistoryTracker: 从822天快照中提取每个板块的状态历史 |
| `scripts/generate_history_cache.py` | **新增** | 预计算 `dashboard/data/history_states.json` |
| `dashboard/data/history_states.json` | **新增** | 预计算缓存输出 |
| `scripts/build_final.py` | **修改** | 板块卡片内嵌5天迷你状态条、sparkline; 日期导航30天+展开全部 |
| `tests/display/__init__.py` | **新增** | 测试包初始化 |
| `tests/display/test_history.py` | **新增** | HistoryTracker 单元测试 |

### A1. 板块卡片内嵌5天状态变化条
- 每个板块卡片顶部显示过去5天状态颜色条（宽2px×5格）
- 颜色映射: 1=灰, 2=灰, 3=蓝, 4=绿, 5=橙, 3'=红
- 趋势方向指示器: 箭头显示状态变化方向

### A2. 迷你sparkline得分曲线
- 板块卡片底部显示过去5天得分迷你折线（内联SVG实现）

### A3. 10天轨迹弹出面板
- 点击板块卡片弹出详情面板（CSS overlay）
- 时间轴展示: 日期、状态颜色块、状态标签、三条件变化(A/B/C)

### A4. 历史状态缓存生成
- `HistoryTracker` 类: 遍历快照JSON，提取状态历史
- 输出 `history_states.json`: `{sectors: {code: [{date, state, score, conditions}]}}`

### A5. 日期导航扩展
- 默认显示最近30天，每周一显示月份标签
- "查看更多"按钮展开全部822天历史

### 验收标准
- [ ] 板块卡片有5天状态变化条（6色正确）
- [ ] 点击弹出10天轨迹面板
- [ ] 迷你sparkline正确显示
- [ ] 历史状态缓存正确生成
- [ ] 日期导航支持30天 + 展开全部历史
- [ ] 87 tests全通过 + 新测试通过

---

## Phase B: 明日推演面板 [Day 2-3]

### 新增/修改文件

| 文件 | 操作 | 说明 |
|------|------|------|
| `src/analysis/scenario.py` | **修改** | generate() 支持外部 weights 参数 |
| `src/analysis/projection_weights.py` | **新增** | 权重管理类，JSON文件驱动 |
| `dashboard/data/projection_weights.json` | **新增** | 初始权重配置 |
| `scripts/build_final.py` | **修改** | Dashboard增加推演区域 |
| `tests/analysis/test_scenario.py` | **修改** | 增加 weights 参数测试 |

### B1. ScenarioEngine重构
- `generate(ts, weights=None)` 支持外部权重
- 当weights为None时使用默认等权分配（向后兼容）

### B2. Dashboard推演面板
- 焦点板块卡片下方增加"明日推演"折叠区
- A=绿色(高概率), B=黄色(中概率), C=红色(低概率)

### 验收标准
- [ ] ScenarioEngine.generate() 接受可选 weights 参数
- [ ] 默认权重不改变现有行为（向后兼容）
- [ ] 权重文件格式正确
- [ ] Dashboard 有推演区域

---

## Phase C: 推演验证回测 [Day 3-5]

### 新增/修改文件

| 文件 | 操作 | 说明 |
|------|------|------|
| `src/analysis/projection_backtest.py` | **新增** | 历史推演回测引擎 |
| `scripts/run_projection_backtest.py` | **新增** | 运行全量推演验证 |
| `dashboard/data/projection_log.json` | **新增** | 推演日志持久化 |
| `scripts/build_final.py` | **修改** | Dashboard准确率面板 |

### C1. 历史推演回测引擎
- 遍历822天×90板块，对比推演与实际次日走势
- 使用Phase A缓存避免重复classify

### C2. 准确率评估
- 正确/部分正确/错误三档评估
- 按状态分类统计、按场景分类统计

### C3. Dashboard准确率面板
- 总体准确率大数字、按状态分类柱状图、趋势折线图（内联SVG）

### 验收标准
- [ ] 推演准确率面板可用，含按状态分类统计
- [ ] 推演日志持久化正确
- [ ] 回测引擎性能可接受（< 30分钟）

---

## Phase D: 反思闭环引擎 [Day 5-7] ⭐核心

### 新增/修改文件

| 文件 | 操作 | 说明 |
|------|------|------|
| `src/analysis/reflection.py` | **新增** | 反思引擎 |
| `src/analysis/rule_discovery.py` | **新增** | 规则发现 |
| `scripts/run_reflection_loop.py` | **新增** | 反思闭环主流程 |
| `dashboard/data/health_dashboard.json` | **新增** | 健康度仪表数据 |
| `scripts/build_final.py` | **修改** | Dashboard健康度仪表面板 |
| `tests/analysis/test_reflection.py` | **新增** | 反思引擎测试 |
| `tests/analysis/test_rule_discovery.py` | **新增** | 规则发现测试 |

### D1. 反思引擎
- 推演正确→提取可复用模式; 推演错误→定位根因+分类(可优化/不可控)

### D2. 权重自动调整
- 衰减机制: 最近30天高权重，早期数据指数衰减
- 调整幅度限制: ±0.1/次，防过度拟合

### D3. 规则发现
- 从正确/错误模式中提取新规则，持久化JSON

### D4. 健康度仪表
- 准确率趋势折线图、最近调整参数、改进项列表

### D5. 822天全量闭环
- 初始推演→验证→反思→权重调整→再次推演（迭代至收敛）
- 预计30-90分钟

### 验收标准
- [ ] 权重可自动调整，准确率对比初始值明显提升(+3%)
- [ ] 822天全量推演验证闭环跑完
- [ ] 73,890次推演验证结果展现在Dashboard
- [ ] 87 tests全通过
