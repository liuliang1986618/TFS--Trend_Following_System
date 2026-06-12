---
name: sidebar-date-nav-protection
description: 侧边栏日期导航保护规则 — 任何改动后必须验证的检查清单
metadata:
  type: project
---

# 侧边栏日期导航保护规则

## 系统架构速查

```
date_nav.json ──→ build_nav_index.py ──→ index.html (侧边栏壳 + iframe)
                       ↓                        ↓
                  拉取指数数据              iframe 加载
                  拉取龙头名称              trend_dashboard_{date}.html
                  服务端渲染侧边栏              ↓
                                        build_final.py 生成
                                        enhanced_actions 增强面板
```

**关键文件（4个，缺一不可）：**

| 文件 | 作用 | 谁写入 |
|------|------|--------|
| `dashboard/data/date_nav.json` | 侧边栏唯一数据源 | pipeline / 手动 |
| `scripts/build_nav_index.py` | 读取 date_nav + 拉取指数 → 渲染侧边栏 | → `index.html` |
| `scripts/build_final.py` | 生成每日仪表板 | → `trend_dashboard_{date}.html` |
| `dashboard/index.html` | 侧边栏壳页面（iframe嵌入仪表板） | build_nav_index.py |

## 铁律

### 1. 新增/更新日期必走完整流程
```
① date_nav.json — 添加日期条目，必须包含完整字段（非空）
② python3 scripts/build_nav_index.py — 重新生成 index.html
③ python3 scripts/build_final.py — 重新生成 trend_dashboard_{date}.html
④ 验证（见第4条）
```

### 2. date_nav.json 条目字段模板
```json
{
  "date": "YYYY-MM-DD",
  "weekday": "周一~周日",
  "uptrend_count": 0,
  "downtrend_count": 0,
  "health": "强势|正常|弱势",
  "top_sectors": [],
  "top_flip": [],
  "leaders": {},
  "is_today": false,
  "is_monday": false
}
```
- **禁止填空数组/空对象**作为终态：`top_sectors`、`leaders` 等必须有数据
- 无真实数据时从最近交易日拷贝（标注来源）
- `sh_pct`/`kc_pct`/`cy_pct` 由 build_nav_index.py 自动拉取，不需要手动填

### 3. build_final.py 禁止写入 index.html
`index.html` 是侧边栏壳，由 build_nav_index.py 独占写入。
- ✅ `open("dashboard/trend_dashboard_{date}.html", "w")` 
- ❌ `open("dashboard/index.html", "w")` — **已移除**

### 4. 改动后强制验证
```bash
python3 -c "
import json, os
# A: index.html 是壳页面 (size < 100KB → 不可能是完整仪表板)
size = os.path.getsize('dashboard/index.html')
assert size < 100000, f'index.html too large ({size}bytes) — may be overwritten by build_final!'
# B: date_nav.json 最新日期匹配 dashboard_data.json
nav = json.load(open('dashboard/data/date_nav.json'))
dd = json.load(open('dashboard/data/dashboard_data.json'))
nav_dates = [e['date'] for e in nav['dates']]
assert dd['date'] in nav_dates, f'{dd[\"date\"]} missing from date_nav!'
# C: 侧边栏范围内的日期有龙头数据 (>= 2026-04-15)
sidebar_dates = [e for e in nav['dates'] if e['date'] >= '2026-04-15']
empty_leaders = [e['date'] for e in sidebar_dates if not e.get('leaders')]
assert not empty_leaders, f'Missing leaders in sidebar range: {empty_leaders}'
# D: 侧边栏范围内的日期有板块数据
empty_sectors = [e['date'] for e in sidebar_dates if not e.get('top_sectors')]
assert not empty_sectors, f'Missing sectors in sidebar range: {empty_sectors}'
# E: index.html 包含侧边栏
with open('dashboard/index.html') as f:
    html = f.read()
assert 'date-item' in html, 'No sidebar date items!'
assert 'iframe' in html, 'No iframe!'
# F: build_final.py 不再写入 index.html
with open('scripts/build_final.py') as f:
    assert 'dashboard/index.html' not in f.read(), 'build_final.py still writes index.html!'
print('✅ 侧边栏日期导航全部检查通过')
"
```

### 5. 测试入口
- 用户看的是 **`index.html`**（侧边栏壳+iframe）
- 仪表板内页是 **`trend_dashboard_{date}.html`**（被iframe加载）
- 测试侧边栏 → 打开 `index.html`

## 历史错误清单（避免重犯）

| # | 错误 | 根因 |
|---|------|------|
| 1 | 不知道 build_nav_index.py 存在 | 没扫描项目结构 |
| 2 | build_final.py 覆盖 index.html | 没检查文件写入冲突 |
| 3 | 新日期没更新 date_nav.json | 不知道侧边栏数据源 |
| 4 | 新条目 top_sectors/leaders 填空 | 没参考已有数据格式 |
| 5 | 改 date_nav 后没重跑 build_nav_index | 不理解服务端渲染 |
| 6 | 复制 HTML 绕过生成流程 | 偷懒 |
| 7 | 测试 trend_dashboard 而非 index.html | 没确认用户入口 |
| 8 | 不理解 iframe 架构 | 没理解系统就动手 |

**原则：除非用户明确要求删除侧边栏，否则日期导航永远不能坏。任何改动后先跑验证。**

