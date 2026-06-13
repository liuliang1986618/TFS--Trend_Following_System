# 趋势跟随交易系统 — 总览手册

> 一个文档，看懂全部：规则、脚本、技能、触发词、构建序列、红线。

## 一、系统概览

A股趋势跟随交易系统。每日收盘后一条命令完成：拉数据 → 全市场扫描 → 生成Dashboard → 打开浏览器。

**入口页面：** `http://localhost:8765/index.html`（侧边栏壳 + iframe 加载每日仪表板）

## 二、每日运行

### 一键构建（推荐）

```bash
bash scripts/build_and_verify.sh
```

自动完成：日期完整性检测(Step0) → build_final → action_panel → funnel_cards → funnel_panel → nav_index → 验证 → 启动no-cache服务 → 打开浏览器。

### 手动构建序列（7步，顺序不可变）

| 步骤 | 命令 | 产出 |
|------|------|------|
| 0 | 日期完整性检测 | 确认近30天无缺失交易日 |
| 1 | `python3 scripts/build_final.py` | `trend_dashboard_{date}.html` + `index.html` |
| 2 | `python3 scripts/render_action_panel.py` | 注入稳健推荐(绿) + 强势追踪(橙) |
| 3 | `python3 scripts/build_funnel_cards.py` | `funnel_cards_{date}.json` |
| 4 | `python3 scripts/render_funnel_panel.py` | 注入强势板块深度穿透(金) |
| 5 | `python3 scripts/build_nav_index.py` | `index.html` 侧边栏壳（**必须最后！**） |
| 6 | 验证（8项检查） | 确认所有面板存在 |
| 7 | `open http://localhost:8765/index.html` | 浏览器打开 |

### 定时调度

```
30 16 * * 1-5 cd /Users/liuliang19/Desktop/project/trend_following_system && bash scripts/build_and_verify.sh >> logs/daily_$(date +\%Y\%m\%d).log 2>&1
```

## 三、脚本速查

### 核心构建脚本（每日必跑）

| 脚本 | 功能 | 输入 | 输出 |
|------|------|------|------|
| `scripts/build_and_verify.sh` | **一键构建+验证+打开** | — | 完整Dashboard |
| `scripts/build_final.py` | 生成基础仪表板 + 30个历史页面 | `dashboard_data.json`, pkl数据 | `trend_dashboard_{date}.html` |
| `scripts/render_action_panel.py` | 注入操作建议面板（稳健+强势） | `standard_template.html`, `enhanced_actions_{date}.json` | 修改 `trend_dashboard_{date}.html` |
| `scripts/build_funnel_cards.py` | 构建四级漏斗数据 | `etf_holdings.json`, `theme_holdings.json` | `funnel_cards_{date}.json` |
| `scripts/render_funnel_panel.py` | 注入漏斗面板 | `funnel_cards_{date}.json` | 修改 `trend_dashboard_{date}.html` |
| `scripts/build_nav_index.py` | 生成侧边栏壳 | `date_nav.json` | `index.html` |

### 数据获取脚本

| 脚本 | 功能 |
|------|------|
| `pipeline.py` | 主数据管道：拉取行情 + 生成 `actions_{date}.json` |
| `src/enhanced_actions.py` | 全市场扫描：ETF+个股趋势判定+评分排序 |
| `scripts/pull_all_themes.py` | 拉取全量概念题材日线 |
| `scripts/build_etf_holdings_cache.py` | ETF持仓缓存（季度更新） |
| `scripts/build_theme_holdings_cache.py` | 题材成分股缓存（季度更新） |
| `scripts/serve.py` | no-cache HTTP 服务（端口8765） |

### 辅助脚本

| 脚本 | 功能 |
|------|------|
| `scripts/aggregate_date_nav.py` | 聚合 date_nav 数据 |
| `scripts/inject_sector_etf.py` | 注入板块ETF关联 |
| `scripts/generate_dashboard_data.py` | 生成 dashboard_data.json |
| `scripts/build_history_dashboards.py` | 批量生成历史仪表板 |
| `scripts/run_reflection_loop.py` | 反思闭环 |
| `scripts/run_projection_backtest.py` | 推演回测 |

## 四、规则文件速查

