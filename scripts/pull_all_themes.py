#!/usr/bin/env python3
"""
全量题材数据拉取 — 补齐290个题材的日线OHLCV+成分股。
首次运行拉全量，后续增量更新。
"""
import json, os, sys, time
import akshare as ak
import pandas as pd

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
THEME_LIST = os.path.join(PROJECT, 'dashboard', 'data', 'theme_list.json')
THEME_DIR = os.path.join(PROJECT, 'dashboard', 'data', 'theme')
HOLDINGS_PATH = os.path.join(PROJECT, 'data', 'theme_holdings.json')


def pull_daily(theme_name: str):
    """拉取题材日线OHLCV数据（带重试）"""
    for attempt in range(3):
        try:
            df = ak.stock_board_concept_hist_em(symbol=theme_name, period='daily',
                                                  start_date='20200101', end_date='20991231',
                                                  adjust='qfq')
            if df is None or len(df) == 0:
                return None
            df.columns = [c.lower() for c in df.columns]
            return df[['date', 'open', 'high', 'low', 'close', 'volume']]
        except Exception:
            if attempt < 2:
                time.sleep(1)
    return None


def pull_constituents(theme_name: str):
    """拉取题材成分股（带重试）"""
    for attempt in range(3):
        try:
            df = ak.stock_board_concept_cons_em(symbol=theme_name)
            stocks = []
            for _, row in df.iterrows():
                code = str(row.get('代码', ''))
                name = str(row.get('名称', ''))
                if code and name:
                    stocks.append({'code': code, 'name': name})
            return stocks
        except Exception:
            if attempt < 2:
                time.sleep(1)
    return []


def main():
    themes = json.load(open(THEME_LIST))
    os.makedirs(THEME_DIR, exist_ok=True)
    os.makedirs(os.path.join(PROJECT, 'data'), exist_ok=True)

    holdings = {}
    if os.path.exists(HOLDINGS_PATH):
        holdings = json.load(open(HOLDINGS_PATH))

    daily_new = daily_skip = holding_new = 0

    for i, t in enumerate(themes):
        name = t['name']
        code = t.get('code', '')
        parquet_path = os.path.join(THEME_DIR, f'theme_{code}.parquet')

        # 日线数据
        if os.path.exists(parquet_path):
            daily_skip += 1
        else:
            print(f'[{i+1}/{len(themes)}] {name} 日线...', end=' ', flush=True)
            df = pull_daily(name)
            if df is not None and len(df) > 20:
                df.to_parquet(parquet_path, index=False)
                daily_new += 1
                print(f'{len(df)}行 ✅')
            else:
                print('无数据 ⚠️')
            time.sleep(0.3)

        # 成分股
        if code not in holdings or len(holdings[code]) == 0:
            print(f'[{i+1}/{len(themes)}] {name} 成分股...', end=' ', flush=True)
            stocks = pull_constituents(name)
            if stocks:
                holdings[code] = stocks
                holding_new += 1
                print(f'{len(stocks)}只 ✅')
            else:
                print('无数据 ⚠️')
            time.sleep(0.3)

    json.dump(holdings, open(HOLDINGS_PATH, 'w'), ensure_ascii=False)
    total = len([f for f in os.listdir(THEME_DIR) if f.endswith('.parquet')])
    print(f'\n✅ 题材日线: {total}个(新增{daily_new}/跳过{daily_skip})')
    print(f'✅ 成分股缓存: {len(holdings)}个题材(新增{holding_new})')


if __name__ == '__main__':
    main()
