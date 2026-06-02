#!/usr/bin/env python3
"""从parquet源数据生成全量822天×90板块历史状态缓存。

与generate_history_cache.py不同：此脚本从raw parquet文件重新classify，
而非依赖已有的趋势快照JSON。这是全量回测的前提。

输出: dashboard/data/history_states_full.json (~11MB)
时间: 预计3-8分钟（73,980次classify调用）
"""
import sys
import os
import json
import time
from datetime import datetime
from pathlib import Path
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.engine.state_machine import StateMachine


def generate_full_history(data_dir: str = "dashboard/data", output_path: str = None):
    """从parquet文件生成全量历史状态缓存。"""
    if output_path is None:
        output_path = os.path.join(data_dir, "history_states_full.json")

    data_path = Path(data_dir)
    sector_files = sorted(data_path.glob("sector_*.parquet"))

    if not sector_files:
        print("❌ 未找到sector parquet文件")
        return {}

    print(f"📊 从 {len(sector_files)} 个parquet文件生成全量历史状态...")
    print(f"   每个文件约822天 → 预计 {len(sector_files) * 822:,} 次classify")

    all_sectors = {}
    total_records = 0
    start_time = time.time()

    for i, fpath in enumerate(sector_files):
        code = fpath.stem.replace("sector_", "")

        try:
            df = pd.read_parquet(str(fpath))
        except Exception as e:
            print(f"   ⚠️ 跳过 {code}: {e}")
            continue

        if df.empty or len(df) < 20:
            continue

        df = df.sort_index()
        records = []

        for j in range(20, len(df) + 1):
            window = df.iloc[:j]
            date_str = window.index[j-1].strftime("%Y-%m-%d")

            try:
                ts = StateMachine.classify(window)
            except Exception:
                continue

            state_key = "3p" if ts.state == "3'" else ts.state

            records.append({
                "date": date_str,
                "state": state_key,
                "state_label": ts.state_label,
                "score": _calc_score(ts),
                "position_ratio": ts.position_ratio,
                "conditions": {
                    "structure": _cond_pass(ts.conditions, "structure"),
                    "volume": _cond_pass(ts.conditions, "volume"),
                    "persistence": _cond_pass(ts.conditions, "persistence"),
                },
            })
            total_records += 1

        all_sectors[code] = records

        if (i + 1) % 20 == 0:
            elapsed = time.time() - start_time
            print(f"   ... {i+1}/{len(sector_files)} 板块, {total_records:,} 条, {elapsed:.0f}s")

    elapsed = time.time() - start_time
    print(f"   ✅ 完成: {len(all_sectors)} 板块, {total_records:,} 条记录, {elapsed:.0f}s")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    output = {
        "meta": {
            "generated_at": datetime.now().isoformat(),
            "total_symbols": len(all_sectors),
            "total_records": total_records,
            "date_range": _get_date_range(all_sectors),
            "source": "parquet_raw",
        },
        "sectors": all_sectors,
    }

    with open(output_path, "w") as f:
        json.dump(output, f, ensure_ascii=False)

    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"💾 已保存: {output_path} ({size_mb:.1f} MB)")
    return all_sectors


def _cond_pass(conditions, key):
    """安全提取条件pass结果。"""
    c = conditions.get(key)
    if c is None:
        return False
    if hasattr(c, 'pass_'):
        return bool(c.pass_)
    if isinstance(c, dict):
        return bool(c.get("pass", False))
    return False


def _calc_score(ts) -> int:
    """从TrendState计算得分（0-100）。"""
    score = 0
    conds = ts.conditions

    if _cond_pass(conds, "structure"): score += 35
    if _cond_pass(conds, "volume"): score += 25
    if _cond_pass(conds, "persistence"): score += 20
    if ts.above_ma20: score += 20
    if ts.broke_prev_high: score += 10
    if ts.broke_prev_low: score -= 15
    return max(0, min(100, score))


def _get_date_range(sectors: dict) -> str:
    dates = set()
    for records in sectors.values():
        for r in records:
            dates.add(r["date"])
    if not dates:
        return "unknown"
    return f"{min(dates)} ~ {max(dates)}"


if __name__ == "__main__":
    generate_full_history()