| 规则文件 | 领域 | 核心红线 |
|----------|------|---------|
| [data-authenticity-prime-directive](.claude/rules/data-authenticity-prime-directive.md) | 数据真实性 | 禁止parquet假数据、空JSON、硬编码列表、复制文件改名 |
| [full-market-download-prime-directive](.claude/rules/full-market-download-prime-directive.md) | 全量下载 | 禁止硬编码ETF列表、设置扫描上限、臆想数量 |
| [full-market-data-integrity](.claude/rules/full-market-data-integrity.md) | 数据完整性 | 五个维度(ETF/个股/题材/成分股/持仓)必检，禁止从Part2开始 |
| [stock-screening-quality-gate](.claude/rules/stock-screening-quality-gate.md) | 标的筛选 | 禁止不筛选直接展示、硬编码候选池、state<3进面板 |
| [display-layer-prime-directive](.claude/rules/display-layer-prime-directive.md) | 展示层 | 禁止Python拼接HTML、f-string生成标签、CSS写进代码 |
| [sidebar-date-nav-protection](.claude/rules/sidebar-date-nav-protection.md) | 侧边栏 | 禁止build_final写index.html、跳过build_nav_index |
| [data-directory-standard](.claude/rules/data-directory-standard.md) | 目录结构 | 按日期组织6层数据，自包含快照 |

### 规则触发条件

| 触发场景 | 激活规则 |
|----------|---------|
| 修改任何数据源/下载逻辑 | `full-market-download-prime-directive` |
| 修改筛选逻辑/候选池 | `stock-screening-quality-gate` |
| 修改面板/HTML/CSS | `display-layer-prime-directive` |
| 修改侧边栏/date_nav | `sidebar-date-nav-protection` |
| 新增日期 | `sidebar-date-nav-protection` + `display-layer-prime-directive` |
| 下载数据/pipeline | `full-market-data-integrity` + `data-authenticity-prime-directive` |
| 任何改动提交前 | 全部验证脚本 |

## 五、触发词映射

| 用户说的话 | 执行动作 |
|-----------|---------|
| "跑系统" "运行系统" "跑最新交易日" "trend system run" | → `bash scripts/build_and_verify.sh` |
| "看Dashboard" "打开面板" "dashboard" | → 打开 `http://localhost:8765/index.html` |
| "新增日期" "补齐X月X日" | → pipeline → enhanced_actions → 完整构建序列 |
| "检查日期完整性" "有没有缺失" | → Step0 日期完整性检测 |
| "工作区干净吗" | → `git status` |

## 六、验证清单

### 每次构建后必检（8项）

```python
h = open(f'dashboard/trend_dashboard_{date}.html').read()

# 操作建议面板（注入后标题）
assert '稳健推荐' in h, '缺少稳健推荐面板'
assert '强势追踪' in h, '缺少强势追踪面板'
assert 'ETF稳健' in h and 'ETF强势' in h
assert '个股稳健' in h and '个股强势' in h

# 漏斗面板
assert '强势板块深度穿透' in h, '缺少漏斗面板'
assert '趋势最强题材' in h

# 通用元素
assert 'widget-details' in h
assert '4ade80' in h               # 绿色边框(稳健)
assert 'f59e0b' in h or 'f0883e' in h  # 橙色/金色边框
assert '特别关注' in h              # WATCHLIST
assert '焦点板块' in h
assert '观察区' in h
```

### 侧边栏验证

```bash
python3 -c "
import json, os
# A: index.html < 100KB (壳页面)
size = os.path.getsize('dashboard/index.html')
assert size < 100000, f'index.html too large ({size}bytes)'
# B: date_nav 最新日期匹配 dashboard_data
nav = json.load(open('dashboard/data/date_nav.json'))
dd = json.load(open('dashboard/data/dashboard_data.json'))
assert dd['date'] in [e['date'] for e in nav['dates']]
# C-D: 有龙头和板块数据
sidebar = [e for e in nav['dates'] if e['date'] >= '2026-04-15']
assert not [e for e in sidebar if not e.get('leaders')], 'Missing leaders'
assert not [e for e in sidebar if not e.get('top_sectors')], 'Missing sectors'
# E: index.html 包含侧边栏+iframe
h = open('dashboard/index.html').read()
assert 'date-item' in h and 'iframe' in h
print('✅ 侧边栏验证通过')
"
```

### 五维数据完整性

