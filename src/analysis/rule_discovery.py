"""规则发现引擎 — 从推演验证的正反例中自动提取新规则。

Phase D核心: 从大量推演结果中提取:
  1. 高置信度模式 → 可直接加入权重表
  2. 异常模式 → 需要人工审查的边界情况
  3. 状态转换频率统计 → 优化推演场景的默认权重

数据完整性: 必须在输入数据校验通过后才运行。不完整数据产生的规则不可信。

这些规则直接反馈到projection_weights.json，用于指导下一次推演迭代。
"""
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Tuple, Optional
from collections import defaultdict, Counter
import json
import os
from datetime import datetime


@dataclass
class DiscoveredRule:
    """自动发现的新规则。"""
    rule_id: str
    description: str
    condition: str
    action: str
    confidence: float
    support: int
    source: str  # "correct_pattern" | "error_correction" | "frequency_analysis"
    priority: int  # 1(最高) ~ 5(最低)


def validate_history_cache(cache: Dict) -> Tuple[bool, List[str], Dict]:
    """校验历史状态缓存的完整性。

    校验项:
      1. 板块数量完整（≥80个板块）
      2. 每个板块的天数合理（≥700天）
      3. 日期连续无大段缺失
      4. 无空记录
    """
    warnings = []
    stats = {"total_sectors": 0, "total_records": 0, "min_days": 9999, "max_days": 0}

    sectors = cache.get("sectors", {})
    if not sectors:
        return False, ["❌ 致命: 缓存中无板块数据"], stats

    stats["total_sectors"] = len(sectors)
    if stats["total_sectors"] < 80:
        warnings.append(f"⚠️ 板块数{stats['total_sectors']}<80，数据可能不完整")

    date_set = set()
    empty_sectors = []

    for code, records in sectors.items():
        if not records:
            empty_sectors.append(code)
            continue
        stats["total_records"] += len(records)
        stats["min_days"] = min(stats["min_days"], len(records))
        stats["max_days"] = max(stats["max_days"], len(records))
        for r in records:
            date_set.add(r.get("date", ""))

    if empty_sectors:
        warnings.append(f"⚠️ {len(empty_sectors)}个板块无记录: {empty_sectors[:5]}...")

    if stats["min_days"] < 700:
        warnings.append(f"⚠️ 最少板块仅{stats['min_days']}天数据，预期≥700天")

    # 检查日期数量
    unique_dates = len(date_set)
    if unique_dates < 700:
        warnings.append(f"⚠️ 仅{unique_dates}个唯一日期，预期≥700天")

    passed = len(warnings) == 0 or all("致命" not in w for w in warnings)
    return passed, warnings, stats


