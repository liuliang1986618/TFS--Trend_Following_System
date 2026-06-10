# 四级漏斗穿透卡片 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。

**目标：** 新增独立面板展示Top3板块的四级漏斗穿透（板块→ETF→成分股龙头→题材→题材ETF→题材龙头）

**架构：** 3个新Python模块，全部独立，零修改已有文件。数据流：akshare→缓存→build_funnel_cards→render_funnel_panel→注入HTML

**技术栈：** Python3, akshare, requests, json, re

---

### 任务 1：题材成分股缓存模块

**文件：**
- 创建：`scripts/build_theme_holdings_cache.py`
- 创建：`data/theme_holdings.json`

- [ ] **步骤 1：编写缓存脚本**

```python
#!/usr/bin/env python3
"""题材成分股缓存 — 从akshare拉取题材板块成分股"""
import json, os, sys, time
import akshare as ak

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_PATH = os.path.join(PROJECT, 'data', 'theme_holdings.json')


def fetch_one(theme_name: str) -> list[dict]:
    """拉取单个题材的所有成分股"""
    try:
        df = ak.stock_board_concept_cons_ths(symbol=theme_name)
        stocks = []
        for _, row in df.iterrows():
            code = str(row.get('代码', row.get('code', '')))
            name = str(row.get('名称', row.get('name', '')))
            if code and name:
                stocks.append({'code': code, 'name': name})
        return stocks
    except Exception as e:
        print(f'  ⚠️ {theme_name}: {e}')
        return []


def main():
    cache = {}
    if os.path.exists(CACHE_PATH):
        cache = json.load(open(CACHE_PATH))

    theme_list_path = os.path.join(PROJECT, 'dashboard', 'data', 'theme_list.json')
    themes = json.load(open(theme_list_path))

    new_count = 0
    for i, t in enumerate(themes):
        name = t['name']
        code = t['code']
        if code in cache and len(cache[code]) > 0:
            continue
        print(f'[{i+1}/{len(themes)}] {name}...', end=' ', flush=True)
        stocks = fetch_one(name)
        if stocks:
            cache[code] = stocks
            new_count += 1
            print(f'{len(stocks)}只')
        time.sleep(0.3)

    json.dump(cache, open(CACHE_PATH, 'w'), ensure_ascii=False)
    print(f'\n✅ 缓存: {len(cache)}个题材, 新增{new_count}')


if __name__ == '__main__':
    if len(sys.argv) > 1:
        cache = {}
        if os.path.exists(CACHE_PATH):
            cache = json.load(open(CACHE_PATH))
        for name in sys.argv[1:]:
            print(f'{name}...', end=' ', flush=True)
            stocks = fetch_one(name)
            if stocks:
                cache[name] = stocks
                print(f'{len(stocks)}只')
            time.sleep(0.3)
        json.dump(cache, open(CACHE_PATH, 'w'), ensure_ascii=False)
    else:
        main()
```

- [ ] **步骤 2：测试拉取**

```bash
python3 scripts/build_theme_holdings_cache.py 芯片概念
```

- [ ] **步骤 3：Commit**

```bash
git add scripts/build_theme_holdings_cache.py data/theme_holdings.json
git commit -m "feat: 题材成分股缓存模块"
```

---

### 任务 2：漏斗数据构建模块

**文件：**
- 创建：`scripts/build_funnel_cards.py`

- [ ] **步骤 1：编写数据构建脚本**

