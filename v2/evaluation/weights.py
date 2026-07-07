"""Projection weight contracts for TFS v2."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class StateWeights:
    scenario_a: float = 0.60
    scenario_b: float = 0.30
    scenario_c: float = 0.10


class ProjectionWeights:
    """Read projection weights by state, reusing the legacy defaults."""

    DEFAULT_WEIGHTS = {
        "1": StateWeights(scenario_a=0.70, scenario_b=0.30, scenario_c=0.0),
        "2": StateWeights(scenario_a=0.50, scenario_b=0.35, scenario_c=0.15),
        "3": StateWeights(scenario_a=0.50, scenario_b=0.35, scenario_c=0.15),
        "4": StateWeights(scenario_a=0.60, scenario_b=0.30, scenario_c=0.10),
        "5": StateWeights(scenario_a=0.50, scenario_b=0.30, scenario_c=0.20),
        "3p": StateWeights(scenario_a=0.45, scenario_b=0.30, scenario_c=0.25),
    }

    def __init__(self, overrides: dict | None = None):
        self.weights = dict(self.DEFAULT_WEIGHTS)
        if overrides:
            for state, values in overrides.items():
                self.weights[self._state_key(state)] = StateWeights(
                    scenario_a=values.get("A", values.get("scenario_a", 0.60)),
                    scenario_b=values.get("B", values.get("scenario_b", 0.30)),
                    scenario_c=values.get("C", values.get("scenario_c", 0.10)),
                )

    def get_weights(self, state) -> dict[str, float]:
        state_key = self._state_key(state)
        weights = self.weights.get(state_key, StateWeights())
        return {"A": weights.scenario_a, "B": weights.scenario_b, "C": weights.scenario_c}

    @staticmethod
    def _state_key(state) -> str:
        return str(state).replace("'", "p")
