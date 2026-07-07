"""Evaluation facade for TFS v2."""

from __future__ import annotations

from .metrics import EvaluationReport
from .projection import ProjectionEngine
from .trade_plan import TradePlanBuilder
from .validation import ProjectionValidation


class Evaluation:
    """Generate minimal evaluation reports from engine signals or state records."""

    def __init__(
        self,
        data_layer=None,
        engine=None,
        projection_engine: ProjectionEngine | None = None,
        trade_plan_builder: TradePlanBuilder | None = None,
    ):
        self.data_layer = data_layer
        self.engine = engine
        self.projection_engine = projection_engine or ProjectionEngine()
        self.trade_plan_builder = trade_plan_builder or TradePlanBuilder()
        self.validation = ProjectionValidation(self.projection_engine)

    def generate_report(self, signals=None, records: list[dict] | None = None) -> EvaluationReport:
        if records is not None:
            return self.validation.validate_records(records)
        signals = list(signals or [])
        projections = {signal.code: self.projection_engine.generate(signal) for signal in signals}
        trade_plans = {
            signal.code: self.trade_plan_builder.build(signal, projections[signal.code]) for signal in signals
        }
        dates = [signal.market_date for signal in signals if getattr(signal, "market_date", None)]
        return EvaluationReport(
            start_date=min(dates) if dates else "",
            end_date=max(dates) if dates else "",
            scope="signals",
            total=len(signals),
            projections=projections,
            trade_plans=trade_plans,
            display_data_pool=self._display_data_pool(signals, projections, trade_plans),
        )

    def _display_data_pool(self, signals: list, projections: dict, trade_plans: dict) -> dict:
        return {
            "symbols": {
                signal.code: self._symbol_display_data(signal, projections.get(signal.code, []), trade_plans.get(signal.code))
                for signal in signals
            }
        }

    def _symbol_display_data(self, signal, scenarios: list, trade_plan) -> dict:
        indicators = getattr(signal, "indicators", {}) or {}
        trend_context = dict(getattr(signal, "trend_context", {}) or {})
        key_levels = self._key_levels(trend_context.get("key_levels", []))
        state = str(getattr(signal, "state", ""))
        return {
            "trend_context": trend_context,
            "today_position": self._today_position(indicators, state),
            "strategy_summary": self._strategy_summary(state),
            "projection": self._projection_data(scenarios),
            "buy_sell_zone": self._buy_sell_zone(indicators),
            "key_levels": key_levels,
            "watch_scenarios": self._watch_scenarios(trade_plan),
            "position_plan": self._position_plan(trade_plan),
        }

    @staticmethod
    def _today_position(indicators: dict, state: str) -> dict:
        pct_today = indicators.get("pct_today", 0.0) or 0.0
        vol_ratio = indicators.get("vol_ratio", 1.0) or 1.0
        if state == "4" and abs(pct_today) < 0.5:
            label = "横盘休整"
        elif state == "4" and pct_today < -0.5 and vol_ratio < 1:
            label = "缩量回调"
        elif state == "4" and pct_today > 1:
            label = "顺势上涨"
        else:
            label = "小幅波动"
        return {"label": label, "narrative": f"今日涨跌 {pct_today:.1f}%，量比 {vol_ratio:.2f}"}

    @staticmethod
    def _strategy_summary(state: str) -> str:
        if state == "4":
            return "上升趋势完好，顺势持有，回调到支撑位再考虑加仓。"
        if state == "5":
            return "趋势偏热，等待回调确认，不追高。"
        if state == "3":
            return "趋势尝试成形，轻仓观察突破有效性。"
        return "趋势信号不足，先观察。"

    @staticmethod
    def _projection_data(scenarios: list) -> dict:
        return {
            "scenarios": [
                {
                    "label": item.label,
                    "probability": item.weight,
                    "title": item.probability_label,
                    "range": "",
                    "conditions": list(item.conditions),
                }
                for item in scenarios
            ]
        }

    @staticmethod
    def _buy_sell_zone(indicators: dict) -> dict:
        bb = indicators.get("bb", {}) if isinstance(indicators.get("bb", {}), dict) else {}
        close = float(indicators.get("today_close") or indicators.get("close") or 0.0)
        lower = float(bb.get("lower", close))
        upper = float(bb.get("upper", close))
        buy_low, buy_high = sorted([lower, close])
        sell_low, sell_high = sorted([close, upper])
        return {
            "buy_zone": {"low": round(buy_low, 3), "high": round(buy_high, 3), "logic": "回踩支撑区"},
            "sell_zone": {"low": round(sell_low, 3), "high": round(sell_high, 3), "logic": "接近压力区"},
        }

    @staticmethod
    def _key_levels(value) -> list:
        if isinstance(value, list):
            return value
        if not isinstance(value, dict):
            return []
        labels = {
            "support": "支撑位",
            "resistance": "阻力位",
            "stop_loss": "止损位",
            "take_profit": "止盈位",
            "current": "昨收",
        }
        return [{"label": labels.get(key, key), "price": price} for key, price in value.items()]

    @staticmethod
    def _watch_scenarios(trade_plan) -> list:
        if not trade_plan:
            return []
        return [
            {
                "level": trigger.scenario_label,
                "action": trigger.action_type,
                "position_pct": trigger.target_position_pct,
                "signals": list(trigger.trigger_conditions),
            }
            for trigger in trade_plan.triggers
        ]

    @staticmethod
    def _position_plan(trade_plan) -> list:
        if not trade_plan:
            return []
        return [{"step": "目标仓位", "target_position_pct": trade_plan.target_position_pct, "condition": "满足触发条件后执行"}]


__all__ = ["Evaluation", "EvaluationReport", "ProjectionEngine", "ProjectionValidation", "TradePlanBuilder"]
