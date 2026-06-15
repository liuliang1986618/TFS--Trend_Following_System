"""二波检测 — 上升趋势→回调→重入信号。

用法:
    from src.engine.second_wave import SecondWaveDetector
    result = SecondWaveDetector.detect(daily_df, current_state, pullback)
"""
import numpy as np; import pandas as pd
from dataclasses import dataclass, asdict
from typing import Optional

@dataclass
class SecondWaveResult:
    detected: bool; confidence: str
    prior_uptrend_days: int; correction_depth_pct: float
    correction_days: int; reentry_signals: list; description: str
    def to_dict(self) -> dict: return asdict(self)

class SecondWaveDetector:

    @staticmethod
    def detect(daily_df: pd.DataFrame, current_state,
               pullback=None) -> Optional[SecondWaveResult]:
        if len(daily_df) < 60: return None
        close = daily_df["close"].astype(float).values
        volume = daily_df["volume"].astype(float).values
        price = float(close[-1])

        ma20_arr = pd.Series(close).rolling(20).mean().values
        ma60_arr = pd.Series(close).rolling(60).mean().values
        diff = ma20_arr - ma60_arr; valid = ~np.isnan(diff)
        golden_idx = None
        for i in range(len(diff)-1, 0, -1):
            if valid[i] and valid[i-1] and diff[i] > 0 and diff[i-1] <= 0:
                golden_idx = i; break
        if golden_idx is None: return None
        prior_uptrend_days = len(diff) - golden_idx
        if prior_uptrend_days < 10: return None

        if pullback is None:
            peak_20 = float(np.max(close[-20:]))
            correction_depth_pct = round((price/peak_20-1)*100, 1)
            correction_days = 0
        else:
            correction_depth_pct = pullback.depth_pct
            correction_days = pullback.days_from_peak
        if correction_depth_pct > -2: return None

        signals = []
        ma20 = float(np.mean(close[-20:]))
        if abs(price/ma20-1) < 0.03:
            is_yang = close[-1] > daily_df["open"].values[-1]
            low = daily_df["low"].values[-1]
            body = abs(close[-1]-daily_df["open"].values[-1])
            has_shadow = (min(daily_df["open"].values[-1],close[-1])-low) > body*1.5
            if is_yang or has_shadow:
                signals.append("MA20附近企稳")

        vol_5d = np.mean(volume[-6:-1]); vol_10d = np.mean(volume[-11:-6])
        if vol_10d > 0 and vol_5d/vol_10d > 1.2:
            signals.append("近5日放量回流")

        delta = np.diff(close[-15:]); g=np.maximum(delta,0); l=np.abs(np.minimum(delta,0))
        rsi = 100-(100/(1+np.mean(g)/np.mean(l))) if np.mean(l)>0 else 100
        de = np.diff(close[-22:-7]); g2=np.maximum(de,0); l2=np.abs(np.minimum(de,0))
        rsi2 = 100-(100/(1+np.mean(g2)/np.mean(l2))) if len(l2)>0 and np.mean(l2)>0 else 100
        if rsi > rsi2 and rsi2 < 50:
            signals.append(f"RSI回升{rsi2:.0f}→{rsi:.0f}")

        recent_3 = np.diff(close[-4:])
        if len(recent_3)>=3 and recent_3[-2]<0 and recent_3[-1]>0:
            signals.append("连跌后首阳")

        try:
            from src.enhanced_actions import _ema
            e12=_ema(close,12); e26=_ema(close,26); d=e12-e26; dea=_ema(d,9)
            hist=(d-dea)*2
            if len(hist)>=3 and hist[-1]>hist[-2]:
                signals.append("MACD柱缩短")
        except: pass

        n = len(signals); detected = n >= 2
        conf = "high" if n>=4 else ("medium" if n>=3 else "low")
        desc = f"二波({'✅' if detected else '❌'}) {conf}: {'; '.join(signals[:3])}" if signals else "二波无信号"

        return SecondWaveResult(
            detected=detected, confidence=conf,
            prior_uptrend_days=prior_uptrend_days,
            correction_depth_pct=correction_depth_pct,
            correction_days=correction_days,
            reentry_signals=signals, description=desc)
