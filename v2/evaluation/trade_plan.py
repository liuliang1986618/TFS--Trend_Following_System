"""Trade guidance projection contracts for TFS v2."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TradeTrigger:
    scenario_label: str
    action_type: str
    expected_next_state: str
    target_position_pct: float
    trigger_conditions: list[str] = field(default_factory=list)
    risk_controls: list[str] = field(default_factory=list)
    evidence: dict = field(default_factory=dict)


@dataclass
class TradePlan:
    code: str
    name: str
    dtype: str
    market_date: str
    current_state: str
    base_position_pct: float
    target_position_pct: float
    triggers: list[TradeTrigger] = field(default_factory=list)
    risk_controls: list[str] = field(default_factory=list)
    evidence: dict = field(default_factory=dict)


class TradePlanBuilder:
    """Turn projection scenarios into structured trading guidance."""

    TARGET_PCT = {
        "stock": {"1": 0.0, "2": 0.0, "3": 0.03, "4": 0.08, "5": 0.10, "3p": 0.03},
        "etf": {"1": 0.0, "2": 0.0, "3": 0.08, "4": 0.15, "5": 0.20, "3p": 0.05},
    }

    TRANSITION_EVIDENCE = {
        "1": {"1": {"frequency": 0.865, "support": None, "confidence": 0.95}},
        "2": {"2": {"frequency": 0.653, "support": None, "confidence": 0.80}},
        "3": {"3": {"frequency": 0.770, "support": None, "confidence": 0.85}},
        "4": {"4": {"frequency": 0.794, "support": 7289, "confidence": 0.95}},
        "5": {
            "3": {"frequency": 0.463, "support": None, "confidence": 0.70},
            "4": {"frequency": 0.390, "support": None, "confidence": 0.70},
        },
        "3p": {"1": {"frequency": 0.784, "support": None, "confidence": 0.85}},
    }

    def build(self, signal, scenarios) -> TradePlan:
        current_state = self._state_key(getattr(signal, "state", ""))
        dtype = getattr(signal, "dtype", "stock") or "stock"
        base_position = self._target_pct(dtype, current_state)
        risk_controls = list(getattr(signal, "risk_flags", []) or [])
        triggers = [self._trigger(dtype, current_state, scenario, risk_controls) for scenario in scenarios]
        return TradePlan(
            code=getattr(signal, "code", ""),
            name=getattr(signal, "name", ""),
            dtype=dtype,
            market_date=getattr(signal, "market_date", ""),
            current_state=current_state,
            base_position_pct=base_position,
            target_position_pct=base_position,
            triggers=triggers,
            risk_controls=risk_controls,
            evidence={"source": "legacy_state_transition_and_portfolio_target_pct"},
        )

    def _trigger(self, dtype: str, current_state: str, scenario, risk_controls: list[str]) -> TradeTrigger:
        next_state = self._state_key(scenario.expected_next_state)
        target_pct = self._target_pct(dtype, next_state)
        action_type = self._action_type(current_state, next_state, target_pct)
        evidence = {
            "scenario_weight": scenario.weight,
            "probability_label": scenario.probability_label,
        }
        evidence.update(self.TRANSITION_EVIDENCE.get(current_state, {}).get(next_state, {}))
        return TradeTrigger(
            scenario_label=scenario.label,
            action_type=action_type,
            expected_next_state=next_state,
            target_position_pct=target_pct,
            trigger_conditions=list(scenario.conditions),
            risk_controls=list(risk_controls),
            evidence=evidence,
        )

    def _action_type(self, current_state: str, next_state: str, target_pct: float) -> str:
        current_pct = self._target_pct("stock", current_state)
        if target_pct <= 0:
            return "exit" if current_pct > 0 else "watch"
        if next_state in {"1", "3p"} or target_pct < current_pct:
            return "reduce"
        if target_pct > current_pct:
            return "add" if current_pct > 0 else "buy"
        if current_pct > 0:
            return "hold"
        return "watch"

    def _target_pct(self, dtype: str, state: str) -> float:
        targets = self.TARGET_PCT.get(dtype, self.TARGET_PCT["stock"])
        return targets.get(self._state_key(state), 0.0)

    @staticmethod
    def _state_key(state) -> str:
        return str(state).replace("'", "p")
