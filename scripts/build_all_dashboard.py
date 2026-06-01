#!/usr/bin/env python3
"""完整四层漏斗Dashboard — 主线 + 翻转关注 + 全板块 + 题材 + 个股"""
import json, os

with open("dashboard/data/dashboard_data.json") as fh:
    data = json.load(fh)

date_str = data["date"]
ov = data["overview"]
funnel = data["funnel"]
sectors = data["sectors"]
themes = data.get("themes", [])
stocks = data.get("stocks", [])
mainline = data.get("mainline", [])
reversal = data.get("reversal_watch", {"sectors":[], "stocks":[]})

def state_badge(state, label):
    colors = {1:("rgba(110,118,129,0.2)","#b0b5c0"),2:("rgba(110,118,129,0.25)","#b0b5c0"),3:("rgba(66,165,245,0.25)","#64b5f6"),4:("#238636","#fff"),5:("rgba(255,112,67,0.2)","#ff8a65"),"3'":("rgba(218,54,51,0.2)","#ef5350")}
    bg,fg=colors.get(state,("#6e7681","#b0b5c0"))
    return f'<span style="display:inline-block;padding:2px 10px;border-radius:12px;font-size:12px;font-weight:700;background:{bg};color:{fg};white-space:nowrap">{label}</span>'

def cond_dot(p): return f'<span style="color:{"#26a69a" if p else "#ef5350"};font-size:14px">{"●" if p else "○"}</span>'

def score_bar(s):
    c="#26a69a" if s>=70 else "#d29922" if s>=40 else "#6e7681"
    return f'<div style="display:flex;align-items:center;gap:6px"><span style="font-weight:700;font-size:12px;color:{c}">{s}</span><div style="height:4px;width:50px;background:#21262d;border-radius:2px"><div style="height:100%;width:{min(s,100)}%;background:{c};border-radius:2px"></div></div></div>'

def pct(v): return f"{'+' if v>=0 else ''}{v:.1f}%" if isinstance(v,(int,float)) else "N/A"
def prc(v): return f"{v:,.2f}" if isinstance(v,(int,float)) else "N/A"

