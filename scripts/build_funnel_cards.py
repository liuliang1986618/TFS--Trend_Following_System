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
        print(f'  {c["name"]}: ETF={c.get("etf",{}).get("name","无")} 题材={len(c["themes"])}个')


if __name__ == '__main__':
    ds = sys.argv[1] if len(sys.argv) > 1 else None
    if not ds:
        dd = json.load(open(os.path.join(PROJECT, 'dashboard/data/dashboard_data.json')))
        ds = dd.get('date', '')
    build(ds)
