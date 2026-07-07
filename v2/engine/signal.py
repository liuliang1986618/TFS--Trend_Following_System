"""Strategy signal data contracts for TFS v2."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EngineContext:
    market_date: str
    relation_version: str | None = None
    metadata: dict = field(default_factory=dict)


@dataclass
class StrategySignal:
    code: str
    name: str
    dtype: str
    market_date: str
    relation_version: str | None
    state: int | str
    state_label: str
    score: float
    confidence: float
    scenario_estimate: dict = field(default_factory=dict)
    action_hint: str = ""
    position_hint: dict = field(default_factory=dict)
    indicators: dict = field(default_factory=dict)
    trend_context: dict = field(default_factory=dict)
    relations: dict = field(default_factory=dict)
    risk_flags: list[str] = field(default_factory=list)
    signals: dict = field(default_factory=dict)
