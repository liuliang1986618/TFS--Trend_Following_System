#!/usr/bin/env python3
"""反思闭环主流程 — Phase D核心脚本。

完整流程:
  1. 加载全量历史缓存（校验完整性）
  2. 运行推演回测 → projection_log.json
  3. 反思引擎分析 → reflection_report.json
  4. 规则发现 → discovered_rules.json
  5. 规则反馈到权重 → projection_weights.json
  6. 重新推演→验证准确率提升

预计运行时间: 5-15分钟（含全量回测+反思+规则发现）
"""
import sys
import os
import json
import time
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.analysis.projection_backtest import ProjectionBacktest
from src.analysis.projection_weights import ProjectionWeights
from src.analysis.reflection import ReflectionEngine
from src.analysis.rule_discovery import RuleDiscovery
from src.analysis.scenario import Scenario


def main():
    data_dir = "dashboard/data"
    start = time.time()

    print("=" * 60)
    print("🔄 Phase D: 反思闭环引擎")
    print("   推演→验证→反思→规则发现→权重调整→再推演")
    print("=" * 60)

    # ====== 第0步: 校验数据完整性 ======
    cache_path = os.path.join(data_dir, "history_states_full.json")
    if not os.path.exists(cache_path):
        print("\n❌ 全量历史缓存不存在！请先运行:")
        print("   python3 scripts/generate_full_history.py")
        return 1

    with open(cache_path) as f:
        history_cache = json.load(f)

    sectors = history_cache.get("sectors", {})
    total_records = sum(len(v) for v in sectors.values())
    min_days = min((len(v) for v in sectors.values()), default=0)
    max_days = max((len(v) for v in sectors.values()), default=0)

    # 完整性门控
    if len(sectors) < 80:
        print(f"\n❌ 数据不完整: 仅{len(sectors)}个板块（需要≥80）")
        print("   请检查parquet数据源完整性。")
        return 1
    if min_days < 700:
        print(f"\n⚠️ 警告: 最少板块仅{min_days}天数据（预期≥700）")
        print("   继续运行但准确性可能受影响。")

    print(f"\n📦 数据完整性:")
    print(f"   板块: {len(sectors)}个")
    print(f"   总记录: {total_records:,}条")
    print(f"   天/板块: {min_days}~{max_days}")
    print(f"   状态: ✅ 可用" if len(sectors) >= 80 else "   状态: ❌ 不足")

    # ====== 第1步: 初始推演回测 ======
    print(f"\n📊 第1步: 初始推演回测...")
    bt = ProjectionBacktest(data_dir=data_dir)
    results = bt.run(history_cache_path=cache_path)

    if not results:
        print("❌ 回测无结果，终止。")
        return 1

    initial_accuracy = bt.overall_accuracy()
    print(f"   初始准确率: {initial_accuracy:.1%} "
          f"(严格) / {bt.overall_partial_accuracy():.1%} (宽松)")
    bt.save_results(os.path.join(data_dir, "projection_log.json"))

    # ====== 第2步: 反思引擎 ======
    print(f"\n🧠 第2步: 反思引擎分析...")
    reflection = ReflectionEngine(data_dir=data_dir)
    entries, patterns = reflection.reflect(results)

    if entries:
        correct = sum(1 for e in entries if e.is_correct)
        print(f"   反思: {len(entries)}条, {correct}正确, "
              f"{len(entries)-correct}错误, {len(patterns)}个模式")
        reflection.save_reflection_report()
    else:
        print("   ⚠️ 反思引擎未产生结果（数据完整性不足或全部正确）")

    # ====== 第3步: 规则发现 ======
    print(f"\n🔍 第3步: 规则发现...")
    discovery = RuleDiscovery(data_dir=data_dir)
    rules = discovery.discover(history_cache, results, entries)

    if rules:
        print(f"   发现{len(rules)}条规则")
        for r in rules[:5]:
            print(f"   [{r.source}] {r.description[:80]} "
                  f"(置信度{r.confidence:.2f})")
        discovery.save_rules()
    else:
        print("   ⚠️ 未发现足够置信度的规则")

    # ====== 第4步: 权重调整 ======
    print(f"\n⚖️ 第4步: 应用规则到权重...")
    weights = ProjectionWeights(
        config_path=os.path.join(data_dir, "projection_weights.json"))

    # 从反思结果调整权重
    for adj in reflection.adjustment_log[:20]:
        try:
            weights.adjust(
                adj["state"], adj["scenario"], adj["delta"],
                reason=adj["reason"],
            )
        except Exception as e:
            print(f"   ⚠️ 调整失败 {adj}: {e}")

    # 从规则发现调整权重
    applied = discovery.apply_to_weights(weights)
    for a in applied:
        print(f"   {a}")

    weights.save()
    print(f"   权重已更新并保存")

    # ====== 第5步: 反思后再次推演 ======
    print(f"\n🔄 第5步: 应用新权重后再次推演...")
    new_weights = weights.get_all_weights()

    def make_weighted_scenes(state):
        s = str(state)
        w = new_weights.get(s, {"A": 0.60, "B": 0.30, "C": 0.10})
        if s == "4":
            return [Scenario("场A", "大概率", w["A"], "", "", "4→4"),
                    Scenario("场B", "中概率", w["B"], "", "", "4→5"),
                    Scenario("场C", "小概率", w["C"], "", "", "4→3p")]
        if s == "3":
            return [Scenario("场A", "大概率", w["A"], "", "", "3→3"),
                    Scenario("场B", "中概率", w["B"], "", "", "3→4"),
                    Scenario("场C", "小概率", w["C"], "", "", "3→1")]
        if s == "5":
            return [Scenario("场A", "大概率", w["A"], "", "", "5→4"),
                    Scenario("场B", "中概率", w["B"], "", "", "5→5"),
                    Scenario("场C", "小概率", w["C"], "", "", "5→3p")]
        if s == "3p":
            return [Scenario("场A", "大概率", w["A"], "", "", "3p→4"),
                    Scenario("场B", "中概率", w["B"], "", "", "3p→3p"),
                    Scenario("场C", "小概率", w["C"], "", "", "3p→1")]
        if s == "2":
            return [Scenario("场A", "大概率", w["A"], "", "", "2→2"),
                    Scenario("场B", "中概率", w["B"], "", "", "2→3"),
                    Scenario("场C", "小概率", w["C"], "", "", "2→1")]
        if s == "1":
            return [Scenario("场A", "大概率", w["A"], "", "", "1→1"),
                    Scenario("场B", "小概率", w["B"], "", "", "1→2")]
        return []

    bt2 = ProjectionBacktest(data_dir=data_dir)
    bt2._make_scenarios = make_weighted_scenes
    results2 = bt2.run(history_cache_path=cache_path)
    new_accuracy = bt2.overall_accuracy() if results2 else initial_accuracy

    if results2:
        improvement = new_accuracy - initial_accuracy
        print(f"   新准确率: {new_accuracy:.1%} "
              f"({'↑' if improvement > 0 else '↓'}{abs(improvement):.1%})")
        if improvement > 0:
            print(f"   ✅ 准确率提升 {improvement:.1%}！反思闭环有效。")
        elif abs(improvement) < 0.001:
            print(f"   ➡️ 准确率基本持平，权重已收敛。")
        else:
            print(f"   ⚠️ 准确率下降，权重调整可能过度拟合。")

    # ====== 第6步: 生成健康度摘要 ======
    print(f"\n💚 第6步: 生成健康度仪表数据...")
    health = _build_health_dashboard(
        initial_accuracy=initial_accuracy,
        new_accuracy=new_accuracy,
        patterns=patterns,
        rules=rules,
        weights=weights,
        daily_accuracy=bt.daily_accuracy,
        reflection=reflection,
    )

    health_path = os.path.join(data_dir, "health_dashboard.json")
    with open(health_path, "w") as f:
        json.dump(health, f, ensure_ascii=False, indent=2)
    print(f"   健康度仪表: {health_path}")

    elapsed = time.time() - start
    print(f"\n✅ 反思闭环完成 ({elapsed:.0f}s)")
    print(f"   初始准确率→最终准确率: {initial_accuracy:.1%}→{new_accuracy:.1%}")
    return 0


