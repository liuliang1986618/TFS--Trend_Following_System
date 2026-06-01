#!/usr/bin/env python3
"""Final dashboard: 1-row overview, expanded cards, leaders with reasons, sector/theme columns, ETFs"""
import json

with open("dashboard/data/dashboard_data.json") as f:
    data = json.load(f)

ov = data["overview"]
focus = [s for s in data["sectors"] if s["state"] in (3,4)]
stocks = data.get("stocks", [])
watching = [s for s in data["sectors"] if s["state"]==2 and s.get("ma_deviation",-99)>-3 and s.get("ret_20d",-99)>-5][:5]

def badge(s,l):
    c={1:("rgba(110,118,129,0.2)","#b0b5c0"),2:("rgba(110,118,129,0.2)","#b0b5c0"),3:("rgba(66,165,245,0.25)","#64b5f6"),4:("#238636","#fff")}
    bg,fg=c.get(s,("#6e7681","#b0b5c0"))
    return '<span style="display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:700;background:%s;color:%s">%s</span>' % (bg,fg,l)
def pct(v): return ("%+.1f%%" % v) if isinstance(v,(int,float)) else "N/A"
def prc(v): return "{:,.2f}".format(v) if isinstance(v,(int,float)) else "N/A"
def cp(p): return "#26a69a" if p else "#ef5350"
def ci(p): return "●" if p else "○"

def card(s, is_ml):
    c = s['conditions']; icon = '★' if is_ml else '🔵'
    bc = 'rgba(210,153,34,0.6)' if is_ml else 'rgba(66,165,245,0.4)'
    h = '<div style="background:#161b22;border:2px solid %s;border-radius:8px;padding:12px">' % bc
    # title
    h += '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">'
    h += '<div style="font-size:14px;font-weight:700">%s <a href="%s" target="_blank" style="color:#e6edf3;text-decoration:none">%s</a> <span style="font-size:10px;color:#8b949e">%s</span></div>' % (icon, s["link"], s["name"], s["code"])
    h += badge(s["state"], s["state_label"])
    h += '</div>'
    # 3 conditions
    h += '<div style="display:flex;gap:12px;font-size:11px;margin-bottom:6px;flex-wrap:wrap">'
    for k,lb in [("structure","A"),("volume","B"),("persistence","C")]:
        p = c[k]["pass"]
        h += '<span style="white-space:nowrap"><span style="color:%s">%s</span> %s: %s</span>' % (cp(p), "✅" if p else "❌", lb, c[k]["detail"])
    h += '</div>'
    # metrics
    h += '<div style="font-size:10px;color:#8b949e">MA20:%s | 20日:%s | 阳%d/阴%d | 连阳%d天 | 仓位:%d%%</div>' % (
        pct(s.get("ma_deviation",0)), pct(s.get("ret_20d",0)), s.get("yang",0), s.get("yin",0),
        s.get("max_consecutive_yang",0), int(s["position"]*100))
    # leaders
    # 过滤龙头: 必须是状态3/4/5且有正收益
    all_leaders = s.get("leaders", [])
    leaders = [l for l in all_leaders if l["ret20"] > 0]
    if leaders:
        h += '<div style="font-size:10px;color:#d29922;font-weight:700;margin:8px 0 4px">🏆 龙头个股（近20日涨幅排名）</div>'
        h += '<table style="width:100%;font-size:11px;border-collapse:collapse">'
        h += '<tr style="color:#8b949e;font-size:10px"><th style="text-align:left;padding:2px 4px">个股</th><th style="text-align:right;padding:2px 4px">涨幅</th><th style="text-align:left;padding:2px 4px">入选原因</th></tr>'
        for i, ldr in enumerate(leaders):
            mkt = "sh" if ldr["code"].startswith("6") else "sz"
            rc = "#26a69a" if ldr["ret20"] > 0 else "#ef5350"
            reason = "涨幅板块内第%d, 近20日%+.1f%%" % (i+1, ldr["ret20"])
            url = "https://quote.eastmoney.com/%s%s.html" % (mkt, ldr["code"])
            h += '<tr><td style="padding:2px 4px"><a href="%s" target="_blank" style="color:#58a6ff;font-weight:600">%s</a></td><td style="text-align:right;padding:2px 4px;color:%s">%+.1f%%</td><td style="padding:2px 4px;color:#8b949e;font-size:10px">%s</td></tr>' % (url, ldr["name"], rc, ldr["ret20"], reason)
        h += '</table>'
    else:
        h += '<div style="font-size:10px;color:#8b949e;margin-top:4px">⚠️ 成分股数据不完整（板块趋势基于同花顺指数自身OHLCV数据），akshare成分股接口不可用</div>'
    # ETFs
    etfs = s.get("etfs", [])
    if etfs:
        h += '<div style="font-size:10px;color:#a371f7;font-weight:700;margin:8px 0 4px">📦 相关ETF</div>'
        h += '<table style="width:100%;font-size:11px;border-collapse:collapse">'
        h += '<tr style="color:#8b949e;font-size:10px"><th style="text-align:left;padding:2px 4px">ETF</th><th style="text-align:left;padding:2px 4px">状态</th><th style="text-align:left;padding:2px 4px">代码</th></tr>'
        for e in etfs:
            mkt = "sh" if e["symbol"].startswith("5") else "sz"
            url = "https://quote.eastmoney.com/%s%s.html" % (mkt, e["symbol"])
            h += '<tr><td style="padding:2px 4px"><a href="%s" target="_blank" style="color:#a371f7">%s</a></td><td style="padding:2px 4px">%s</td><td style="padding:2px 4px;color:#8b949e;font-size:10px">%s</td></tr>' % (url, e["name"], badge(e["state"], e["state_label"]), e["symbol"])
        h += '</table>'
    return h + '</div>'

