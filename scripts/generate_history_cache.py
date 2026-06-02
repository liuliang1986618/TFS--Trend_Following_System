#!/usr/bin/env python3
"""预计算历史状态缓存 — 从快照JSON提取板块状态历史。

调用: daily_run.py pipeline 中在 build_final.py 之前运行
输出: dashboard/data/history_states.json
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.display.history import HistoryTracker


def generate_from_snapshots():
    """从现有快照JSON生成历史状态缓存（快速路径）。"""
    print("📊 扫描快照JSON生成历史状态缓存...")
    tracker = HistoryTracker(data_dir="dashboard/data")
    records = tracker.load_from_snapshots()

    total = sum(len(v) for v in records.values())
    print(f"   -> {len(records)} 个标的, {total} 条记录")

    path = tracker.save_cache("dashboard/data/history_states.json")
    size_kb = os.path.getsize(path) / 1024
    print(f"✅ 缓存: {path} ({size_kb:.1f} KB)")

    if records:
        sample_code = list(records.keys())[0]
        sample = records[sample_code]
        print(f"   样例 {sample_code}: {len(sample)}天, 状态 {sample[0].state}→{sample[-1].state}")
    return records


if __name__ == "__main__":
    generate_from_snapshots()
