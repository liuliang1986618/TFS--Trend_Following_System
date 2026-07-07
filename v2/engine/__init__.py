"""Trend engine facade for TFS v2."""

from __future__ import annotations

from .analyzers import analyze_trend_context, detect_risk_flags
from .classifier import TrendClassifier
from .filters import apply_trend_filters
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
        passed_filter, filter_reasons = apply_trend_filters(state, indicators)
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
    ) -> list[StrategySignal]:
        if self.data_layer is None:
            raise ValueError("TrendEngine requires a DataLayer")
        signals: list[StrategySignal] = []
        for code in self.data_layer.list_symbols(dtype):
            try:
                signal = self.analyze_symbol(dtype, code, end_date=end_date, market_context=market_context)
            except Exception:
                continue
            if not signal.signals.get("passed_filter", True):
                continue
            signals.append(signal)
        signals.sort(key=lambda item: (item.score, item.confidence, str(item.code)), reverse=True)
        if max_candidates is None:
            return signals
        return signals[:max_candidates]

    def scan_stock_full(self, date: str | None = None, max_candidates: int | None = 50) -> list[StrategySignal]:
        return self.run_universe("stock", end_date=date, max_candidates=max_candidates)

    def scan_etf_direct(self, date: str | None = None, max_candidates: int | None = 50) -> list[StrategySignal]:
        return self.run_universe("etf", end_date=date, max_candidates=max_candidates)

    def scan_etf_full(self, date: str | None = None, max_candidates: int | None = 50) -> list[StrategySignal]:
        return self.scan_etf_direct(date=date, max_candidates=max_candidates)

    def scan_stock_funnel(self, date: str | None = None, max_candidates: int | None = 50) -> dict:
        stocks = self.scan_stock_full(date=date, max_candidates=max_candidates)
        relation_lookup = self._relation_entity_lookup()
        return {
            "relation_version": self.data_layer.get_relation_version() if hasattr(self.data_layer, "get_relation_version") else None,
            "sectors": self._group_candidates_by_relation(stocks, "sectors", relation_lookup.get("sectors", {})),
            "themes": self._group_candidates_by_relation(stocks, "themes", relation_lookup.get("themes", {})),
            "stocks": stocks,
        }

    @staticmethod
    def _group_candidates_by_relation(signals: list[StrategySignal], relation_key: str, names: dict) -> list[dict]:
        groups: dict[str, dict] = {}
        for signal in signals:
            for code in signal.relations.get(relation_key, []):
                group = groups.setdefault(code, {"code": code, "name": names.get(code, code), "candidate_count": 0, "top_score": 0.0, "candidates": []})
                group["candidate_count"] += 1
                group["top_score"] = max(group["top_score"], signal.score)
                group["candidates"].append(signal.code)
        return sorted(groups.values(), key=lambda item: (item["candidate_count"], item["top_score"], item["code"]), reverse=True)

    def _relation_entity_lookup(self) -> dict:
        relation_store = getattr(self.data_layer, "relations", None)
        if relation_store is None or not hasattr(relation_store, "_load_current"):
            return {"sectors": {}, "themes": {}}
        relation = relation_store._load_current()
        return {
            "sectors": {str(item.get("code")): item.get("name", item.get("code")) for item in relation.get("sectors", []) if isinstance(item, dict)},
            "themes": {str(item.get("code")): item.get("name", item.get("code")) for item in relation.get("themes", []) if isinstance(item, dict)},
        }

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


__all__ = ["TrendEngine", "StrategySignal", "StrategyParams"]
