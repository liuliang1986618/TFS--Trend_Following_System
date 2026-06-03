#!/usr/bin/env python3
"""Final dashboard: overview, cards with 5d-state-bar+sparkline, trajectory popup, projection panel, accuracy panel, health dashboard, 30d nav.

Phase A: 5d状态条 + sparkline + 轨迹弹窗
Phase B: 明日推演面板
Phase C: 推演准确率面板
Phase D: 反思闭环健康度仪表
"""
import json
import os
from datetime import datetime

with open("dashboard/data/dashboard_data.json") as f:
    data = json.load(f)

# Phase A: 加载历史状态缓存（用全量缓存，取最近10天，得分和状态完整）
history_data = {}
full_cache_path = "dashboard/data/history_states_full.json"
if os.path.exists(full_cache_path):
    with open(full_cache_path) as f:
        full_cache = json.load(f).get("sectors", {})
    for code, recs in full_cache.items():
        if recs: history_data[code] = recs[-10:]
if not history_data:
    snap_path = "dashboard/data/history_states.json"
    if os.path.exists(snap_path):
        with open(snap_path) as f:
            history_data = json.load(f).get("sectors", {})

# Phase B/C: 加载推演回测结果（汇总数据，~50KB）
projection_data = {}
proj_path = "dashboard/data/projection_log.json"
if os.path.exists(proj_path):
    with open(proj_path) as f:
        projection_data = json.load(f)

# Phase B: 加载推演权重
weights_data = {}
weights_path = "dashboard/data/projection_weights.json"
if os.path.exists(weights_path):
    with open(weights_path) as f:
        weights_data = json.load(f).get("weights", {})

# Phase D: 加载健康度仪表数据
health_data = {}
health_path = "dashboard/data/health_dashboard.json"
if os.path.exists(health_path):
    with open(health_path) as f:
        health_data = json.load(f)

# Phase 4.1 实盘工具: 加载板块统计(持续天数+明日概率+历史趋势长度)
sector_stats = {}
stats_path = "dashboard/data/sector_stats.json"
if os.path.exists(stats_path):
    with open(stats_path) as f:
        sector_stats = json.load(f).get("sectors", {})

# 日期导航数据
date_nav = []
nav_path = "dashboard/data/date_nav.json"
if os.path.exists(nav_path):
    with open(nav_path) as f:
        date_nav = json.load(f).get("dates", [])

ov = data["overview"]
focus = [s for s in data["sectors"] if s["state"] in (3,4)]
stocks = data.get("stocks", [])
watching = [s for s in data["sectors"] if s["state"]==2 and s.get("ma_deviation",-99)>-3 and s.get("ret_20d",-99)>-5][:5]

# 状态名称翻译（交易员能看懂的中文）
def sn(s):
    """状态编号→中文名称（兼容整数和字符串）"""
    m = {1:"下跌趋势",2:"下跌反弹",3:"翻转确认中",4:"上涨趋势",5:"上涨回调","3p":"转跌确认中","3'":"转跌确认中"}
    # 尝试整数key和字符串key
    if s in m: return m[s]
    if isinstance(s, str) and s.isdigit() and int(s) in m: return m[int(s)]
    return str(s)

# 通用术语翻译: 把所有"状态X"、"模式ID"、"场景X"等转成大句话
def tx(text):
    """把一个字符串里所有技术术语翻译成大句话"""
    if not isinstance(text, str): return str(text)
    for num, name in [("1","下跌趋势"),("2","下跌反弹"),("3","翻转确认中"),("4","上涨趋势"),("5","上涨回调"),("3p","转跌确认中"),("3'","转跌确认中")]:
        text = text.replace("状态"+num, name).replace("→"+num, "→"+name)
    for old, new in [("场A场景","上涨场景"),("场B场景","整理场景"),("场C场景","下跌场景"),
                     (" 且 ","，"),("当前状态=","当前是")]:
        text = text.replace(old, new)
    return text

# 翻译条件文本: "当前状态=3 且预测=3" → "当前是翻转确认中，预测继续整理"
def tc(cond):
    return tx(cond)

# 翻译规则ID: FREQ_1_1 → "历史频率: 下跌趋势→下跌趋势", ERR_3 → "纠错: 翻转确认中"
def rn(rid):
    for prefix, label in [("FREQ_","历史规律: "),("ERR_","纠错规则: "),("PTN_","模式: ")]:
        if rid.startswith(prefix):
            parts = rid.replace(prefix,"").split("_")
            if len(parts)==2:
                return label + sn(parts[0])+"→"+sn(parts[1])
            elif len(parts)==1:
                return label + sn(parts[0])
    return tx(rid)

# 模式编号翻译 PTN_3_3 → "翻转确认中→继续整理"
def pn(pid):
    parts = pid.replace("PTN_","").split("_")
    if len(parts)==2:
        return sn(parts[0])+"→"+sn(parts[1])
    return pid

def badge(s,l):
    c={1:("rgba(110,118,129,0.2)","#b0b5c0"),2:("rgba(110,118,129,0.2)","#b0b5c0"),3:("rgba(66,165,245,0.25)","#64b5f6"),4:("#238636","#fff")}
    bg,fg=c.get(s,("#6e7681","#b0b5c0"))
    return '<span style="display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:700;background:%s;color:%s">%s</span>' % (bg,fg,l)
def pct(v): return ("%+.1f%%" % v) if isinstance(v,(int,float)) else "N/A"
def prc(v): return "{:,.2f}".format(v) if isinstance(v,(int,float)) else "N/A"
def cp(p): return "#26a69a" if p else "#ef5350"
def ci(p): return "●" if p else "○"
def sc(state):
    """状态→颜色映射（6状态）"""
    return {1:"#6e7681",2:"#8b949e",3:"#42a5f5",4:"#26a69a",5:"#d29922","3p":"#da3633"}.get(state,"#6e7681")

