"""Projection scenario generation boundary for TFS v2."""

from __future__ import annotations

from dataclasses import dataclass, field

from .weights import ProjectionWeights


@dataclass
class ProjectionScenario:
    label: str
    current_state: str
    expected_next_state: str
    weight: float = 0.0
    probability_label: str = ""
    conditions: list[str] = field(default_factory=list)
    action_hint: str | None = None
    risk_flags: list[str] = field(default_factory=list)


class ProjectionEngine:
    """Generate A/B/C projection scenarios from a StrategySignal state."""

    SCENARIO_MAP = {
        "4": [
            ("A", "大概率", "4", "继续沿MA20上方运行, 无异常信号"),
            ("B", "中概率", "5", "缩量回调, 不破前低"),
            ("C", "小概率", "3p", "放量跌破前低, 收盘未收复"),
        ],
        "3": [
            ("A", "大概率", "3", "回调不破前低, 继续整理"),
            ("B", "中概率", "4", "放量再创新高, 结构完整"),
            ("C", "小概率", "1", "放量跌破前低, 假突破确认"),
        ],
        "5": [
            ("A", "大概率", "4", "缩量企稳反弹, 不破前低"),
            ("B", "中概率", "5", "继续整理, 方向不明"),
            ("C", "小概率", "3p", "放量跌破前低"),
        ],
        "3p": [
            ("A", "大概率", "4", "假跌破确认, 快速收复前低"),
            ("B", "中概率", "3p", "继续在低点附近缩量整理"),
            ("C", "小概率", "1", "继续下跌, 再破新低"),
        ],
        "2": [
            ("A", "大概率", "2", "继续反弹, 逐步靠近前高"),
            ("B", "中概率", "3", "放量突破前高"),
            ("C", "小概率", "1", "反弹结束, 回落破前低"),
        ],
        "1": [
            ("A", "大概率", "1", "继续沿MA20下方运行, 持续下跌"),
            ("B", "小概率", "2", "出现连续上涨反弹信号"),
        ],
    }

    def __init__(self, weights: ProjectionWeights | None = None):
        self.weights = weights or ProjectionWeights()

    def generate(self, signal, *args, **kwargs) -> list[ProjectionScenario]:
        state = self._state_key(signal.state)
        weights = self.weights.get_weights(state)
        scenarios = []
        for label, probability, next_state, condition in self.SCENARIO_MAP.get(state, []):
            scenarios.append(
                ProjectionScenario(
                    label=label,
                    probability_label=probability,
                    current_state=state,
                    expected_next_state=next_state,
                    weight=weights.get(label, 0.0),
                    conditions=[condition],
                    action_hint=None,
                    risk_flags=list(getattr(signal, "risk_flags", []) or []),
                )
            )
        return scenarios

    @staticmethod
    def _state_key(state) -> str:
        return str(state).replace("'", "p")
