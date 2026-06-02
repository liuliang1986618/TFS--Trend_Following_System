#!/usr/bin/env python3
"""全量推演验证回测 — Phase C主控脚本。

从parquet源数据遍历全部822天×90板块，生成推演并对比次日实际走势。
输出: dashboard/data/projection_log.json (汇总统计，~50KB)

⚠️ 数据完整性: 每一步都记录进度和统计，源数据缺失日期明确报告。
预计运行时间: 3-10分钟。
"""
import sys
import os
import json
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.analysis.projection_backtest import ProjectionBacktest


def main():
    data_dir = "dashboard/data"
    start = time.time()

    print("=" * 60)
    print("📊 Phase C: 全量推演验证回测")
    print(f"   数据源: parquet → history_states_full.json")
    print(f"   范围: 2023-01-03 ~ 2026-05-29 (822天 × 90板块)")
    print(f"   理论推演数: ~73,890 (实际取决于缓存覆盖)")
    print("=" * 60)

    # 步骤1: 检查/生成全量缓存
    cache_path = os.path.join(data_dir, "history_states_full.json")
    if not os.path.exists(cache_path):
        print("\n📦 全量缓存不存在，开始生成...")
        from scripts.generate_full_history import generate_full_history
        records = generate_full_history(data_dir, cache_path)
        if not records:
            print("❌ 缓存生成失败")
            return 1
    else:
        size_mb = os.path.getsize(cache_path) / (1024 * 1024)
        print(f"\n📦 使用已有缓存: {cache_path} ({size_mb:.1f}MB)")

        # 快速校验缓存完整性
        with open(cache_path) as f:
            cache = json.load(f)
        sectors = cache.get("sectors", {})
        total = sum(len(v) for v in sectors.values())
        print(f"   校验: {len(sectors)}板块, {total:,}条记录")

    # 步骤2: 运行推演回测
    print("\n🔮 运行推演回测...")
    bt = ProjectionBacktest(data_dir=data_dir)
    results = bt.run(history_cache_path=cache_path)

    if not results:
        print("❌ 回测无结果")
        return 1

    # 步骤3: 数据完整性报告
    unique_dates = set(r.date for r in results)
    unique_symbols = set(r.symbol for r in results)
    states_covered = set(str(r.current_state) for r in results)
    print(f"\n📋 数据完整性报告:")
    print(f"   总推演: {len(results):,}次")
    print(f"   覆盖日期: {len(unique_dates)}天")
    print(f"   覆盖板块: {len(unique_symbols)}个")
    print(f"   覆盖状态: {states_covered}")

    if len(unique_dates) < 700:
        print(f"   ⚠️ 日期数不足（{len(unique_dates)}<700），数据可能不完整!")
    if len(unique_symbols) < 80:
        print(f"   ⚠️ 板块数不足（{len(unique_symbols)}<80），数据可能不完整!")

    # 步骤4: 展示结果
    print(f"\n📊 推演准确率:")
    print(f"   严格准确率: {bt.overall_accuracy():.1%}")
    print(f"   宽松准确率(含部分正确): {bt.overall_partial_accuracy():.1%}")

    print(f"\n   按状态分类:")
    for st in sorted(bt.by_state.keys(), key=lambda x: str(x)):
        s = bt.by_state[st]
        print(f"   状态{str(st):>3}: {s.accuracy:.1%} ({s.correct}/{s.total})"
              f" +{s.partial_accuracy - s.accuracy:.1%}部分")

    # 步骤5: 保存结果
    log_path = bt.save_results(os.path.join(data_dir, "projection_log.json"))
    print(f"\n✅ 推演回测完成 ({time.time()-start:.1f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
