"""Trend engine facade for TFS v2."""

from __future__ import annotations

from .analyzers import analyze_trend_context, detect_risk_flags
from .classifier import TrendClassifier
from .filters import apply_trend_filters
from .funnel import FunnelRunner
from .indicators import calculate_indicators
from .levels import calculate_key_levels
from .params import StrategyParams
from .scoring import (
    calculate_old_score_150,
    calculate_position_hint,
    calculate_score,
    estimate_confidence,
    estimate_scenario,
)
from .signal import StrategySignal


class TrendEngine:
    """Analyze a single symbol into a stable StrategySignal."""

    def __init__(self, data_layer=None, params: StrategyParams | None = None):
        self.data_layer = data_layer
        self.params = params or StrategyParams()
        self.classifier = TrendClassifier()
        self.funnel = FunnelRunner(engine=self, data_layer=data_layer)

    def analyze_symbol(
        self,
        dtype: str,
        code: str,
        name: str | None = None,
        end_date: str | None = None,
        market_context: dict | None = None,
    ) -> StrategySignal:
        if self.data_layer is None:
            raise ValueError("TrendEngine requires a DataLayer")
        daily_df = self.data_layer.load_daily(dtype, code, end_date=end_date)
        if len(daily_df) < self.params.min_history_days:
            raise ValueError(f"insufficient history: {code} has {len(daily_df)} rows, need {self.params.min_history_days}")

        indicators = calculate_indicators(daily_df, self.params)
        classification = self.classifier.classify(daily_df, indicators)
        state = classification["state"]
        trend_context = analyze_trend_context(daily_df, indicators, state)
        risk_flags = detect_risk_flags(indicators, state)
        score = calculate_score(state, indicators, self.params, stage=trend_context.get("stage", ""))
        confidence = estimate_confidence(score, state, risk_flags)
        scenario = estimate_scenario(score, confidence, state)
        position_hint = calculate_position_hint(state, score, self.params, market_context=market_context)
        passed_filter, filter_reasons = apply_trend_filters(state, indicators, daily_df)
        key_levels = calculate_key_levels(daily_df, indicators)

        market_date = daily_df["date"].iloc[-1]
        if hasattr(market_date, "strftime"):
            market_date = market_date.strftime("%Y-%m-%d")
        else:
            market_date = str(market_date)

        relations = {}
        relation_version = None
        if hasattr(self.data_layer, "get_relation_version"):
            relation_version = self.data_layer.get_relation_version()
        if dtype == "stock" and hasattr(self.data_layer, "get_stock_profile"):
            relations = self.data_layer.get_stock_profile(code, relation_version=relation_version)

        return StrategySignal(
            code=code,
            name=name or code,
            dtype=dtype,
            market_date=market_date,
            relation_version=relation_version,
            state=state,
            state_label=classification["state_label"],
            score=score,
            confidence=confidence,
            scenario_estimate=scenario,
            action_hint=self._action_hint(state, passed_filter, filter_reasons),
            position_hint=position_hint,
            indicators=indicators,
            trend_context={**trend_context, "key_levels": key_levels},
            relations=relations,
            risk_flags=risk_flags,
            signals={
                "old_score_150": calculate_old_score_150(state, indicators, stage=trend_context.get("stage", "")),
                "passed_filter": passed_filter,
                "filter_reasons": filter_reasons,
                "classification_events": classification.get("events", {}),
                "raw_state": classification.get("raw_state"),
            },
        )

    def run_universe(
        self,
        dtype: str,
        end_date: str | None = None,
        max_candidates: int | None = 50,
        market_context: dict | None = None,
        parallel: bool = True,
        prefilter: bool = True,
    ) -> list[StrategySignal]:
        if self.data_layer is None:
            raise ValueError("TrendEngine requires a DataLayer")
        all_codes = self.data_layer.list_symbols(dtype)
        if prefilter:
            codes = self._prefilter_symbols(dtype, all_codes, end_date)
        else:
            codes = all_codes
        if parallel and len(codes) > 1:
            signals = self._run_universe_parallel(dtype, codes, end_date, market_context)
        else:
            signals = self._run_universe_sequential(dtype, codes, end_date, market_context)
        signals.sort(key=lambda item: (item.score, item.confidence, str(item.code)), reverse=True)
        if max_candidates is None:
            return signals
        return signals[:max_candidates]

    def _run_universe_sequential(self, dtype, codes, end_date, market_context) -> list[StrategySignal]:
        signals: list[StrategySignal] = []
        for code in codes:
            try:
                name = self.data_layer.get_symbol_name(code, dtype) if hasattr(self.data_layer, "get_symbol_name") else code
                signal = self.analyze_symbol(dtype, code, name=name or code, end_date=end_date, market_context=market_context)
            except Exception:
                continue
            if not signal.signals.get("passed_filter", True):
                continue
            signals.append(signal)
        return signals

    def _run_universe_parallel(self, dtype, codes, end_date, market_context) -> list[StrategySignal]:
        from concurrent.futures import ProcessPoolExecutor
        data_dir = str(self.data_layer.data_dir)
        name_fn = hasattr(self.data_layer, "get_symbol_name")
        args_list = []
        for code in codes:
            name = self.data_layer.get_symbol_name(code, dtype) if name_fn else code
            args_list.append((data_dir, end_date, code, dtype, name))
        signals: list[StrategySignal] = []
        with ProcessPoolExecutor() as executor:
            for sig in executor.map(_analyze_symbol_worker, args_list):
                if sig is not None:
                    signals.append(sig)
        return signals

    def _prefilter_symbols(self, dtype: str, codes: list[str], end_date: str | None) -> list[str]:
        """快速预筛：仅读 date/close 两列，跳过明显弱势(state-1)标的。

        state-1（弱势/下跌）从不进入展示层，可安全跳过以大幅减少分析量。
        判定：20日收益 < -8% 且收盘价跌破 MA20 → 视为明显弱势。
        """
        if self.data_layer is None:
            return codes
        kept: list[str] = []
        for code in codes:
            try:
                df = self.data_layer.load_daily_columns(dtype, code, ["date", "close"], end_date=end_date)
                if df is None or len(df) < 22:
                    kept.append(code)
                    continue
                close = df["close"].astype(float)
                ma20 = close.rolling(20).mean().iloc[-1]
                last = close.iloc[-1]
                prev20 = close.iloc[-21]
                ret20 = (last / prev20 - 1) if prev20 else 0
                if ret20 < -0.08 and last < ma20:
                    continue
                kept.append(code)
            except Exception:
                kept.append(code)
        return kept

    def scan_stock_full(self, date: str | None = None, max_candidates: int | None = 50) -> list[StrategySignal]:
        return self.run_universe("stock", end_date=date, max_candidates=max_candidates)

    def scan_etf_direct(self, date: str | None = None, max_candidates: int | None = 50) -> list[StrategySignal]:
        return self.run_universe("etf", end_date=date, max_candidates=max_candidates)

    def scan_etf_full(self, date: str | None = None, max_candidates: int | None = 50) -> list[StrategySignal]:
        return self.scan_etf_direct(date=date, max_candidates=max_candidates)

    def scan_stock_funnel(self, date: str | None = None, max_candidates: int | None = 50) -> dict:
        """漏斗扫描：委托给 FunnelRunner（Top6 板块 + ABC + 最佳ETF + 龙头）。"""
        return self.funnel.scan_stock_funnel(date=date, max_candidates=max_candidates)

    @staticmethod
    def _action_hint(state, passed_filter: bool, filter_reasons: list[str]) -> str:
        if not passed_filter:
            return "规避" if filter_reasons else "观望"
        if state == 4:
            return "持有"
        if state == 5:
            return "观察回调"
        if state == 3:
            return "试探"
        return "观望"


def _analyze_symbol_worker(args: tuple):
    """多进程 worker：在子进程内重建 DataLayer + TrendEngine 并分析单标的。"""
    data_dir, end_date, code, dtype, name = args
    try:
        from v2.data_layer import DataLayer
        from v2.engine import TrendEngine

        dl = DataLayer(data_dir)
        engine = TrendEngine(dl)
        signal = engine.analyze_symbol(dtype, code, name=name or code, end_date=end_date)
        if not signal.signals.get("passed_filter", True):
            return None
        return signal
    except Exception:
        return None


__all__ = ["TrendEngine", "StrategySignal", "StrategyParams", "_analyze_symbol_worker"]