html = '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>趋势跟随交易系统</title>'
html += '<style>*{margin:0;padding:0;box-sizing:border-box}body{background:#0d1117;color:#e6edf3;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;font-size:13px}.header{background:#161b22;border-bottom:1px solid #30363d;padding:16px 24px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px}.header h1{font-size:20px;background:linear-gradient(90deg,#58a6ff,#3fb950);-webkit-background-clip:text;-webkit-text-fill-color:transparent}.health{padding:6px 16px;border-radius:20px;font-size:13px;font-weight:700}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px;padding:16px 24px}.card{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:12px;text-align:center}.card .val{font-size:24px;font-weight:800}.card .lbl{font-size:10px;color:#8b949e;margin-top:3px}.funnel{margin:8px 24px 16px;padding:14px;background:linear-gradient(135deg,rgba(88,166,255,0.05),rgba(88,166,255,0.01));border:1px solid rgba(88,166,255,0.2);border-radius:10px}.funnel h2{font-size:14px;color:#58a6ff;margin-bottom:10px}.funnel-steps{display:flex;align-items:center;gap:6px;flex-wrap:wrap}.fstep{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:8px 12px;text-align:center;min-width:80px}.fstep .n{font-size:20px;font-weight:800}.fstep .t{font-size:10px;margin-top:2px}.arrow{color:#8b949e;font-size:16px}.highlight{margin:8px 24px 16px;padding:14px;border-radius:10px}.highlight h2{font-size:15px;margin-bottom:10px}.hl-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:10px}.hl-card{background:#1c2128;border-radius:8px;padding:12px;position:relative}.hl-card .tag{position:absolute;top:8px;right:10px;font-size:11px;font-weight:700}.hl-card .name{font-size:14px;font-weight:700;margin-bottom:4px}.hl-card .name a{text-decoration:none}.hl-card .name a:hover{text-decoration:underline}.hl-card .detail{font-size:11px;color:#8b949e;line-height:1.6}.tabs{display:flex;gap:0;margin:0 24px;border-bottom:2px solid #30363d}.tab-btn{padding:8px 16px;border:none;background:none;color:#8b949e;font-size:13px;font-weight:600;cursor:pointer;border-bottom:2px solid transparent;margin-bottom:-2px}.tab-btn.active{color:#58a6ff;border-bottom-color:#58a6ff}.section{padding:0 24px 24px}.table-wrap{overflow-x:auto;border:1px solid #30363d;border-radius:8px}table{width:100%;border-collapse:collapse;font-size:13px;min-width:900px}thead th{background:#21262d;padding:8px 8px;text-align:left;font-size:11px;color:#8b949e;border-bottom:2px solid #30363d;font-weight:600;white-space:nowrap;position:sticky;top:0;z-index:10}tbody td{padding:5px 8px;border-bottom:1px solid #21262d;white-space:nowrap}tbody tr:hover{background:rgba(88,166,255,0.04)}tr.mainline-row{background:linear-gradient(90deg,rgba(210,153,34,0.06),transparent);border-left:3px solid #d29922}tr.reversal-row{background:linear-gradient(90deg,rgba(66,165,245,0.06),transparent);border-left:3px solid #58a6ff}.detail-row td{padding:14px 20px;background:#161b22;border-bottom:1px solid #30363d}.dgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:10px}.dbox{background:#0d1117;border:1px solid #30363d;border-radius:6px;padding:10px}.dbox h4{font-size:11px;color:#8b949e;text-transform:uppercase;margin-bottom:6px}.dbox p{font-size:12px;line-height:1.6}a{color:#58a6ff;text-decoration:none;font-weight:600}a:hover{text-decoration:underline}.search{margin:12px 24px}.search input{width:100%;padding:8px 14px;background:#161b22;border:1px solid #30363d;border-radius:6px;color:#e6edf3;font-size:13px;outline:none}.search input:focus{border-color:#58a6ff}.footer{padding:14px 24px;border-top:1px solid #30363d;text-align:center;color:#8b949e;font-size:11px}.hidden{display:none}.arrow-up{color:#39d353}.arrow-down{color:#da3633}.empty{text-align:center;padding:24px;color:#8b949e}</style></head><body>'

html += f'<div class="header"><div><h1>趋势跟随交易系统</h1><div style="font-size:11px;color:#8b949e">Dashboard · {date_str} · 板块→题材→个股 三层漏斗 · 主线+翻转双关注</div></div><div style="display:flex;align-items:center;gap:12px"><span style="color:#8b949e">市场:</span><span class="health" style="padding:6px 16px;border-radius:20px;font-size:13px;font-weight:700'

if ov['market_health'] == '强势':
    html += ';background:rgba(35,134,54,0.15);color:#39d353;border:1px solid #238636'
elif ov['market_health'] == '正常':
    html += ';background:rgba(210,153,34,0.15);color:#d29922;border:1px solid #d29922'
else:
    html += ';background:rgba(218,54,51,0.15);color:#da3633;border:1px solid #da3633'
html += f'">{ov["market_health"]}</span></div></div>'

# Cards
html += '<div class="cards">'
cards = [
    (str(ov['total_sectors']), '全板块', '#8b949e'),
    (str(ov['uptrend_sectors']), '上涨(3/4/5)', '#58a6ff'),
    (str(ov['mainline_sectors']), '★主线(全满)', '#d29922'),
    (str(ov.get('reversal_sectors',0)), '🔵翻转(状态3)', '#42a5f5'),
    (str(ov['active_themes']), '活跃题材', '#a371f7'),
    (str(ov['trend_stocks']), '趋势个股', '#3fb950'),
]
for val, lbl, color in cards:
    html += f'<div class="card"><div class="val" style="color:{color}">{val}</div><div class="lbl">{lbl}</div></div>'
html += '</div>'

# Funnel
html += '<div class="funnel"><h2>漏斗筛选</h2><div class="funnel-steps">'
for i, layer in enumerate(funnel["layers"]):
    html += f'<div class="fstep"><div class="n" style="color:{layer["color"]}">{layer["count"]}</div><div class="t" style="color:{layer["color"]}">{layer["name"]}</div></div>'
    if i < len(funnel["layers"]) - 1:
        html += '<div class="arrow">→</div>'
