#!/usr/bin/env python3
"""增量更新 pkl 缓存 — 仅拉取缺失日期，追加到已有文件。"""
import sys, os, pickle, time

PROJECT = '/Users/liuliang19/Desktop/project/trend_following_system'
os.chdir(PROJECT)
sys.path.insert(0, PROJECT)

import numpy as np
import pandas as pd
import akshare as ak


def update_etf_pkl(target_date, delay=0.3):
    etf_dir = 'data/etf_stocks'
    files = sorted([f for f in os.listdir(etf_dir) if f.endswith('.pkl')])
    target_dt = np.datetime64(target_date)
    updated, skipped, failed = 0, 0, 0

    for i, fname in enumerate(files):
        code = fname.replace('etf_', '').replace('.pkl', '')
        path = os.path.join(etf_dir, fname)
        try:
            df = pickle.load(open(path, 'rb'))
        except Exception:
            failed += 1; continue
        if target_dt in df['date'].values:
            skipped += 1; continue
        last_date = str(df['date'].max())[:10].replace('-', '')
        if last_date >= target_date.replace('-', ''):
            skipped += 1; continue
        try:
            new = ak.fund_etf_hist_sina(symbol=code)
        except Exception:
            failed += 1; continue
        if new is None or len(new) == 0:
            failed += 1; continue
        new['date'] = pd.to_datetime(new['date'])
        new = new[new['date'] > df['date'].max()]
        if len(new) == 0:
            skipped += 1; continue
        combined = pd.concat([df, new], ignore_index=True)
        combined.to_pickle(path)
        updated += 1
        if (i+1) % 30 == 0:
            print(f'  ETF进度: {i+1}/{len(files)}')
        time.sleep(delay)

    print(f'  ETF: {updated}更新 {skipped}最新 {failed}失败 (共{len(files)})')
    return updated


def update_stock_pkl(target_date, limit=2000, delay=0.15):
    stock_dir = 'data/massive_stocks'
    files = sorted([f for f in os.listdir(stock_dir) if f.endswith('.pkl')])[:limit]
    target_dt = np.datetime64(target_date)
    updated, skipped, failed = 0, 0, 0

    for i, fname in enumerate(files):
        code = fname.replace('.pkl', '')
        path = os.path.join(stock_dir, fname)
        try:
            df = pickle.load(open(path, 'rb'))
        except Exception:
            failed += 1; continue
        if target_dt in df['date'].values:
            skipped += 1; continue
        last_date = str(df['date'].max())[:10].replace('-', '')
        if last_date >= target_date.replace('-', ''):
            skipped += 1; continue
        try:
            new = ak.stock_zh_a_daily(symbol=f'sz{code}', adjust='qfq')
        except Exception:
            try:
                new = ak.stock_zh_a_daily(symbol=f'sh{code}', adjust='qfq')
            except Exception:
                failed += 1; continue
        if new is None or len(new) == 0:
            failed += 1; continue
        new['date'] = pd.to_datetime(new['date'])
        new = new[new['date'] > df['date'].max()]
        if len(new) == 0:
            skipped += 1; continue
        combined = pd.concat([df, new], ignore_index=True)
        combined.to_pickle(path)
        updated += 1
        if (i+1) % 200 == 0:
            print(f'  个股进度: {i+1}/{len(files)} (更新{updated})')
        time.sleep(delay)

    print(f'  个股: {updated}更新 {skipped}最新 {failed}失败 (共{len(files)})')
    return updated


if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else '2026-06-05'
    print(f'📥 增量更新 pkl 缓存 -> {target}')
    print('='*50)
    print('\n📦 更新 ETF (132只)...')
    update_etf_pkl(target)
    print('\n📊 更新个股 (前2000只)...')
    update_stock_pkl(target, limit=2000)
    print(f'\n✅ 缓存更新完成 -> {target}')