def state_bar_5d(code):
    """生成5天状态变化条HTML（宽2px×5格的紧凑颜色条）"""
    if code not in history_data or len(history_data[code]) < 2:
        return ""
    recent = history_data[code][-5:]
    states = [r["state"] for r in recent]
    direction = trajectory_dir(states)
    arrows = {"up":" ↑","down":" ↓","stable":" →","mixed":" ⇅"}
    h = '<div style="display:flex;align-items:center;gap:3px;margin:4px 0">'
    h += '<span style="font-size:9px;color:#8b949e">%dd</span>' % len(states)
    for s in states:
        h += '<span style="width:6px;height:14px;background:%s;border-radius:1px;display:inline-block" title="%s"></span>' % (sc(s), sn(s))
    h += '<span style="font-size:9px;color:%s">%s</span>' % (sc(states[-1]), arrows.get(direction,""))
    h += '</div>'
    return h

def trajectory_dir(states):
    """简化的趋势方向判断（JS兼容版本内联在HTML中）"""
    if len(states) < 2: return "stable"
    order = {1:0,2:1,3:2,"3p":2.5,5:3,4:4}
    ranks = [order.get(s,0) for s in states]
    has_up = any(ranks[i] > ranks[i-1]+0.5 for i in range(1,len(ranks)))
    has_down = any(ranks[i] < ranks[i-1]-0.5 for i in range(1,len(ranks)))
    if has_up and has_down: return "mixed"
    if ranks[-1] > ranks[0]+0.5: return "up"
    if ranks[-1] < ranks[0]-0.5: return "down"
    return "stable"

def sparkline_svg(code, w=80, h=18):
    """生成迷你sparkline SVG折线图（5天得分趋势）+ 文字说明"""
    if code not in history_data or len(history_data[code]) < 2:
        return ""
    recent = history_data[code][-5:]
    scores = [r["score"] for r in recent]
    if not scores or max(scores) == min(scores):
        # 得分没变化，显示持平
        return ('<span style="font-size:9px;color:#8b949e;margin-left:4px">'
                '📊5日得分持平(%d分)</span>' % scores[0] if scores else "")
    mn, mx = min(scores), max(scores)
    rng = mx - mn if mx > mn else 1
    pts = []
    for i, v in enumerate(scores):
        x = 2 + (w - 4) * i / max(len(scores)-1, 1)
        y = h - 2 - (v - mn) / rng * (h - 4)
        pts.append("%.1f,%.1f" % (x, y))
    poly = " ".join(pts)
    direction = "↑走强" if scores[-1] >= scores[0] else "↓走弱"
    color = "#26a69a" if scores[-1] >= scores[0] else "#ef5350"
    svg = ('<span style="font-size:9px;color:%s;margin-left:4px">📊%s</span>'
           '<svg width="%d" height="%d" style="vertical-align:middle">'
           '<polyline points="%s" fill="none" stroke="%s" stroke-width="1.5" stroke-linecap="round"/>'
           '<circle cx="%.1f" cy="%.1f" r="2" fill="%s"/></svg>'
           '<span style="font-size:9px;color:#8b949e">%d→%d分</span>') % (
        color, direction, w, h, poly, color,
        float(pts[-1].split(",")[0]), float(pts[-1].split(",")[1]), color,
        scores[0], scores[-1])
    return svg