html += '</div></div>'

# Mainline
if mainline:
    html += '<div class="highlight" style="border:2px solid rgba(210,153,34,0.5);background:linear-gradient(135deg,rgba(210,153,34,0.08),rgba(210,153,34,0.02))"><h2 style="color:#d29922">★ 市场主线板块（状态4 + 三条件全满 + MA20上方）</h2><div class="hl-grid">'
    for s in mainline:
        c = s['conditions']
        html += f'<div class="hl-card" style="border:1px solid rgba(210,153,34,0.4)"><div class="tag" style="color:#d29922">★ 主线</div><div class="name"><a href="{s["link"]}" target="_blank" style="color:#d29922">{s["name"]}</a> <span style="font-size:11px;color:#8b949e">{s["code"]}</span></div><div class="detail">得分:{s["score"]} | 仓位:{s["position"]*100:.0f}%<br>结构:{c["structure"]["detail"]}<br>量能:{c["volume"]["detail"]}<br>持续性:{c["persistence"]["detail"]}<br>MA20:{pct(s.get("ma_deviation",0))} | 20日:{pct(s.get("ret_20d",0))}</div></div>'
    html += '</div></div>'
else:
    html += '<div class="highlight" style="border:1px solid rgba(110,118,129,0.3);background:rgba(110,118,129,0.02)"><h2 style="color:#8b949e">★ 市场主线板块</h2><p style="color:#8b949e;font-size:13px">当前无板块同时满足状态4+三条件全满+MA20上方。市场弱势，耐心等待。</p></div>'

# Reversal Watch
rs = reversal["sectors"]
rst = reversal["stocks"]
if rs or rst:
    html += '<div class="highlight" style="border:2px solid rgba(66,165,245,0.4);background:linear-gradient(135deg,rgba(66,165,245,0.06),rgba(66,165,245,0.01))"><h2 style="color:#42a5f5">🔵 翻转关注（状态3 — 随时可能开启行情，盈亏比最佳位置）</h2>'
    if rs:
        html += '<p style="font-size:12px;color:#8b949e;margin-bottom:8px">板块</p><div class="hl-grid">'
        for s in rs:
            c = s['conditions']
            html += f'<div class="hl-card" style="border:1px solid rgba(66,165,245,0.3)"><div class="tag" style="color:#42a5f5">状态3</div><div class="name"><a href="{s["link"]}" target="_blank" style="color:#58a6ff">{s["name"]}</a> <span style="font-size:11px;color:#8b949e">{s["code"]}</span></div><div class="detail">得分:{s["score"]} | 仓位:{s["position"]*100:.0f}%<br>结构:{c["structure"]["detail"]}<br>量能:{c["volume"]["detail"]}<br>持续性:{c["persistence"]["detail"]}<br>MA20:{pct(s.get("ma_deviation",0))} | 20日:{pct(s.get("ret_20d",0))}</div></div>'
        html += '</div>'
    if rst:
        html += '<p style="font-size:12px;color:#8b949e;margin:8px 0">个股</p><div class="hl-grid">'
        for s in rst:
            c = s['conditions']
            html += f'<div class="hl-card" style="border:1px solid rgba(66,165,245,0.3)"><div class="tag" style="color:#42a5f5">状态3</div><div class="name"><a href="{s["link"]}" target="_blank" style="color:#58a6ff">{s["name"]}</a> <span style="font-size:11px;color:#8b949e">{s["code"]}</span></div><div class="detail">得分:{s["score"]} | 现价:{prc(s.get("price"))} | 止损:{prc(s.get("stop_loss"))}<br>结构:{c["structure"]["detail"]}<br>量能:{c["volume"]["detail"]}<br>持续性:{c["persistence"]["detail"]}</div></div>'
        html += '</div>'
    html += '</div>'

