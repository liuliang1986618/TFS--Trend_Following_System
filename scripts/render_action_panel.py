#!/usr/bin/env python3
"""
操作建议面板 — 从标准模板提取面板HTML，注入到build_final产出的仪表板中。
页面其他部分（概览/板块/个股表）由build_final按日期生成，不受影响。
"""
import json, os, sys, re

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMPL = os.path.join(PROJECT, 'dashboard', 'data', 'standard_template.html')


def extract_action_panel(html):
    """从HTML中提取操作建议面板（从panel div到焦点板块之前）"""
    start = html.find('<div class="panel" style="margin:10px 20px 12px;border:2px solid #4ade80')
    if start < 0:
        return None
    end = html.find('🔍 焦点板块', start)
    if end < 0:
        return None
    end = html.rfind('<div class="panel"', start, end)
    if end < 0:
        return None
    return html[start:end]


def replace_panel_data(panel_html, date_str, etfs, stocks, regime):
    """替换面板中所有数据值"""
    h = panel_html

    # 日期全量替换
    h = h.replace('2026-06-08', date_str)
    # regime替换
    rm = {'bull': '强牛', 'bear': '强熊', 'normal': '震荡'}
    h = h.replace('强熊', rm.get(regime, '强熊'))

    # 找到所有卡片位置
    card_starts = [m.start() for m in re.finditer(
        r'<div style="background:rgba\(22,27,34,0\.6\);border:1px solid #30363d', h)]

    old_cards = []
    for start in card_starts:
        name_m = re.search(r'font-size:14px">([^<]+)</a>', h[start:start + 20000])
        code_m = re.search(r'\((\d+)\)</span>', h[start:start + 20000])
        score_m = re.search(r'评分 ([\d.]+)', h[start:start + 20000])
        if name_m:
            old_cards.append({
                'start': start,
                'name': name_m.group(1),
                'code': code_m.group(1) if code_m else '?',
                'score': score_m.group(1) if score_m else '?',
            })

    all_new = list(etfs[:5]) + list(stocks[:5])
    for i in range(min(10, len(old_cards), len(all_new))):
        old, new = old_cards[i], all_new[i]
        pos = old['start']
        # 名称
        idx = h.find(old['name'], pos)
        if idx > 0:
            h = h[:idx] + new['name'] + h[idx + len(old['name']):]
        # 代码
        old_code = f'({old["code"]})</span>'
        idx = h.find(old_code, pos)
        if idx > 0:
            h = h[:idx] + f'({new["code"]})</span>' + h[idx + len(old_code):]
        # 评分
        old_score = f'评分 {old["score"]}'
        idx = h.find(old_score, pos)
        if idx > 0:
            h = h[:idx] + f'评分 {new["score"]:.1f}' + h[idx + len(old_score):]
        # action_label
        al_match = re.search(r'💡 ([^<]+)</div>', h[pos:pos + 20000])
        if al_match:
            old_al = f'💡 {al_match.group(1)}</div>'
            new_al = f'💡 {new.get("action_label", "")[:150]}</div>'
            al_pos = pos + al_match.start()
            h = h[:al_pos] + new_al + h[al_pos + len(old_al):]
        # 链接
        old_ln = f'sh{old["code"]}.html' if old['code'].startswith(('5', '6')) else f'sz{old["code"]}.html'
        new_ln = f'sh{new["code"]}.html' if new['code'].startswith(('5', '6')) else f'sz{new["code"]}.html'
        idx = h.find(old_ln, pos)
        if idx > 0:
            h = h[:idx] + new_ln + h[idx + len(old_ln):]

    return h


def inject(dashboard_path, panel_html):
    """注入面板到仪表板（替换旧操作建议面板或插入到焦点板块之前）"""
    if not panel_html:
        return
    html = open(dashboard_path).read()
    # 删除旧的操作建议面板
    old_start = html.find('<div class="panel" style="margin:10px 20px 12px;border:2px solid #4ade80')
    if old_start > 0:
        old_end = html.find('🔍 焦点板块', old_start)
        if old_end > 0:
            old_end = html.rfind('<div class="panel"', old_start, old_end)
            if old_end > 0:
                html = html[:old_start] + html[old_end:]
    # 注入新面板
    marker = '<div class="panel"><h2 style="color:#42a5f5">🔍 焦点板块'
    idx = html.find(marker)
    if idx < 0:
        idx = html.find('🔍 焦点板块')
        if idx > 0:
            idx = html.rfind('<div class="panel"', 0, idx)
    if idx > 0:
        html = html[:idx] + panel_html + html[idx:]
        open(dashboard_path, 'w').write(html)
        return True
    return False


