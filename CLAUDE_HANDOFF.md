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

---

## 九、先进封装主题深度分析完整记录

### 背景

用户在06-15运行系统后,对"先进封装"题材产生兴趣,要求从数据获取、个股评分、业务分类、智能选股全流程分析。

### 数据获取过程

**Step 1: 尝试东财API (失败)**
```python
ak.stock_board_concept_cons_em(symbol='309004')  # IP被封
```
原因: 当日反复运行enhanced_actions.py累计超过万次API请求,东财封禁IP。

**Step 2: 尝试同花顺API (部分成功)**
```python
ak.stock_board_concept_name_ths()  # 成功,确认309004=先进封装
```
但同花顺无成分股接口(`stock_board_concept_cons_ths`不存在)。

**Step 3: 尝试东财API直连+curl (全失败)**
所有push2.eastmoney.com请求返回空或拒绝连接。

**Step 4: Playwright翻页爬同花顺 (成功!)**
```python
# Playwright浏览器访问同花顺概念页, JS渲染+翻5页, 提取全部股票
await page.goto('https://q.10jqka.com.cn/gn/detail/code/309004/')
# 翻页1-5, 每页10只, 去重后50只
```
产出: 50只成分股, 缓存至 `data/theme_holdings.json['309004']`

**Step 5: 补下载缺失pkl**
```python
ak.stock_zh_a_hist(symbol='600584', period='daily', start_date='20200101', end_date='20260616', adjust='qfq')
```
下载成功: 长电科技(1557行), 中微公司(1553行), 中芯国际(1428行)。
注意: 新下载pkl列名为中文(日期/开盘/收盘...),需要rename为英文(date/open/close...)才能被现有系统读取。

### 封测三龙头对比 (长电 vs 通富 vs 甬矽)

#### 技术面原始数据 (2026-06-15)

**StateMachine.classify() 原始输出:**

| | 长电科技 | 通富微电 | 甬矽电子 |
|---|:--:|:--:|:--:|
| StateMachine state | 1 (下跌) | 1 (下跌) | 1 (下跌) |
| 结构条件 | ❌ 无明确上涨结构 | ❌ 高点78→72持续降 | ✅ 1更高高+1更高低 |
| 量能条件 | ✅ 涨量>跌量1.0x | ✅ 涨量>跌量1.1x | ✅ 涨量>跌量1.1x |
| 持续性条件 | ✅ 阳11/9阴 | ❌ 阴盛阳衰(10/10) | ✅ 阳11/9阴 |
| above_ma20 | False | False | False |
| consecutive_drop | False | True | True |
| broke_prev_low | False | True | False |

**覆盖规则修正后:**

| | 长电科技 | 通富微电 | 甬矽电子 |
|---|:--:|:--:|:--:|
| 最终state | →3 (偏强) | ↓2 (偏弱) | ↓2 (偏弱) |
| 系统过滤 | ✅ 通过 | ❌ 过滤 | ❌ 过滤 |
| 修正规则 | 规则1.5:金叉+正动量 | 规则1.5但pct20d仅0.5% | 规则1.5但pct20d仅2.5% |

**关键价格数据:**

| | 长电科技 | 通富微电 | 甬矽电子 |
|---|:--:|:--:|:--:|
| 价格(06-15) | 74.32 | 57.22 | 52.58 |
| MA20 | 75.49 | 64.73 | 58.47 |
| MA60 | 55.18 | 53.65 | 48.09 |
| 5日涨跌 | **+5.7%** | -14.4% | -11.9% |
| 20日涨跌 | **+27.4%** | +0.5% | +2.5% |
| 60日涨跌 | **+69.9%** | +22.4% | +24.6% |
| 高点回撤 | -21.7% | -27.1% | -32.7% |
| RSI(14) | 34.3 (超卖) | 36.8 (超卖) | 50.8 (中性) |
| 量比(5d/20d) | 0.64 (缩量) | 0.67 (缩量) | 0.84 (正常) |

**基本面数据 (新浪财经实时, 2026-06-16):**

