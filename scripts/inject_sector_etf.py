#!/usr/bin/env python3
"""
板块→ETF反向关联注入 — 在每个焦点板块卡片底部追加最佳ETF推荐。

在 build_final + render_action_panel 之后运行。
从 enhanced_actions JSON 取 ETF 数据，按品类匹配到板块卡片，
str.replace 注入最佳ETF信息。

用法: python3 scripts/inject_sector_etf.py [date]
"""
import json, os, re, sys

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 板块名 → ETF品类关键词 映射（手写，覆盖主要板块）
SECTOR_ETF_MAP = {
    '半导体': ['半导体', '芯片'],
    '通信': ['通信', '5G'],
    '通信设备': ['通信', '5G'],
    '消费电子': ['消费电子'],
    '元件': ['半导体', '芯片'],
    '其他电子': ['半导体', '芯片', '消费电子', '5G'],
    '机器人': ['机器人'],
    '白色家电': ['消费电子', '家电'],
    '电机': ['机器人'],
    '军工': ['军工'],
    '医药': ['医药', '医疗'],
    '银行': ['银行'],
    '证券': ['证券'],
    '汽车': ['新能源车'],
    '电力': ['电力'],
    '煤炭': ['煤炭'],
    '传媒': ['传媒'],
    '食品饮料': ['食品饮料', '消费'],
}


def match_etf_to_sector(sector_name, etf_pool):
    """从ETF池中找到匹配板块的最佳ETF（按评分降序取第一只）"""
    keywords = SECTOR_ETF_MAP.get(sector_name, [sector_name])
    best = None
    for e in etf_pool:
        name = e.get('name', '')
        for kw in keywords:
            if kw in name:
                score = e.get('score', 0)
                if best is None or score > best.get('score', 0):
                    best = e
                break
    return best


def inject(dash_path, date_str):
    """向焦点板块每个卡片注入最佳ETF"""
    # 加载ETF数据
    ea_path = os.path.join(PROJECT, 'dashboard', 'data', f'enhanced_actions_{date_str}.json')
    if not os.path.exists(ea_path):
        print(f'  ❌ no enhanced_actions')
        return False

    ea = json.load(open(ea_path))
    etf_pool = ea.get('etf_cards', []) + ea.get('hot_etf_cards', [])

    # 加载板块列表
    dd_path = os.path.join(PROJECT, 'dashboard', 'data', 'dashboard_data.json')
    dd = json.load(open(dd_path))
    sectors = dd.get('sectors', [])

    # 读HTML
    h = open(dash_path).read()

    # 找到焦点板块区域
    fp_start = h.find('🔍 焦点板块')
    if fp_start < 0:
        print('  ❌ no 焦点板块')
        return False

    # 找焦点板块结束位置（下一个 WATCHLIST 或页面结束）
    wl = h.find('WATCHLIST', fp_start)
    if wl < 0:
        wl = h.find('<!--WATCHLIST-->', fp_start)
    fp_end = wl if wl > 0 else len(h)

    injected = 0
    # 对每个板块卡片注入
    for sector in sectors:
        sname = sector.get('name', '')
        if not sname:
            continue

        best = match_etf_to_sector(sname, etf_pool)
        if not best:
            continue

        # 在板块名附近找注入点
        idx = h.find(f'>{sname}<', fp_start, fp_end)
        if idx < 0:
            continue

        # 构建注入HTML（极简，复用现有样式）
        etf_html = (
            f'<div style="font-size:10px;color:#f59e0b;margin-top:6px;padding-top:4px;'
            f'border-top:1px solid #21262d">'
            f'📊 最佳ETF: <a href="{best.get("link","#")}" target="_blank" '
            f'style="color:#f59e0b">{best.get("name","")}</a>'
            f'<span style="color:#8b949e">({best.get("score",0):.0f}分)</span>'
            f'</div>'
        )

        # 在这个板块卡片结束前注入（找下一个card-clickable或focus-grid结束）
        end_pos = h.find('class="card-clickable"', idx + 1, fp_end)
        if end_pos < 0:
            end_pos = h.find('</div>', h.find('focus-grid', fp_start), fp_end)

        # 精确定位：找板块卡片末尾的 </table></div>
        card_end_marker = h.find('</table>', idx, end_pos if end_pos > 0 else fp_end)
        if card_end_marker > 0:
            card_end = h.find('</div>', card_end_marker + 8)
            if card_end > 0 and card_end < (end_pos if end_pos > 0 else fp_end):
                h = h[:card_end] + etf_html + h[card_end:]
                injected += 1

    open(dash_path, 'w').write(h)
    print(f'  ✅ {date_str}: 板块→ETF 注入{injected}处')
    return injected > 0


if __name__ == '__main__':
    ds = sys.argv[1] if len(sys.argv) > 1 else None
    if not ds:
        dd = json.load(open(os.path.join(PROJECT, 'dashboard', 'data', 'dashboard_data.json')))
        ds = dd.get('date', '')
    dash = os.path.join(PROJECT, 'dashboard', f'trend_dashboard_{ds}.html')
    inject(dash, ds)
