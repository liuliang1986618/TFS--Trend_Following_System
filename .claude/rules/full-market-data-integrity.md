---
name: full-market-data-integrity
description: 全量市场数据完整性 — 必须拉取全市场股票+ETF数据，禁止部分数据、禁止临时构造、禁止绕过pipeline
metadata:
  type: project
---

# 全量市场数据完整性规则

## 一、核心原则

**任何分析、推荐、展示，必须基于全量市场数据。不允许用部分数据代替全量数据。**

数据分三层，每一层都不能跳过：

```
Part 1: 全量原始数据（5000+ 股票 + 全量 ETF）
   │  来源：pipeline._update_pkl_caches() → akshare 接口
   │  存储：data/etf_stocks/*.pkl + data/massive_stocks/*.pkl
   │
   ▼
Part 2: 趋势判定后的候选池（state≥3 的标的）
   │  来源：enhanced_actions._build_card() 质量筛选
   │  从 Part 1 全部标的中逐个判定
   │
   ▼
Part 3: 评分排序 Top N（进入操作建议面板）
   │  来源：_calc_trend_score() 评分 → 降序取 top 5
   │  展示：trend_dashboard_{date}.html
```

**禁止：从 Part 2 或 Part 3 开始。必须从 Part 1 开始。**

## 二、数据完整性检查 — 五个维度全部必检

| 维度 | 来源 | 阈值 | 检查命令 |
|------|------|------|---------|
| ETF日线 | `data/etf_stocks/etf_*.pkl` | >= 130 | `ls data/etf_stocks/*.pkl \| wc -l` |
| 个股日线 | `data/massive_stocks/*.pkl` | >= 4000 | `ls data/massive_stocks/*.pkl \| wc -l` |
| **题材日线** | `dashboard/data/theme/theme_*.parquet` | **>= 200** | `ls dashboard/data/theme/*.parquet \| wc -l` |
| **题材成分股** | `data/theme_holdings.json` | **>= 200个key** | `python3 -c "import json;print(len(json.load(open('data/theme_holdings.json'))))"` |
| ETF持仓 | `data/etf_holdings.json` | >= 10 | 同上 |

**任一维度不满足 → 先补齐再继续。**
- 题材数据：`python3 scripts/pull_all_themes.py`
- ETF持仓：`python3 scripts/build_etf_holdings_cache.py`

> **反思：为什么题材数据反复不全？**
> 之前验证脚本只查ETF+个股数量，题材根本没在检查清单里。
> 规则说"全量"但没具体到每个维度。这次五个维度全列入强制检查。

## 三、补齐数据的正确方式

```bash
# 运行完整 pipeline（拉取全量数据）
python3 pipeline.py 2026-06-08
```

## 四、历史错误清单（数据相关，共 9 条）

| # | 错误 | 具体表现 | 根因 | 教训 |
|---|------|---------|------|------|
| 1 | 只下载5只股票 | massive_stocks只有5只 | 只下了actions JSON中出现的股票 | 必须拉全量，不是"谁出现就拉谁" |
| 2 | 用parquet转换代替pipeline | 800只股票来自旧数据 | pipeline没跑完就放弃 | parquet是缓存快照，pkl是正源 |
| 3 | 接受805只代替5000+ | 181只候选 vs 实际应有1000+ | 没质疑"为什么只有800只" | 数据量不对时要警觉 |
| 4 | 手动创建空actions JSON | 跳过pipeline构造假数据 | pipeline超时就偷懒 | 不允许绕过pipeline构造数据 |
| 5 | ETF数据完整但股票不完整 | ETF 132只 vs 股票 5只 | 处理不对称 | 两个池子都要全量 |
| 6 | 扫描上限只设200只 | 800只中只扫200 | 硬编码限制 | 扫描=全量，不允许设上限 |
| 7 | 从Part 2开始分析 | 直接用parquet数据做趋势判定 | 跳过了全量数据拉取 | 必须从Part 1开始 |
| 8 | 不自检数据完整性 | 805只就当成"全量"了 | 没跟5000+对比 | 关键数据量必须自检 |
| 9 | 反复在数据不完整基础上做功能 | 评分、筛选、标签都在残缺数据上做 | 把"有数据"当"数据全" | Part 1不完，后面全白做 |

## 五、绝对禁止

1. ❌ 用 Parquet 缓存代替 pipeline pkl 作为数据源
2. ❌ 只下载"需要的"股票，不拉全量
3. ❌ 接受"只有几百只"就当成完整数据
8. ❌ 使用数据不足250个交易日的标的做趋势判定 — 短线数据不可靠
4. ❌ 手动创建空 JSON 绕过 pipeline
5. ❌ 扫描设置上限（必须扫描全部可用标的）
6. ❌ Part 1 数据不完整时继续做 Part 2/3
7. ❌ 不自检数据量就声称"完成"

