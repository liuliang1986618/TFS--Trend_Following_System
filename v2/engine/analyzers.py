"""Pullback, second-wave, stage, and risk analyzers for TFS v2.

基于v1实现，修复了PivotDetector失败时broke_prev_low默认False的问题。
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class PullbackProfile:
    """回调特征分析结果。"""
    depth_pct: float
    days_from_peak: int
    volume_pattern: str       # shrinking|expanding|neutral
    touched_ma20: bool
    touched_ma60: bool
    broke_prev_low: Optional[bool]  # None表示未知（PivotDetector失败）
    is_healthy: bool
    description: str

    def to_dict(self) -> dict:
        d = asdict(self)
        for k in ['depth_pct', 'days_from_peak']:
            if k in d and hasattr(d[k], 'item'):
                d[k] = d[k].item()
        return d


class PullbackAnalyzer:
    """回调特征分析器 — 判断回调是否健康（缩量、未破位、浅回调）。
    
    修复：PivotDetector失败时broke_prev_low不再默认False，而是标记为None。
    在is_healthy判断中，None视为不健康。
    """

    @staticmethod
    def analyze(daily_df: pd.DataFrame,
                peak_price: float = None) -> Optional[PullbackProfile]:
        if len(daily_df) < 60:
            return None

        close = daily_df["close"].astype(float).values
        volume = daily_df["volume"].astype(float).values
        high = daily_df["high"].astype(float).values
        price = float(close[-1])

        if peak_price is None:
            peak_price = float(np.max(high[-20:]))
        if peak_price <= price:
            return None

        depth_pct = round((price / peak_price - 1) * 100, 1)

        peak_idx_20 = np.argmax(high[-20:])
        days_from_peak = 19 - peak_idx_20

        ma20 = float(np.mean(close[-20:]))
        ma60 = float(np.mean(close[-60:]))
        touched_ma20 = price <= ma20
        touched_ma60 = price <= ma60

        vol_5d = np.mean(volume[-6:-1]) if len(volume) >= 6 else np.mean(volume[-5:])
        vol_20d = np.mean(volume[-21:-1]) if len(volume) >= 21 else np.mean(volume[:-1])
        vol_ratio = vol_5d / vol_20d if vol_20d > 0 else 1.0

        if vol_ratio < 0.8:
            volume_pattern = "shrinking"
        elif vol_ratio > 1.3:
            volume_pattern = "expanding"
        else:
            volume_pattern = "neutral"

        # 修复：PivotDetector失败时broke_prev_low标记为None
        try:
            from v2.engine.levels import PivotDetector
            pd_obj = PivotDetector()
            prev_low = pd_obj.recent_low(daily_df)
            broke_prev_low = prev_low is not None and price < prev_low["low"]
        except Exception:
            broke_prev_low = None  # 未知状态，不再默认False

        # 修复：is_healthy判断中，None或True视为不健康
        is_healthy = (
            volume_pattern == "shrinking"
            and not broke_prev_low  # False=健康, True或None=不健康
            and not touched_ma60
            and depth_pct > -10
        )

        if is_healthy:
            desc = (f"健康回调: 回撤{abs(depth_pct)}%缩量, 未破位, 加仓机会")
        elif broke_prev_low is None:
            desc = (f"未知回调: 无法确认支撑位, 回撤{abs(depth_pct)}%, 需谨慎")
        elif broke_prev_low:
            desc = (f"危险回调: 跌破前低, 回撤{abs(depth_pct)}%, 结构可能破坏")
        elif touched_ma60:
            desc = (f"深度回调: 触及MA60, 回撤{abs(depth_pct)}%, 关注支撑")
        elif volume_pattern == "expanding":
            desc = (f"放量回调: 回撤{abs(depth_pct)}%, 警惕出货")
        else:
            desc = (f"回调中: 回撤{abs(depth_pct)}%")

        return PullbackProfile(
            depth_pct=depth_pct, days_from_peak=days_from_peak,
            volume_pattern=volume_pattern, touched_ma20=touched_ma20,
            touched_ma60=touched_ma60, broke_prev_low=broke_prev_low,
            is_healthy=is_healthy, description=desc,
        )


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
