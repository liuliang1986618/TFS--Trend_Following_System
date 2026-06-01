#!/usr/bin/env python3
"""生成纯静态预渲染Dashboard HTML — 零JavaScript依赖。所有数据直接写入HTML。"""
import json, os

PROJECT_ROOT = "/Users/liuliang19/Desktop/project/trend_following_system"

with open(f"{PROJECT_ROOT}/dashboard/data/dashboard_data.json") as f:
    data = json.load(f)

date_str = data["date"]
overview = data["overview"]
sectors = data["sectors"]
stocks = data["stocks"]
mainline = data["mainline"]

def state_badge(state, label):
    colors = {
        1: ("rgba(110,118,129,0.2)", "#b0b5c0"),
        2: ("rgba(110,118,129,0.25)", "#b0b5c0"),
        3: ("rgba(66,165,245,0.2)", "#64b5f6"),
        4: ("#238636", "#fff"),
        5: ("rgba(255,112,67,0.2)", "#ff8a65"),
        "3'": ("rgba(218,54,51,0.2)", "#ef5350"),
    }
    bg, fg = colors.get(state, ("#6e7681","#b0b5c0"))
    return f'<span style="display:inline-block;padding:2px 10px;border-radius:12px;font-size:12px;font-weight:700;background:{bg};color:{fg};white-space:nowrap">{label}</span>'

def cond_dot(passed):
    return f'<span style="color:{"#26a69a" if passed else "#ef5350"};font-size:14px">{"●" if passed else "○"}</span>'

def score_bar(score):
    color = "#26a69a" if score >= 70 else "#d29922" if score >= 40 else "#6e7681"
    return f'<div style="display:flex;align-items:center;gap:6px"><span style="font-weight:700;font-size:12px;color:{color}">{score}</span><div style="height:4px;width:50px;background:#21262d;border-radius:2px"><div style="height:100%;width:{score}%;background:{color};border-radius:2px"></div></div></div>'

def pct_str(v):
    if not isinstance(v, (int, float)):
        return "N/A"
    return f"{'+' if v >= 0 else ''}{v:.1f}%"

def price_str(v):
    if not isinstance(v, (int, float)):
        return "N/A"
    return f"{v:,.2f}"

