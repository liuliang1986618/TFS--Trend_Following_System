"""Evaluation metric data contracts for TFS v2."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AccuracyStats:
    total: int = 0
    correct: int = 0
    directional: int = 0
    incorrect: int = 0

    @property
    def exact_accuracy(self) -> float:
        return self.correct / self.total if self.total else 0.0

    @property
    def directional_accuracy(self) -> float:
        return self.directional / self.total if self.total else 0.0


@dataclass
class ErrorPattern:
    name: str
    count: int = 0
    examples: list[dict] = field(default_factory=list)


@dataclass
class ProjectionValidationResult:
    date: str
    code: str
    dtype: str
    current_state: str
    scenario_label: str
    expected_next_state: str
    actual_next_state: str
    is_exact: bool
    is_directionally_correct: bool


@dataclass
class EvaluationReport:
    start_date: str = ""
    end_date: str = ""
    scope: str = ""
    total: int = 0
    exact_accuracy: float = 0.0
    directional_accuracy: float = 0.0
    by_state: dict = field(default_factory=dict)
    by_scenario: dict = field(default_factory=dict)
    top_errors: list[dict] = field(default_factory=list)
    projections: dict = field(default_factory=dict)
    trade_plans: dict = field(default_factory=dict)
    display_data_pool: dict = field(default_factory=dict)
    validation_results: list[ProjectionValidationResult] = field(default_factory=list)
