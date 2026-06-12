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
            score_text = f'{t["score"]}分' if t.get('state', 0) > 0 else '无趋势数据'
            h += f'<div style="margin:4px 0 4px 12px;font-size:11px">├ <span style="color:{tc}">{t["name"]}</span> <span style="color:#8b949e;font-size:10px">({score_text})</span>'
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
    panel += '<h2 style="color:#a371f7;margin-bottom:8px;font-size:16px">🔥 强势板块深度穿透 — 板块→ETF→龙头→题材 全链路</h2>'
    for c in cards:
        panel += render_card(c)
    panel += '</div>'

    h = open(dash_path).read()

    # 先删除已有的漏斗面板（避免重复注入）
    old_start = h.find('🔽 四级漏斗穿透')
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
