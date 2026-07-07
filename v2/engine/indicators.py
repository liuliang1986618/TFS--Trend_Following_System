"""Technical indicator calculations for TFS v2."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .params import StrategyParams


def ma(close: np.ndarray, period: int) -> np.ndarray:
    if len(close) < period:
        return np.full_like(close, np.nan, dtype=float)
    result = np.full_like(close, np.nan, dtype=float)
    cumsum = np.cumsum(np.insert(close.astype(float), 0, 0))
    result[period - 1:] = (cumsum[period:] - cumsum[:-period]) / period
    return result


def ema(close: np.ndarray, period: int) -> np.ndarray:
    close = close.astype(float)
    result = np.full_like(close, np.nan, dtype=float)
    if len(close) == 0:
        return result
    k = 2.0 / (period + 1)
    result[0] = close[0]
    for i in range(1, len(close)):
        result[i] = close[i] * k + result[i - 1] * (1 - k)
    return result


def rsi(close: np.ndarray, period: int = 14) -> float:
    if len(close) < period + 1:
        return 50.0
    delta = np.diff(close[-period - 1:].astype(float))
    gain = np.maximum(delta, 0).sum() / period
    loss = np.maximum(-delta, 0).sum() / period
    if loss == 0:
        return 100.0
    return float(100.0 - 100.0 / (1.0 + gain / loss))


def bbands(close: np.ndarray, period: int = 20, std_dev: float = 2.0) -> dict:
    if len(close) < period:
        last = float(close[-1])
        return {"upper": last, "middle": last, "lower": last, "position": 0.5, "width": 0.0}
    c = close[-period:].astype(float)
    mid = float(np.mean(c))
    std = float(np.std(c))
    upper = mid + std_dev * std
    lower = mid - std_dev * std
    price = float(close[-1])
    rng = upper - lower
    pos = (price - lower) / rng if rng > 0 else 0.5
    width = rng / mid if mid > 0 else 0.0
    return {"upper": upper, "middle": mid, "lower": lower, "position": pos, "width": width}


def macd(close: np.ndarray, fast: int = 12, slow: int = 26, sig: int = 9) -> dict:
    if len(close) < slow + sig:
        return {"dif": 0.0, "dea": 0.0, "macd": 0.0, "golden_cross": False, "hist_rising": False}
    c = close.astype(float)
    dif = ema(c, fast) - ema(c, slow)
    dea = ema(dif, sig)
    hist = (dif - dea) * 2
    golden = bool(dif[-2] <= dea[-2] and dif[-1] > dea[-1]) if len(dif) >= 2 else False
    hist_rising = bool(hist[-1] > hist[-2] and hist[-1] < 0) if len(hist) >= 3 else False
    return {"dif": float(dif[-1]), "dea": float(dea[-1]), "macd": float(hist[-1]), "golden_cross": golden, "hist_rising": hist_rising}


def mfi(high: np.ndarray, low: np.ndarray, close: np.ndarray, volume: np.ndarray, period: int = 14) -> float:
    if len(close) < period + 1:
        return 50.0
    h = high[-period - 1:].astype(float)
    l = low[-period - 1:].astype(float)
    c = close[-period - 1:].astype(float)
    v = volume[-period - 1:].astype(float)
    tp = (h + l + c) / 3.0
    mf = tp * v
    pos_flow = np.sum(mf[1:][tp[1:] > tp[:-1]])
    neg_flow = np.sum(mf[1:][tp[1:] < tp[:-1]])
    if neg_flow == 0:
        return 100.0
    return float(100.0 - 100.0 / (1.0 + pos_flow / neg_flow))


def calculate_indicators(daily_df: pd.DataFrame, params: StrategyParams | None = None) -> dict:
    params = params or StrategyParams()
    df = daily_df.sort_values("date") if "date" in daily_df.columns else daily_df.copy()
    close = df["close"].astype(float).to_numpy()
    volume = df["volume"].astype(float).to_numpy()
    high = df["high"].astype(float).to_numpy() if "high" in df.columns else close.copy()
    low = df["low"].astype(float).to_numpy() if "low" in df.columns else close.copy()
    open_arr = df["open"].astype(float).to_numpy() if "open" in df.columns else close.copy()

    result: dict = {}
    for period in params.ma_periods:
        if period <= len(close) or period in (5, 10, 20, 60):
            result[f"ma{period}"] = ma(close, period)

    ma5 = result.get("ma5", np.array([np.nan]))[-1]
    ma10 = result.get("ma10", np.array([np.nan]))[-1]
    ma20 = result.get("ma20", np.array([np.nan]))[-1]
    ma60 = result.get("ma60", np.array([np.nan]))[-1]

    result["ma_bullish"] = bool(not np.isnan(ma5) and not np.isnan(ma10) and not np.isnan(ma20) and ma5 > ma10 > ma20)
    result["ma_mid_bullish"] = bool(not np.isnan(ma20) and not np.isnan(ma60) and ma20 > ma60)
    result["ma5_below_ma10"] = bool(not np.isnan(ma5) and not np.isnan(ma10) and ma5 < ma10)
    if len(result.get("ma5", [])) >= 2 and len(result.get("ma10", [])) >= 2:
        prev_ma5 = result["ma5"][-2]
        prev_ma10 = result["ma10"][-2]
        result["ma_death_cross"] = bool(not np.isnan(prev_ma5) and not np.isnan(prev_ma10) and prev_ma5 >= prev_ma10 and ma5 < ma10)
    else:
        result["ma_death_cross"] = False

    result["price_below_ma5"] = bool(not np.isnan(ma5) and close[-1] < ma5)
    result["rsi"] = rsi(close, params.rsi_period)
    result["bb"] = bbands(close)
    result["macd"] = macd(close, params.macd_fast, params.macd_slow, params.macd_signal)
    result["mfi"] = mfi(high, low, close, volume)

    vol_ma20 = float(np.mean(volume[-20:])) if len(volume) >= 20 else float(volume[-1])
    result["vol_ratio"] = float(volume[-1] / vol_ma20) if vol_ma20 > 0 else 1.0
    result["pct_today"] = float((close[-1] - close[-2]) / close[-2] * 100) if len(close) >= 2 else 0.0
    result["pct_5d"] = float((close[-1] - close[-6]) / close[-6] * 100) if len(close) >= 6 else 0.0
    result["pct_20d"] = float((close[-1] - close[-21]) / close[-21] * 100) if len(close) >= 21 else 0.0
    result["pct_60d"] = float((close[-1] - close[-61]) / close[-61] * 100) if len(close) >= 61 else 0.0
    result["ma_deviation"] = float((close[-1] - ma20) / ma20 * 100) if not np.isnan(ma20) and ma20 > 0 else 0.0
    result["vol_trend"] = float(np.mean(volume[-5:]) / np.mean(volume[-25:-5])) if len(volume) >= 25 and np.mean(volume[-25:-5]) > 0 else 1.0
    result["high_20d"] = float(np.max(high[-20:])) if len(high) >= 20 else float(close[-1])
    result["low_20d"] = float(np.min(low[-20:])) if len(low) >= 20 else float(close[-1])
    result["high_60d"] = float(np.max(high[-60:])) if len(high) >= 60 else result["high_20d"]
    result["low_60d"] = float(np.min(low[-60:])) if len(low) >= 60 else result["low_20d"]
    if len(close) >= 60:
        c60 = close[-60:]
        peak = np.maximum.accumulate(c60)
        result["max_drawdown_60d"] = float(np.min((c60 - peak) / peak * 100))
    else:
        result["max_drawdown_60d"] = 0.0
    result["today_open"] = float(open_arr[-1])
    result["today_high"] = float(high[-1])
    result["today_low"] = float(low[-1])
    result["today_close"] = float(close[-1])
    return result
