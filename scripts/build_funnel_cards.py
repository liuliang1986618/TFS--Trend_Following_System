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
    '白色家电': ['家电', '消费电子', '智能家居'],
    '白酒': ['白酒', '酒'], '电力': ['电力', '绿电'],
    '零售': ['零售', '电商', '消费'],
    '光学光电子': ['光学', '光电子', 'LED'],
}


# ETF产品关键词 → 同义词扩展（题材→ETF匹配时，芯片≈半导体）
KW_SYNONYMS = {'芯片': ['芯片', '半导体'], '半导体': ['半导体', '芯片'],
               '5G': ['5G', '通信'], '通信': ['通信', '5G'],
               '光伏': ['光伏', '新能源'], '锂电池': ['锂电池', '新能源']}

ETF_PRODUCT_KW = ['半导体', '芯片', '通信', '5G', '消费电子', '机器人',
                  '新能源', '光伏', '锂电池', '军工', '医药', '银行', '证券',
                  '煤炭', '电力', '传媒', '食品饮料', '白酒', '家电', '汽车']

def match_best_etf(name, etf_pool):
    keywords = CATEGORY_ETF_MAP.get(name, [])
    if not keywords:
        for kw in ETF_PRODUCT_KW:
            if kw in name:
                # 扩展同义词（芯片→[芯片,半导体]）
                keywords.extend(KW_SYNONYMS.get(kw, [kw]))
        if not keywords:
            keywords = [name]
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
        # 完整板块信息（从dashboard_data搬过来）
        card = {
            'name': sname, 'code': sec.get('code', ''),
            'state': sec.get('state'), 'state_label': sec.get('state_label', ''),
            'score': sec.get('score', 0), 'position': sec.get('position', 0),
            'ma_deviation': sec.get('ma_deviation', 0), 'ret_20d': sec.get('ret_20d', 0),
            'yang': sec.get('yang', 0), 'yin': sec.get('yin', 0),
            'max_consecutive_yang': sec.get('max_consecutive_yang', 0),
            'vol_ratio': sec.get('vol_ratio', 0),
            'conditions': sec.get('conditions', {}),
            'signals': sec.get('signals', {}),
            'prev_high': sec.get('prev_high', {}),
            'prev_low': sec.get('prev_low', {}),
            'stop_loss': sec.get('stop_loss', 0),
            'is_mainline': sec.get('is_mainline', False),
            'link': sec.get('link', '#'),
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

        # 趋势最强题材：用全量theme_list做关键词匹配
        theme_list_path = os.path.join(PROJECT, 'dashboard', 'data', 'theme_list.json')
        all_theme_names = []
        if os.path.exists(theme_list_path):
            all_theme_names = json.load(open(theme_list_path))

        theme_index = {t.get('name', ''): t for t in themes}
        keywords = CATEGORY_ETF_MAP.get(sname, [sname])
        related = []
        for tn in all_theme_names:
            tname = tn.get('name', '')
            tcode = tn.get('code', '')
            matched = any(kw in tname for kw in keywords)
            if not matched:
                continue
            if tname in theme_index:
                t = theme_index[tname]
                if t.get('state', 0) >= 3:
                    related.append(t)
            elif theme_holdings.get(tcode):
                related.append({'name': tname, 'code': tcode, 'state': 0, 'score': 0,
                                '_no_data': True})

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
            # 题材龙头：从theme_holdings取成分股，趋势择优
            th_code = t.get('code', '')
            th_stocks = theme_holdings.get(th_code, [])
            tc['leaders'] = get_trend_leaders(th_stocks, date_str) if th_stocks else []
            card['themes'].append(tc)

        funnel_cards.append(card)

    out = os.path.join(PROJECT, 'dashboard/data', f'funnel_cards_{date_str}.json')
    json.dump({'date': date_str, 'cards': funnel_cards}, open(out, 'w'),
              ensure_ascii=False, indent=2)
    print(f'✅ {date_str}: {len(funnel_cards)}板块')
    for c in funnel_cards:
        etf_info = c.get("etf") or {}
        print(f'  {c["name"]}: ETF={etf_info.get("name","无")} 题材={len(c["themes"])}个')


if __name__ == '__main__':
    ds = sys.argv[1] if len(sys.argv) > 1 else None
    if not ds:
        dd = json.load(open(os.path.join(PROJECT, 'dashboard/data/dashboard_data.json')))
        ds = dd.get('date', '')
    build(ds)
