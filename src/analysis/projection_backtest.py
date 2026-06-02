"""推演验证回测引擎 — Phase C: 历史推演回测，评估准确率。"""
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Tuple
from collections import defaultdict
import json
import os
from datetime import datetime

from .scenario import ScenarioEngine, Scenario
from ..engine.state_machine import StateMachine


@dataclass
class ProjectionResult:
    date: str
    symbol: str
    current_state: str
    predicted_state: str
    actual_state: str
    scenario_label: str
    is_correct: bool
    is_partial: bool


@dataclass
class AccuracyStats:
    total: int = 0
    correct: int = 0
    partial: int = 0
    incorrect: int = 0

    @property
    def accuracy(self) -> float:
        return self.correct / self.total if self.total > 0 else 0.0

    @property
    def partial_accuracy(self) -> float:
        return (self.correct + self.partial) / self.total if self.total > 0 else 0.0


class ProjectionBacktest:
    """推演验证回测引擎。"""

    def __init__(self, data_dir: str = "dashboard/data"):
        self.data_dir = data_dir
        self.results: List[ProjectionResult] = []
        self.daily_accuracy: List[Dict] = []
        self.by_state: Dict[str, AccuracyStats] = defaultdict(AccuracyStats)
        self.by_scenario: Dict[str, AccuracyStats] = defaultdict(AccuracyStats)

    def run(self, history_cache_path: str = None) -> List[ProjectionResult]:
        if history_cache_path is None:
            history_cache_path = os.path.join(self.data_dir, "history_states.json")
        if not os.path.exists(history_cache_path):
            print(f"❌ 缓存不存在: {history_cache_path}")
            return []

        with open(history_cache_path) as f:
            cache = json.load(f)
        sectors = cache.get("sectors", {})
        if not sectors:
            return []

        all_dates = set()
        for code, records in sectors.items():
            for r in records:
                all_dates.add(r["date"])
        all_dates = sorted(all_dates)

        print(f"📊 回测: {len(sectors)}板块 × {len(all_dates)-1}天")
        total = 0

        for code, records in sectors.items():
            if len(records) < 2:
                continue
            by_date = {r["date"]: r for r in records}

            for i, date_str in enumerate(all_dates[:-1]):
                if date_str not in by_date:
                    continue
                today = by_date[date_str]
                next_date = all_dates[i + 1]
                tomorrow = by_date.get(next_date)
                if tomorrow is None:
                    continue

                state = str(today["state"])
                scenarios = self._make_scenarios(state)
                if not scenarios:
                    continue

                for sc in scenarios:
                    predicted_next = sc.next_state.split("→")[-1].replace("3'", "3p")
                    actual_state = str(tomorrow["state"]).replace("3'", "3p")

                    is_correct = (predicted_next == actual_state)
                    is_partial = (not is_correct and self._same_dir(predicted_next, actual_state))

                    result = ProjectionResult(
                        date=date_str, symbol=code, current_state=state,
                        predicted_state=predicted_next, actual_state=actual_state,
                        scenario_label=sc.label[:3], is_correct=is_correct, is_partial=is_partial)
                    self.results.append(result)
                    total += 1

                    st = self.by_state[state]
                    st.total += 1
                    if is_correct: st.correct += 1
                    elif is_partial: st.partial += 1
                    else: st.incorrect += 1

                    sc_st = self.by_scenario[sc.label[:3]]
                    sc_st.total += 1
                    if is_correct: sc_st.correct += 1
                    elif is_partial: sc_st.partial += 1
                    else: sc_st.incorrect += 1

            if total % 5000 == 0 and total > 0:
                print(f"   ... {total} 次")

        # Daily accuracy
        ds = defaultdict(lambda: {"total": 0, "correct": 0})
        for r in self.results:
            ds[r.date]["total"] += 1
            if r.is_correct: ds[r.date]["correct"] += 1
        self.daily_accuracy = [
            {"date": d, "accuracy": round(s["correct"]/s["total"], 4) if s["total"]>0 else 0,
             "total": s["total"], "correct": s["correct"]}
            for d, s in sorted(ds.items())]

        print(f"✅ 回测完成: {total}次, 总体准确率={self.overall_accuracy():.1%}")
        return self.results

    def overall_accuracy(self) -> float:
        if not self.results:
            return 0.0
        return sum(1 for r in self.results if r.is_correct) / len(self.results)

    def overall_partial_accuracy(self) -> float:
        if not self.results:
            return 0.0
        return sum(1 for r in self.results if r.is_correct or r.is_partial) / len(self.results)

    def save_results(self, path: str = None) -> str:
        if path is None:
            path = os.path.join(self.data_dir, "projection_log.json")

        by_s = {}
        for st, s in self.by_state.items():
            by_s[st] = {"total": s.total, "correct": s.correct,
                        "partial": s.partial, "incorrect": s.incorrect,
                        "accuracy": round(s.accuracy, 4),
                        "partial_accuracy": round(s.partial_accuracy, 4)}

        by_sc = {}
        for sc, s in self.by_scenario.items():
            by_sc[sc] = {"total": s.total, "correct": s.correct,
                         "accuracy": round(s.accuracy, 4)}

        errors = defaultdict(int)
        for r in self.results:
            if not r.is_correct and not r.is_partial:
                k = f"{r.current_state}→{r.predicted_state}(实{r.actual_state})"
                errors[k] += 1
        top = sorted(errors.items(), key=lambda x: -x[1])[:20]

        out = {
            "meta": {"total_projections": len(self.results),
                     "overall_accuracy": round(self.overall_accuracy(), 4),
                     "overall_partial_accuracy": round(self.overall_partial_accuracy(), 4),
                     "generated_at": datetime.now().isoformat(),
                     "daily_count": len(self.daily_accuracy)},
            "daily_accuracy": self.daily_accuracy,
            "by_state": by_s,
            "by_scenario": by_sc,
            "top_errors": [{"pattern": k, "count": v} for k, v in top],
        }
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
        with open(path, "w") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print(f"✅ 已保存: {path} ({os.path.getsize(path)/1024:.1f}KB)")
        return path

    def _make_scenarios(self, state: str) -> List[Scenario]:
        w = {"A": 0.60, "B": 0.30, "C": 0.10}
        s = str(state)
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

    @staticmethod
    def _same_dir(pred: str, actual: str) -> bool:
        def d(s):
            if s in ("4","5"): return 1
            if s in ("1","2"): return -1
            return 0
        return d(pred) == d(actual)