def make_card(s, is_ml=False, ss_dict=None, w_dict=None):
    """生成板块卡片HTML。ss_dict和w_dict可选传入用于历史日期,默认用全局sector_stats和weights_data"""
    if ss_dict is None: ss_dict = sector_stats
    if w_dict is None: w_dict = weights_data
    c = s['conditions']; icon = '★' if is_ml else '🔵'
    bc = 'rgba(210,153,34,0.6)' if is_ml else 'rgba(66,165,245,0.4)'
    code = s.get("code", s.get("symbol", ""))
    h = '<div class="card-clickable" style="background:#161b22;border:2px solid %s;border-radius:8px;padding:12px" onclick="showTrajectory(\'%s\')">' % (bc, code)
    h += '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:2px">'
    h += '<div style="font-size:14px;font-weight:700">%s <a href="%s" target="_blank" style="color:#e6edf3;text-decoration:none">%s</a> <span style="font-size:10px;color:#8b949e">%s</span></div>' % (icon, s["link"], s["name"], code)
    h += badge(s["state"], s["state_label"])
    h += '</div>'
    if code:
        bar = state_bar_5d(code)
        if bar: h += bar
    # 明日推演
    if code and w_dict:
        state_key = str(s.get("state", "")).replace("'", "p")
        w = w_dict.get(state_key, {})
        if w:
            pa = w.get("scenario_a", 0); pb = w.get("scenario_b", 0); pc = w.get("scenario_c", 0)
            st = str(s.get("state", ""))
            if st == "4": la,lb,lc = "继续上涨","转为回调","转为转跌"
            elif st == "3": la,lb,lc = "继续整理","突破上涨","假突破下跌"
            elif st == "5": la,lb,lc = "企稳反弹","继续回调","转为转跌"
            elif st == "2": la,lb,lc = "继续反弹","突破翻转","回落下跌"
            elif st == "1": la,lb,lc = "继续下跌","出现反弹",""
            elif st == "3p" or st == "3'": la,lb,lc = "假跌修复","继续整理","继续下跌"
            else: la,lb,lc = "继续","转折","反转"
            h += '<div style="display:flex;align-items:center;gap:4px;margin:3px 0;font-size:10px">'
            h += '<span style="color:#8b949e">🔮 明天:</span>'
            h += '<span style="color:%s;background:rgba(38,166,154,0.15);padding:1px 6px;border-radius:8px">%s %.0f%%</span>' % ("#26a69a", la, pa*100)
            h += '<span style="color:%s;background:rgba(210,153,34,0.15);padding:1px 6px;border-radius:8px">%s %.0f%%</span>' % ("#d29922", lb, pb*100)
            if pc > 0.02 and lc:
                h += '<span style="color:%s;background:rgba(218,54,51,0.15);padding:1px 6px;border-radius:8px">%s %.0f%%</span>' % ("#da3633", lc, pc*100)
            h += '</div>'
    # 实盘指标
    if code and ss_dict:
        ss = ss_dict.get(code, {})
        if ss:
            sk = ss.get("streak_days", 0); pr = ss.get("tomorrow_prob", 0)
            av = ss.get("avg_uptrend_days", 0); mx = ss.get("max_uptrend_days", 0)
            st = str(s.get("state", ""))
            if st == "4":
                wn = ""
                if sk > av*2 and av > 0:
                    wn = '<span style="color:#d29922;font-weight:700"> ⚠已超历史均值%.0f倍(平均%.0f天,已%d天)</span>'%(sk/av, av, sk)
                h += '<div style="display:flex;gap:6px;font-size:10px;margin:3px 0">'
                h += '<span style="color:#26a69a;font-weight:700">📈持续%d天</span>'%sk
                h += '<span style="color:#8b949e">| 明天继续涨</span><span style="color:#26a69a;font-weight:700">%.0f%%</span>'%(pr*100)
                h += '<span style="color:#8b949e">| 该板块平均涨%.0f天/最长%d天</span>'%(av,mx)
                er = ss.get("expected_return", 0)
                h += '<span style="color:%s">| 预期收益%+.2f%%</span>'%("#26a69a" if er>0 else "#ef5350", er)
                h += wn + '</div>'
            elif st == "3":
                h += '<div style="font-size:10px;margin:3px 0"><span style="color:#42a5f5;font-weight:700">🔄翻转%d天</span> <span style="color:#8b949e">| 明天继续整理%.0f%%</span></div>'%(sk,pr*100)
            elif st == "1":
                h += '<div style="font-size:10px;margin:3px 0;color:#6e7681">📉下跌%d天 | 继续跌%.0f%%</div>'%(sk,pr*100)
    # 三条件(分三行)
    h += '<div style="font-size:11px;margin-bottom:6px">'
    for k,lb in [("structure","A 结构"),("volume","B 量能"),("persistence","C 持续性")]:
        p = c[k]["pass"]
        h += '<div style="margin:1px 0"><span style="color:%s">%s</span> %s: %s</div>' % (cp(p), "✅" if p else "❌", lb, c[k]["detail"])
    h += '</div>'
    # 技术指标
    h += '<div style="font-size:10px;color:#8b949e">MA20:%s | 20日:%s | 阳%d/阴%d | 连阳%d天 | 仓位:%d%%%s</div>' % (
        pct(s.get("ma_deviation",0)), pct(s.get("ret_20d",0)), s.get("yang",0), s.get("yin",0),
        s.get("max_consecutive_yang",0), int(s["position"]*100),
        sparkline_svg(code) if code else "")
    # 龙头
    all_leaders = s.get("leaders", [])
    if all_leaders:
        h += '<div style="font-size:10px;color:#d29922;font-weight:700;margin:8px 0 4px">🏆 龙头个股（近20日涨幅排名）</div>'
        h += '<table style="width:100%;font-size:11px;border-collapse:collapse">'
        h += '<tr style="color:#8b949e;font-size:10px"><th style="text-align:left;padding:2px 4px">个股</th><th style="text-align:right;padding:2px 4px">涨幅</th><th style="text-align:left;padding:2px 4px">入选原因</th></tr>'
        for i, ldr in enumerate(all_leaders[:5]):
            mkt = "sh" if str(ldr.get("code","")).startswith("6") else "sz"
            rc = "#26a69a" if ldr.get("ret20",0) > 0 else "#ef5350"
            reason = ldr.get("reason","涨幅板块内第%d"%(i+1))
            url = "https://quote.eastmoney.com/%s%s.html" % (mkt, ldr["code"])
            h += '<tr><td style="padding:2px 4px"><a href="%s" target="_blank" style="color:#58a6ff;font-weight:600">%s</a></td><td style="text-align:right;padding:2px 4px;color:%s">%+.1f%%</td><td style="padding:2px 4px;color:#8b949e;font-size:10px">%s</td></tr>' % (url, ldr.get("name",ldr["code"]), rc, ldr.get("ret20",0), reason)
        h += '</table>'
    else:
        h += '<div style="font-size:10px;color:#8b949e;margin-top:4px">⚠️ 暂无龙头数据</div>'
    # ETFs
    etfs = s.get("etfs", [])
    if etfs:
        h += '<div style="font-size:10px;color:#a371f7;font-weight:700;margin:8px 0 4px">📦 相关ETF</div>'
        h += '<table style="width:100%;font-size:11px;border-collapse:collapse">'
        h += '<tr style="color:#8b949e;font-size:10px"><th style="text-align:left;padding:2px 4px">ETF</th><th style="text-align:left;padding:2px 4px">状态</th><th style="text-align:left;padding:2px 4px">代码</th></tr>'
        for e in etfs:
            ec = e.get("code", e.get("symbol", ""))
            mkt = "sh" if str(ec).startswith("5") else "sz"
            url = "https://quote.eastmoney.com/%s%s.html" % (mkt, ec)
            h += '<tr><td style="padding:2px 4px"><a href="%s" target="_blank" style="color:#a371f7">%s</a></td><td style="padding:2px 4px">%s</td><td style="padding:2px 4px;color:#8b949e;font-size:10px">%s</td></tr>' % (url, e.get("name",""), badge(e.get("state",1), e.get("state_label","未知")), ec)
        h += '</table>'
    return h + '</div>'

# 向后兼容
def card(s, is_ml): return make_card(s, is_ml)