## 补充：新增日期完整操作手册

当需要新增一个日期（如今天）时，**必须按顺序执行以下全部步骤**，跳过任何一步都会导致数据不一致。

### 前置检查
```bash
# 确认 pipeline 是否已跑过今天的数据
ls dashboard/data/actions_2026-06-08.json 2>/dev/null && echo "已存在" || echo "需要生成"
```

### 步骤1：生成 actions JSON（如果不存在）
```bash
# 方案A：跑完整 pipeline（可能超时）
python3 pipeline.py 2026-06-08

# 方案B：如果 pipeline 超时，至少创建最小 actions JSON
python3 -c "
import json
json.dump({
    'date': '2026-06-08',
    'generated_at': '2026-06-08',
    'market_regime': 'strong_bear',  # 从最近交易日拷贝
    'etf_top5': [], 'stock_top5': [], 'watchlist': []
}, open('dashboard/data/actions_2026-06-08.json', 'w'), ensure_ascii=False)
"
```

### 步骤2：生成 enhanced_actions JSON
```bash
python3 src/enhanced_actions.py 2026-06-08
```

### 步骤3：更新 dashboard_data.json 日期
```bash
python3 -c "
import json
d = json.load(open('dashboard/data/dashboard_data.json'))
d['date'] = '2026-06-08'
json.dump(d, open('dashboard/data/dashboard_data.json', 'w'), ensure_ascii=False)
"
```

### 步骤4：更新 date_nav.json（新增日期条目）
```bash
# 必须包含完整字段，从最近交易日拷贝 top_sectors / leaders / health 等
# 禁止使用空数组/空对象作为终态
python3 -c "
import json
from datetime import datetime
nav = json.load(open('dashboard/data/date_nav.json'))
existing = {e['date'] for e in nav['dates']}
target = '2026-06-08'
if target not in existing:
    template = nav['dates'][0]  # 最新日期作为模板
    dt = datetime.strptime(target, '%Y-%m-%d')
    nav['dates'].insert(0, {
        'date': target,
        'weekday': ['周一','周二','周三','周四','周五','周六','周日'][dt.weekday()],
        'uptrend_count': template.get('uptrend_count', 0),
        'downtrend_count': template.get('downtrend_count', 0),
        'health': template.get('health', '正常'),
        'top_sectors': template.get('top_sectors', []),
        'top_flip': template.get('top_flip', []),
        'leaders': template.get('leaders', {}),
        'is_today': True,
        'is_monday': dt.weekday() == 0
    })
    # 清除其他日期的 is_today
    for e in nav['dates']:
        if e['date'] != target:
            e['is_today'] = False
    json.dump(nav, open('dashboard/data/date_nav.json', 'w'), ensure_ascii=False)
    print('Added', target)
else:
    print(target, 'already exists')
"
```

### 步骤5：重新生成侧边栏壳
```bash
python3 scripts/build_nav_index.py
```

### 步骤6：重新生成仪表板 HTML
```bash
python3 scripts/build_final.py
```

### 步骤7：跑验证
```bash
# 跑第4条铁律中的完整验证脚本
```

## 补充：改动完成后的交付动作（自动执行，无需用户确认）

**只有在全部代码改动彻底结束、所有生成脚本跑完、验证全部通过之后，才打开一次页面。中间过程不允许打开页面打扰用户。**

```bash
# 0. 确保 HTTP 服务运行中
curl -s -o /dev/null http://localhost:8765/ 2>/dev/null || (cd dashboard && python3 -m http.server 8765 &)

# 1. ⚠️ 先用 Playwright 确认页面正确（不可跳过！）
#   - browser_navigate → browser_evaluate 检查关键标记
#   - 确认 iframe src 指向正确文件
#   - 截图确认无重复面板、无旧标题残留

# 2. Playwright 确认后，带时间戳破缓存打开
open "http://localhost:8765/index.html?v=$(date +%s)"
```

⚠️ **严格禁止**：
- ❌ Playwright 未验证就 open
- ❌ 不加时间戳直接 open（浏览器缓存）
- ❌ 说"已打开"但从未用 Playwright 确认
- ❌ 改动过程中多次打开页面

## 补充：不要做的事（红线）

1. **❌ 不要复制 HTML 文件改名** — 日期/导航/数据都会错，必须走 build_final.py
2. **❌ 不要在 build_final.py 中写入 index.html** — 已被永久移除
3. **❌ 不要手动创建 date_nav.json 条目时不填 leaders/top_sectors** — 侧边栏会空白
4. **❌ 不要跳过 build_nav_index.py** — 改了 date_nav.json 就必须重跑它
5. **❌ 不要测试 trend_dashboard_*.html 当作最终页面** — 用户入口是 index.html
6. **❌ 不要假设只有一个生成脚本** — 先扫描 scripts/ 目录了解全部脚本
7. **❌ 不要给动态扫描的标的留空链接（`#`）** — ETF 必须用 `_etf_link()`，个股必须用 `_stock_link()`，都是东方财富行情页
8. **❌ 不要在 `_build_card` 中对个股使用 `#` 作为默认链接** — 一律通过 `_stock_link(code)` 生成
9. **❌ 不要生成完页面就结束** — 必须执行交付动作：检查HTTP服务 → `open index.html`