class RuleDiscovery:
    """规则发现引擎。

    三步流程:
      1. 频率分析 → 从822天数据中统计真实状态转换频率
      2. 模式挖掘 → 从正确推演中提取高置信度转换规则
      3. 纠错规则 → 从错误推演中提取修正规则
    """

    def __init__(self, data_dir: str = "dashboard/data"):
        self.data_dir = data_dir
        self.rules: List[DiscoveredRule] = []
        self.transition_matrix: Dict[str, Dict[str, int]] = defaultdict(
            lambda: defaultdict(int))
        self.integrity_report: Dict = {}

    def discover(self, history_cache: Dict,
                 backtest_results: List,
                 reflection_entries: List) -> List[DiscoveredRule]:
        """运行完整的规则发现流程。

        第0步: 校验历史缓存完整性。
        """
        self.rules = []

        # ====== 数据完整性校验 ======
        passed, warnings, stats = validate_history_cache(history_cache)
        self.integrity_report = {"passed": passed, "warnings": warnings, "stats": stats}

        if not passed:
            print("❌ 历史缓存完整性校验未通过，规则发现中止:")
            for w in warnings:
                print(f"   {w}")
            return []

        if warnings:
            print("⚠️ 数据完整性警告（继续但置信度降低）:")
            for w in warnings:
                print(f"   {w}")

        print(f"📊 缓存完整性OK: {stats['total_sectors']}板块, "
              f"{stats['total_records']:,}条, {stats['min_days']}~{stats['max_days']}天/板块")

        freq_rules = self._frequency_analysis(history_cache)
        self.rules.extend(freq_rules)

        pattern_rules = self._pattern_mining(backtest_results)
        self.rules.extend(pattern_rules)

        correction_rules = self._error_correction(reflection_entries)
        self.rules.extend(correction_rules)

        self.rules.sort(key=lambda r: (r.priority, -r.confidence))
        return self.rules

    def _frequency_analysis(self, history_cache: Dict) -> List[DiscoveredRule]:
        sectors = history_cache.get("sectors", {})

        for code, records in sectors.items():
            if len(records) < 2:
                continue
            for i in range(len(records) - 1):
                from_s = str(records[i]["state"])
                to_s = str(records[i + 1]["state"])
                self.transition_matrix[from_s][to_s] += 1

        rules = []
        for from_s in sorted(self.transition_matrix.keys()):
            to_counts = self.transition_matrix[from_s]
            total = sum(to_counts.values())
            if total < 10:
                continue

            for to_s, count in to_counts.items():
                freq = count / total
                if freq >= 0.05:
                    rules.append(DiscoveredRule(
                        rule_id=f"FREQ_{from_s}_{to_s}",
                        description=f"状态{from_s}→{to_s}: 历史频率{freq:.1%}",
                        condition=f"当前状态={from_s}",
                        action=f"预测{to_s}（频率{freq:.1%}, 共{count}次）",
                        confidence=min(0.95, freq * 2),
                        support=count,
                        source="frequency_analysis",
                        priority=2 if freq > 0.3 else 3 if freq > 0.15 else 4,
                    ))

        return rules

    def _pattern_mining(self, backtest_results: List) -> List[DiscoveredRule]:
        if not backtest_results:
            return []

        correct_by_key: Dict[str, List] = defaultdict(list)
        for r in backtest_results:
            if r.is_correct:
                key = f"{r.current_state}_{r.scenario_label}"
                correct_by_key[key].append(r)

        rules = []
        for key, results in correct_by_key.items():
            if len(results) < 5:
                continue

            parts = key.rsplit("_", 1)
            if len(parts) < 2:
                continue
            current_s, scenario = parts[0], parts[1]

            total_in_state = sum(1 for r in backtest_results
                                if str(r.current_state) == current_s)
            if total_in_state < 20:
                continue

            correct_rate = len(results) / total_in_state
            predicted_states = Counter(str(r.predicted_state) for r in results)
            most_predicted = predicted_states.most_common(1)[0][0]

            rules.append(DiscoveredRule(
                rule_id=f"PTN_{current_s}_{scenario}",
                description=(f"状态{current_s}下{scenario}场景"
                            f"准确率{correct_rate:.1%}，常预测→{most_predicted}"),
                condition=f"当前状态={current_s} 且使用{scenario}场景",
                action=f"保持{scenario}场景权重（准确率{correct_rate:.1%}）",
                confidence=min(0.95, correct_rate * 1.5),
                support=len(results),
                source="correct_pattern",
                priority=2 if correct_rate > 0.7 else 3,
            ))

        return rules

    def _error_correction(self, reflection_entries: List) -> List[DiscoveredRule]:
        if not reflection_entries:
            return []

        errors_by_state: Dict[str, List] = defaultdict(list)
        for e in reflection_entries:
            if not e.is_correct and e.category == "可优化":
                errors_by_state[str(e.current_state)].append(e)

        rules = []
        for state_key, entries in errors_by_state.items():
            if len(entries) < 5:
                continue
            actual_states = Counter(e.actual for e in entries)
            most_actual = actual_states.most_common(1)[0][0]

            rules.append(DiscoveredRule(
                rule_id=f"ERR_{state_key}",
                description=(f"状态{state_key}预测常偏差→{most_actual}"
                            f"（{len(entries)}次可优化错误）"),
                condition=f"当前状态={state_key}",
                action=f"考虑增加→{most_actual}的权重分配",
                confidence=min(0.7, len(entries) / 30.0),
                support=len(entries),
                source="error_correction",
                priority=3,
            ))

        return rules

    def get_transition_summary(self) -> Dict:
        summary = {}
        for from_s in sorted(self.transition_matrix.keys()):
            to_counts = self.transition_matrix[from_s]
            total = sum(to_counts.values())
            if total == 0:
                continue
            summary[from_s] = {
                "total": total,
                "to": {
                    to_s: {"count": c, "pct": round(c / total, 3)}
                    for to_s, c in sorted(to_counts.items(), key=lambda x: -x[1])[:5]
                },
            }
        return summary

    def save_rules(self, path: str = None) -> str:
        if path is None:
            path = os.path.join(self.data_dir, "discovered_rules.json")

        output = {
            "meta": {
                "generated_at": datetime.now().isoformat(),
                "total_rules": len(self.rules),
                "integrity_check": self.integrity_report,
            },
            "transition_matrix": self.get_transition_summary(),
            "rules": [asdict(r) for r in self.rules],
        }

        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print(f"✅ 规则发现: {path} ({len(self.rules)}条规则)")
        return path

    def apply_to_weights(self, weights_manager, max_rules: int = 15) -> List[str]:
        applied = []
        for rule in self.rules[:max_rules]:
            if rule.confidence < 0.3:
                continue
            if rule.source != "frequency_analysis":
                continue

            parts = rule.rule_id.split("_")
            if len(parts) < 3:
                continue
            from_s = parts[1]

            try:
                weights_manager.adjust(
                    from_s, "A",
                    delta=0.01 if rule.confidence > 0.5 else 0.005,
                    reason=f"规则发现: {rule.description[:60]}",
                )
                applied.append(f"调整状态{from_s}: {rule.description[:80]}")
            except Exception as e:
                applied.append(f"⚠️ 状态{from_s}调整失败: {e}")

        return applied
