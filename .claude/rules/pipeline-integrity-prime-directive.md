---
name: pipeline-integrity-prime-directive
description: 管道完整性最高准则 — 禁止空壳数据/禁止孤儿子系统/仓位必须计算/回退必须补齐
metadata:
  type: project
---

# 管道完整性最高准则

> **本规则在 `stock-screening-quality-gate` 第4条基础上，进一步细化：禁止空actions JSON、仓位必须计算、孤儿子统必须接入。**

## 一、核心原则

1. **管道中每个环节的输出必须完整。空壳数据不允许存在超过 24 小时。**
2. **系统中不允许存在"写完但没接入主管道"的孤儿子系统。写代码 = 接线。**
3. **仓位是推荐的核心输出，不允许永远为 0。**
4. **任何 fallback 回退机制必须有补齐计划，不允许临时方案永久化。**

## 二、空壳数据禁令

### 定义

**空壳数据** = 文件存在、格式正确、但核心数据字段为空数组/空对象/默认值的数据文件。

```
❌ actions JSON: {"etf_top5": [], "stock_top5": [], "watchlist": []}
❌ enhanced_actions JSON: {"etf_cards": [], "stock_cards": []}
❌ date_nav entry: {"leaders": {}, "top_sectors": []}
```

### 铁律

1. **禁止手动创建空 actions JSON。** 如果 pipeline 超时，必须：
   - 修复超时原因（网络/API/数据量），然后重跑
   - 永不接受"先建空壳，以后补"的做法
2. **空壳数据存活不超过 24 小时。** 临时空壳必须打标记 + 记录补齐计划。
3. **每次构建前自动检测空壳。**

### 自动检测脚本

```bash
python3 -c "
import os, json
from datetime import datetime, timedelta
empty_actions = []
for i in range(10):
    d = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
    f = f'dashboard/data/actions_{d}.json'
    if os.path.exists(f):
        data = json.load(open(f))
        etf = data.get('etf_top5', [])
        stock = data.get('stock_top5', [])
        if len(etf) == 0 and len(stock) == 0:
            empty_actions.append(d)
if empty_actions:
    print(f'❌ 空壳 actions JSON ({len(empty_actions)}个): {empty_actions}')
    print('   这些文件 etf_top5=[] 且 stock_top5=[]')
    print('   请运行: python3 pipeline.py <date> 补齐')
    exit(1)
else:
    print('✅ 近10天 actions JSON 全部非空壳')
"
```

## 三、仓位必须计算

### 当前状态

- `src/fusion/position_optimizer.py` (199行)：Kelly公式仓位优化器 ✅ 已写完
- `src/fusion/orchestrator.py` (223行)：融合编排器 ✅ 已写完
- `src/fusion/market_gate.py` (129行)：红黄绿灯市场门控 ✅ 已写完
- **`enhanced_actions.py` → 仓位计算：❌ 未接入**
- **结果：所有推荐 `position_pct = 0`（全历史，从系统第一天运行至今）**

### 仓位数据流（修复后）

```
enhanced_actions.generate()
  │
  ├─ _build_card() → 计算趋势指标 → state, score, indicators
  │
  ├─ PositionOptimizer.optimize()
  │     ├─ 输入: state, win_rate, volatility, market_regime
  │     ├─ Kelly公式: f = (p*b - q) / b
  │     ├─ 约束: 单标的上限20%, 最小5%, 总仓位上限80%
  │     └─ 输出: position_pct (5%-20%)
  │
  ├─ MarketGate.assess()
  │     ├─ green: 仓位上限100%
  │     ├─ yellow: 仓位上限50%
  │     └─ red: 仓位上限0% (空仓)
  │
  └─ 最终 position_pct = min(Kelly, Gate上限)
```

### 仓位字段规范

| 字段 | 含义 | 取值范围 | 说明 |
|------|------|---------|------|
| `position_pct` | 建议仓位百分比 | 5-20 (正常) / 0 (禁止) | 0 只有红灯时才合法 |
| `position_reason` | 仓位推导说明 | 字符串 | 如 "Kelly公式 f=12% × 黄灯0.5 = 6%" |