# ====== HTML生成 ======
h = '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>趋势跟随交易系统</title>'
h += '<style>*{margin:0;padding:0;box-sizing:border-box}body{background:#0d1117;color:#e6edf3;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;font-size:13px}.header{background:#161b22;border-bottom:1px solid #30363d;padding:12px 20px;display:flex;justify-content:space-between;align-items:center}.header h1{font-size:17px;background:linear-gradient(90deg,#58a6ff,#3fb950);-webkit-background-clip:text;-webkit-text-fill-color:transparent}.overview{display:flex;gap:0;margin:10px 20px;border:1px solid #30363d;border-radius:8px;overflow:hidden;flex-wrap:wrap}.ov-item{flex:1;min-width:80px;padding:10px 12px;text-align:center;background:#161b22;border-right:1px solid #30363d}.ov-item:last-child{border-right:none}.ov-item .v{font-size:20px;font-weight:800}.ov-item .l{font-size:9px;color:#8b949e;margin-top:1px}.panel{margin:0 20px 12px}.panel h2{font-size:14px;margin-bottom:8px}.focus-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(380px,1fr));gap:10px}.all-t{overflow-x:auto;border:1px solid #30363d;border-radius:6px;margin:10px 20px 16px}.all-t table{width:100%;border-collapse:collapse;font-size:11px;min-width:1100px}.all-t thead th{background:#21262d;padding:5px 7px;text-align:left;font-size:10px;color:#8b949e;border-bottom:2px solid #30363d;font-weight:600;white-space:nowrap}.all-t tbody td{padding:4px 7px;border-bottom:1px solid #21262d;white-space:nowrap}.all-t tbody tr:hover{background:rgba(88,166,255,0.03)}a{color:#58a6ff;text-decoration:none;font-weight:600}a:hover{text-decoration:underline}.search{margin:8px 20px}.search input{width:100%;padding:6px 12px;background:#161b22;border:1px solid #30363d;border-radius:6px;color:#e6edf3;font-size:12px;outline:none}.footer{padding:10px 20px;border-top:1px solid #30363d;text-align:center;color:#8b949e;font-size:10px}.date-bar{display:flex;gap:6px;padding:8px 20px;overflow-x:auto;border-bottom:1px solid #30363d;background:#0d1117;flex-wrap:wrap}.date-chip{background:#161b22;border:1px solid #30363d;color:#8b949e;padding:6px 14px;border-radius:16px;font-size:12px;font-weight:600;text-decoration:none;white-space:nowrap;transition:all 0.15s}.date-chip:hover{background:#1c2128;border-color:#58a6ff;color:#e6edf3}.date-chip.active{background:rgba(88,166,255,0.15);border-color:#58a6ff;color:#58a6ff}.date-chip.month-label{background:transparent;border-color:transparent;color:#d29922;font-weight:800;font-size:11px;pointer-events:none}.show-more-btn{background:#161b22;border:1px dashed #30363d;color:#58a6ff;padding:6px 14px;border-radius:16px;font-size:11px;cursor:pointer;white-space:nowrap}.show-more-btn:hover{border-color:#58a6ff}.trajectory-overlay{display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.7);z-index:1000;justify-content:center;align-items:center}.trajectory-overlay.show{display:flex}.trajectory-panel{background:#161b22;border:1px solid #30363d;border-radius:12px;padding:20px;max-width:500px;width:90%;max-height:80vh;overflow-y:auto}.trajectory-panel h3{font-size:16px;margin-bottom:12px;color:#58a6ff}.trajectory-panel .close-btn{float:right;background:none;border:none;color:#8b949e;font-size:20px;cursor:pointer;line-height:1}.trajectory-panel .close-btn:hover{color:#e6edf3}.trajectory-row{display:flex;align-items:center;gap:8px;padding:6px 0;border-bottom:1px solid #21262d;font-size:12px}.trajectory-row .t-date{width:80px;color:#8b949e;font-size:11px}.trajectory-row .t-state{width:12px;height:12px;border-radius:50%;flex-shrink:0}.trajectory-row .t-conds{display:flex;gap:4px;font-size:10px}.t-cond{width:18px;height:18px;border-radius:4px;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:700}.t-cond.pass{background:rgba(38,166,154,0.2);color:#26a69a}.t-cond.fail{background:rgba(239,83,80,0.2);color:#ef5350}.card-clickable{cursor:pointer;transition:all 0.15s}.card-clickable:hover{transform:translateY(-1px);box-shadow:0 4px 12px rgba(88,166,255,0.1)}.app-layout{display:flex;flex:1;overflow:hidden}.date-sidebar{width:260px;min-width:260px;background:#0d1117;border-right:1px solid #30363d;overflow-y:auto;flex-shrink:0}.date-sidebar h3{position:sticky;top:0;background:#161b22;padding:10px 12px;font-size:12px;color:#58a6ff;border-bottom:1px solid #30363d;z-index:10}.date-row{display:flex;align-items:center;gap:5px;padding:5px 10px;border-bottom:1px solid rgba(48,54,61,0.3);cursor:pointer;font-size:11px;min-height:40px}.date-row:hover{background:#161b22}.date-row.active{background:rgba(88,166,255,0.1);border-left:3px solid #58a6ff}.date-row .d{font-size:10px;color:#8b949e;min-width:40px}.date-row .w{font-size:9px;color:#6e7681;min-width:26px}.date-row .n{font-size:10px;font-weight:700;padding:1px 4px;border-radius:6px;min-width:32px;text-align:center}.date-row .s{font-size:9px;color:#8b949e;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:120px}.date-row .h{width:6px;height:6px;border-radius:50%;flex-shrink:0}.main-content{flex:1;overflow-y:auto;overflow-x:hidden;padding:0 16px 16px;height:100vh}.mnth-divider{padding:6px 12px;font-size:10px;color:#d29922;font-weight:700;background:#161b22;border-bottom:1px solid #30363d}</style></head><body>'

# Header
hc_map = {"强势":"#39d353","正常":"#d29922","弱势":"#da3633"}
hc = hc_map.get(ov["market_health"],"#da3633")

# Build date bar: beautiful horizontal chips
daily_dates = data.get("daily_snapshots", [data["date"]])
weekdays_cn = ["周一","周二","周三","周四","周五","周六","周日"]
months_cn = ["1月","2月","3月","4月","5月","6月","7月","8月","9月","10月","11月","12月"]
date_chips = ""
last_month = ""
for d in sorted(daily_dates):
    dt = datetime.strptime(d, "%Y-%m-%d")
    wd = weekdays_cn[dt.weekday()]
    label = "%s %s" % (wd, d[5:])
    active = " active" if d == data["date"] else ""
    # 每月首日或周一显示月份标签
    month_label = months_cn[dt.month - 1]
    if wd == "周一" and month_label != last_month:
        date_chips += '<span class="date-chip month-label">%s</span>' % month_label
        last_month = month_label
    date_chips += '<a href="trend_dashboard_%s.html" class="date-chip%s">%s</a>' % (d, active, label)

h += '<div class="header"><div><h1>趋势跟随交易系统</h1></div><span style="background:rgba(%s,0.15);color:%s;border:1px solid %s;padding:4px 12px;border-radius:14px;font-size:12px;font-weight:700">%s</span></div>' % (
    "35,134,54" if ov["market_health"]=="强势" else "210,153,34" if ov["market_health"]=="正常" else "218,54,51", hc, hc, ov["market_health"])

