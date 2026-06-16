# 趋势跟随系统 — 全量改造手交文档

> 本文档供下一个 Claude 会话使用。包含所有已完成功能、待办事项、实现细节、关键代码位置、已知问题和经验教训。

---

## 一、系统架构速查

```
数据流: pipeline.py → enhanced_actions.py → build_final.py → build_nav_index.py → index.html
展示层: index.html (侧边栏壳 + iframe) → trend_dashboard_{date}.html (仪表板)
关键入口: http://localhost:8765/index.html
Build:  scripts/build_and_verify.sh (0/7 ~ 7/7)
```

---

## 二、全量任务清单

| 序号 | 功能 | 数据 | 展示 | 建议 | 说明 |
|:--:|------|:--:|:--:|------|------|
| 1 | StateMachine 6态 | ✅ | ❌ | 低优 | _determine_state委托6态(1-5及"3'")+4条覆盖规则 |
| 2 | 量能不否决趋势 | ✅ | — | 无展示 | 结构✅+持续✅但量能❌→仍为state=4，量能弱仅评分惩罚 |
| 3 | 评分连续化 | ✅ | — | 无展示 | 从55/42二进制→3条件推导30-60连续基分 |
| 4 | 排序分适配6态 | ✅ | — | 无展示 | {4:8,5:7,3:6,"3'":4},先比基分再比detail |
| 5 | ETF候选Top10 | ✅ | ❌ | **必做** | _scan_best_etfs top_n=10,模板5槽限制 |
| 6 | 个股候选Top10 | ✅ | ❌ | **必做** | _scan_best_stocks top_n=10,模板5槽限制 |
| 7 | ETF强势Top10 | ✅ | ❌ | **必做** | HOT_TOP_N=10,去互斥+降阈值(20→10,70→60) |
| 8 | 仓位Kelly计算 | ✅ | ✅ | 已完成 | _calc_position,action_label嵌入💰建议仓位X% |
| 9 | PortfolioManager | ✅ | ❌ | 下期 | src/portfolio/manager.py,需独立面板 |
| 10 | 管道完整性检测 | ✅ | — | 已完成 | build_and_verify.sh Step0 |
| 11 | transition()跨日追踪 | ✅ | ✅ | 已完成 | prev_states持久化,⬆升级/⬇变化 |
| 12 | PullbackAnalyzer | ✅ | ✅ | 已完成 | src/engine/pullback.py,回调描述嵌入action_label |
| 13 | SecondWaveDetector | ✅ | ✅ | 已完成 | src/engine/second_wave.py,二波信号嵌入action_label |
| 14 | 模板5→10扩展 | — | ❌ | **必做** | 核心UI,需慎重改模板(standard_template.html) |
| 15 | 漏斗真漏斗 | ⏳ | — | 下期 | sector_filter替代build_funnel_cards硬编码关键词 |
| 16 | 30天数据重建 | ⏳ | — | 最后 | 清旧数据全量重跑build_and_verify |
| 17 | StageClassifier | ⏳ | ⏳ | 下期 | 趋势早/中/晚期,_calc_trend_score已预留stage参数 |
| 18 | MarketGate | ⏳ | ⏳ | 下期 | 红黄绿灯,_calc_position已预留regime参数 |
| 19 | **题材深钻模块** | ✅ | ⏳ | **优先** | src/theme_deep_dive.py,三级漏斗闭环 |
| 20 | 主题数据完整性 | ✅ | — | 已完成 | 构建前检测,多源回退策略已写入fallback.py |

---

## 三、核心代码位置与改动细节

### 数据层

**`src/enhanced_actions.py`** — 主引擎,所有改动集中于此:

- `_determine_state(daily_df)` (行~420): 委托StateMachine.classify() + 4条覆盖规则Post-Processing
  - 规则1: state=3+struct✅+persist✅+golden+pct20d>0 → state=4 (量能不否决)
  - 规则1.5: state=1+golden+pct20d>0 → state=2或3 (金叉不判弱)
  - 规则2: state=2+golden+p>ma20*0.97 → state=3
  - 规则3: state=3+golden+pct20d>3+连续跌 → state=5
- `_calc_trend_score(state,ind,days_running,stage="")` (行~1140): 连续评分,30-60基分+5项加分
- `_calc_position(state,ind)` (行~1310): Kelly公式+分状态基准映射
- `_build_card()` (行~1380): 新增pullback/second_wave/transition嵌入action_label
- `_scan_best_etfs(top_n=10)` (行~1630): 排序分适配6态,强势追踪全量扫描不再互斥
- `_scan_best_stocks(top_n=10)` (行~1800): 同上
- `generate()` (行~1930): 新增prev_states加载/保存
- Import区: 新增pandas, StateMachine, PositionOptimizer, MarketRegime

**`src/engine/pullback.py`** (新建): PullbackAnalyzer, 计算depth/days/volume/health

**`src/engine/second_wave.py`** (新建): SecondWaveDetector, 5个重入信号≥2确认

**`src/portfolio/manager.py`** (新建): PortfolioManager, 100万/7ETF+3个股/真实持仓追踪

**`src/theme_deep_dive.py`** (新建): ThemeDeepDive, 全成分股排名+分类统计+智能结论