# Tabs
html += '<div class="tabs"><button class="tab-btn active" onclick="switchTab(\'sectors\')">板块 (90)</button><button class="tab-btn" onclick="switchTab(\'themes\')">题材 (20)</button><button class="tab-btn" onclick="switchTab(\'stocks\')">个股</button></div>'
html += '<div class="search"><input type="text" placeholder="搜索..." oninput="var q=this.value.toLowerCase();document.querySelectorAll(\'tr[data-search]\').forEach(function(r){r.style.display=r.getAttribute(\'data-search\').includes(q)?\'\':\'none\'})"></div>'

# Build tables
def build_table(items, item_type, cols, detail_fn):
    h = '<div class="table-wrap"><table><thead><tr>'
    for col in cols: h += f'<th>{col}</th>'
    h += '</tr></thead><tbody>'
    for i, s in enumerate(items):
        c = s['conditions']
        rc = 'mainline-row' if s.get('is_mainline') else 'reversal-row' if s['state'] == 3 else ''
        st = (s['name'] + ' ' + s['code'] + ' ' + s['state_label']).lower()
        h += f'<tr class="{rc}" data-search="{st}" onclick="var d=document.getElementById(\'d{item_type}{i}\');d.classList.toggle(\'open\');d.style.display=d.classList.contains(\'open\')?\'\':\'none\'">'
        prefix = '★ ' if s.get('is_mainline') else ('🔵 ' if s['state'] == 3 else '')
        h += f'<td><a href="{s["link"]}" target="_blank" onclick="event.stopPropagation()" style="font-weight:600">{prefix}{s["name"]}</a></td>'
        h += f'<td style="color:#8b949e;font-size:12px">{s["code"]}</td>'
        h += f'<td>{state_badge(s["state"], s["state_label"])}</td>'
        h += f'<td>{score_bar(s["score"])}</td>'
        h += f'<td>{cond_dot(c["structure"]["pass"])}</td><td>{cond_dot(c["volume"]["pass"])}</td><td>{cond_dot(c["persistence"]["pass"])}</td>'
        if item_type != "stock":
            h += f'<td class="{"arrow-up" if s.get("ma_deviation",0)>=0 else "arrow-down"}">{pct(s.get("ma_deviation",0))}</td>'
            h += f'<td class="{"arrow-up" if s.get("ret_20d",0)>=0 else "arrow-down"}">{pct(s.get("ret_20d",0))}</td>'
            h += f'<td>{s.get("vol_ratio","N/A")}</td><td>{s.get("max_consecutive_yang",0)}天</td>'
        else:
            h += f'<td>{prc(s.get("price"))}</td><td style="color:#da3633">{prc(s.get("stop_loss"))}</td>'
        h += f'<td style="font-weight:600">{s["position"]*100:.0f}%</td></tr>'
        h += detail_fn(i, s)
    h += '</tbody></table></div>'
    return h

def sdetail(i, s):
    c = s['conditions']
    r = f'<tr class="detail-row" id="dsector{i}" style="display:none"><td colspan="12"><div class="dgrid">'
    r += f'<div class="dbox"><h4>A 结构判断</h4><p style="color:{"#39d353" if c["structure"]["pass"] else "#da3633"}">{"✅" if c["structure"]["pass"] else "❌"} {c["structure"]["detail"]}</p></div>'
    r += f'<div class="dbox"><h4>B 量能判断</h4><p style="color:{"#39d353" if c["volume"]["pass"] else "#da3633"}">{"✅" if c["volume"]["pass"] else "❌"} {c["volume"]["detail"]}</p></div>'
    r += f'<div class="dbox"><h4>C 持续性判断</h4><p style="color:{"#39d353" if c["persistence"]["pass"] else "#da3633"}">{"✅" if c["persistence"]["pass"] else "❌"} {c["persistence"]["detail"]}</p></div>'
    r += '<div class="dbox"><h4>关键技术位</h4><p>'
    if s.get('prev_high'): r += f'前高: {prc(s["prev_high"]["price"])} ({s["prev_high"]["date"]})<br>'
    if s.get('prev_low'): r += f'前低: {prc(s["prev_low"]["price"])} ({s["prev_low"]["date"]})<br>'
    r += f'MA20: {prc(s.get("ma20"))} | 现价: {prc(s.get("price"))}<br>阳{s.get("yang",0)}/阴{s.get("yin",0)} | 连阳{s.get("max_consecutive_yang",0)}天</p></div>'
    r += '<div class="dbox"><h4>判定原因</h4><p>' + '<br>'.join('• '+x for x in s.get('reasons',['无'])) + '</p></div>'
    r += '</div></td></tr>'
    return r