# 日期导航栏（紧凑横条，保留全功能）
h += '<div class="date-bar" id="dateNav" style="display:flex;gap:4px;padding:6px 12px;overflow-x:auto;border-bottom:1px solid #30363d;background:#161b22;flex-wrap:nowrap;align-items:center"></div>'

# Overview row
ov_items = [
    (ov['total_sectors'],'全部板块','#8b949e'),
    (ov['uptrend_sectors'],'上涨趋势板块','#58a6ff'),
    (ov.get('reversal_sectors',0),'翻转确认中','#42a5f5'),
    (ov['mainline_sectors'],'主线板块','#d29922'),
    (ov['trend_stocks'],'上涨趋势个股','#3fb950'),
    (ov.get('trend_etfs',0),'上涨趋势ETF','#a371f7'),
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
    h += '<div class="panel"><h2 style="color:#8b949e">👀 观察区（反弹中 — 接近突破，随时可能进入上涨趋势）</h2><div class="focus-grid">'
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
        h += '<td style="color:#8b949e;font-size:11px">%s</td>' % e["code"]
        h += '<td>%s</td>' % badge(e["state"], e["state_label"])
        h += '<td style="font-weight:700">%s</td>' % e["score"]
        for k in ["structure","volume","persistence"]:
            p = c.get(k, {}).get("pass", False) if c else False
            h += '<td style="color:%s">%s</td>' % (cp(p), ci(p))
        h += '<td style="color:%s">%s</td>' % ("#26a69a" if e.get("ma_deviation",0)>=0 else "#ef5350", pct(e.get("ma_deviation",0)))
        h += '<td style="color:%s">%s</td>' % ("#26a69a" if e.get("ret_20d",0)>=0 else "#ef5350", pct(e.get("ret_20d",0)))
        h += '<td style="font-weight:600">%d%%</td></tr>' % int(e["position"]*100)
    h += '</tbody></table></div>'

# Backtest section
bt = data.get("backtest", {})
if bt:
    h += '<div class="panel"><h2>📊 回测结果（%s — 状态机板块轮动策略）<span style="color:#8b949e;font-weight:400;font-size:11px"> 下跌反弹突破→试探建仓, 趋势走坏→止损离场</span></h2>' % bt.get("period","")
    h += '<div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:12px">'
    h += '<div class="card"><div class="v" style="color:%s">%+.1f%%</div><div class="l">总收益</div></div>' % ("#26a69a" if bt.get("total_return",0)>=0 else "#ef5350", bt.get("total_return",0))
    h += '<div class="card"><div class="v" style="color:#ef5350">%.1f%%</div><div class="l">最大回撤</div></div>' % bt.get("max_drawdown",0)
    h += '<div class="card"><div class="v" style="color:#58a6ff">%d</div><div class="l">交易次数</div></div>' % bt.get("num_trades",0)
    h += '<div class="card"><div class="v" style="color:#8b949e">%s</div><div class="l">初始资金</div></div>' % ("{:,}".format(int(bt.get("initial_capital",0))))
    h += '<div class="card"><div class="v" style="color:%s">%s</div><div class="l">最终权益</div></div>' % ("#26a69a" if bt.get("final_equity",0)>=bt.get("initial_capital",1) else "#ef5350", "{:,}".format(int(bt.get("final_equity",0))))
    h += '</div>'
    # Recent trades
    trades_list = bt.get("trades", [])[-5:]
    if trades_list:
        h += '<div style="font-size:12px;color:#8b949e;margin-bottom:4px">最近交易:</div>'
        h += '<div class="all-t"><table><thead><tr><th>日期</th><th>标的</th><th>操作</th><th>价格</th><th>盈亏</th></tr></thead><tbody>'
        for t in trades_list:
            pnl_str = "%+.1f%%" % t.get("pnl_pct",0) if "pnl_pct" in t else "-"
            pnl_color = "#26a69a" if t.get("pnl_pct",0) >= 0 else "#ef5350"
            h += '<tr><td>%s</td><td>%s</td><td style="color:%s">%s</td><td>%.2f</td><td style="color:%s">%s</td></tr>' % (
                t["date"], t["code"], "#26a69a" if t["action"]=="买入" else "#ef5350", t["action"], t["price"], pnl_color, pnl_str)
        h += '</tbody></table></div>'
    h += '</div>'

# ====== Phase C: 推演准确率面板 ======
if projection_data:
    pmeta = projection_data.get("meta", {})
    by_state = projection_data.get("by_state", {})
    daily_acc = projection_data.get("daily_accuracy", [])
    top_errors = projection_data.get("top_errors", [])

    h += '<div class="panel"><h2>🔮 推演准确率面板 <span style="color:#8b949e;font-weight:400;font-size:11px"> 822天×90板块全量回测 | %s次推演</span></h2>' % (pmeta.get("total_projections", 0))

    # 总览卡片
    oa = pmeta.get("overall_accuracy", 0)
    opa = pmeta.get("overall_partial_accuracy", 0)
    h += '<div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:12px">'
    h += '<div style="background:#161b22;border:1px solid #30363d;border-radius:8px;padding:16px;text-align:center;flex:1;min-width:120px">'
    h += '<div style="font-size:28px;font-weight:800;color:%s">%.1f%%</div>' % ("#26a69a" if oa > 0.5 else "#d29922", oa*100)
    h += '<div style="font-size:10px;color:#8b949e">完全预测正确</div></div>'
    h += '<div style="background:#161b22;border:1px solid #30363d;border-radius:8px;padding:16px;text-align:center;flex:1;min-width:120px">'
    h += '<div style="font-size:28px;font-weight:800;color:%s">%.1f%%</div>' % ("#26a69a" if opa > 0.5 else "#d29922", opa*100)
    h += '<div style="font-size:10px;color:#8b949e">方向预测正确</div></div>'
    h += '<div style="background:#161b22;border:1px solid #30363d;border-radius:8px;padding:16px;text-align:center;flex:1;min-width:120px">'
    h += '<div style="font-size:28px;font-weight:800;color:#58a6ff">%s</div>' % (pmeta.get("total_projections", 0))
    h += '<div style="font-size:10px;color:#8b949e">推演总次数</div></div>'
    h += '</div>'

    # 按状态分类表格
    if by_state:
        h += '<div style="font-size:12px;color:#58a6ff;font-weight:600;margin:8px 0 4px">📊 按状态分类准确率</div>'
        h += '<div class="all-t"><table><thead><tr><th>趋势阶段</th><th>总次数</th><th>预测对</th><th>方向对</th><th>预测错</th><th>命中率</th><th>方向命中率</th></tr></thead><tbody>'
        for st in sorted(by_state.keys(), key=lambda x: str(x)):
            bs = by_state[st]
            ac = bs.get("accuracy", 0)
            pac = bs.get("partial_accuracy", 0)
            ac_color = "#26a69a" if ac > 0.5 else "#ef5350"
            state_color = sc(st) if isinstance(st, int) else sc("3p")
            h += '<tr><td style="color:%s;font-weight:600">%s</td><td>%d</td><td style="color:#26a69a">%d</td><td style="color:#d29922">%d</td><td style="color:#ef5350">%d</td><td style="color:%s;font-weight:700">%.1f%%</td><td style="color:%s">%.1f%%</td></tr>' % (
                state_color, sn(st), bs["total"], bs["correct"], bs.get("partial", 0), bs["incorrect"], ac_color, ac*100, "#d29922", pac*100)
        h += '</tbody></table></div>'

    # Top错误模式
    if top_errors:
        h += '<div style="font-size:12px;color:#ef5350;font-weight:600;margin:8px 0 4px">⚠️ 高频错误模式 Top 5</div>'
        h += '<div class="all-t"><table><thead><tr><th>错误模式</th><th>出现次数</th></tr></thead><tbody>'
        for e in top_errors[:5]:
            ep = e["pattern"]
            # 翻译错误模式: "4→3p(实4)" → "上涨趋势→转跌确认(实际是上涨趋势)"
            for num, name in [(1,"下跌趋势"),(2,"下跌反弹"),(3,"翻转确认中"),(4,"上涨趋势"),(5,"上涨回调")]:
                ep = ep.replace("→"+str(num), "→"+name).replace("实"+str(num), "实"+name)
            ep = ep.replace("→3p","→转跌确认").replace("实3p","实转跌确认")
            ep = ep.replace("→3'","→转跌确认").replace("实3'","实转跌确认")
            h += '<tr><td style="color:#da3633">%s</td><td style="font-weight:700">%d</td></tr>' % (ep, e["count"])
        h += '</tbody></table></div>'

    h += '</div>'  # end panel

# ====== Phase D: 健康度仪表 ======
if health_data:
    hmeta = health_data.get("meta", {})
    h += '<div class="panel"><h2>💚 反思闭环健康度仪表 <span style="color:#8b949e;font-weight:400;font-size:11px"> 推演→验证→反思→规则发现→权重调整</span></h2>'

    # 准确率变化
    init_acc = hmeta.get("initial_accuracy", 0)
    final_acc = hmeta.get("final_accuracy", 0)
    improve = hmeta.get("improvement", 0)
    improve_color = "#26a69a" if improve > 0 else "#ef5350" if improve < 0 else "#8b949e"
    improve_arrow = "↑" if improve > 0 else "↓" if improve < 0 else "→"

    h += '<div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:12px">'
    h += '<div style="background:#161b22;border:1px solid #30363d;border-radius:8px;padding:16px;text-align:center;flex:1;min-width:100px">'
    h += '<div style="font-size:22px;font-weight:800;color:#58a6ff">%.1f%%</div>' % (init_acc*100)
    h += '<div style="font-size:10px;color:#8b949e">初始准确率</div></div>'
    h += '<div style="background:#161b22;border:1px solid #30363d;border-radius:8px;padding:16px;text-align:center;flex:1;min-width:100px">'
    h += '<div style="font-size:22px;font-weight:800;color:%s">%s %.1f%%</div>' % (improve_color, improve_arrow, abs(improve)*100)
    h += '<div style="font-size:10px;color:#8b949e">提升/下降</div></div>'
    h += '<div style="background:#161b22;border:1px solid #30363d;border-radius:8px;padding:16px;text-align:center;flex:1;min-width:100px">'
    h += '<div style="font-size:22px;font-weight:800;color:#26a69a">%.1f%%</div>' % (final_acc*100)
    h += '<div style="font-size:10px;color:#8b949e">优化后准确率</div></div>'
    h += '</div>'

    # 发现的模式
    top_patterns = health_data.get("top_patterns", [])
    if top_patterns:
        h += '<div style="font-size:12px;color:#26a69a;font-weight:600;margin:8px 0 4px">✅ 可复用模式</div>'
        h += '<div class="all-t"><table><thead><tr><th>模式</th><th>条件</th><th>置信度</th><th>出现次数</th></tr></thead><tbody>'
        for p in top_patterns[:5]:
            h += '<tr><td style="font-weight:600">%s</td><td>%s</td><td>%.1f%%</td><td>%d</td></tr>' % (
                pn(p["id"]), tc(p["condition"])[:60], p["confidence"]*100, p["occurrences"])
        h += '</tbody></table></div>'

    # 经验教训
    lessons = health_data.get("top_lessons", [])
    if lessons:
        h += '<div style="font-size:12px;color:#d29922;font-weight:600;margin:8px 0 4px">📝 经验教训</div>'
        h += '<ul style="font-size:11px;color:#8b949e;list-style:disc;padding-left:16px">'
        for lesson in lessons[:5]:
            # 翻译教训中的术语
            txt = lesson[:150]
            for num, name in [(1,"下跌趋势"),(2,"下跌反弹"),(3,"翻转确认中"),(4,"上涨趋势"),(5,"上涨回调")]:
                txt = txt.replace("状态"+str(num), name).replace("3'","转跌确认").replace("场A","上涨场景").replace("场B","整理场景").replace("场C","下跌场景").replace("3→1","翻转向下").replace("3→4","翻转向上").replace("→4","→上涨").replace("→3","→翻转").replace("→1","→下跌").replace("≠","不是")
            h += '<li style="margin:4px 0">%s</li>' % txt
        h += '</ul>'

    # 当前权重
    cur_w = health_data.get("current_weights", {})
    if cur_w:
        h += '<div style="font-size:12px;color:#a371f7;font-weight:600;margin:8px 0 4px">⚖️ 当前权重配置</div>'
        h += '<div class="all-t"><table><thead><tr><th>趋势状态</th><th>最可能(继续)</th><th>有可能(转折)</th><th>不太可能(反转)</th></tr></thead><tbody>'
        for st_key in ["1", "2", "3", "4", "5", "3p"]:
            w = cur_w.get(st_key, {"A": 0.60, "B": 0.30, "C": 0.10})
            state_color = sc(int(st_key) if st_key.isdigit() else "3p")
            h += '<tr><td style="color:%s;font-weight:600">%s</td><td>%.0f%%</td><td>%.0f%%</td><td>%.0f%%</td></tr>' % (
                state_color, sn(st_key), w.get("A",0)*100, w.get("B",0)*100, w.get("C",0)*100)
        h += '</tbody></table></div>'

    h += '</div>'  # end panel

# Trajectory popup overlay (Phase A)
h += '<div class="trajectory-overlay" id="trajectoryOverlay" onclick="hideTrajectory(event)">'
h += '<div class="trajectory-panel" onclick="event.stopPropagation()">'
h += '<button class="close-btn" onclick="hideTrajectory()">✕</button>'
h += '<h3 id="trajTitle">📈 趋势轨迹</h3>'
h += '<div id="trajContent" style="margin-top:12px"></div>'
h += '</div></div>'

# Inject history + projection + health data as JS variables
h += '<script>'
h += 'var HISTORY_DATA = %s;' % json.dumps(history_data, ensure_ascii=False)
if projection_data:
    h += 'var PROJECTION_DATA = %s;' % json.dumps(projection_data, ensure_ascii=False)
else:
    h += 'var PROJECTION_DATA = null;'
if weights_data:
    h += 'var WEIGHTS_DATA = %s;' % json.dumps(weights_data, ensure_ascii=False)
else:
    h += 'var WEIGHTS_DATA = null;'
if health_data:
    h += 'var HEALTH_DATA = %s;' % json.dumps(health_data, ensure_ascii=False)
else:
    h += 'var HEALTH_DATA = null;'
h += 'var DATE_NAV = %s;' % json.dumps(date_nav, ensure_ascii=False)
h += 'var TODAY_DATE = "%s";' % data["date"]
# 历史日期数据不再嵌入主页(已生成独立HTML文件)
h += 'var DATE_FULL = null;'
h += '''
var STATE_COLORS = {1:"#6e7681",2:"#8b949e",3:"#42a5f5",4:"#26a69a",5:"#d29922","3p":"#da3633"};
var STATE_LABELS = {1:"下跌趋势",2:"下跌反弹",3:"翻转确认中",4:"上涨趋势",5:"上涨回调","3p":"转跌确认中"};
function showTrajectory(code) {
  var data = HISTORY_DATA[code];
  if (!data || data.length < 2) { alert("暂无足够历史数据"); return; }
  var recent = data.slice(-10);
  document.getElementById("trajTitle").textContent = "📈 " + code + " 趋势轨迹（近" + recent.length + "天）";
  var h = "";
  for (var i = 0; i < recent.length; i++) {
    var r = recent[i];
    var c = STATE_COLORS[r.state] || "#6e7681";
    var cs = r.conditions || {};
    var sa = cs.structure ? "pass" : "fail";
    var sv = cs.structure ? "A" : "A";
    var va = cs.volume ? "pass" : "fail";
    var vv = cs.volume ? "B" : "B";
    var pa = cs.persistence ? "pass" : "fail";
    var pv = cs.persistence ? "C" : "C";
    h += '<div class="trajectory-row">';
    h += '<span class="t-date">' + r.date + '</span>';
    h += '<span class="t-state" style="background:' + c + '"></span>';
    h += '<span style="font-weight:600;color:' + c + '">' + (STATE_LABELS[r.state]||r.state) + '</span>';
    h += '<span class="t-conds"><span class="t-cond ' + sa + '">' + sv + '</span>';
    h += '<span class="t-cond ' + va + '">' + vv + '</span>';
    h += '<span class="t-cond ' + pa + '">' + pv + '</span></span>';
    h += '<span style="font-size:10px;color:#8b949e">得分:' + (r.score||0) + '</span>';
    h += '</div>';
  }
  document.getElementById("trajContent").innerHTML = h;
  document.getElementById("trajectoryOverlay").classList.add("show");
}
function hideTrajectory(e) {
  if (e && e.target !== document.getElementById("trajectoryOverlay")) return;
  document.getElementById("trajectoryOverlay").classList.remove("show");
}
// Keyboard close
document.addEventListener("keydown", function(e) { if (e.key === "Escape") document.getElementById("trajectoryOverlay").classList.remove("show"); });
</script>'''

# 日期导航渲染JS(支持动态切换,不跳转页面)
h += '''<script>
function renderDateNav(){
  var nav=document.getElementById("dateNav");if(!nav||!DATE_NAV||!DATE_NAV.length)return;
  var h='<span style="font-size:10px;color:#d29922;font-weight:700;padding:4px 8px;white-space:nowrap;flex-shrink:0">📅</span>';
  for(var i=0;i<Math.min(DATE_NAV.length,60);i++){
    var d=DATE_NAV[i],isA=d.date==TODAY_DATE;
    var bg=isA?"rgba(88,166,255,0.2)":"#161b22";
    var bd=isA?"1px solid #58a6ff":"1px solid #30363d";
    var clr=isA?"#58a6ff":"#8b949e";
    h+='<a href="trend_dashboard_'+d.date+'.html" style="background:'+bg+';border:'+bd+';color:'+clr+';padding:4px 10px;border-radius:12px;font-size:10px;font-weight:600;text-decoration:none;white-space:nowrap;flex-shrink:0">'+d.date.substring(5)+' '+d.weekday+' '+d.uptrend_count+'涨</a>';
  }
  nav.innerHTML=h;
}
document.addEventListener("DOMContentLoaded",renderDateNav);
</script>'''

h += '<div class="footer">趋势跟随交易系统 | 焦点%d板块 | 趋势%d个股 | %dETF | %s | %d天回测 | ★主线 🔵翻转 | 5d状态条+sparkline | 推演+准确率+反思闭环 | 免责声明:仅供辅助参考</div></body></html>' % (len(focus), len(stocks), len(etfs), data["date"], len(daily_dates))

with open("dashboard/index.html", "w") as f: f.write(h)
with open("dashboard/trend_dashboard_%s.html" % data["date"], "w") as f: f.write(h)
print("✅ dashboard/index.html (%dKB)" % (len(h)/1024))
print("焦点=%d板块 个股=%d只" % (len(focus), len(stocks)))

# ====== 生成历史日期页面(使用同一个make_card函数保证格式100%一致) ======
print("📦 生成历史日期页面...")
import re as _re

# 板块名称/链接/ETF映射
_code_info = {}
for _s in data.get("sectors", []):
    _c = _s.get("code", _s.get("symbol", ""))
    if _c: _code_info[_c] = {"name": _s.get("name", _c), "link": _s.get("link", "#"), "etfs": _s.get("etfs", [])}

df_path = "dashboard/data/date_full_data.json"
if os.path.exists(df_path):
    df_full = json.load(open(df_path))
    v2_probs = df_full.get("v2_probs", {})
    all_dates_list = sorted(df_full.get("dates", {}).keys())

    # 转换v2_probs为weights格式(make_card需要w_dict)
    hist_weights = {}
    for st, probs in v2_probs.items():
        entries = sorted(probs.items(), key=lambda x: -x[1])
        hist_weights[st] = {
            "scenario_a": entries[0][1] if len(entries) > 0 else 0.6,
            "scenario_b": entries[1][1] if len(entries) > 1 else 0.3,
            "scenario_c": entries[2][1] if len(entries) > 2 else 0.1,
        }

    gen_count = 0
    for d in all_dates_list[-30:]:
        snap_path = f"dashboard/data/snapshot_{d}.json"
        if not os.path.exists(snap_path): continue

        snap = json.load(open(snap_path))
        ss_data = df_full["dates"][d]["sectors"]

        # 构建板块数据列表(兼容card函数)
        sectors_list = []
        for c, info in snap["sectors"].items():
            st = str(info["state"])
            if st not in ("4", "3", "5"): continue
            ss = ss_data.get(c, {})
            sec = {
                "code": c, "name": info.get("name", _code_info.get(c, {}).get("name", c)),
                "link": _code_info.get(c, {}).get("link", "#"),
                "state": info["state"],
                "state_label": info.get("state_label", sn(st)),
                "position": info.get("position", 0),
                "score": info.get("score", 0),
                "ma_deviation": info.get("ma_deviation", 0),
                "ret_20d": info.get("ret_20d", 0),
                "yang": info.get("yang", 0), "yin": info.get("yin", 0),
                "max_consecutive_yang": info.get("max_consecutive_yang", 0),
                "conditions": info.get("conditions", {}),
                "leaders": snap.get("leaders", {}).get(c, []),
                "etfs": _code_info.get(c, {}).get("etfs", []),
            }
            sectors_list.append(sec)

        sectors_list.sort(key=lambda x: (str(x["state"])!="4", str(x["state"])!="3", -x.get("score", 0)))

        # 用make_card生成卡片(传入ss_dict和w_dict)
        hist_ss = {}
        for c in ss_data:
            hist_ss[c] = {
                "streak_days": ss_data[c].get("streak", 0),
                "tomorrow_prob": ss_data[c].get("tomorrow_prob", 0),
                "avg_uptrend_days": ss_data[c].get("avg_uptrend", 0),
                "max_uptrend_days": ss_data[c].get("max_uptrend", 0),
                "expected_return": ss_data[c].get("expected_return", 0),
            }

        cards_html = ""
        for sec in sectors_list[:25]:
            cards_html += make_card(sec, False, hist_ss, hist_weights)
        if not cards_html:
            cards_html = '<div style="color:#8b949e;padding:40px;text-align:center">该日期无上涨/翻转板块</div>'

        up_c = sum(1 for s in sectors_list if str(s["state"]) == "4")
        fl_c = sum(1 for s in sectors_list if str(s["state"]) == "3")
        dn_c = snap["total"] - up_c - fl_c

        # 用今天页面模板替换内容
        hist_html = h
        hist_html = hist_html.replace('var TODAY_DATE = "%s"' % data["date"], 'var TODAY_DATE = "%s"' % d)
        hist_html = hist_html.replace('<title>趋势跟随交易系统</title>', '<title>趋势跟随交易系统 - %s</title>' % d)

        # 替换概览
        overview_new = '<div class="overview">'
        overview_new += '<div class="ov-item"><div class="v" style="color:#8b949e">%d</div><div class="l">全部板块</div></div>' % snap["total"]
        overview_new += '<div class="ov-item"><div class="v" style="color:#58a6ff">%d</div><div class="l">上涨趋势</div></div>' % up_c
        overview_new += '<div class="ov-item"><div class="v" style="color:#42a5f5">%d</div><div class="l">翻转确认</div></div>' % fl_c
        overview_new += '<div class="ov-item"><div class="v" style="color:#d29922">%d</div><div class="l">下跌/反弹</div></div>' % dn_c
        overview_new += '<div class="ov-item"><div class="v" style="color:#8b949e">%s</div><div class="l">%s</div></div>' % (d[5:], snap["health"])
        overview_new += '</div>'
        hist_html = _re.sub(r'<div class="overview">.*?</div>\s*<div class="panel">', overview_new + '\n<div class="panel">', hist_html, count=1, flags=_re.DOTALL)

        # 替换焦点板块
        fp = hist_html.find('<h2 style="color:#42a5f5">🔍 焦点板块')
        if fp > 0:
            fe = hist_html.find('<div class="panel"><h2>📈', fp)
            if fe < 0: fe = hist_html.find('<div class="panel"><h2>📊', fp)
            if fe < 0: fe = hist_html.find('<div class="all-t">', fp)
            if fe > 0:
                new_fp = '<h2 style="color:#42a5f5">🔍 焦点板块（%d个） — %s</h2><div class="focus-grid">%s</div>\n' % (len(sectors_list), d, cards_html)
                hist_html = hist_html[:fp] + new_fp + hist_html[fe:]

        with open("dashboard/trend_dashboard_%s.html" % d, "w") as f: f.write(hist_html)
        gen_count += 1

    print("   ✅ 生成%d个历史页面(格式与今天完全一致)" % gen_count)
else:
    print("   ⚠️ date_full_data.json不存在, 跳过历史页面")
