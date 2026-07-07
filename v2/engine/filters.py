"""Trend quality filters for TFS v2."""

from __future__ import annotations


def apply_trend_filters(state, indicators: dict) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if state in (1, 2, "3'"):
        reasons.append("defensive_state")
    if state == 3 and indicators.get("pct_20d", 0.0) < -3:
        reasons.append("weak_midterm_momentum")
    if state == 5 and indicators.get("ma_death_cross"):
        reasons.append("pullback_with_death_cross")
    return len(reasons) == 0, reasons