def _build_health_dashboard(initial_accuracy, new_accuracy, patterns,
                           rules, weights, daily_accuracy, reflection) -> dict:
    """构建健康度仪表数据（嵌入Dashboard HTML）。"""
    return {
        "meta": {
            "generated_at": datetime.now().isoformat(),
            "initial_accuracy": round(initial_accuracy, 4),
            "final_accuracy": round(new_accuracy, 4),
            "improvement": round(new_accuracy - initial_accuracy, 4),
        },
        "accuracy_trend": daily_accuracy[-822:] if len(daily_accuracy) > 822
                          else daily_accuracy,
        "top_patterns": [
            {"id": p.pattern_id, "condition": p.condition,
             "confidence": round(p.confidence, 3), "occurrences": p.occurrences}
            for p in patterns[:10]
        ],
        "top_rules": [
            {"id": r.rule_id, "description": r.description[:100],
             "confidence": round(r.confidence, 3), "source": r.source}
            for r in rules[:10]
        ],
        "current_weights": weights.get_all_weights(),
        "error_categories": reflection._summarize_by("category")
                            if reflection.entries else {},
        "integrity": {
            "reflection_entries": len(reflection.entries),
            "patterns_found": len(patterns),
            "rules_discovered": len(rules),
        },
        "top_lessons": reflection._top_lessons(8) if reflection.entries else [],
    }


if __name__ == "__main__":
    sys.exit(main())