```python
#!/usr/bin/env python3
"""四级漏斗卡片数据构建"""
import json, os, sys

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CATEGORY_ETF_MAP = {
    '半导体': ['半导体', '芯片'], '通信设备': ['通信', '5G'],
    '通信': ['通信', '5G'], '消费电子': ['消费电子'],
    '元件': ['半导体', '芯片'], '其他电子': ['芯片', '5G'],
    '机器人': ['机器人'], '白色家电': ['消费电子'],
    '电机': ['机器人'], '军工': ['军工'],
    '医药': ['医药', '医疗'], '银行': ['银行'], '证券': ['证券'],
    '汽车': ['新能源车'], '电力': ['电力'], '煤炭': ['煤炭'],
    '传媒': ['传媒'], '食品饮料': ['食品饮料', '消费'],
}


def match_best_etf(name, etf_pool):
    keywords = CATEGORY_ETF_MAP.get(name, [name])
    best = None
    for e in etf_pool:
        ename = e.get('name', '')
        for kw in keywords:
            if kw in ename:
                if best is None or e.get('score', 0) > best.get('score', 0):
                    best = e
                break
    return best


def get_trend_leaders(holdings, date_str, top_n=3):
    import sys as _sys
    _sys.path.insert(0, PROJECT)
    from src.enhanced_actions import EnhancedActionGenerator
    gen = EnhancedActionGenerator()
    scored = []
    for s in holdings:
        code = s['code']
        link = f'https://quote.eastmoney.com/sh{code}.html' if code.startswith(('6','9')) \
               else f'https://quote.eastmoney.com/sz{code}.html'
        card = gen._build_card({'code': code, 'name': s['name'], 'link': link},
                               date_str, is_etf=False)
        if card and card.get('score', 0) >= 60:
            scored.append({'code': code, 'name': s['name'], 'score': card['score']})
    scored.sort(key=lambda x: -x['score'])
    return scored[:top_n]


def build(date_str):
    dd = json.load(open(os.path.join(PROJECT, 'dashboard/data/dashboard_data.json')))
    ea = json.load(open(os.path.join(PROJECT, 'dashboard/data',
                     f'enhanced_actions_{date_str}.json')))
    etf_pool = ea.get('etf_cards', []) + ea.get('hot_etf_cards', [])

    etf_holdings = {}
    if os.path.exists(os.path.join(PROJECT, 'data/etf_holdings.json')):
        etf_holdings = json.load(open(os.path.join(PROJECT, 'data/etf_holdings.json')))

    theme_holdings = {}
    if os.path.exists(os.path.join(PROJECT, 'data/theme_holdings.json')):
        theme_holdings = json.load(open(os.path.join(PROJECT, 'data/theme_holdings.json')))

    themes = dd.get('themes', [])
    sectors = [s for s in dd.get('sectors', []) if s.get('state', 0) >= 3]
    sectors.sort(key=lambda x: -x.get('score', 0))

    funnel_cards = []
    for sec in sectors[:3]:
        sname = sec.get('name', '')
        card = {
            'name': sname, 'state': sec.get('state'),
            'state_label': sec.get('state_label', ''),
            'score': sec.get('score', 0),
            'leaders': sec.get('leaders', [])[:3],
        }
        # 板块最佳ETF
        best_etf = match_best_etf(sname, etf_pool)
        if best_etf:
            card['etf'] = {'name': best_etf['name'], 'code': best_etf['code'],
                           'score': best_etf['score'], 'link': best_etf.get('link', '')}
            e_stocks = etf_holdings.get(best_etf['code'], [])
            if e_stocks:
                card['etf']['leaders'] = get_trend_leaders(e_stocks, date_str)
        else:
            card['etf'] = None

        # 趋势最强题材
        keywords = CATEGORY_ETF_MAP.get(sname, [sname])
        related = []
        for t in themes:
            tname = t.get('name', '')
            if t.get('state', 0) < 3:
                continue
            for kw in keywords:
                if kw in tname:
                    related.append(t)
                    break
        related.sort(key=lambda x: -x.get('score', 0))

        card['themes'] = []
        for t in related[:3]:
            tname = t.get('name', '')
            tc = {'name': tname, 'code': t.get('code', ''),
                  'state': t.get('state'), 'score': t.get('score', 0)}
            t_etf = match_best_etf(tname, etf_pool)
            if t_etf:
                tc['etf'] = {'name': t_etf['name'], 'code': t_etf['code'],
                             'score': t_etf['score'], 'link': t_etf.get('link', '')}
                e_stocks = etf_holdings.get(t_etf['code'], [])
                if e_stocks:
                    tc['etf']['leaders'] = get_trend_leaders(e_stocks, date_str)
            else:
                tc['etf'] = None
            th_stocks = theme_holdings.get(t.get('code', ''), [])
            tc['leaders'] = get_trend_leaders(th_stocks, date_str) if th_stocks else []
            card['themes'].append(tc)

        funnel_cards.append(card)

    out = os.path.join(PROJECT, 'dashboard/data', f'funnel_cards_{date_str}.json')
    json.dump({'date': date_str, 'cards': funnel_cards}, open(out, 'w'),
              ensure_ascii=False, indent=2)
    print(f'✅ {date_str}: {len(funnel_cards)}板块')
    for c in funnel_cards:
        print(f'  {c["name"]}: ETF={c.get(\"etf\",{}).get(\"name\",\"无\")} 题材={len(c[\"themes\"])}个')


if __name__ == '__main__':
    ds = sys.argv[1] if len(sys.argv) > 1 else None
    if not ds:
        dd = json.load(open(os.path.join(PROJECT, 'dashboard/data/dashboard_data.json')))
        ds = dd.get('date', '')
    build(ds)
```