# ====== HTML ======
h = '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>趋势跟随交易系统</title>'
h += '<style>*{margin:0;padding:0;box-sizing:border-box}body{background:#0d1117;color:#e6edf3;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;font-size:13px}.header{background:#161b22;border-bottom:1px solid #30363d;padding:12px 20px;display:flex;justify-content:space-between;align-items:center}.header h1{font-size:17px;background:linear-gradient(90deg,#58a6ff,#3fb950);-webkit-background-clip:text;-webkit-text-fill-color:transparent}.overview{display:flex;gap:0;margin:10px 20px;border:1px solid #30363d;border-radius:8px;overflow:hidden;flex-wrap:wrap}.ov-item{flex:1;min-width:80px;padding:10px 12px;text-align:center;background:#161b22;border-right:1px solid #30363d}.ov-item:last-child{border-right:none}.ov-item .v{font-size:20px;font-weight:800}.ov-item .l{font-size:9px;color:#8b949e;margin-top:1px}.panel{margin:0 20px 12px}.panel h2{font-size:14px;margin-bottom:8px}.focus-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(380px,1fr));gap:10px}.all-t{overflow-x:auto;border:1px solid #30363d;border-radius:6px;margin:10px 20px 16px}.all-t table{width:100%;border-collapse:collapse;font-size:11px;min-width:1100px}.all-t thead th{background:#21262d;padding:5px 7px;text-align:left;font-size:10px;color:#8b949e;border-bottom:2px solid #30363d;font-weight:600;white-space:nowrap}.all-t tbody td{padding:4px 7px;border-bottom:1px solid #21262d;white-space:nowrap}.all-t tbody tr:hover{background:rgba(88,166,255,0.03)}a{color:#58a6ff;text-decoration:none;font-weight:600}a:hover{text-decoration:underline}.search{margin:8px 20px}.search input{width:100%;padding:6px 12px;background:#161b22;border:1px solid #30363d;border-radius:6px;color:#e6edf3;font-size:12px;outline:none}.footer{padding:10px 20px;border-top:1px solid #30363d;text-align:center;color:#8b949e;font-size:10px}</style></head><body>'

# Header
hc_map = {"强势":"#39d353","正常":"#d29922","弱势":"#da3633"}
hc = hc_map.get(ov["market_health"],"#da3633")
h += '<div class="header"><div style="display:flex;align-items:center;gap:12px"><h1>趋势跟随交易系统</h1><select onchange="if(this.value)window.location.href=this.value" style="background:#161b22;border:1px solid #30363d;color:#e6edf3;padding:4px 8px;border-radius:4px;font-size:12px;cursor:pointer"><option>%s</option></select></div><div style="font-size:10px;color:#8b949e">板块→个股 漏斗筛选 · 800只核心标的</div></div><span style="background:rgba(%s,0.15);color:%s;border:1px solid %s;padding:4px 12px;border-radius:14px;font-size:12px;font-weight:700">%s</span></div>' % (
    data["date"], "35,134,54" if ov["market_health"]=="强势" else "210,153,34" if ov["market_health"]=="正常" else "218,54,51", hc, hc, ov["market_health"])

# Overview row
ov_items = [
    (ov['total_sectors'],'全板块','#8b949e'),(ov['uptrend_sectors'],'上涨(3/4/5)','#58a6ff'),
    (ov.get('reversal_sectors',0),'翻转关注🔵','#42a5f5'),(ov['mainline_sectors'],'主线★','#d29922'),
    (ov['trend_stocks'],'趋势个股','#3fb950'),(ov.get('trend_etfs',0),'趋势ETF','#a371f7'),
]
h += '<div class="overview">'
for v,l,c in ov_items:
    h += '<div class="ov-item"><div class="v" style="color:%s">%s</div><div class="l">%s</div></div>' % (c,v,l)
h += '</div>'

# Focus cards
h += '<div class="panel"><h2 style="color:#42a5f5">🔍 焦点板块（%d个 — 全展开，含龙头个股+入选原因）</h2><div class="focus-grid">' % len(focus)
for s in focus:
    h += card(s, s.get("is_mainline", False))
h += '</div></div>'

# Watching
if watching:
    h += '<div class="panel"><h2 style="color:#8b949e">👀 观察区（状态2 — 接近突破MA20）</h2><div class="focus-grid">'
    for s in watching:
        h += card(s, False)
    h += '</div></div>'

