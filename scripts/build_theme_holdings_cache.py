#!/usr/bin/env python3
"""题材成分股缓存 — 从akshare拉取题材板块成分股"""
import json, os, sys, time, re, ssl, urllib.request
import akshare as ak

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_PATH = os.path.join(PROJECT, 'data', 'theme_holdings.json')

# SSL context for urllib (ignore cert for 10jqka scraping)
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE


def fetch_one_em(theme_name: str) -> list[dict]:
    """通过东方财富API拉取成分股"""
    try:
        df = ak.stock_board_concept_cons_em(symbol=theme_name)
        stocks = []
        for _, row in df.iterrows():
            code = str(row.get('代码', row.get('code', '')))
            name = str(row.get('名称', row.get('name', '')))
            if code and name:
                stocks.append({'code': code, 'name': name})
        return stocks
    except Exception as e:
        print(f'EM: {e}', end=' ')
        return []


def fetch_one_ths(ths_code: str) -> list[dict]:
    """通过同花顺概念页抓取成分股（第一页）"""
    try:
        url = f'http://q.10jqka.com.cn/gn/detail/code/{ths_code}/'
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        resp = urllib.request.urlopen(req, timeout=15, context=_SSL_CTX)
        html = resp.read().decode('gbk', errors='ignore')

        # Parse stock table rows: 代码→名称 columns
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL)
        stocks = []
        seen = set()
        for row in rows:
            # Extract 6-digit codes and names from table cells
            cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
            for i, cell in enumerate(cells):
                code_match = re.search(r'\b(\d{6})\b', re.sub(r'<[^>]+>', '', cell))
                if code_match:
                    code = code_match.group(1)
                    # Next cell(s) should contain the name
                    name = None
                    for j in range(i + 1, len(cells)):
                        name_text = re.sub(r'<[^>]+>', '', cells[j]).strip()
                        # Filter out numeric-only cells (price/percentage)
                        if name_text and not re.match(r'^[\d.\-+%]+$', name_text) and re.search(r'[一-鿿]', name_text):
                            name = name_text
                            break
                    if name and code not in seen:
                        seen.add(code)
                        stocks.append({'code': code, 'name': name})
                        break
        return stocks
    except Exception as e:
        print(f'THS: {e}', end=' ')
        return []


def fetch_one(theme_name: str, ths_code: str = '') -> list[dict]:
    """拉取单个题材的成分股（优先EM API，回退THS页面抓取）"""
    stocks = fetch_one_em(theme_name)
    if not stocks and ths_code:
        stocks = fetch_one_ths(ths_code)
    return stocks


def main():
    cache = {}
    if os.path.exists(CACHE_PATH):
        cache = json.load(open(CACHE_PATH))

    theme_list_path = os.path.join(PROJECT, 'dashboard', 'data', 'theme_list.json')
    themes = json.load(open(theme_list_path))

    new_count = 0
    for i, t in enumerate(themes):
        name = t['name']
        code = t['code']
        if code in cache and len(cache[code]) > 0:
            continue
        print(f'[{i+1}/{len(themes)}] {name}...', end=' ', flush=True)
        stocks = fetch_one(name, code)
        if stocks:
            cache[code] = stocks
            new_count += 1
            print(f'{len(stocks)}只')
        else:
            print('0只')
        time.sleep(0.3)

    json.dump(cache, open(CACHE_PATH, 'w'), ensure_ascii=False)
    print(f'\n✅ 缓存: {len(cache)}个题材, 新增{new_count}')


if __name__ == '__main__':
    if len(sys.argv) > 1:
        cache = {}
        if os.path.exists(CACHE_PATH):
            cache = json.load(open(CACHE_PATH))
        # Load theme_list for code lookup when using CLI names
        theme_map = {}
        theme_list_path = os.path.join(PROJECT, 'dashboard', 'data', 'theme_list.json')
        if os.path.exists(theme_list_path):
            theme_map = {t['name']: t['code'] for t in json.load(open(theme_list_path))}
        for name in sys.argv[1:]:
            print(f'{name}...', end=' ', flush=True)
            ths_code = theme_map.get(name, name)  # fallback: use name as key
            stocks = fetch_one(name, ths_code)
            if stocks:
                cache[ths_code] = stocks
                print(f'{len(stocks)}只')
            else:
                print('0只')
            time.sleep(0.3)
        json.dump(cache, open(CACHE_PATH, 'w'), ensure_ascii=False)
    else:
        main()