html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>趋势跟随交易系统 — {date_str}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#0d1117;color:#e6edf3;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;font-size:13px}}
.header{{background:#161b22;border-bottom:1px solid #30363d;padding:16px 24px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px}}
.header h1{{font-size:20px;background:linear-gradient(90deg,#58a6ff,#3fb950);-webkit-background-clip:text;-webkit-text-fill-color:transparent}}
.header .sub{{font-size:12px;color:#8b949e}}
.health{{padding:6px 16px;border-radius:20px;font-size:13px;font-weight:700}}
.health.weak{{background:rgba(218,54,51,0.15);color:#da3633;border:1px solid #da3633}}
.health.normal{{background:rgba(210,153,34,0.15);color:#d29922;border:1px solid #d29922}}
.health.strong{{background:rgba(35,134,54,0.15);color:#39d353;border:1px solid #238636}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;padding:16px 24px}}
.card{{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:16px;text-align:center}}
.card .val{{font-size:28px;font-weight:800}}
.card .lbl{{font-size:11px;color:#8b949e;margin-top:4px}}
.green .val{{color:#39d353}}.blue .val{{color:#58a6ff}}.gold .val{{color:#d29922}}.red .val{{color:#da3633}}
.mainline{{margin:0 24px 16px;padding:16px;background:linear-gradient(135deg,rgba(210,153,34,0.08),rgba(210,153,34,0.02));border:2px solid rgba(210,153,34,0.4);border-radius:10px}}
.mainline h2{{font-size:16px;color:#d29922;margin-bottom:12px}}
.ml-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:10px}}
.ml-card{{background:#1c2128;border:1px solid rgba(210,153,34,0.4);border-radius:8px;padding:14px;position:relative}}
.ml-card .star{{position:absolute;top:8px;right:10px;color:#d29922;font-size:11px;font-weight:700}}
.ml-card .name{{font-size:15px;font-weight:700;margin-bottom:8px}}
.ml-card .name a{{color:#d29922;text-decoration:none}}
.ml-card .name a:hover{{text-decoration:underline}}
.ml-card .info{{font-size:11px;color:#8b949e;line-height:1.7}}
.section{{padding:0 24px 24px}}
.section h2{{font-size:16px;margin:24px 0 12px;color:#e6edf3}}
.table-wrap{{overflow-x:auto;border:1px solid #30363d;border-radius:8px}}
table{{width:100%;border-collapse:collapse;font-size:13px;min-width:1000px}}
thead th{{background:#21262d;padding:10px 8px;text-align:left;font-size:11px;color:#8b949e;border-bottom:2px solid #30363d;font-weight:600;white-space:nowrap;position:sticky;top:0;z-index:10}}
tbody td{{padding:6px 8px;border-bottom:1px solid #21262d;white-space:nowrap}}
tbody tr:hover{{background:rgba(88,166,255,0.04)}}
tr.mainline-row{{background:linear-gradient(90deg,rgba(210,153,34,0.06),transparent);border-left:3px solid #d29922}}
.detail-row td{{padding:16px 24px;background:#161b22;border-bottom:1px solid #30363d}}
.detail-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px}}
.dbox{{background:#0d1117;border:1px solid #30363d;border-radius:6px;padding:12px}}
.dbox h4{{font-size:11px;color:#8b949e;text-transform:uppercase;margin-bottom:8px;letter-spacing:0.5px}}
.dbox p{{font-size:13px;line-height:1.6}}
a{{color:#58a6ff;text-decoration:none;font-weight:600}}
a:hover{{text-decoration:underline}}
.search{{margin:12px 24px}}
.search input{{width:100%;padding:8px 14px;background:#161b22;border:1px solid #30363d;border-radius:6px;color:#e6edf3;font-size:13px;outline:none}}
.search input:focus{{border-color:#58a6ff}}
.footer{{padding:16px 24px;border-top:1px solid #30363d;text-align:center;color:#8b949e;font-size:11px}}
.hidden{{display:none}}
.tabs{{display:flex;gap:0;margin:0 24px 16px;border-bottom:2px solid #30363d}}
.tab-btn{{padding:8px 16px;border:none;background:none;color:#8b949e;font-size:13px;font-weight:600;cursor:pointer;border-bottom:2px solid transparent;margin-bottom:-2px}}
.tab-btn.active{{color:#58a6ff;border-bottom-color:#58a6ff}}
.arrow-up{{color:#39d353}}.arrow-down{{color:#da3633}}
</style>
</head>
<body>

<div class="header">
<div><h1>📊 趋势跟随交易系统</h1><div class="sub">Dashboard · {date_str} · 生成 {data["generated_at"][:19]}</div></div>
<div style="display:flex;align-items:center;gap:12px">
<span style="color:#8b949e">市场健康度:</span>
<span class="health {overview['market_health']}">{overview['market_health']}</span>
</div></div>

<div class="cards">
<div class="card green"><div class="val">{overview['uptrend_sectors']}</div><div class="lbl">上涨板块 (状态3/4/5)</div></div>
<div class="card gold"><div class="val">{overview['mainline_sectors']}</div><div class="lbl">★ 主线板块 (三条件全满)</div></div>
<div class="card green"><div class="val">{overview['state4_sectors']}</div><div class="lbl">状态4 上涨趋势</div></div>
<div class="card blue"><div class="val">{overview['trend_stocks']}</div><div class="lbl">趋势个股</div></div>
<div class="card blue"><div class="val">{overview['state4_stocks']}</div><div class="lbl">状态4个股</div></div>
<div class="card"><div class="val" style="color:#8b949e">{overview['total_sectors']}</div><div class="lbl">全市场板块</div></div>
</div>
'''

# 主线板块
if mainline:
    html += '<div class="mainline"><h2>⭐ 市场主线板块</h2><div class="ml-grid">'
    for s in mainline:
        conds = s['conditions']
        html += f'''<div class="ml-card"><div class="star">★ 主线</div>
<div class="name"><a href="{s['link']}" target="_blank">{s['name']}</a> <span style="font-size:11px;color:#8b949e">{s['code']}</span></div>
<div class="info">
得分: {s['score']} | 仓位: {s['position']*100:.0f}%<br>
A结构: {conds['structure']['detail']}<br>
B量能: {conds['volume']['detail']}<br>
C持续性: {conds['persistence']['detail']}<br>
MA20偏离: {pct_str(s.get('ma_deviation',0))} | 近20日: {pct_str(s.get('ret_20d',0))}
</div></div>'''
    html += '</div></div>'

# Tabs
html += '<div class="tabs"><button class="tab-btn active" onclick="document.getElementById(\'tab-sectors\').classList.remove(\'hidden\');document.getElementById(\'tab-stocks\').classList.add(\'hidden\');this.classList.add(\'active\');this.nextElementSibling.classList.remove(\'active\')">📋 板块分析 (90)</button><button class="tab-btn" onclick="document.getElementById(\'tab-stocks\').classList.remove(\'hidden\');document.getElementById(\'tab-sectors\').classList.add(\'hidden\');this.classList.add(\'active\');this.previousElementSibling.classList.remove(\'active\')">📈 个股分析 (39)</button></div>'

# Search
html += '<div class="search"><input type="text" placeholder="搜索板块或个股..." oninput="var q=this.value.toLowerCase();document.querySelectorAll(\'tr[data-search]\').forEach(r=>{r.style.display=r.getAttribute(\'data-search\').includes(q)?\'\':\'none\'});document.querySelectorAll(\'.detail-row\').forEach(r=>{r.classList.remove(\'open\');r.style.display=\'none\'})"></div>'

# 板块表格
html += '<div class="section" id="tab-sectors"><div class="table-wrap"><table><thead><tr>'
for h in ['板块名称','代码','状态','得分','A结构','B量能','C持续性','MA20偏离','20日涨跌','量比','连阳','仓位']:
    html += f'<th>{h}</th>'
html += '</tr></thead><tbody>'

for i, s in enumerate(sectors):
    conds = s['conditions']
    ml_class = 'mainline-row' if s.get('is_mainline') else ''
    search_text = f"{s['name']} {s['code']} {s['state_label']}".lower()
    html += f'''<tr class="{ml_class}" data-search="{search_text}" onclick="var d=document.getElementById('ds{i}');d.classList.toggle('open');d.style.display=d.classList.contains('open')?'':'none'">
<td><a href="{s['link']}" target="_blank" onclick="event.stopPropagation()" style="font-weight:600">{'★ ' if s.get('is_mainline') else ''}{s['name']}</a></td>
<td style="color:#8b949e;font-size:12px">{s['code']}</td>
<td>{state_badge(s['state'], s['state_label'])}</td>
<td>{score_bar(s['score'])}</td>
<td>{cond_dot(conds['structure']['pass'])}</td>
<td>{cond_dot(conds['volume']['pass'])}</td>
<td>{cond_dot(conds['persistence']['pass'])}</td>
<td class="{'arrow-up' if s.get('ma_deviation',0)>=0 else 'arrow-down'}">{pct_str(s.get('ma_deviation',0))}</td>
<td class="{'arrow-up' if s.get('ret_20d',0)>=0 else 'arrow-down'}">{pct_str(s.get('ret_20d',0))}</td>
<td>{s.get('vol_ratio','N/A')}</td>
<td>{s.get('max_consecutive_yang',0)}天</td>
<td style="font-weight:600">{s['position']*100:.0f}%</td>
</tr>
<tr class="detail-row" id="ds{i}" style="display:none"><td colspan="12"><div class="detail-grid">
<div class="dbox"><h4>📐 条件A: 结构判断</h4><p style="color:{'#39d353' if conds['structure']['pass'] else '#da3633'}">{'✅' if conds['structure']['pass'] else '❌'} {conds['structure']['detail']}</p></div>
<div class="dbox"><h4>📊 条件B: 量能判断</h4><p style="color:{'#39d353' if conds['volume']['pass'] else '#da3633'}">{'✅' if conds['volume']['pass'] else '❌'} {conds['volume']['detail']}</p></div>
<div class="dbox"><h4>⏱ 条件C: 持续性判断</h4><p style="color:{'#39d353' if conds['persistence']['pass'] else '#da3633'}">{'✅' if conds['persistence']['pass'] else '❌'} {conds['persistence']['detail']}</p></div>
<div class="dbox"><h4>📍 关键技术位</h4><p>'''
    if s.get('prev_high'): html += f'前高: {price_str(s["prev_high"]["price"])} ({s["prev_high"]["date"]})<br>'
    if s.get('prev_low'): html += f'前低: {price_str(s["prev_low"]["price"])} ({s["prev_low"]["date"]})<br>'
    html += f'MA20: {price_str(s.get("ma20"))} | 现价: {price_str(s.get("price"))}<br>'
    html += f'阳{s.get("yang",0)}/阴{s.get("yin",0)} | 最长连阳{s.get("max_consecutive_yang",0)}天'
    html += '</p></div><div class="dbox"><h4>💡 判定原因</h4><p>'
    reasons = s.get('reasons', [])
    if reasons:
        for r in reasons:
            html += f'• {r}<br>'
    else:
        html += '三条件自动判定'
    html += f'</p></div></div></td></tr>'

html += '</tbody></table></div></div>'

# 个股表格
html += '<div class="section hidden" id="tab-stocks"><div class="table-wrap"><table><thead><tr>'
for h in ['股票名称','代码','状态','得分','A结构','B量能','C持续性','现价','止损价','MA20偏离','20日涨跌','仓位']:
    html += f'<th>{h}</th>'
html += '</tr></thead><tbody>'

for i, s in enumerate(stocks):
    conds = s['conditions']
    search_text = f"{s['name']} {s['code']} {s['state_label']}".lower()
    html += f'''<tr data-search="{search_text}" onclick="var d=document.getElementById('dt{i}');d.classList.toggle('open');d.style.display=d.classList.contains('open')?'':'none'">
<td><a href="{s['link']}" target="_blank" onclick="event.stopPropagation()" style="font-weight:600">{s['name']}</a></td>
<td style="color:#8b949e;font-size:12px">{s['code']}</td>
<td>{state_badge(s['state'], s['state_label'])}</td>
<td>{score_bar(s['score'])}</td>
<td>{cond_dot(conds['structure']['pass'])}</td>
<td>{cond_dot(conds['volume']['pass'])}</td>
<td>{cond_dot(conds['persistence']['pass'])}</td>
<td>{price_str(s.get('price'))}</td>
<td style="color:#da3633">{price_str(s.get('stop_loss'))}</td>
<td class="{'arrow-up' if s.get('ma_deviation',0)>=0 else 'arrow-down'}">{pct_str(s.get('ma_deviation',0))}</td>
<td class="{'arrow-up' if s.get('ret_20d',0)>=0 else 'arrow-down'}">{pct_str(s.get('ret_20d',0))}</td>
<td style="font-weight:600">{s['position']*100:.0f}%</td>
</tr>
<tr class="detail-row" id="dt{i}" style="display:none"><td colspan="12"><div class="detail-grid">
<div class="dbox"><h4>📐 条件A: 结构</h4><p style="color:{'#39d353' if conds['structure']['pass'] else '#da3633'}">{'✅' if conds['structure']['pass'] else '❌'} {conds['structure']['detail']}</p></div>
<div class="dbox"><h4>📊 条件B: 量能</h4><p style="color:{'#39d353' if conds['volume']['pass'] else '#da3633'}">{'✅' if conds['volume']['pass'] else '❌'} {conds['volume']['detail']}</p></div>
<div class="dbox"><h4>⏱ 条件C: 持续性</h4><p style="color:{'#39d353' if conds['persistence']['pass'] else '#da3633'}">{'✅' if conds['persistence']['pass'] else '❌'} {conds['persistence']['detail']}</p></div>
<div class="dbox"><h4>🛡 止损价格</h4><p style="font-size:18px;font-weight:700;color:#da3633">{price_str(s.get('stop_loss'))}</p><p style="font-size:11px;color:#8b949e">前低下方-0.5%</p></div>
<div class="dbox"><h4>💡 判定原因</h4><p>'''
    reasons = s.get('reasons', [])
    if reasons:
        for r in reasons:
            html += f'• {r}<br>'
    else:
        state_label = s.get('state_label', '')
        html += f'当前状态: {state_label}'
    html += '</p></div></div></td></tr>'

html += '</tbody></table></div></div>'

# Footer
html += f'''
<div class="footer">
趋势跟随交易系统 v1.0 | 数据来源: akshare(同花顺板块) + baostock(个股)<br>
★主线 = 状态4 + 三条件(A结构/B量能/C持续性)全部通过 | {len(sectors)}板块 · {len(stocks)}个股 | {date_str}
</div>

<script>
// 最小化JS: 只做展开/折叠 + tab切换 + 搜索
Array.from(document.querySelectorAll(".detail-row")).forEach(function(r){{r.classList.add("open")}});
</script>
</body></html>'''

# 写入
for path in ["dashboard/index.html", f"dashboard/trend_dashboard_{date_str}.html"]:
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✅ {path} ({os.path.getsize(path)/1024:.1f}KB)")

# 验证
tr_count = html.count('<tr class=')
link_count = html.count('target="_blank"')
jq_count = html.count('10jqka.com.cn')
em_count = html.count('eastmoney.com')
print(f"\n板块行: {tr_count} | 链接: {link_count}个")
print(f"10jqka链接: {jq_count} | 东方财富链接: {em_count}")
