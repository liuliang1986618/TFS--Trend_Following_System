"""回调特征分析 — 判断回调是否健康（缩量、未破位、浅回调）。

用法:
    from src.engine.pullback import PullbackAnalyzer
    profile = PullbackAnalyzer.analyze(daily_df)
"""
import numpy as np
import pandas as pd
from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class PullbackProfile:
    depth_pct: float
    days_from_peak: int
    volume_pattern: str       # shrinking|expanding|neutral
    touched_ma20: bool
    touched_ma60: bool
    broke_prev_low: bool
    is_healthy: bool
    description: str

    def to_dict(self) -> dict:
        return asdict(self)


class PullbackAnalyzer:

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

        try:
            from src.engine.pivots import PivotDetector
            pd_obj = PivotDetector()
            prev_low = pd_obj.recent_low(daily_df)
            broke_prev_low = prev_low is not None and price < prev_low["low"]
        except Exception:
            broke_prev_low = False

        is_healthy = (
            volume_pattern == "shrinking"
            and not broke_prev_low
            and not touched_ma60
            and depth_pct > -10
        )

        if is_healthy:
            desc = (f"健康回调: 回撤{abs(depth_pct)}%缩量, 未破位, 加仓机会")
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
