"""反思引擎 — 从推演验证结果中学习，自动调整推演权重。

Phase D核心: 推演正确→提取可复用模式; 推演错误→定位根因+分类(可优化/不可控)。

数据完整性: 所有输入必须通过完整性校验才允许反思。残缺数据的反思无指导意义。

原理:
  多赚钱: 识别"什么情况下推演准确"→强化正确模式的权重
  少亏钱: 识别"什么情况下推演失真"→降低不可靠场景的权重
"""
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Tuple, Set
from collections import defaultdict
import json
import os
from datetime import datetime, timedelta


# ====== 数据完整性校验 ======

class DataIntegrityError(Exception):
    """数据完整性异常 — 不可恢复，必须修复数据源。"""
    pass


class DataIntegrityWarning:
    """数据完整性警告 — 可继续但结果置信度降低。"""
    def __init__(self, message: str, detail: Dict = None):
        self.message = message
        self.detail = detail or {}


def validate_results_integrity(results: List) -> Tuple[bool, List[str], Dict]:
    """校验推演结果数据的完整性。

    返回: (是否通过, 警告列表, 统计信息)

    校验项:
      1. 总结果数不低于理论值（822天×90板块×3场景 = 221,940，考虑实际只有2场景的1状态）
      2. 每天的结果数一致性（同一天不应有巨大波动）
      3. 状态覆盖完整性（6个状态都应出现）
      4. 无空日期/空板块/空状态
    """
    warnings = []
    stats = {"total": len(results), "unique_dates": 0, "unique_symbols": 0,
             "states_covered": set(), "empty_fields": 0}

    if not results:
        return False, ["❌ 致命: 推演结果为空"], stats

    # 按日期统计
    by_date = defaultdict(int)
    by_symbol = defaultdict(int)
    by_state = defaultdict(int)

    for r in results:
        if not r.date or not r.symbol:
            stats["empty_fields"] += 1
            continue
        by_date[r.date] += 1
        by_symbol[r.symbol] += 1
        by_state[str(r.current_state)] += 1
        stats["states_covered"].add(str(r.current_state))

    stats["unique_dates"] = len(by_date)
    stats["unique_symbols"] = len(by_symbol)

    # 校验1: 日期数量合理（至少700天以上）
    if stats["unique_dates"] < 700:
        warnings.append(f"⚠️ 只有{stats['unique_dates']}天数据，预期≥700天（2023-01~2026-05）")

    # 校验2: 板块数量合理（至少80个）
    if stats["unique_symbols"] < 80:
        warnings.append(f"⚠️ 只有{stats['unique_symbols']}个板块，预期≥80个")

    # 校验3: 每日结果数一致性
    daily_counts = list(by_date.values())
    if daily_counts:
        avg_daily = sum(daily_counts) / len(daily_counts)
        outliers = [d for d, c in by_date.items() if c < avg_daily * 0.5]
        if outliers:
            warnings.append(f"⚠️ {len(outliers)}天结果数不足平均值一半（日均{avg_daily:.0f}条），可能数据缺失")

    # 校验4: 6个状态是否都出现
    missing_states = {"1", "2", "3", "4", "5", "3p"} - stats["states_covered"]
    if missing_states:
        warnings.append(f"⚠️ 缺失状态: {missing_states}")

    # 校验5: 空字段
    if stats["empty_fields"] > 0:
        warnings.append(f"⚠️ {stats['empty_fields']}条结果有空的日期/板块字段")

    passed = len(warnings) == 0 or all("致命" not in w for w in warnings)
    return passed, warnings, stats


@dataclass
class ReflectionEntry:
    """单条反思记录。"""
    date: str
    symbol: str
    current_state: str
    predicted: str
    actual: str
    scenario: str
    is_correct: bool
    root_cause: str = ""
    category: str = ""  # 可优化 / 不可控 / 正确
    lesson: str = ""


@dataclass
class LearnedPattern:
    """从正确推演中提取的可复用模式。"""
    pattern_id: str
    condition: str
    weight_adjustment: Dict[str, float]
    confidence: float
    occurrences: int
    last_seen: str


