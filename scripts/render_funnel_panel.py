#!/usr/bin/env python3
"""四级漏斗面板渲染"""
import json, os, sys

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def render_card(c):
    sc = {4: '#26a69a', 3: '#42a5f5'}.get(c.get('state', 0), '#8b949e')
    h = f'<div style="background:#161b22;border:2px solid {sc};border-radius:8px;padding:12px;margin-bottom:12px">'

    # 标题：板块名 + 代码 + 状态标签 + 评分
    code = c.get('code', '')
    h += f'<div style="font-size:14px;font-weight:700;color:#e6edf3;margin-bottom:2px">'
    h += f'🔵 <a href="{c.get("link","#")}" target="_blank" style="color:#e6edf3;text-decoration:none">{c["name"]}</a>'
    h += f' <span style="font-size:10px;color:#8b949e">{code}</span></div>'
    h += f'<span style="display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:700;background:{sc};color:#fff">{c.get("state_label","")}</span>'
    h += f' <span style="font-size:11px;color:#8b949e">📊{c["score"]}分</span>'

    # 板块指标
    ret = c.get('ret_20d', 0)
    ma_dev = c.get('ma_deviation', 0)
    yang = c.get('yang', 0)
    yin = c.get('yin', 0)
    vol_r = c.get('vol_ratio', 0)
    pos = c.get('position', 0)
    h += f'<div style="font-size:10px;color:#8b949e;margin:4px 0">'
    h += f'MA20:{ma_dev:+.1f}% | 20日:{ret:+.1f}% | 阳{yang}/阴{yin} | 量比{vol_r:.1f} | 仓位:{pos*100:.0f}%'
    h += '</div>'

    # ABC条件
    cond = c.get('conditions', {})
    if cond:
        h += '<div style="font-size:11px;margin:4px 0">'
        for key, label in [('structure','A 结构'), ('volume','B 量能'), ('persistence','C 持续性')]:
            v = cond.get(key, {})
            ok = v.get('pass', False)
            color = '#26a69a' if ok else '#ef5350'
            icon = '✅' if ok else '❌'
            h += f'<div style="margin:1px 0"><span style="color:{color}">{icon}</span> {label}: {v.get("detail","")}</div>'
        h += '</div>'

    h += '<div style="border-top:1px solid #21262d;margin:8px 0"></div>'

    # 最佳ETF + 成分股龙头
    etf = c.get('etf')
    if etf:
        h += f'<div style="font-size:11px;margin:4px 0">📊 最佳ETF: <a href="{etf.get("link","#")}" target="_blank" style="color:#f59e0b;text-decoration:none">{etf["name"]}</a> <span style="color:#8b949e">({etf["score"]:.0f}分)</span>'
        if etf.get('leaders'):
            names = ' '.join(l['name'] for l in etf['leaders'][:3])
            h += f' <span style="color:#8b949e;font-size:10px">└ {names}</span>'
        h += '</div>'

    # 板块龙头
    leaders = c.get('leaders', [])
    if leaders:
        h += '<div style="font-size:10px;color:#d29922;font-weight:700;margin:6px 0 2px">🏆 板块龙头（近20日涨幅）</div>'
        for l in leaders[:3]:
            ret20 = l.get('ret20', 0)
            h += f'<span style="color:#4ade80;font-size:10px">{l.get("name",l.get("code"))}({ret20:+.1f}%)</span> '

    h += '<div style="border-top:1px solid #21262d;margin:8px 0"></div>'

    # 趋势最强题材
    themes = c.get('themes', [])
    if themes:
        h += '<div style="font-size:10px;color:#8b949e;margin-bottom:2px">🔗 趋势最强题材:</div>'
        for t in themes:
            tc = {4: '#26a69a', 3: '#42a5f5'}.get(t.get('state', 0), '#8b949e')
            score_text = f'{t["score"]}分' if t.get('state', 0) > 0 else ''
            h += f'<div style="margin:2px 0 2px 12px;font-size:11px">├ <span style="color:{tc}">{t["name"]}</span> <span style="color:#8b949e;font-size:10px">{score_text}</span>'
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

    panel = '<div class="panel" style="margin:10px 20px 12px;border:2px solid #d29922;border-radius:10px;padding:16px;background:linear-gradient(135deg,rgba(210,153,34,0.08),rgba(210,153,34,0.02))">'
    panel += '<h2 style="color:#d29922;margin-bottom:2px;font-size:16px">🔥 强势板块深度穿透</h2>'
    panel += '<p style="color:#8b949e;font-size:10px;margin-bottom:8px">Top3趋势最强板块（state≥3，按评分降序） | 每板块下钻：ETF→成分股龙头→趋势最强题材</p>'
    panel += '<div class="focus-grid">'  # 使用双列布局
    for c in cards:
        panel += render_card(c)
    panel += '</div></div>'

    h = open(dash_path).read()

    # 先删除已有的漏斗面板（避免重复注入）
    old_start = h.find('强势板块深度穿透')
    if old_start > 0:
        old_end = h.find('<div class="panel"', old_start + 1)
        if old_end > 0:
            h = h[:old_start] + h[old_end:]

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
