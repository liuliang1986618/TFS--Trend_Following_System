"""Support, resistance, stop, and key-level calculations for TFS v2."""

from __future__ import annotations


def calculate_key_levels(daily_df, indicators: dict) -> dict:
    close = float(daily_df["close"].iloc[-1])
    return {
        "support": indicators.get("low_20d", close),
        "resistance": indicators.get("high_20d", close),
        "stop_loss": round(close * 0.92, 3),
        "current": close,
    }
