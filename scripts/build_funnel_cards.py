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
    '电子化学品': ['电子化学', '化工', '材料', '电子'],
    '非金属材料': ['非金属', '材料', '化工', '建材'],
    '金属新材料': ['金属', '新材料', '有色', '稀土', '材料'],
    '小金属': ['小金属', '稀有', '稀土', '钨', '有色', '金属'],
    '工业金属': ['工业金属', '有色', '金属', '铜', '铝'],
    '自动化设备': ['自动化', '机器人', '智能', '设备'],
    '通用设备': ['通用设备', '设备', '机械'],
    '军工电子': ['军工', '电子', '国防'],
    '能源金属': ['能源金属', '锂', '钴', '镍', '有色'],
    '塑料制品': ['塑料', '化工', '材料'],
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

    # 全量ETF池：从parquet目录扫描，不用top20硬编码
    import pandas as pd
    etf_names_map = {}
    etf_names_path = os.path.join(PROJECT, 'dashboard', 'data', 'etf_names.json')
    if os.path.exists(etf_names_path):
        etf_names_map = json.load(open(etf_names_path))
    # fallback: etf_list.json
    if not etf_names_map:
        etf_list_path = os.path.join(PROJECT, 'dashboard', 'data', 'etf_list.json')
        if os.path.exists(etf_list_path):
            for e in json.load(open(etf_list_path)):
                etf_names_map[e.get('symbol', e.get('code', ''))] = e.get('name', '')

    etf_pool = []
    etf_dir = os.path.join(PROJECT, 'dashboard', 'data', 'etf')
    if os.path.isdir(etf_dir):
        for fname in sorted(os.listdir(etf_dir)):
            if not fname.endswith('.parquet'): continue
            code = fname.replace('.parquet', '')
            name = etf_names_map.get(code, code)
            link = f'https://quote.eastmoney.com/sh{code}.html' if code.startswith('5') \
                   else f'https://quote.eastmoney.com/sz{code}.html'
            etf_pool.append({'code': code, 'name': name, 'score': 0, 'link': link})

    etf_holdings = {}
    if os.path.exists(os.path.join(PROJECT, 'data/etf_holdings.json')):
        etf_holdings = json.load(open(os.path.join(PROJECT, 'data/etf_holdings.json')))

    theme_holdings = {}
    if os.path.exists(os.path.join(PROJECT, 'data/theme_holdings.json')):
        theme_holdings = json.load(open(os.path.join(PROJECT, 'data/theme_holdings.json')))

    # 加载constituent_map反向映射（用于题材关联）
    cm = json.load(open(os.path.join(PROJECT, 'dashboard/data/constituent_map.json')))
    cm_rev = cm.get('reverse', {})

    # 加载主题名称映射
    theme_names_map = {}
    theme_list_path = os.path.join(PROJECT, 'dashboard', 'data', 'theme_list.json')
    if os.path.exists(theme_list_path):
        for t in json.load(open(theme_list_path)):
            theme_names_map[t.get('code', '')] = t.get('name', '')

    # 加载stock_names
    stock_names = {}
    sp = os.path.join(PROJECT, 'data/stock_names.json')
    if os.path.exists(sp):
        stock_names = json.load(open(sp))

    # 初始化增强扫描器（用于题材龙头趋势判定）
    import sys
    if PROJECT not in sys.path:
        sys.path.insert(0, PROJECT)
    from src.enhanced_actions import EnhancedActionGenerator
    gen = EnhancedActionGenerator()

    themes = dd.get('themes', [])
    sectors = [s for s in dd.get('sectors', []) if s.get('state', 0) >= 3]
    sectors.sort(key=lambda x: (-x.get('score', 0), -x.get('ret_20d', 0)))

    funnel_cards = []
    for sec in sectors[:6]:  # 从Top4扩展到Top6，覆盖更多板块
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

        # 趋势最强题材：从constituent_map反向映射，统计板块成分股的热门主题
        card['themes'] = []
        # 板块成分股：从constituent_map反向映射获取（同时用于龙头和题材）
        scode = sec.get('code', '')
        sector_stocks = []
        for code, info in cm_rev.items():
            if scode in info.get('sectors', []):
                sector_stocks.append(code)

        # 板块成分股龙头：用_build_card实时扫描取top3
        scored_leaders = []
        for code in sector_stocks:
            path = os.path.join(PROJECT, 'dashboard', 'data', 'stock', f'{code}.parquet')
            if not os.path.exists(path): continue
            name = stock_names.get(code, code)
            link = f'https://quote.eastmoney.com/sh{code}.html' if code.startswith(('6','9')) \
                   else f'https://quote.eastmoney.com/sz{code}.html'
            sc = gen._build_card({'code': code, 'name': name, 'link': link},
                                 date_str, is_etf=False)
            if sc and sc.get('state') in (3, 4):
                ctx = sc.get('trend_context', {})
                state_penalty = 1.0 if sc.get('state') == 4 else 0.5
                leader_score = (ctx.get('total_return_pct', 0) * 0.6 + sc.get('score', 0) * 0.4) * state_penalty
                scored_leaders.append({
                    'code': code, 'name': name,
                    'ret20': ctx.get('total_return_pct', 0),
                    'state': sc.get('state'),
                    'state_label': sc.get('state_label', ''),
                    'score': sc.get('score', 0),
                    '_sort': leader_score
                })
        scored_leaders.sort(key=lambda x: -x['_sort'])
        card['leaders'] = scored_leaders[:3]

        if sector_stocks:
            # 找出该板块关联的所有题材（去重）
            theme_set = set()
            for code in sector_stocks:
                for tcode in cm_rev.get(code, {}).get('themes', []):
                    theme_set.add(tcode)
            
            # 对每个题材做趋势评估：读parquet数据，计算评分
            import pandas as pd
            import numpy as np
            theme_scored = []
            for tcode in theme_set:
                tpath = os.path.join(PROJECT, 'dashboard', 'data', 'theme', f'{tcode}.parquet')
                if not os.path.exists(tpath): continue
                try:
                    tdf = pd.read_parquet(tpath)
                    if len(tdf) < 30: continue
                    close = tdf['close'].values
                    # 简单趋势评估：20日涨幅 + state判定
                    pct20 = (close[-1] / close[-21] - 1) * 100 if len(close) >= 21 else 0
                    ma20 = np.mean(close[-20:])
                    ma_dev = (close[-1] / ma20 - 1) * 100
                    # 粗略评分：20日涨幅越大越好，回调越少越好
                    score = pct20 * 0.5 + ma_dev * 0.3 + 30  # 基础分30
                    score = max(0, min(150, score))
                    theme_scored.append((tcode, score, pct20, ma_dev))
                except: pass
            
            # 按评分降序取top10
            theme_scored.sort(key=lambda x: -x[1])
            top_themes = theme_scored[:10]
            
            # 为每个主题找最强的趋势龙头
            for tcode, tscore, pct20, ma_dev in top_themes:
                tname = theme_names_map.get(tcode, tcode)
                # 从constituent_map找该主题的成分股，找主板块（出现频率最高的板块）
                t_stocks = []
                sector_counter = {}
                for code, info in cm_rev.items():
                    if tcode in info.get('themes', []):
                        t_stocks.append(code)
                        for sc in info.get('sectors', []):
                            sector_counter[sc] = sector_counter.get(sc, 0) + 1
                
                # 确定主板块（该题材真正的业务归属）
                main_sector = max(sector_counter, key=sector_counter.get) if sector_counter else None
                
                # 只取属于主板块的成分股（排除业务关联弱的杂股）
                t_filtered = [c for c in t_stocks if main_sector and main_sector in cm_rev.get(c, {}).get('sectors', [])]
                if len(t_filtered) < 3:
                    t_filtered = t_stocks  # 不够3只就不过滤
                
                # 扫描趋势，取top5
                scored = []
                for code in t_filtered[:100]:
                    path = os.path.join(PROJECT, 'dashboard', 'data', 'stock', f'{code}.parquet')
                    if not os.path.exists(path): continue
                    name = stock_names.get(code, code)
                    link = f'https://quote.eastmoney.com/sh{code}.html' if code.startswith(('6','9')) \
                           else f'https://quote.eastmoney.com/sz{code}.html'
                    sc = gen._build_card({'code': code, 'name': name, 'link': link},
                                           date_str, is_etf=False)
                    if sc and sc.get('state') in (3, 4) and sc.get('score', 0) >= 60:
                        ctx = sc.get('trend_context', {})
                        pct = ctx.get('total_return_pct', 0)
                        # 龙头排序：state=4上升趋势优先，state=3打折（不稳定的不算龙头）
                        state_penalty = 1.0 if sc.get('state') == 4 else 0.5
                        sort_key = (pct * 0.6 + sc['score'] * 0.4) * state_penalty
                        scored.append({'code': code, 'name': name, 'score': sc['score'], '_s': sort_key})
                scored.sort(key=lambda x: -x['_s'])
                
                tc = {'name': tname, 'code': tcode,
                      'state': 4 if pct20 > 5 else 3, 'score': round(tscore, 1),
                      'leaders': scored[:5]}
                # 匹配ETF
                t_etf = match_best_etf(tname, etf_pool)
                if t_etf:
                    tc['etf'] = {'name': t_etf['name'], 'code': t_etf['code'],
                                 'score': t_etf['score'], 'link': t_etf.get('link', '')}
                else:
                    tc['etf'] = None
                card['themes'].append(tc)

        funnel_cards.append(card)

    out = os.path.join(PROJECT, 'dashboard/data', f'funnel_cards_{date_str}.json')
    json.dump({'date': date_str, 'cards': funnel_cards}, open(out, 'w'),
              ensure_ascii=False, indent=2)
    print(f'✅ {date_str}: {len(funnel_cards)}板块')
    for c in funnel_cards:
        print(f'  {c["name"]}: ETF={(c.get("etf") or {}).get("name","无")} 题材={len(c["themes"])}个')


if __name__ == '__main__':
    ds = sys.argv[1] if len(sys.argv) > 1 else None
    if not ds:
        dd = json.load(open(os.path.join(PROJECT, 'dashboard/data/dashboard_data.json')))
        ds = dd.get('date', '')
    build(ds)