# Stocks table with sector/theme columns
h += '<div class="panel"><h2>📈 趋势个股（%d只）<span style="color:#8b949e;font-weight:400;font-size:11px"> 含板块归属+关联题材</span></h2></div>' % len(stocks)
h += '<div class="search"><input type="text" placeholder="搜索个股..." oninput="var q=this.value.toLowerCase();document.querySelectorAll(\'tr[data-s]\').forEach(function(r){r.style.display=r.getAttribute(\'data-s\').includes(q)?\'\':\'none\'})"></div>'
h += '<div class="all-t"><table><thead><tr><th>名称</th><th>代码</th><th>状态</th><th>得分</th><th>结构</th><th>量能</th><th>持续</th><th>所属板块</th><th>关联题材</th><th>现价</th><th>止损</th><th>仓位</th></tr></thead><tbody>'

for s in stocks:
    c = s['conditions']; st = (s['name']+s['code']+s['state_label']).lower()
    mkt = "sh" if str(s["code"]).startswith("6") else "sz"
    sectors_str = ", ".join(s.get("sectors",["-"])) if s.get("sectors") else "-"
    themes_str = ", ".join(s.get("themes",["-"])) if s.get("themes") else "-"
    h += '<tr data-s="%s">' % st
    h += '<td><a href="https://quote.eastmoney.com/%s%s.html" target="_blank" style="font-weight:600">%s</a></td>' % (mkt, s["code"], s["name"])
    h += '<td style="color:#8b949e;font-size:11px">%s</td>' % s["code"]
    h += '<td>%s</td>' % badge(s["state"], s["state_label"])
    h += '<td style="font-weight:700">%s</td>' % s["score"]
    h += '<td style="color:%s">%s</td>' % (cp(c["structure"]["pass"]), ci(c["structure"]["pass"]))
    h += '<td style="color:%s">%s</td>' % (cp(c["volume"]["pass"]), ci(c["volume"]["pass"]))
    h += '<td style="color:%s">%s</td>' % (cp(c["persistence"]["pass"]), ci(c["persistence"]["pass"]))
    h += '<td style="font-size:10px;color:#8b949e">%s</td>' % sectors_str
    h += '<td style="font-size:10px;color:#a371f7">%s</td>' % themes_str
    h += '<td>%s</td><td style="color:#da3633">%s</td>' % (prc(s.get("price")), prc(s.get("stop_loss")))
    h += '<td style="font-weight:600">%d%%</td></tr>' % int(s["position"]*100)
h += '</tbody></table></div>'

# ETF section
etfs = data.get("etfs", [])
if etfs:
    # Sort ETFs by score descending
    etfs.sort(key=lambda x: -x["score"])
    h += '<div class="panel"><h2>📦 ETF直筛（%d只 — 与漏斗并行路径）<span style="color:#8b949e;font-weight:400;font-size:11px"> baostock真实数据 · 按得分排序</span></h2></div>' % len(etfs)
    h += '<div class="all-t"><table><thead><tr><th>名称</th><th>代码</th><th>状态</th><th>得分</th><th>结构</th><th>量能</th><th>持续</th><th>MA20偏离</th><th>20日涨跌</th><th>仓位</th></tr></thead><tbody>'
    for e in etfs:
        c = e.get("conditions", {})
        h += '<tr>'
        h += '<td><a href="%s" target="_blank" style="font-weight:600">%s</a></td>' % (e["link"], e["name"])
        h += '<td style="color:#8b949e;font-size:11px">%s</td>' % e["symbol"]
        h += '<td>%s</td>' % badge(e["state"], e["state_label"])
        h += '<td style="font-weight:700">%s</td>' % e["score"]
        for k in ["structure","volume","persistence"]:
            p = c.get(k, {}).get("pass", False) if c else False
            h += '<td style="color:%s">%s</td>' % (cp(p), ci(p))
        h += '<td style="color:%s">%s</td>' % ("#26a69a" if e.get("ma_deviation",0)>=0 else "#ef5350", pct(e.get("ma_deviation",0)))
        h += '<td style="color:%s">%s</td>' % ("#26a69a" if e.get("ret_20d",0)>=0 else "#ef5350", pct(e.get("ret_20d",0)))
        h += '<td style="font-weight:600">%d%%</td></tr>' % int(e["position"]*100)
    h += '</tbody></table></div>'

h += '<div class="footer">趋势跟随交易系统 | 焦点%d板块 | 趋势%d个股 | %dETF | %s | ★主线 🔵翻转 | 免责声明:仅供辅助参考</div></body></html>' % (len(focus), len(stocks), len(etfs), data["date"])

with open("dashboard/index.html", "w") as f: f.write(h)
with open("dashboard/trend_dashboard_%s.html" % data["date"], "w") as f: f.write(h)
print("✅ dashboard/index.html (%dKB)" % (len(h)/1024))
print("焦点=%d板块 个股=%d只" % (len(focus), len(stocks)))