```bash
python3 -c "
import os, json
etf = len([f for f in os.listdir('data/etf_stocks') if f.endswith('.pkl')])
stk = len([f for f in os.listdir('data/massive_stocks') if f.endswith('.pkl')])
thm_p = len([f for f in os.listdir('dashboard/data/theme') if f.endswith('.parquet')])
thm_h = len(json.load(open('data/theme_holdings.json'))) if os.path.exists('data/theme_holdings.json') else 0
etf_h = len(json.load(open('data/etf_holdings.json'))) if os.path.exists('data/etf_holdings.json') else 0
assert etf >= 130, f'ETF不足: {etf}'
assert stk >= 4000, f'个股不足: {stk}'
assert thm_p >= 200, f'题材日线不足: {thm_p}'
assert thm_h >= 200, f'题材成分股不足: {thm_h}'
assert etf_h >= 10, f'ETF持仓不足: {etf_h}'
print(f'✅ ETF={etf} 个股={stk} 题材={thm_p} 成分股={thm_h} 持仓={etf_h}')
"
```

## 七、数据流全景

```
akshare API
  │
  ├─→ ETF日线 ──→ data/etf_stocks/etf_{code}.pkl (~1500只)
  │
  └─→ 个股日线 ──→ data/massive_stocks/{code}.pkl (~4500只)
         │
         ▼
    pipeline.py → actions_{date}.json (etf_top5/stock_top5)
         │
         ▼
    enhanced_actions.py → enhanced_actions_{date}.json
         │                    (全量扫描 → 趋势判定 → 质量筛选 → 评分排序)
         ▼
    build_final.py → trend_dashboard_{date}.html (基础仪表板)
         │
         ├─ render_action_panel.py → 稳健推荐(绿) + 强势追踪(橙)
         ├─ build_funnel_cards.py  → funnel_cards_{date}.json
         ├─ render_funnel_panel.py → 强势板块深度穿透(金)
         │
         ▼
    build_nav_index.py → index.html (侧边栏壳 + iframe)
         │
         ▼
    用户浏览器 → http://localhost:8765/index.html
```

## 八、关键文件地图

| 文件/目录 | 负责什么 | 谁写入 |
|-----------|---------|--------|
| `dashboard/index.html` | 侧边栏壳 + iframe | `build_nav_index.py` **独占** |
| `dashboard/trend_dashboard_{date}.html` | 每日仪表板 | `build_final.py` → `render_action_panel.py` → `render_funnel_panel.py` |
| `dashboard/data/date_nav.json` | 侧边栏唯一数据源 | `pipeline.py` / 手动 |
| `dashboard/data/dashboard_data.json` | 当前日期 | 手动 / pipeline |
| `dashboard/data/actions_{date}.json` | 操作建议原始数据 | `pipeline.py` |
| `dashboard/data/enhanced_actions_{date}.json` | 增强操作建议 | `enhanced_actions.py` |
| `dashboard/data/standard_template.html` | 操作建议面板模板 | 用户确认的正确版本 |
| `dashboard/data/funnel_cards_{date}.json` | 漏斗面板数据 | `build_funnel_cards.py` |
| `data/etf_stocks/etf_{code}.pkl` | ETF日线缓存 | `pipeline.py` |
| `data/massive_stocks/{code}.pkl` | 个股日线缓存 | `pipeline.py` |
| `data/etf_names.json` | ETF名称缓存(~1500只) | akshare全量拉取 |
| `data/stock_names.json` | 个股名称缓存(~5500只) | akshare全量拉取 |

## 九、常见操作

### 新增一个缺失日期

```bash
# 1. 创建 actions JSON（如果 pipeline 太慢可用最小版）
python3 -c "
import json
json.dump({'date':'YYYY-MM-DD','generated_at':'YYYY-MM-DD','market_regime':'bear',
           'etf_top5':[],'stock_top5':[],'watchlist':[]},
          open('dashboard/data/actions_YYYY-MM-DD.json','w'), ensure_ascii=False)
"

# 2. 生成 enhanced_actions
python3 src/enhanced_actions.py YYYY-MM-DD

# 3. 更新 dashboard_data.json 日期
python3 -c "import json;d=json.load(open('dashboard/data/dashboard_data.json'));d['date']='YYYY-MM-DD';json.dump(d,open('dashboard/data/dashboard_data.json','w'))"

# 4. 添加 date_nav 条目（从最近交易日拷贝）
# 5. 跑完整构建序列
bash scripts/build_and_verify.sh
```

