"""增量补齐 v2 K线数据：只补缺口交易日，读旧+合并增量，不丢历史。

用法:
  python3 v2/scripts/backfill_daily.py --end 2026-07-10
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from v2.data_layer import DataLayer
from v2.data_layer.fetcher import DataFetcher
from v2.data_layer.providers.akshare_em import AkshareEMProvider


def compact(d: str) -> str:
    return d.replace("-", "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--end", default="2026-07-10", help="补齐到的最晚交易日 (YYYY-MM-DD)")
    ap.add_argument("--dtypes", nargs="*", default=["stock", "etf"], help="补齐类型")
    ap.add_argument("--sleep", type=float, default=0.02, help="每只间隔秒数，防限流")
    args = ap.parse_args()

    dl = DataLayer()
    provider = AkshareEMProvider()
    fetcher = DataFetcher(data_dir=dl.data_dir, provider=provider)

    overall_start = time.time()
    for dtype in args.dtypes:
        symbols = dl.list_symbols(dtype)
        done = 0
        skipped = 0
        failed = 0
        t0 = time.time()
        for code in symbols:
            try:
                old = dl.load_daily(dtype, code)
                if old is not None and not old.empty:
                    last = old["date"].max()
                    if hasattr(last, "strftime"):
                        last = last.strftime("%Y-%m-%d")
                    if last >= args.end:
                        skipped += 1
                        continue
                    start = _next_day(last)
                else:
                    start = "20200101"
                # 拉增量
                daily = _fetch_incremental(fetcher, dtype, code, start, args.end)
                if daily is None or daily.empty:
                    skipped += 1
                    continue
                # 合并旧+新
                if old is not None and not old.empty:
                    merged = _merge(old, daily)
                else:
                    merged = daily
                fetcher._write_daily(dtype, code, merged)
                done += 1
            except Exception as exc:
                failed += 1
                if failed <= 10:
                    print(f"  [FAIL] {dtype} {code}: {exc}", flush=True)
            if args.sleep:
                time.sleep(args.sleep)
        print(f"[{dtype}] done={done} skipped={skipped} failed={failed} in {round(time.time()-t0)}s", flush=True)
    print(f"ALL DONE in {round(time.time()-overall_start)}s", flush=True)


def _next_day(date_str: str) -> str:
    from datetime import datetime, timedelta
    d = datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=1)
    return d.strftime("%Y%m%d")


def _fetch_incremental(fetcher, dtype, code, start, end):
    from v2.data_layer.providers.akshare_em import AkshareEMProvider
    provider = fetcher.provider
    if dtype == "stock":
        return provider.fetch_stock_daily(code, start_date=start, end_date=compact(end))
    if dtype == "etf":
        return provider.fetch_etf_daily(code, start_date=start, end_date=compact(end))
    return None


def _merge(old, new):
    import pandas as pd
    df = pd.concat([old, new], ignore_index=True)
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").drop_duplicates("date", keep="last").reset_index(drop=True)
    return df


if __name__ == "__main__":
    main()