def stock_detail(i, s):
    c = s['conditions']
    r = f'<tr class="detail-row" id="dstock{i}" style="display:none"><td colspan="10"><div class="dgrid">'
    r += f'<div class="dbox"><h4>A 结构</h4><p style="color:{"#39d353" if c["structure"]["pass"] else "#da3633"}">{"✅" if c["structure"]["pass"] else "❌"} {c["structure"]["detail"]}</p></div>'
    r += f'<div class="dbox"><h4>B 量能</h4><p style="color:{"#39d353" if c["volume"]["pass"] else "#da3633"}">{"✅" if c["volume"]["pass"] else "❌"} {c["volume"]["detail"]}</p></div>'
    r += f'<div class="dbox"><h4>C 持续性</h4><p style="color:{"#39d353" if c["persistence"]["pass"] else "#da3633"}">{"✅" if c["persistence"]["pass"] else "❌"} {c["persistence"]["detail"]}</p></div>'
    r += f'<div class="dbox"><h4>止损</h4><p style="font-size:18px;font-weight:700;color:#da3633">{prc(s.get("stop_loss"))}</p><p style="font-size:11px;color:#8b949e">前低-0.5%</p></div>'
    r += f'<div class="dbox"><h4>来源</h4><p>漏斗第三层筛选<br>状态:{s["state_label"]}<br>仓位:{s["position"]*100:.0f}%</p></div></div></td></tr>'
    return r

# Sector table
html += '<div class="section" id="tab-sectors"><h2 style="font-size:15px;margin:16px 0 8px;color:#e6edf3">板块状态表 <span style="color:#8b949e;font-weight:400;font-size:11px">★主线 🔵翻转 灰=回避</span></h2>'
html += build_table(sectors, "sector", ['名称','代码','状态','得分','A','B','C','MA20偏离','20日','量比','连阳','仓位'], sdetail)
html += '</div>'

# Theme table
html += '<div class="section hidden" id="tab-themes"><h2 style="font-size:15px;margin:16px 0 8px;color:#e6edf3">题材分析</h2>'
html += build_table(themes, "theme", ['名称','代码','状态','得分','A','B','C','MA20偏离','20日','量比','连阳','仓位'], sdetail) if themes else '<div class="empty">暂无题材数据</div>'
html += '</div>'

# Stock table
html += '<div class="section hidden" id="tab-stocks"><h2 style="font-size:15px;margin:16px 0 8px;color:#e6edf3">趋势个股 <span style="color:#8b949e;font-weight:400;font-size:11px">仅状态3/4/5</span></h2>'
html += build_table(stocks, "stock", ['名称','代码','状态','得分','A','B','C','现价','止损','仓位'], stock_detail)
html += '</div>'

html += f'<div class="footer">趋势跟随交易系统 | akshare+baostock | {date_str} | ★主线=状态4全满 🔵翻转=状态3临界 | 免责声明:仅供辅助参考</div>'
html += '<script>function switchTab(t){document.querySelectorAll(".tab-btn").forEach(function(b){b.classList.remove("active")});event.target.classList.add("active");["sectors","themes","stocks"].forEach(function(id){document.getElementById("tab-"+id).classList.add("hidden")});document.getElementById("tab-"+t).classList.remove("hidden")}document.addEventListener("keydown",function(e){if(e.key==="Escape")document.querySelectorAll(".detail-row").forEach(function(r){r.classList.remove("open");r.style.display="none"})})</script></body></html>'

for path in ["dashboard/index.html", f"dashboard/trend_dashboard_{date_str}.html"]:
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✅ {path} ({os.path.getsize(path)/1024:.1f}KB)")
