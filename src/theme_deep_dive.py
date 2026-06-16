"""题材深度穿透 — 全成分股评分排序+分类统计+智能结论.

用法: python3 src/theme_deep_dive.py <theme_code> [date]
示例: python3 src/theme_deep_dive.py 309004 2026-06-15
输出: dashboard/data/theme_dive_{date}.json
"""
import json, os, sys
from datetime import datetime
import numpy as np, pandas as pd

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(PROJECT)
sys.path.insert(0, PROJECT)
from src.enhanced_actions import EnhancedActionGenerator

# 业务分类映射 (行业标准, 按code→类别)
THEME_309004_CATEGORIES = {
    '600584':'封测','002156':'封测','002185':'封测','603005':'封测',
    '688362':'封测','002077':'封测','600667':'封测','000021':'封测',
    '688352':'封测','002119':'封测',
    '688456':'材料','600206':'材料','002741':'材料','300398':'材料',
    '002409':'材料','002669':'材料','300236':'材料','688603':'材料',
    '605589':'材料','688020':'材料','600703':'材料',
    '300747':'设备','300776':'设备','688559':'设备','002008':'设备',
    '301200':'设备','300604':'设备','688200':'设备','688012':'设备',
    '002371':'设备','300751':'设备','301682':'设备',
    '603773':'显示','600552':'显示','002449':'显示','300433':'显示',
    '300088':'显示','300303':'显示','002429':'显示',
}
CATEGORY_MAPS = {'309004': THEME_309004_CATEGORIES}


