"""Trend state classification for TFS v2."""

from __future__ import annotations

import numpy as np
import pandas as pd


class TrendClassifier:
    STATE_LABELS = {
        1: "下跌趋势",
        2: "下跌中的反弹",
        3: "翻转确认中",
        4: "上涨趋势",
        5: "上涨中的回调",
        "3'": "转跌确认中",
    }

    def classify(self, daily_df: pd.DataFrame, indicators: dict | None = None) -> dict:
        state = None
        raw = None
        if len(daily_df) >= 60:
            try:
                from src.engine.state_machine import StateMachine

                raw = StateMachine.classify(daily_df)
                state = raw.state
            except Exception:
                state = None

        state = self._post_process_state(daily_df, indicators or {}, state)
        return {
            "state": state,
            "state_label": self.STATE_LABELS.get(state, "未知"),
            "raw_state": getattr(raw, "state", None),
            "conditions": getattr(raw, "conditions", {}),
            "events": self._events_from_raw(raw),
        }

    def _post_process_state(self, daily_df: pd.DataFrame, indicators: dict, state):
        close = daily_df["close"].astype(float).to_numpy()
        if len(close) < 20:
            return state or 1
        p = float(close[-1])
        ma20 = float(np.mean(close[-20:]))
        ma60 = float(np.mean(close[-60:])) if len(close) >= 60 else ma20
        golden_cross = ma20 > ma60
        pct_20d = indicators.get("pct_20d", (close[-1] / close[-21] - 1) * 100 if len(close) >= 21 else 0.0)

        if state is None:
            if golden_cross and p > ma20 and indicators.get("ma_bullish", False):
                state = 4
            elif golden_cross and p > ma20 * 0.97:
                state = 3
            elif p > ma20:
                state = 2
            else:
                state = 1

        if state == 1 and golden_cross and pct_20d > 0:
            state = 3 if p > ma20 * 0.97 else 2
        if state == 2 and golden_cross and p > ma20 * 0.97:
            state = 3
        if state == 3 and golden_cross and indicators.get("ma_bullish") and pct_20d > 0:
            state = 4
        if state in (4, 5) and p < ma20:
            state = 3
        if indicators.get("ma5_below_ma10") and state == 4:
            state = 5
        if indicators.get("ma_death_cross") and p < ma20 and state in (3, 4, 5):
            state = 2
        return state

    @staticmethod
    def _events_from_raw(raw) -> dict:
        if raw is None:
            return {}
        return {
            "consecutive_drop": bool(getattr(raw, "consecutive_drop", False)),
            "consecutive_rise": bool(getattr(raw, "consecutive_rise", False)),
            "volume_surge": bool(getattr(raw, "volume_surge", False)),
            "volume_shrink": bool(getattr(raw, "volume_shrink", False)),
            "broke_prev_high": bool(getattr(raw, "broke_prev_high", False)),
            "broke_prev_low": bool(getattr(raw, "broke_prev_low", False)),
        }