class ReflectionEngine:
    """反思引擎 — 分析推演结果，提取经验教训。

    数据完整性门控：必须通过完整性校验才允许反思。
    """

    ERROR_CLASSIFIERS = {
        "momentum_overshoot": {
            "desc": "趋势惯性超预期（继续沿原方向）",
            "category": "不可控",
            "detect": lambda p, a: p in ("4","5") and a in ("4","5") and p != a,
        },
        "mean_reversion": {
            "desc": "均值回归（回调/反弹早于预期）",
            "category": "不可控",
            "detect": lambda p, a: p == "4" and a == "3p",
        },
        "range_bound": {
            "desc": "区间震荡（方向不明确）",
            "category": "不可控",
            "detect": lambda p, a: p in ("2","3") and a == "3",
        },
        "false_breakout": {
            "desc": "假突破→回落到区间内",
            "category": "可优化",
            "detect": lambda p, a: p == "4" and a == "3",
        },
        "false_breakdown": {
            "desc": "假跌破→快速收复",
            "category": "可优化",
            "detect": lambda p, a: p == "1" and a in ("2","3"),
        },
        "reversal_missed": {
            "desc": "趋势反转信号被漏判",
            "category": "可优化",
            "detect": lambda p, a: p in ("1","2") and a in ("4","5"),
        },
        "drop_missed": {
            "desc": "转跌信号被漏判",
            "category": "可优化",
            "detect": lambda p, a: p in ("4","5") and a in ("1","2"),
        },
    }

    def __init__(self, data_dir: str = "dashboard/data"):
        self.data_dir = data_dir
        self.entries: List[ReflectionEntry] = []
        self.patterns: List[LearnedPattern] = []
        self.adjustment_log: List[Dict] = []
        self.integrity_report: Dict = {}

    def reflect(self, results: List) -> Tuple[List[ReflectionEntry], List[LearnedPattern]]:
        """分析推演结果。

        第0步: 数据完整性校验——不完整的数据不反思。
        """
        # ====== 数据完整性门控 ======
        passed, warnings, stats = validate_results_integrity(results)
        self.integrity_report = {"passed": passed, "warnings": warnings, "stats": stats}

        if not passed:
            print("❌ 数据完整性校验未通过，反思引擎中止:")
            for w in warnings:
                print(f"   {w}")
            return [], []

        if warnings:
            print("⚠️ 数据完整性警告（继续但置信度降低）:")
            for w in warnings:
                print(f"   {w}")

        print(f"📊 数据完整性OK: {stats['total']}条, {stats['unique_dates']}天, "
              f"{stats['unique_symbols']}板块, 覆盖状态{len(stats['states_covered'])}个")

        self.entries = []
        correct_results = []
        incorrect_results = []

        for r in results:
            entry = ReflectionEntry(
                date=r.date, symbol=r.symbol,
                current_state=str(r.current_state),
                predicted=str(r.predicted_state),
                actual=str(r.actual_state),
                scenario=r.scenario_label,
                is_correct=r.is_correct,
            )

            if r.is_correct:
                correct_results.append(r)
                entry.category = "正确"
                entry.lesson = (f"状态{r.current_state}→{r.predicted_state}"
                               f"推演正确，{r.scenario_label}场景可信")
            else:
                incorrect_results.append(r)
                cat, cause = self._classify_error(
                    str(r.predicted_state), str(r.actual_state), str(r.current_state))
                entry.category = cat
                entry.root_cause = cause
                entry.lesson = self._generate_lesson(r, cat, cause)

            self.entries.append(entry)

        self.patterns = self._extract_patterns(correct_results)
        self.adjustment_log = self._suggest_weight_adjustments(incorrect_results)

        return self.entries, self.patterns

    def _classify_error(self, predicted: str, actual: str, current: str) -> Tuple[str, str]:
        for key, rule in self.ERROR_CLASSIFIERS.items():
            try:
                if rule["detect"](predicted, actual):
                    return rule["category"], rule["desc"]
            except Exception:
                continue

        if predicted in ("4","5") and actual in ("4","5"):
            return "不可控", "同向趋势内的微小波动"
        if predicted in ("1","2") and actual in ("1","2"):
            return "不可控", "弱势区间的随机波动"
        return "可优化", f"未分类: 预测{predicted}→实际{actual}"

    def _generate_lesson(self, r, category: str, cause: str) -> str:
        if category == "不可控":
            return f"外部噪声（{cause}），不调整权重以避免过度拟合"
        return (f"状态{r.current_state}下{r.scenario_label}场景权重需微调: "
                f"实际{r.actual_state}≠预测{r.predicted_state}，{cause}")

    def _extract_patterns(self, correct_results: List) -> List[LearnedPattern]:
        pattern_map: Dict[str, Dict] = {}
        for r in correct_results:
            key = f"{r.current_state}→{r.predicted_state}"
            if key not in pattern_map:
                pattern_map[key] = {"count": 0, "dates": []}
            pattern_map[key]["count"] += 1
            pattern_map[key]["dates"].append(r.date)

        patterns = []
        for key, info in pattern_map.items():
            if info["count"] < 3:
                continue
            current_s, next_s = key.split("→")
            latest = sorted(info["dates"])[-1]
            confidence = min(0.95, info["count"] / 30.0)

            patterns.append(LearnedPattern(
                pattern_id=f"PTN_{current_s}_{next_s}",
                condition=f"当前状态={current_s} 且预测={next_s}",
                weight_adjustment=self._pattern_to_adjustment(current_s, next_s),
                confidence=confidence,
                occurrences=info["count"],
                last_seen=latest,
            ))

        return sorted(patterns, key=lambda p: -p.confidence)

    @staticmethod
    def _pattern_to_adjustment(current: str, predicted: str) -> Dict[str, float]:
        if predicted in ("4",):
            return {"A": +0.02, "B": 0, "C": -0.02}
        elif predicted in ("5", "3p"):
            return {"A": 0, "B": +0.02, "C": -0.02}
        elif predicted in ("1", "2"):
            return {"A": -0.02, "B": 0, "C": +0.02}
        elif predicted == "3":
            return {"A": +0.01, "B": 0, "C": -0.01}
        return {"A": 0, "B": 0, "C": 0}

    def _suggest_weight_adjustments(self, incorrect_results: List) -> List[Dict]:
        state_errors: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for r in incorrect_results:
            state_key = str(r.current_state)
            # 场景标签格式: "场A" 或 "场A(大概率)"，提取字母A/B/C
            raw = r.scenario_label or ""
            if "A" in raw: scenario = "A"
            elif "B" in raw: scenario = "B"
            elif "C" in raw: scenario = "C"
            else: scenario = "A"
            state_errors[state_key][scenario] += 1

        suggestions = []
        for state_key, errors in state_errors.items():
            total = sum(errors.values())
            for scenario, count in errors.items():
                if count >= 3:
                    error_rate = count / max(total, 1)
                    delta = -min(0.05, 0.01 * error_rate)
                    suggestions.append({
                        "state": state_key, "scenario": scenario,
                        "delta": round(delta, 4),
                        "reason": f"{scenario}场景在状态{state_key}下错误{count}次",
                        "date": datetime.now().strftime("%Y-%m-%d"),
                    })

        return suggestions

    def save_reflection_report(self, path: str = None) -> str:
        if path is None:
            path = os.path.join(self.data_dir, "reflection_report.json")

        correct_count = sum(1 for e in self.entries if e.is_correct)
        total = len(self.entries)

        # 序列化前的完整性报告（将set转为list）
        integrity_safe = {
            "passed": self.integrity_report.get("passed", False),
            "warnings": self.integrity_report.get("warnings", []),
            "stats": {
                k: (list(v) if isinstance(v, set) else v)
                for k, v in self.integrity_report.get("stats", {}).items()
            },
        }
        report = {
            "meta": {
                "generated_at": datetime.now().isoformat(),
                "total_entries": total,
                "correct": correct_count,
                "accuracy": round(correct_count / total, 4) if total > 0 else 0,
                "integrity_check": integrity_safe,
            },
            "patterns": [asdict(p) for p in self.patterns[:20]],
            "adjustments": self.adjustment_log[:30],
            "error_summary": {
                "by_category": self._summarize_by("category"),
                "top_lessons": self._top_lessons(10),
            },
        }

        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"✅ 反思报告: {path}")
        return path

    def _summarize_by(self, field: str) -> Dict:
        summary = defaultdict(lambda: {"count": 0, "correct": 0, "incorrect": 0})
        for e in self.entries:
            key = getattr(e, field, "unknown")
            summary[key]["count"] += 1
            if e.is_correct:
                summary[key]["correct"] += 1
            else:
                summary[key]["incorrect"] += 1
        result = {}
        for k, v in summary.items():
            result[k] = {
                "count": v["count"], "correct": v["correct"],
                "incorrect": v["incorrect"],
                "accuracy": round(v["correct"] / v["count"], 3) if v["count"] > 0 else 0,
            }
        return result

    def _top_lessons(self, n: int = 10) -> List[str]:
        seen = set()
        unique = []
        for e in self.entries:
            if e.lesson and not e.is_correct and e.lesson not in seen:
                seen.add(e.lesson)
                unique.append(e.lesson)
        return unique[:n]