class ThemeDeepDive:
    """题材深度穿透分析器。"""

    def __init__(self):
        self.gen = EnhancedActionGenerator()
        self.stock_names = json.load(open(os.path.join(PROJECT, 'data/stock_names.json')))
        self.th = json.load(open(os.path.join(PROJECT, 'data/theme_holdings.json')))

    def analyze(self, theme_code: str, date_str: str) -> dict:
        tl = json.load(open(os.path.join(PROJECT, 'dashboard/data/theme_list.json')))
        theme_name = next((t['name'] for t in tl if t['code'] == theme_code), theme_code)
        cat_map = CATEGORY_MAPS.get(theme_code, {})
        stocks = self.th.get(theme_code, [])
        if not stocks:
            return {"error": f"题材{theme_code}无成分股数据"}

        results, missing_pkl = [], []
        for s in stocks:
            code, name = s['code'], s['name']
            name = self.stock_names.get(code, name)
            cat = cat_map.get(code, '其他')
            path = os.path.join(PROJECT, f'data/massive_stocks/{code}.pkl')
            if not os.path.exists(path):
                missing_pkl.append({'code': code, 'name': name, 'category': cat})
                continue
            try:
                df = pd.read_pickle(path)
                df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
                df = df[df['date'] <= date_str]
                if len(df) < 60: continue
            except Exception:
                missing_pkl.append({'code': code, 'name': name, 'category': cat})
                continue

            c = df['close'].astype(float).values
            h = df['high'].astype(float).values
            card = self.gen._build_card(
                {'code': code, 'name': name, 'link': self.gen._stock_link(code)},
                date_str, is_etf=False)

            p = c[-1]
            pct5 = (c[-1] / c[-6] - 1) * 100 if len(c) >= 6 else 0
            pct20 = (c[-1] / c[-21] - 1) * 100 if len(c) >= 21 else 0
            pct60 = (c[-1] / c[-61] - 1) * 100 if len(c) >= 61 else 0
            dd = (p / np.max(h[-20:]) - 1) * 100
            delta = np.diff(c[-15:])
            g = np.maximum(delta, 0); lo = np.abs(np.minimum(delta, 0))
            rsi = 100 - (100 / (1 + np.mean(g) / np.mean(lo))) if np.mean(lo) > 0 else 100

            results.append({
                'code': code, 'name': name, 'category': cat,
                'state': card['state'] if card else 0,
                'score': card['score'] if card else 0,
                'position_pct': card.get('position_pct', 0) if card else 0,
                'action': card.get('action', '')[:100] if card else '',
                'passed': card is not None,
                'pct5': round(pct5, 1), 'pct20': round(pct20, 1),
                'pct60': round(pct60, 1), 'dd': round(dd, 1), 'rsi': round(rsi, 1),
            })

        passed = sorted([r for r in results if r['passed']], key=lambda x: -x['score'])
        failed = sorted([r for r in results if not r['passed']], key=lambda x: -x['pct20'])
        ranking = passed + failed

        cats = {}
        for r in results:
            cat = r['category']
            if cat not in cats:
                cats[cat] = {'total': 0, 'passed': 0, 'scores': [], 'tp': '', 'ts': 0}
            cats[cat]['total'] += 1
            if r['passed']:
                cats[cat]['passed'] += 1
                cats[cat]['scores'].append(r['score'])
                if r['score'] > cats[cat]['ts']:
                    cats[cat]['ts'] = r['score']; cats[cat]['tp'] = r['name']

        categories = {}
        for cat, d in sorted(cats.items()):
            categories[cat] = {
                'total': d['total'], 'passed': f"{d['passed']}/{d['total']}",
                'avg_score': round(sum(d['scores']) / len(d['scores']), 0) if d['scores'] else 0,
                'top_name': d['tp'], 'top_score': d['ts'],
            }

        conclusion = self._conclude(theme_name, ranking, categories, missing_pkl)
        return {
            'date': date_str, 'theme': {'code': theme_code, 'name': theme_name},
            'data_quality': {'total': len(stocks), 'with_pkl': len(results),
                             'missing_pkl': len(missing_pkl), 'passed': len(passed)},
            'categories': categories, 'ranking': ranking,
            'missing_pkl': missing_pkl, 'conclusion': conclusion,
        }

    def _conclude(self, theme_name, ranking, categories, missing_pkl):
        passed = [r for r in ranking if r['passed']]
        if not passed:
            return f"{theme_name}: 无标的通过系统筛选。"
        parts = []
        if len(categories) >= 2:
            best = max(categories.items(), key=lambda x: x[1]['avg_score'])
            worst = min(categories.items(), key=lambda x: x[1]['avg_score'])
            if best[1]['avg_score'] - worst[1]['avg_score'] > 10:
                parts.append(f"{best[0]}均分{best[1]['avg_score']:.0f}最高,{worst[0]}{worst[1]['avg_score']:.0f}最低。")

        top1 = passed[0]
        flags = []
        if top1['dd'] > -5: flags.append(f"回撤仅{abs(top1['dd']):.1f}%")
        if top1['pct20'] > 30: flags.append("20日涨幅大需谨慎")
        if top1['rsi'] < 35: flags.append("RSI超卖可能见底")
        if top1['pct5'] < -3: flags.append("短期回调等企稳")
        parts.append(f"{top1['name']}(sc={top1['score']:.0f}): {'; '.join(flags)}" if flags else top1['name'])

        for r in passed[:5]:
            if abs(r['pct60']) > 200:
                parts.append(f"{r['name']}60日涨{abs(r['pct60']):.0f}%注意风险")

        if len(passed) >= 3:
            for name, sc, dd, p5 in [(r['name'], r['score'], r['dd'], r['pct5']) for r in passed[:3]]:
                if abs(dd) < 10 and p5 > -3:
                    parts.insert(1, f"首选{name}(高分低回撤非急跌)。")
                    break

        if missing_pkl:
            names = [m['name'] for m in missing_pkl[:5]]
            parts.append(f"⚠️{len(missing_pkl)}只缺数据({','.join(names)}等)")

        return ' '.join(parts)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python3 src/theme_deep_dive.py <theme_code> [date]")
        print("Example: python3 src/theme_deep_dive.py 309004 2026-06-15")
        sys.exit(1)

    theme_code = sys.argv[1]
    date_str = sys.argv[2] if len(sys.argv) > 2 else datetime.now().strftime('%Y-%m-%d')
    diver = ThemeDeepDive()
    result = diver.analyze(theme_code, date_str)
    if 'error' in result:
        print(f"❌ {result['error']}")
        sys.exit(1)

    out_path = os.path.join(PROJECT, 'dashboard', 'data', f"theme_dive_{date_str}.json")
    with open(out_path, 'w') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    dq = result['data_quality']
    print(f"✅ {result['theme']['name']}({result['theme']['code']})")
    print(f"   数据:{dq['total']}只 有效:{dq['with_pkl']}只 通过:{dq['passed']}只 缺:{dq['missing_pkl']}只")
    for cat, d in result['categories'].items():
        print(f"   {cat}: {d['passed']}通过 均分{d['avg_score']:.0f} Top:{d['top_name']}({d['top_score']:.0f})")
    print(f"   Top3: {', '.join(r['name'] for r in result['ranking'][:3])}")
    print(f"   结论: {result['conclusion']}")
    print(f"   输出: {out_path}")
