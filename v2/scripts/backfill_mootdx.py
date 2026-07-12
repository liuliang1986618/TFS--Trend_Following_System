"""用 MootdxTencentProvider 补 06-29 ~ 07-10 缺失的日K数据。

增量合并：读现有 parquet → 拉新数据 → concat → 去重 → 覆盖写回。
不丢历史，只补缺口。
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

# 确保项目根目录在 sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

from v2.data_layer.providers.mootdx_tencent import MootdxTencentProvider

DATA_DIR = Path("v2/data")
BACKFILL_START = "2026-06-20"  # 多拉几天确保覆盖
BACKFILL_END = "2026-07-10"


def backfill_dtype(provider: MootdxTencentProvider, dtype: str):
    """增量补一个 dtype（stock/etf）的缺失数据。"""
    data_dir = DATA_DIR / dtype
    if not data_dir.exists():
        print(f"  {dtype}/ 目录不存在，跳过")
        return

    parquets = sorted(data_dir.glob("*.parquet"))
    total = len(parquets)
    success = 0
    skipped = 0
    failed = 0
    errors = []

    print(f"\n{'='*50}")
    print(f"补 {dtype}: {total} 只")
    print(f"{'='*50}")

    t_start = time.time()

    for i, pq in enumerate(parquets):
        code = pq.stem

        # 读现有数据
        try:
            existing = pd.read_parquet(pq)
        except Exception as e:
            failed += 1
            if len(errors) < 10:
                errors.append({"code": code, "error": f"读取失败: {e}"})
            continue

        # 检查是否已有 07-10 数据
        if not existing.empty and "date" in existing.columns:
            latest = pd.to_datetime(existing["date"]).max()
            if latest >= pd.to_datetime(BACKFILL_END):
                skipped += 1
                continue

        # 拉新数据
        try:
            if dtype == "stock":
                new_data = provider.fetch_stock_daily(code, BACKFILL_START, BACKFILL_END)
            elif dtype == "etf":
                new_data = provider.fetch_etf_daily(code, BACKFILL_START, BACKFILL_END)
            else:
                new_data = provider.fetch_index_daily(code, BACKFILL_START, BACKFILL_END)
        except Exception as e:
            failed += 1
            if len(errors) < 10:
                errors.append({"code": code, "error": str(e)})
            continue

        if new_data.empty:
            skipped += 1
            continue

        # 增量合并
        if not existing.empty and "date" in existing.columns:
            combined = pd.concat([existing, new_data], ignore_index=True)
            combined["date"] = pd.to_datetime(combined["date"])
            combined = combined.sort_values("date").drop_duplicates("date", keep="last")
        else:
            combined = new_data

        # 写回
        try:
            combined.to_parquet(pq, index=False)
            success += 1
        except Exception as e:
            failed += 1
            if len(errors) < 10:
                errors.append({"code": code, "error": f"写入失败: {e}"})

        if (i + 1) % 100 == 0:
            elapsed = time.time() - t_start
            speed = (i + 1) / elapsed if elapsed > 0 else 0
            print(f"  进度: {i+1}/{total} ({speed:.0f}/s)")

    elapsed = time.time() - t_start
    print(f"\n完成: {dtype}")
    print(f"  成功: {success}, 跳过(已有): {skipped}, 失败: {failed}")
    print(f"  耗时: {elapsed:.1f}s, 速度: {total/elapsed:.0f}/s")
    if errors:
        print(f"  前几个错误:")
        for e in errors[:5]:
            print(f"    {e['code']}: {e['error']}")


def main():
    print("初始化 mootdx 客户端...")
    provider = MootdxTencentProvider(data_dir=DATA_DIR)
    # 触发客户端初始化
    _ = provider.client
    print("客户端就绪\n")

    backfill_dtype(provider, "stock")
    backfill_dtype(provider, "etf")


if __name__ == "__main__":
    main()
