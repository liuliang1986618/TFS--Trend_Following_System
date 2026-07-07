"""Pullback, second-wave, stage, and risk analyzers for TFS v2."""

from __future__ import annotations


def analyze_trend_context(daily_df, indicators: dict, state) -> dict:
    stage = "early"
    if indicators.get("pct_60d", 0.0) > 40:
        stage = "late"
    elif indicators.get("pct_20d", 0.0) > 10:
        stage = "continuation"
    return {
        "stage": stage,
        "pct_5d": indicators.get("pct_5d", 0.0),
        "pct_20d": indicators.get("pct_20d", 0.0),
        "pct_60d": indicators.get("pct_60d", 0.0),
        "max_drawdown_60d": indicators.get("max_drawdown_60d", 0.0),
        "state_family": "uptrend" if state in (3, 4, 5) else "defensive",
    }


def detect_risk_flags(indicators: dict, state) -> list[str]:
    flags: list[str] = []
    if indicators.get("ma_death_cross"):
        flags.append("ma_death_cross")
    if indicators.get("pct_5d", 0.0) < -5:
        flags.append("sharp_5d_pullback")
    if indicators.get("max_drawdown_60d", 0.0) < -20:
        flags.append("deep_60d_drawdown")
    if state == "3'":
        flags.append("downshift_confirming")
    return flags
