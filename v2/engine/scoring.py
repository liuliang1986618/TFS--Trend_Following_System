"""Score, confidence, scenario, and position calculations for TFS v2."""

from __future__ import annotations

from .params import StrategyParams


def calculate_score(state: int | str, indicators: dict, params: StrategyParams | None = None, days_running: int = 0, stage: str = "") -> float:
    params = params or StrategyParams()
    old_score = calculate_old_score_150(state, indicators, days_running=days_running, stage=stage)
    score = old_score / 150.0 * 100.0
    return max(params.score_min, min(params.score_max, round(score, 1)))


def calculate_old_score_150(state: int | str, indicators: dict, days_running: int = 0, stage: str = "") -> float:
    base = 30.0
    if indicators.get("ma_mid_bullish", False):
        base += 10
    if indicators.get("ma_bullish", False):
        base += 10
    pct_20d = indicators.get("pct_20d", 0.0)
    if pct_20d > 0:
        base += 10

    if state == 4:
        base += 35
    elif state == 5:
        base += 25
    elif state == 3:
        base += 5
    else:
        base -= 5

    if stage == "late":
        base -= 5

    if days_running < 10:
        freshness = 12
    elif days_running < 30:
        freshness = 8
    elif days_running < 60:
        freshness = 5
    else:
        freshness = 3

    transition = 0
    if state == 3 and indicators.get("ma_bullish"):
        transition = 8
        if indicators.get("vol_ratio", 1.0) > 1.2:
            transition += 4
    if state == 5 and indicators.get("ma_bullish") and indicators.get("pct_today", 0.0) > 0:
        transition = 6

    if pct_20d > 20:
        momentum = 12
    elif pct_20d > 10:
        momentum = 8
    elif pct_20d > 5:
        momentum = 5
    elif pct_20d > 0:
        momentum = 2
    else:
        momentum = 0

    quality = 0
    if indicators.get("ma_bullish"):
        quality += 5
    if indicators.get("ma_mid_bullish"):
        quality += 3

    total_ret = indicators.get("total_return_pct", pct_20d)
    if total_ret > 150:
        strength = 15
    elif total_ret > 100:
        strength = 12
    elif total_ret > 60:
        strength = 8
    elif total_ret > 30:
        strength = 4
    elif total_ret > 10:
        strength = 2
    else:
        strength = 0

    vol = 3 if 1.0 < indicators.get("vol_ratio", 1.0) < 2.0 else 0
    pct_5d = indicators.get("pct_5d", 0.0)
    penalty = -10 if pct_5d < -5 else -5 if pct_5d < -3 else 0
    score = base + freshness + transition + momentum + quality + strength + vol + penalty
    return max(0.0, min(150.0, round(score, 1)))


def estimate_confidence(score: float, state: int | str, risk_flags: list[str] | None = None) -> float:
    confidence = score / 100.0
    if state in (4, 5):
        confidence += 0.05
    if state in (1, 2, "3'"):
        confidence -= 0.10
    confidence -= 0.05 * len(risk_flags or [])
    return max(0.0, min(1.0, round(confidence, 3)))


def estimate_scenario(score: float, confidence: float, state: int | str) -> dict:
    up = min(0.80, max(0.15, confidence * 0.75 + (0.10 if state in (4, 5) else 0.0)))
    down = max(0.05, min(0.60, (1.0 - confidence) * 0.45 + (0.10 if state in (1, 2, "3'") else 0.0)))
    flat = max(0.05, 1.0 - up - down)
    total = up + flat + down
    return {"up": round(up / total, 3), "flat": round(flat / total, 3), "down": round(down / total, 3)}


def calculate_position_hint(state: int | str, score: float, params: StrategyParams | None = None, market_context: dict | None = None) -> dict:
    params = params or StrategyParams()
    base = {1: 0.0, 2: 0.0, 3: 16.6, 4: 100.0, 5: 100.0, "3'": 33.3}.get(state, 0.0)
    score_adjusted = base * max(0.0, min(1.0, score / 100.0))
    cap_reason = "market_context_unknown"
    cap = params.unknown_market_position_cap * 100.0
    if market_context and market_context.get("position_cap") is not None:
        cap = float(market_context["position_cap"]) * 100.0
        cap_reason = "market_context_cap"
    pct = min(score_adjusted, cap)
    return {"pct": round(pct, 1), "base_pct": round(base, 1), "cap_pct": round(cap, 1), "cap_reason": cap_reason}
