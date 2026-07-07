"""Projection validation boundary for TFS v2."""

from __future__ import annotations

from collections import Counter, defaultdict

from v2.engine.signal import StrategySignal

from .metrics import AccuracyStats, EvaluationReport, ProjectionValidationResult
from .projection import ProjectionEngine


class ProjectionValidation:
    """Validate today's projected states against the next trading day's state."""

    def __init__(self, projection_engine: ProjectionEngine | None = None):
        self.projection_engine = projection_engine or ProjectionEngine()

    def validate_records(self, records: list[dict]) -> EvaluationReport:
        by_symbol: dict[tuple[str, str], list[dict]] = defaultdict(list)
        for record in records:
            by_symbol[(record.get("dtype", ""), str(record["code"]))].append(record)

        results: list[ProjectionValidationResult] = []
        by_state: dict[str, AccuracyStats] = defaultdict(AccuracyStats)
        by_scenario: dict[str, AccuracyStats] = defaultdict(AccuracyStats)
        errors: Counter[str] = Counter()
        dates: list[str] = []

        for (dtype, code), symbol_records in by_symbol.items():
            ordered = sorted(symbol_records, key=lambda item: item["date"])
            for today, tomorrow in zip(ordered, ordered[1:]):
                current_state = self._state_key(today["state"])
                actual_state = self._state_key(tomorrow["state"])
                dates.append(str(today["date"]))
                signal = StrategySignal(
                    code=code,
                    name=code,
                    dtype=dtype,
                    market_date=str(today["date"]),
                    relation_version=None,
                    state=current_state,
                    state_label=current_state,
                    score=0.0,
                    confidence=0.0,
                )
                for scenario in self.projection_engine.generate(signal):
                    exact = scenario.expected_next_state == actual_state
                    directional = exact or self._same_direction(scenario.expected_next_state, actual_state)
                    result = ProjectionValidationResult(
                        date=str(today["date"]),
                        code=code,
                        dtype=dtype,
                        current_state=current_state,
                        scenario_label=scenario.label,
                        expected_next_state=scenario.expected_next_state,
                        actual_next_state=actual_state,
                        is_exact=exact,
                        is_directionally_correct=directional,
                    )
                    results.append(result)
                    self._update_stats(by_state[current_state], exact, directional)
                    self._update_stats(by_scenario[scenario.label], exact, directional)
                    if not directional:
                        errors[f"{current_state}->{scenario.expected_next_state}(actual={actual_state})"] += 1

        total = len(results)
        exact_count = sum(1 for item in results if item.is_exact)
        directional_count = sum(1 for item in results if item.is_directionally_correct)
        return EvaluationReport(
            start_date=min(dates) if dates else "",
            end_date=max(dates) if dates else "",
            scope="records",
            total=total,
            exact_accuracy=exact_count / total if total else 0.0,
            directional_accuracy=directional_count / total if total else 0.0,
            by_state=dict(by_state),
            by_scenario=dict(by_scenario),
            top_errors=[{"pattern": pattern, "count": count} for pattern, count in errors.most_common(20)],
            validation_results=results,
        )

    @staticmethod
    def _update_stats(stats: AccuracyStats, exact: bool, directional: bool) -> None:
        stats.total += 1
        if exact:
            stats.correct += 1
        elif directional:
            stats.directional += 1
        else:
            stats.incorrect += 1

    @staticmethod
    def _same_direction(predicted: str, actual: str) -> bool:
        def direction(state: str) -> int:
            if state in ("4", "5"):
                return 1
            if state in ("1", "2"):
                return -1
            return 0

        return direction(predicted) == direction(actual)

    @staticmethod
    def _state_key(state) -> str:
        return str(state).replace("'", "p")