### 仓位验证

```bash
python3 -c "
import json, os
from datetime import datetime
d = datetime.now().strftime('%Y-%m-%d')
f = f'dashboard/data/enhanced_actions_{d}.json'
if os.path.exists(f):
    data = json.load(open(f))
    all_cards = data.get('etf_cards',[]) + data.get('stock_cards',[]) + data.get('hot_etf_cards',[]) + data.get('hot_stock_cards',[])
    zero_pos = [c['name'] for c in all_cards if c.get('position_pct',0) == 0]
    if zero_pos and len(zero_pos) == len(all_cards):
        print(f'❌ 所有{len(all_cards)}个标的仓位=0%！仓位优化器未接入！')
        exit(1)
    elif zero_pos:
        print(f'⚠️ {len(zero_pos)}/{len(all_cards)} 仓位=0%: {zero_pos}')
    else:
        print(f'✅ 全部{len(all_cards)}个标的仓位>0%')
else:
    print(f'⚠️ 今日 enhanced_actions 不存在，跳过仓位验证')
"
```

## 四、孤儿子系统禁令

### 定义

**孤儿子系统** = 代码存在、测试存在、但没有任何生产管道调用它的模块。

### 检测标准

任何 `src/` 下的 Python 模块，必须满足以下至少一项：
1. 被 `pipeline.py` 直接或间接调用
2. 被 `enhanced_actions.py` 直接或间接调用
3. 被 `build_final.py` / `build_nav_index.py` 直接或间接调用
4. 有独立 CLI 入口且被文档记录的独立工具

### 当前已知孤儿子系统

| 模块 | 行数 | 被谁调用 | 状态 |
|------|------|---------|------|
| `src/fusion/position_optimizer.py` | 199 | 仅 orchestrator.py | ⚠️ 间接孤立 |
| `src/fusion/orchestrator.py` | 223 | 仅 cli.py (独立CLI) | ⚠️ 孤立 |
| `src/fusion/market_gate.py` | 129 | 仅 orchestrator.py | ⚠️ 间接孤立 |

### 孤儿子系统检测

```bash
python3 -c "
import os, ast
MAIN = ['src/enhanced_actions.py', 'scripts/build_final.py', 'scripts/build_nav_index.py', 'pipeline.py']
def imports_of(filepath):
    if not os.path.exists(filepath): return set()
    with open(filepath) as f:
        try: tree = ast.parse(f.read())
        except: return set()
    imps = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imps.add(alias.name.split('.')[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imps.add(node.module.split('.')[0])
    return imps

all_imports = set()
for f in MAIN:
    all_imports |= imports_of(f)

src_modules = set()
for root, dirs, files in os.walk('src'):
    for f in files:
        if f.endswith('.py') and not f.startswith('__'):
            rel = os.path.relpath(os.path.join(root, f), 'src').replace('/', '.').replace('.py', '')
            src_modules.add(rel)

# 排除标准库和第三方
third_party = {'numpy','pandas','akshare','json','os','sys','pickle','datetime',
               're','math','collections','typing','dataclasses','pathlib','logging'}
orphan = {m for m in src_modules if m not in all_imports and m.split('.')[0] not in third_party}
if orphan:
    print(f'⚠️ 疑似孤儿子系统 ({len(orphan)}个):')
    for m in sorted(orphan):
        print(f'  - src/{m.replace(\".\", \"/\")}.py')
else:
    print('✅ 无孤儿子系统')
"
```

## 五、修复优先级

1. **P0（立即）**：补齐近 5 天空壳 actions JSON — 跑 pipeline 或让动态扫描正式化
2. **P1（本周）**：仓位优化器接入 `enhanced_actions.py` — position_pct 不再永远为 0
3. **P2（本月）**：孤儿子系统全部接入或删除

## 六、历史错误清单

