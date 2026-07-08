"""Strategy parameter contracts for TFS v2."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class StrategyParams:
    ma_periods: tuple[int, ...] = (5, 10, 20, 60, 120, 250)
    rsi_period: int = 14
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    min_history_days: int = 60
    score_min: float = 0.0
    score_max: float = 100.0
    unknown_market_position_cap: float = 0.50
    score_weights: dict = field(default_factory=dict)
    enabled_indicators: set[str] = field(default_factory=set)