## 七、全量数据下载工具

### 批量下载脚本

当股票池不完整时（个股 < 4000），使用以下脚本补齐全量数据：

```bash
python3 /tmp/batch_download.py /Users/liuliang19/Desktop/project/trend_following_system/data/massive_stocks
```

脚本逻辑：从 akshare 获取全市场 5526 只 A 股列表 → 跳过已存在的 → 逐个下载 OHLCV 日线数据 → 存为 pkl。

### ETF 数据

ETF 数据通常由 pipeline 自动维护（`_update_pkl_caches`），一般不需要手动下载。若 ETF 池不足 130 只，运行 pipeline 即可补齐。

## 八、每日完整工作流（必须按顺序执行）

**这是趋势跟随系统的核心流水线。每天必须走完这 7 步，不允许跳过或颠倒。**

```
Step 1: 数据完整性检查
  ├─ ETF: ls data/etf_stocks/*.pkl | wc -l  (需 >= 130)
  ├─ 个股: ls data/massive_stocks/*.pkl | wc -l  (需 >= 4000)
  └─ 不满足 → 先跑全量下载补齐

Step 2: 拉取增量行情数据
  └─ python3 pipeline.py 2026-06-08  (更新ETF/个股pkl到今日+板块数据+生成actions JSON)

Step 3: 生成增强操作建议数据 (Part 2+3)
  └─ python3 src/enhanced_actions.py 2026-06-08
       ├─ 从全量池动态扫描ETF+个股
       ├─ 趋势判定 → 质量筛选 (state>=3)
       ├─ 趋势强度评分 (0-100)
       └─ 输出 enhanced_actions_{date}.json

Step 4: 生成每日 Dashboard HTML
  └─ python3 scripts/build_final.py
       └─ 输出 trend_dashboard_{date}.html (含增强操作建议卡片)

Step 5: 重新生成侧边栏壳
  └─ python3 scripts/build_nav_index.py
       └─ 输出 index.html (侧边栏+iframe壳)

Step 6: 全量验证
  └─ 跑三条规则的验证脚本
       ├─ sidebar-date-nav-protection: A~F 检查
       ├─ stock-screening-quality-gate: 筛选全量验证
       └─ full-market-data-integrity: 数据量自检

Step 7: 打开页面
  └─ open http://localhost:8765/index.html
```

## 九、数据流全景图

```
akshare API
  │
  ├─→ ETF日线数据 ──→ data/etf_stocks/etf_{code}.pkl (132只)
  │
  └─→ 个股日线数据 ──→ data/massive_stocks/{code}.pkl (5000+只)
         │
         ▼
    enhanced_actions.py
         │
         ├─ _build_card() × N → 趋势判定 + 质量筛选
         │     ├─ state=1,2 → ❌ 过滤
         │     └─ state≥3 → ✅ + 评分
         │
         ├─ _scan_best_etfs() → 132只择优Top5
         ├─ _scan_best_stocks() → 5000+只择优Top5
         │
         └─→ enhanced_actions_{date}.json
                │
                ▼
           build_final.py → trend_dashboard_{date}.html
                │
                ▼
           build_nav_index.py → index.html (侧边栏壳)
                │
                ▼
           用户浏览器
```

## 六、改动后强制验证（五个维度全检）

```bash
python3 -c "
import os, json

etf_count = len([f for f in os.listdir('data/etf_stocks') if f.endswith('.pkl')])
stock_count = len([f for f in os.listdir('data/massive_stocks') if f.endswith('.pkl')])
theme_parquet = len([f for f in os.listdir('dashboard/data/theme') if f.endswith('.parquet')])
theme_holdings = len(json.load(open('data/theme_holdings.json'))) if os.path.exists('data/theme_holdings.json') else 0
etf_holdings = len(json.load(open('data/etf_holdings.json'))) if os.path.exists('data/etf_holdings.json') else 0

print(f'ETF日线: {etf_count} (>=130)')
print(f'个股日线: {stock_count} (>=4000)')
print(f'题材日线: {theme_parquet} (>=200)')
print(f'题材成分股: {theme_holdings} (>=200)')
print(f'ETF持仓: {etf_holdings} (>=10)')

assert etf_count >= 130, f'ETF不足!'
assert stock_count >= 4000, f'个股不足!'
assert theme_parquet >= 200, f'题材日线不足({theme_parquet}), 需运行 pull_all_themes.py'
assert theme_holdings >= 200, f'题材成分股不足({theme_holdings}), 需运行 pull_all_themes.py'
assert etf_holdings >= 10, f'ETF持仓不足({etf_holdings}), 需运行 build_etf_holdings_cache.py'
print('✅ 五维数据全部完整')
"
```