| # | 错误 | 日期 | 根因 | 教训 |
|---|------|------|------|------|
| 1 | 5天空壳actions JSON | 06-14 | pipeline超时→手动建空壳→永久残留 | 空壳24h内必须补齐 |
| 2 | 全历史仓位=0% | 始终 | 仓位优化器从未接入主管道 | 写完代码≠系统在工作 |
| 3 | 551行fusion代码闲置 | 始终 | orchestrator只被cli.py调用 | 孤儿子系统必须接入或删除 |
| 4 | **关键词猜股冒充真数据** | 06-15 | 先进封装API拉不到→用关键词猜测成分股 | **最严重**: 数据不完整就直说，绝不造假 |
| 5 | **pull_all_themes未定期运行** | 始终 | 只有板块列表无成分股缓存，309004无数据 | 孤儿子系统，同#3 |
| 6 | **东方财富IP被封** | 06-15 | 全天反复跑enhanced_actions(每次1392次请求) | 限制重跑次数 |
| 7 | **fallback.py缺题材成分股备用** | 06-15 | 只有股票/ETF/指数备用，无概念板块成分股 | fallback必须覆盖全部维度 |
| 8 | **render脚本多次改崩布局** | 06-15 | 反复修改render_action_panel导致页面错乱 | 展示层零容忍改动 |
| 9 | **概念题材跨源不一致** | 06-16 | 同花顺50只vs东方财富更全,同花顺混入材料/设备 | 标注来源,告知差异 |
| 10 | **核心龙头缺pkl** | 06-16 | 长电科技/中芯国际等封测龙头无日线数据 | 概念成分股pkl覆盖率需检查 |
| 11 | **StateMachine判定与常识冲突** | 06-16 | 华天+12.3%被判弱,深科技+10.2%判跌 | 规则1.5:金叉+正动量不判弱 |
| 12 | **评分排序≠领域龙头** | 06-16 | 材料公司趋势强但封测核心才是用户关心的 | 系统看趋势,领域看基本面 |
| 13 | **行业标签偏见覆盖系统数据** | 06-16 | score:材料100>设备96>封测75,却因"封测龙头"标签反复推荐长电 | 系统数据优先于行业叙事 |

## 七、铁律补充

1. **数据不完整 = 直说，绝不猜。**
2. **展示层零改动。** action_label嵌入文字是唯一例外。
3. **API调用有成本。** 被封后用Playwright爬同花顺替代。
4. **多源对比。** 同花顺和东方财富概念定义不同(成分股数差5倍),需标注来源。
5. **核心标的pkl覆盖率。** 概念龙头必须全部有pkl,发现缺失立即下载。
6. **系统数据优先。** 行业叙事会骗人,系统score不会。相信数据而非标签。
7. **三级漏斗是核心工具。** sector→theme→stock,用好了自动告诉你哪个题材最强。

## 八、数据完整性保障策略

### 题材成分股多源获取

```
Source 1: akshare 东方财富 stock_board_concept_cons_em
  → 3s重试 → 9s重试 → Source 2
Source 2: 东方财富 API 直连 push2.eastmoney.com
  → Source 3
Source 3: 同花顺 Playwright 翻页渲染(5页全抓)
  → 缓存到 theme_holdings.json
Source 4: 本地缓存 data/theme_holdings.json
  → 无? 标记缺失, 不猜测
```

### 个股pkl多源获取

```
Source 1: akshare stock_zh_a_hist
  → Source 2: baostock
  → Source 3: 本地 pkl
  → 无? 报告缺失
```

### 构建前强制检查

```
Step 0 新增: 题材成分股覆盖率 + pkl覆盖率 + parquet覆盖率
任一维度<80% → 警告, <50% → 终止
```

## 九、与现有规则的关系

- [[stock-screening-quality-gate]] — 第4条已禁止空actions JSON，本规则加强为自动化检测+补齐时限
- [[display-layer-prime-directive]] — 构建序列不可缺步骤
- [[full-market-data-integrity]] — 数据完整性 → 管道完整性