- [ ] **步骤 2：测试**

```bash
python3 scripts/build_theme_holdings_cache.py 芯片概念 第三代半导体 光刻机
python3 scripts/build_funnel_cards.py 2026-06-10
python3 -c "
import json
d=json.load(open('dashboard/data/funnel_cards_2026-06-10.json'))
for c in d['cards']:
    print(f'{c[\"name\"]}: etf={bool(c[\"etf\"])} themes={len(c[\"themes\"])}')
"
```

- [ ] **步骤 3：Commit**

```bash
git add scripts/build_funnel_cards.py
git commit -m "feat: 四级漏斗数据构建模块"
```

---

### 任务 3：漏斗面板渲染模块

**文件：**
- 创建：`scripts/render_funnel_panel.py`

- [ ] **步骤 1：编写渲染脚本**

```python
#!/usr/bin/env python3
"""四级漏斗面板渲染"""
import json, os, sys

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def render_card(c):
    h = ''
    sc = {4: '#26a69a', 3: '#42a5f5'}.get(c.get('state', 0), '#8b949e')
    h += f'<div style="background:#161b22;border:2px solid {sc};border-radius:8px;padding:12px;margin-bottom:12px">'
    h += f'<div style="font-size:14px;font-weight:700;color:#e6edf3;margin-bottom:6px">'
    h += f'🔥 {c["name"]} <span style="font-size:11px;color:{sc}">{c.get("state_label","")} {c["score"]}分</span></div>'

    etf = c.get('etf')
    if etf:
        h += f'<div style="font-size:11px;margin:4px 0">📊 最佳ETF: <a href="{etf.get("link","#")}" target="_blank" style="color:#f59e0b;text-decoration:none">{etf["name"]}</a> <span style="color:#8b949e">({etf["score"]:.0f}分)</span>'
        if etf.get('leaders'):
            names = ' '.join(l['name'] for l in etf['leaders'][:3])
            h += f' <span style="color:#8b949e;font-size:10px">└ {names}</span>'
        h += '</div>'

    leaders = c.get('leaders', [])
    if leaders:
        names = ' '.join(l.get('name', l.get('code', '')) for l in leaders[:3])
        h += f'<div style="font-size:11px;margin:4px 0;color:#4ade80">🏆 板块龙头: {names}</div>'

    h += '<div style="border-top:1px solid #21262d;margin:8px 0"></div>'

    themes = c.get('themes', [])
    if themes:
        h += '<div style="font-size:10px;color:#8b949e;margin-bottom:4px">🔗 趋势最强题材:</div>'
        for t in themes:
            tc = {4: '#26a69a', 3: '#42a5f5'}.get(t.get('state', 0), '#8b949e')
            h += f'<div style="margin:4px 0 4px 12px;font-size:11px">├ <span style="color:{tc}">{t["name"]}</span> <span style="color:#8b949e;font-size:10px">({t["score"]}分)</span>'
            t_etf = t.get('etf')
            if t_etf:
                h += f' | 📊 <a href="{t_etf.get("link","#")}" target="_blank" style="color:#f59e0b;text-decoration:none;font-size:10px">{t_etf["name"]}</a>'
                if t_etf.get('leaders'):
                    names = ' '.join(l['name'] for l in t_etf['leaders'][:2])
                    h += f' <span style="color:#8b949e;font-size:9px">└{names}</span>'
            t_leaders = t.get('leaders', [])
            if t_leaders:
                names = ' '.join(l.get('name', '') for l in t_leaders[:3])
                h += f' | 🏆 <span style="color:#4ade80;font-size:10px">{names}</span>'
            h += '</div>'

    h += '</div>'
    return h


def inject(dash_path, date_str):
    fc_path = os.path.join(PROJECT, 'dashboard/data', f'funnel_cards_{date_str}.json')
    if not os.path.exists(fc_path):
        print(f'  ⚠️ no funnel_cards')
        return False
    fc = json.load(open(fc_path))
    cards = fc.get('cards', [])
    if not cards:
        return False

    panel = '<div class="panel" style="margin:10px 20px 12px;border:2px solid #a371f7;border-radius:10px;padding:16px;background:linear-gradient(135deg,rgba(163,113,247,0.08),rgba(163,113,247,0.02))">'
    panel += '<h2 style="color:#a371f7;margin-bottom:8px;font-size:16px">🔽 四级漏斗穿透 — Top3强势板块</h2>'
    for c in cards:
        panel += render_card(c)
    panel += '</div>'

    h = open(dash_path).read()
    marker = '<div class="panel"><h2 style="color:#42a5f5">🔍 焦点板块'
    idx = h.find(marker)
    if idx < 0:
        print('  ❌ no marker')
        return False
    h = h[:idx] + panel + h[idx:]
    open(dash_path, 'w').write(h)
    print(f'  ✅ {date_str}: 漏斗面板 {len(cards)}张卡')
    return True


if __name__ == '__main__':
    ds = sys.argv[1] if len(sys.argv) > 1 else None
    if not ds:
        dd = json.load(open(os.path.join(PROJECT, 'dashboard/data/dashboard_data.json')))
        ds = dd.get('date', '')
    dash = os.path.join(PROJECT, 'dashboard', f'trend_dashboard_{ds}.html')
    inject(dash, ds)
```