### 检查日期完整性

```bash
python3 -c "
import json, os
from datetime import datetime, timedelta
nav = json.load(open('dashboard/data/date_nav.json'))
nav_dates = {e['date'] for e in nav['dates']}
existing = {f.replace('trend_dashboard_','').replace('.html','')
            for f in os.listdir('dashboard') if f.startswith('trend_dashboard_') and f.endswith('.html')}
today = datetime.now()
for i in range(30):
    d = (today - timedelta(days=i)).strftime('%Y-%m-%d')
    if datetime.strptime(d, '%Y-%m-%d').weekday() >= 5: continue
    if d not in existing or d not in nav_dates:
        print(f'❌ 缺失: {d}')
print('检查完成')
"
```

### 仅启动HTTP服务

```bash
python3 scripts/serve.py  # no-cache服务 :8765
```

### 仅重新生成侧边栏

```bash
python3 scripts/build_nav_index.py
```

## 十、历史错误全景（21条）

| # | 错误 | 根因 | 教训 |
|---|------|------|------|
| 1 | heredoc注入代码到build_final | 数据逻辑混入展示层 | 独立渲染脚本 |
| 2 | 双代码块共存 | 没检查旧代码残留 | 先grep确认 |
| 3 | 双面板输出 | 两套代码都往h写HTML | 单一代码源 |
| 4 | 删A误删B | 字符串匹配边界不准 | 独立文件 |
| 5 | f-string重新生成HTML | 以为结构一样就行 | 模板直接替换数据 |
| 6 | build_nav被覆盖 | build_final也写index.html | 构建顺序固化 |
| 7 | grep误报 | 大文件输出截断 | Python读取验证 |
| 8 | 改完不验证 | 没有自动化检查 | 每次构建后强制验证 |
| 9 | 手调CSS颜色字体 | 手工拼HTML不可能一致 | CSS属于模板文件 |
| 10 | 不听用户指令 | 自以为是绕圈 | 执行用户给定架构 |
| 11 | 重写render时又手写CSS | 从记忆写而非从模板复制 | 任何样式从模板提取 |
| 12 | 策略总纲颜色反复错 | Python代码里的CSS和模板不一致 | CSS只在模板文件里 |
| 13 | 页面无明日操作建议 | 漏跑render_action_panel.py | 构建序列三步不可缺一 |
| 14 | render默认日期硬编码 | 死日期 | 默认日期从dashboard_data.json读取 |
| 15 | ETF名称显示为代码 | ETF_NAME_MAP只157条 | akshare全量→etf_names.json |
| 16 | 漏斗面板重复渲染 | inject不删旧面板 | 注入前去重 |
| 17 | 题材ETF关键词不匹配 | 芯片概念无ETF | 同义词扩展 |
| 18 | 交付不验证 | 说已打开但未Playwright确认 | 改后必须Playwright验证 |
| 19 | 浏览器缓存旧页面 | http.server无Cache-Control头 | 必须用no-cache服务 |
| 20 | **规则文档验证标记过时** | 面板标题改了但规则文档没同步更新 | 改面板标题→同步更新规则+验证脚本 |
| 21 | **日期缺失未自动检测** | 6月11日漏掉，人工发现 | build_and_verify.sh增加Step0 |

## 十一、技能（Skill）

**名称：** `trend-system`  
**触发词：** 趋势系统、跑系统、运行系统、看Dashboard、trend、pipeline、构建  
**位置：** `~/.claude/skills/trend-system/skill.md`

## 十二、核心原则（不可妥协）

1. **数据真实** — 只从akshare获取，禁止parquet假数据、空JSON、硬编码列表
2. **全量覆盖** — ETF~1500只 + 个股~4500只，不设上限
3. **质量筛选** — state≥3 才进入面板，下跌趋势不推荐
4. **模板替换** — 展示层只用 `str.replace`，禁用Python生成HTML
5. **构建顺序** — build_nav_index.py 必须最后，index.html 由其独占写入
6. **验证先行** — 改后必验证，不改完不开页面
7. **no-cache服务** — 禁止 `python3 -m http.server`
