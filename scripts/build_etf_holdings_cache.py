#!/usr/bin/env python3
"""
ETF持仓缓存 — 从东方财富拉取ETF成分股，缓存为JSON。
季度运行一次即可（持仓数据季度更新）。

用法:
  python3 scripts/build_etf_holdings_cache.py              # 拉取所有已有ETF
  python3 scripts/build_etf_holdings_cache.py 588170 159994 # 只拉指定ETF
"""
import json, os, re, sys, time
import requests

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_PATH = os.path.join(PROJECT, 'data', 'etf_holdings.json')
ETF_DIR = os.path.join(PROJECT, 'data', 'etf_stocks')
HEADERS = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}


def fetch_one(code: str) -> list[dict]:
    """拉取单只ETF全部成分股，尝试多个季度直到找到数据"""
    url = 'https://fundf10.eastmoney.com/FundArchivesDatas.aspx'
    quarters = [('2026', '1'), ('2025', '4'), ('2025', '3'), ('2025', '2'), ('2025', '1')]
    for year, month in quarters:
        params = {'type': 'jjcc', 'code': code, 'topline': 100, 'year': year, 'month': month}
        try:
            r = requests.get(url, params=params, timeout=15, headers=HEADERS)
            r.encoding = 'utf-8'
            # 兼容不同季度：2026有最新价/涨跌幅列，2025及之前没有
            # 匹配: <a href='.../1.688072'>688072</a>...</td>...<a...>拓荆科技</a>
            pattern = r"unify/r/[01]\.(\d+)'>(\d+)</a></td><td[^>]*>(?:<a[^>]*>)?([^<]+)</a>"
            stocks = []
            seen = set()
            for m in re.finditer(pattern, r.text):
                stock_code = m.group(1)
                stock_name = m.group(3)
                # 过滤非股票名称的列（股吧、行情、变动详情等）
                if stock_name in ('股吧', '行情', '变动详情'):
                    continue
                if stock_code not in seen:
                    seen.add(stock_code)
                    stocks.append({'code': stock_code, 'name': stock_name})
            if stocks:
                return stocks
        except Exception:
            continue
    return []


def main():
    # 加载已有缓存
    cache = {}
    if os.path.exists(CACHE_PATH):
        cache = json.load(open(CACHE_PATH))

    # 确定要拉取的ETF列表
    if len(sys.argv) > 1:
        codes = sys.argv[1:]
    else:
        codes = sorted(
            f.replace('etf_', '').replace('.pkl', '')
            for f in os.listdir(ETF_DIR) if f.endswith('.pkl')
        )

    new_count = 0
    for i, code in enumerate(codes):
        if code in cache and len(cache[code]) > 0:
            continue  # 已有缓存，跳过
        print(f'[{i+1}/{len(codes)}] {code}...', end=' ', flush=True)
        stocks = fetch_one(code)
        if stocks:
            cache[code] = stocks
            new_count += 1
            print(f'{len(stocks)}只')
        time.sleep(0.3)  # 避免请求过快

    json.dump(cache, open(CACHE_PATH, 'w'), ensure_ascii=False)
    print(f'\n✅ 缓存更新完成: {len(cache)}只ETF, 本次新增{new_count}只')


if __name__ == '__main__':
    main()