**`src/data/fallback.py`**: 新增fetch_concept_stocks_multisource(三源回退)

### 展示层 (必须从git恢复,不可瞎改)

**每个脚本的最新正确版本commit**:
- render_action_panel.py → `07c28091`
- build_final.py → `07c28091`
- build_funnel_cards.py → `07c28091`
- render_funnel_panel.py → `07c28091` (但需修marker)
- build_nav_index.py → `07c28091`
- build_and_verify.sh → `07c28091`

**render_funnel_panel.py marker修复** (必须):
```python
marker = '<h2 style="color:#42a5f5'  # 原为 '<div class="panel"><h2 style="color:#42a5f5">🔍 焦点板块'
```
原因: build_final 输出的 h2 多了 `margin-bottom:8px`,导致全字符串匹配失败。

---

## 四、题材深钻模块详解

### 设计目标
三级漏斗闭环: 板块轮动 → 题材热点 → **题材深钻(缺失环)** → 个股推演

### CLI
```bash
python3 src/theme_deep_dive.py 309004 2026-06-15
```

### 工作流程
1. 从theme_holdings.json获取题材成分股清单
2. 检查pkl完整性→缺失标记,不猜测
3. 逐只调用EnhancedActionGenerator._build_card()评分
4. 按score降序排列
5. 按业务分类统计: 封测/材料/设备/显示/其他 (THEME_309004_CATEGORIES字典)
6. 生成智能结论(基于数据特征自动推导)
7. 输出: dashboard/data/theme_dive_{date}.json

### 产出JSON
```json
{"date":"2026-06-15","theme":{"code":"309004","name":"先进封装"},
 "data_quality":{"total":50,"with_pkl":42,"missing_pkl":8,"passed":24},
 "categories":{"封测":{"avg_score":79,"passed":"2/4","top_name":"长电科技","top_score":75}},
 "ranking":[...全部24只通过筛选+18只被过滤+8只缺数据...],
 "conclusion":"显示均分92最高,封测79最低。首选有研粉材(高分低回撤非急跌)。沃格光电60日涨246%注意风险。"
}
```

### 展示方案
独立HTML页面 `dashboard/theme_dive_309004.html`,通过链接跳转。**零改动原有页面**。

### 已有运行结果 (06-15)
先进封装50只: 24只通过,18只被过滤,8只缺数据。
分类均分: 显示92>材料89>设备86>其他80>封测79。
智能结论: 首选有研粉材(高分+低回撤+非急跌)。材料整体强于封测。

---

## 五、Build Pipeline (不可变顺序)

```bash
# Step 0: 数据完整性检测
0/7 date_check + 题材成分股覆盖率 + pkl覆盖率

# Step 1-5: 生成流水线
1/7 build_final.py        # 生成基础仪表板HTML
2/7 render_action_panel.py # str.replace替换卡片数据(不改HTML结构)
3/7 build_funnel_cards.py  # 构建漏斗数据JSON
4/7 render_funnel_panel.py # 注入漏斗面板(⚠️不能缺失marker)
5/7 build_nav_index.py     # ⚠️MUST BE LAST! 生成侧边栏壳

# Step 6-7: 验证+服务
6/7 verify
7/7 serve
```

**关键**: build_final.py会覆盖dashboard HTML(含漏斗面板)。必须严格按序执行,不可跳步。

---

## 六、已知问题和坑

### 致命
1. **build_final.py覆盖dashboard**: 跑完build_final后漏斗面板丢失。必须跑完整pipeline。
2. **06-15.dashboard被多次覆盖**: 颜色和结构与06-12不同。解决方案: 每次改完cp 06-12 → 06-15。
3. **standard_template.html在.gitignore**: git checkout无法恢复。模板丢失=页面全毁。
4. **marker不匹配**: 见上文修复方案。

### 中等
5. **东财API易被封**: 每次enhanced_actions跑1392次请求。被封后用Playwright爬同花顺。
6. **pull_all_themes未定期运行**: 题材dashboard数据全空(10个半导体题材无一有数据)。
7. **render_action_panel inject有删除逻辑**: 注入失败时会误删漏斗面板。

### 颜色
8. 面板配色: 绿#4ade80(稳健)/橙#f59e0b(强势)/紫#a371f7(特别关注)/**粉#f472b6(漏斗)**/蓝#42a5f5(焦点)。改色: 直接sed替换HTML中的颜色值。

---

## 七、经验教训(已沉淀至规则)

1. 数据不完整=直说,绝不猜(如:不能用关键词猜先进封装成分股)
2. 展示层零改动(action_label嵌入文字是唯一例外)
3. API有成本(被封用Playwright替代)
4. 多源对比(同花顺vs东财概念定义不同,成分股差5倍)
5. 核心标的pkl覆盖率检查(长电科技等龙头曾缺pkl)
6. **系统数据>行业叙事**(材料score100>封测75,但曾被"封测龙头"标签带偏)
7. **三级漏斗是核心工具**(sector→theme→stock,用好了自动告诉你哪个题材最强)

详细: `.claude/rules/pipeline-integrity-prime-directive.md` (含13条历史错误+7条铁律)