- [ ] **步骤 2：测试渲染**

```bash
python3 scripts/render_funnel_panel.py 2026-06-10
python3 scripts/build_nav_index.py
python3 -c "
h=open('dashboard/trend_dashboard_2026-06-10.html').read()
assert '四级漏斗' in h
assert '趋势最强题材' in h
print('✅')
"
```

- [ ] **步骤 3：Commit**

```bash
git add scripts/render_funnel_panel.py dashboard/trend_dashboard_2026-06-10.html dashboard/index.html
git commit -m "feat: 四级漏斗面板渲染模块"
```

---

### 任务 4：端到端验证

- [ ] **步骤 1：完整构建序列**

```bash
python3 scripts/build_final.py
python3 scripts/render_action_panel.py 2026-06-10
python3 scripts/build_funnel_cards.py 2026-06-10
python3 scripts/render_funnel_panel.py 2026-06-10
python3 scripts/build_nav_index.py
```

- [ ] **步骤 2：全断言**

```bash
python3 -c "
h=open('dashboard/trend_dashboard_2026-06-10.html').read()
for tag in ['四级漏斗','趋势最强题材','📋 稳健推荐','🔥 强势追踪','🏆龙头','🔍 焦点板块','widget-details']:
    assert tag in h, f'MISSING: {tag}'
print('✅ 全部通过')
"
```

- [ ] **步骤 3：打开浏览器**

```bash
open http://localhost:8765/index.html
```

- [ ] **步骤 4：Commit**

```bash
git add . && git commit -m "chore: 端到端验证通过"
```