def process_date(date_str):
    """处理单个日期：加载build_final产出 → 注入操作建议面板（稳健+强势）"""
    # 确保 dashboard 文件存在
    dash_path = os.path.join(PROJECT, 'dashboard', f'trend_dashboard_{date_str}.html')
    if not os.path.exists(dash_path):
        # 尝试运行 build_final
        import subprocess
        dd = json.load(open(os.path.join(PROJECT, 'dashboard', 'data', 'dashboard_data.json')))
        dd['date'] = date_str
        json.dump(dd, open(os.path.join(PROJECT, 'dashboard', 'data', 'dashboard_data.json'), 'w'),
                  ensure_ascii=False, indent=2)
        subprocess.run([sys.executable, os.path.join(PROJECT, 'scripts', 'build_final.py')],
                       capture_output=True, timeout=60)

    if not os.path.exists(dash_path):
        print(f'  ❌ {date_str}: no dashboard file')
        return False

    # 加载增强数据（含新增的强势追踪字段）
    ea_path = os.path.join(PROJECT, 'dashboard', 'data', f'enhanced_actions_{date_str}.json')
    if not os.path.exists(ea_path):
        print(f'  ❌ {date_str}: no enhanced_actions')
        return False

    ea = json.load(open(ea_path))
    regime = ea.get('market_regime', 'bear')
    etfs = sorted(ea['etf_cards'], key=lambda x: x.get('score', 0), reverse=True)[:5]
    stocks = sorted(ea['stock_cards'], key=lambda x: x.get('score', 0), reverse=True)[:5]
    hot_etfs = ea.get('hot_etf_cards', [])[:5]
    hot_stocks = ea.get('hot_stock_cards', [])[:5]

    # 加载标准模板，提取操作建议面板
    tmpl_html = open(TMPL).read()
    panel_tmpl = extract_action_panel(tmpl_html)
    if not panel_tmpl:
        print(f'  ❌ {date_str}: cannot extract panel from template')
        return False

    # 面板1: 稳健推荐（绿色边框，沿用原模板配色）
    panel1 = replace_panel_data(panel_tmpl, date_str, etfs, stocks, regime)
    panel1 = panel1.replace('📋 明日操作建议', '📋 稳健推荐 — 趋势初期，适合建仓')
    panel1 = panel1.replace('ETF操作', 'ETF稳健')
    panel1 = panel1.replace('个股操作', '个股稳健')

    # 面板2: 强势追踪（橙色边框，趋势强但过热）
    hot_panel = ''
    if hot_etfs or hot_stocks:
        panel2 = replace_panel_data(panel_tmpl, date_str, hot_etfs, hot_stocks, regime)
        panel2 = panel2.replace('📋 明日操作建议', '🔥 强势追踪 — 趋势极强但短期过热，等回调再进')
        panel2 = panel2.replace('ETF操作', 'ETF强势')
        panel2 = panel2.replace('个股操作', '个股强势')
        # 绿框 → 橙框，区分视觉
        panel2 = panel2.replace('border:2px solid #4ade80', 'border:2px solid #f59e0b')
        panel2 = panel2.replace('rgba(74,222,128,', 'rgba(245,158,11,')
        panel2 = panel2.replace('color:#4ade80', 'color:#f59e0b')
        hot_panel = panel2

    # 注入（稳健面板 + 强势面板拼在一起）
    combined = panel1 + hot_panel
    if inject(dash_path, combined):
        size = os.path.getsize(dash_path)
        w = combined.count('widget-details')
        hot_count = len(hot_etfs) + len(hot_stocks)
        print(f'  ✅ {date_str}: {size}b widgets={w} hot_cards={hot_count}')
        return True
    print(f'  ❌ {date_str}: inject failed')
    return False


if __name__ == '__main__':
    # 默认使用 dashboard_data.json 中的日期，而非硬编码
    if len(sys.argv) > 1:
        ds = sys.argv[1]
    else:
        from datetime import datetime as _dt
        dd = json.load(open(os.path.join(PROJECT, 'dashboard', 'data', 'dashboard_data.json')))
        ds = dd.get('date', _dt.now().strftime('%Y-%m-%d'))
    if ds == 'all':
        dates_dir = os.path.join(PROJECT, 'data', 'dates')
        for d in sorted(os.listdir(dates_dir)):
            process_date(d)
    else:
        process_date(ds)