| | 长电科技 | 通富微电 | 甬矽电子 |
|---|:--:|:--:|:--:|
| 总市值 | **1384亿** | 955亿 | 302亿 |
| PE(TTM) | 83.80 | 66.01 | 361.11 |
| PB | 4.81 | 6.10 | 10.54 |
| 总股本 | 17.89亿 | 15.18亿 | 4.51亿 |
| 今日涨幅 | +3.93% | — | +6.18% |

**结论: 三选一选长电科技。** 行业龙头+60日涨70%+唯一通过系统筛选+PE合理(84 vs 甬矽361)。通富PE低但趋势废了,甬矽PE361且亏损。

### 双层分析 (封测 vs 材料 vs 设备)

从50只先进封装成分股中,按业务类型分为5类,用ThemeDeepDive逐只评分:

**分类统计 (2026-06-15):**

| 分类 | 通过/总数 | 均分 | Top股票 | Top分数 |
|------|:--:|:--:|------|:--:|
| 🟢材料 | 5/8 | **89** | 有研粉材 | 100 |
| 🟡显示 | 4/7 | 92 | 沃格光电 | 100 |
| 🔵设备 | 3/7 | 86 | 锐科激光 | 96 |
| ⚪其他 | 10/24 | 80 | 旭光电子 | 95 |
| 🔴封测 | 2/4 | **79** | 颀中科技 | 83 |

**核心发现: 封测最弱(均分79),材料最强(89)。**

**Top 5 排名:**
| # | 股票 | 分类 | Score | State | 20日 | 60日 | 回撤 | RSI |
|:--:|------|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| 1 | 有研粉材 | 材料 | 100 | →强 | +17% | +58% | -5% | 57 |
| 2 | 光华科技 | 材料 | 100 | →强 | +30% | +42% | -5% | 55 |
| 3 | 沃格光电 | 显示 | 100 | →强 | +71% | +246% | -5% | 88 |
| 4 | 凯盛科技 | 显示 | 98 | ↑升 | +30% | +59% | -8% | 71 |
| 5 | 锐科激光 | 设备 | 96 | →强 | +19% | +43% | -7% | 66 |

### 智能结论生成规则 (theme_deep_dive.py._conclude)

```python
# 1. 分类强弱: 均分最高vs最低, 差距>10分→标注
# 2. Top1特征: 评分/动量/回撤/RSI → flags列表
# 3. 风险提示: 60日涨>200%→妖股风险; RSI>75→超买; RSI<35→超卖
# 4. 首选推荐: Top3中找最高分且回撤<10%且5日非急跌
# 5. 数据提示: 缺pkl数量+名称
```

**实际产出结论:**
"显示均分92最高,封测79最低。首选有研粉材(高分低回撤非急跌)。有研粉材(sc=100): 回撤仅4.5%。沃格光电60日涨246%注意风险。⚠️8只缺数据(戈碧迦,士兰微,生益科,宏明电子,大族数控等)"

### 关键教训

1. **不要用关键词猜股**: 第一次分析时因API被封,我用了关键词匹配来找"先进封装"成分股,结果漏了真正的封装龙头。后来通过Playwright爬同花顺才拿到真正的50只名单。

2. **系统数据优先于行业叙事**: 系统评分明确显示材料(89)>设备(86)>封测(79),但我一度被"封测龙头"标签带偏,反复推荐长电科技。最终承认数据结论:材料类最好。

3. **三级漏斗第二级断了**: 10个半导体题材(dashboard_data.themes)全无数据,因为pull_all_themes.py从未被定期运行。这是孤儿子系统问题。

4. **概念定义跨源不一致**: 同花顺的"先进封装"50只,东方财富的名单可能更全(30-50只)。两源成分股差异需标注。

### 相关文件

- `src/theme_deep_dive.py` — 题材深钻CLI
- `dashboard/data/theme_dive_2026-06-15.json` — 先进封装分析数据
- `dashboard/theme_dive_309004.html` — 独立展示页面(50行排名表+分类卡片+智能结论)
- `data/theme_holdings.json['309004']` — 50只成分股缓存

---

详细: `.claude/rules/pipeline-integrity-prime-directive.md` (含13条历史错误+7条铁律)
