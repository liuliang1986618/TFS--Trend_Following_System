#!/usr/bin/env python3
"""
从 data/dates/{date}/6-display/sidebar_entry.json 聚合生成 date_nav.json，
供 build_nav_index.py 使用。
"""
import json
import os
import sys
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATES_DIR = os.path.join(PROJECT_ROOT, "data", "dates")
OUTPUT_PATH = os.path.join(PROJECT_ROOT, "dashboard", "data", "date_nav.json")


def aggregate():
    entries = []
    if not os.path.isdir(DATES_DIR):
        print("❌ data/dates/ 目录不存在")
        sys.exit(1)

    for dname in sorted(os.listdir(DATES_DIR), reverse=True):
        date_dir = os.path.join(DATES_DIR, dname)
        if not os.path.isdir(date_dir):
            continue
        sidebar_path = os.path.join(date_dir, "6-display", "sidebar_entry.json")
        if not os.path.exists(sidebar_path):
            print(f"  ⚠️ {dname} 缺少 sidebar_entry.json，跳过")
            continue

        try:
            with open(sidebar_path) as f:
                entry = json.load(f)
            dt = datetime.strptime(dname, "%Y-%m-%d")
            entry["is_today"] = (dname == datetime.now().strftime("%Y-%m-%d"))
            entry["is_monday"] = (dt.weekday() == 0)
            entries.append(entry)
        except Exception as e:
            print(f"  ⚠️ {dname} 读取失败: {e}")

    if not entries:
        print("❌ 未找到任何 sidebar_entry.json")
        sys.exit(1)

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    output = {"dates": entries}
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"✅ 聚合 {len(entries)} 天 → {OUTPUT_PATH}")
    print(f"   日期范围: {entries[-1]['date']} → {entries[0]['date']}")


if __name__ == "__main__":
    aggregate()
