"""推演权重管理器 — JSON文件驱动，支持自动调整和衰减机制。

Phase B: 为ScenarioEngine提供外部weights参数
Phase D: 反思引擎通过此类自动调整权重
"""
from dataclasses import dataclass, field, asdict
from typing import Dict, Optional
import json
import os
from datetime import datetime


@dataclass
class StateWeights:
    """单个状态的场景权重分配。"""
    scenario_a: float = 0.60
    scenario_b: float = 0.30
    scenario_c: float = 0.10
    last_adjusted: str = ""
    reason: str = ""


class ProjectionWeights:
    """推演权重管理器。"""

    DEFAULT_WEIGHTS: Dict[str, StateWeights] = {
        "1": StateWeights(scenario_a=0.70, scenario_b=0.30, scenario_c=0.0),
        "2": StateWeights(scenario_a=0.50, scenario_b=0.35, scenario_c=0.15),
        "3": StateWeights(scenario_a=0.50, scenario_b=0.35, scenario_c=0.15),
        "4": StateWeights(scenario_a=0.60, scenario_b=0.30, scenario_c=0.10),
        "5": StateWeights(scenario_a=0.50, scenario_b=0.30, scenario_c=0.20),
        "3p": StateWeights(scenario_a=0.45, scenario_b=0.30, scenario_c=0.25),
    }

    def __init__(self, config_path: str = "dashboard/data/projection_weights.json"):
        self.config_path = config_path
        self.weights: Dict[str, StateWeights] = {}
        self._load()

    def _load(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path) as f:
                    data = json.load(f)
                for state_key, wdata in data.get("weights", {}).items():
                    self.weights[state_key] = StateWeights(**wdata)
            except (json.JSONDecodeError, TypeError):
                self.weights = dict(self.DEFAULT_WEIGHTS)
        else:
            self.weights = dict(self.DEFAULT_WEIGHTS)

    def save(self):
        output = {
            "meta": {"version": "1.0", "updated_at": datetime.now().isoformat(),
                     "description": "推演场景权重 — 由反思引擎自动调整"},
            "weights": {k: asdict(v) for k, v in self.weights.items()},
        }
        os.makedirs(os.path.dirname(self.config_path) if os.path.dirname(self.config_path) else ".", exist_ok=True)
        with open(self.config_path, "w") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

    def get_weights(self, state) -> Dict[str, float]:
        """获取指定状态的场景权重 {A, B, C}。"""
        state_key = str(state).replace("'", "p")
        w = self.weights.get(state_key, self.DEFAULT_WEIGHTS.get(state_key))
        if w is None:
            w = StateWeights()
        return {"A": w.scenario_a, "B": w.scenario_b, "C": w.scenario_c}

    def get_all_weights(self) -> Dict[str, Dict[str, float]]:
        return {k: {"A": v.scenario_a, "B": v.scenario_b, "C": v.scenario_c}
                for k, v in self.weights.items()}

    def adjust(self, state, scenario: str, delta: float, reason: str = ""):
        """调整权重，delta限制±0.1，调整后自动归一化。"""
        state_key = str(state).replace("'", "p")
        if state_key not in self.weights:
            self.weights[state_key] = StateWeights()

        w = self.weights[state_key]
        delta = max(-0.10, min(0.10, delta))

        if scenario == "A":
            w.scenario_a = max(0.05, min(0.95, w.scenario_a + delta))
        elif scenario == "B":
            w.scenario_b = max(0.05, min(0.95, w.scenario_b + delta))
        elif scenario == "C":
            w.scenario_c = max(0.02, min(0.80, w.scenario_c + delta))

        self._normalize(state_key, scenario)
        w.last_adjusted = datetime.now().strftime("%Y-%m-%d")
        w.reason = reason

    def _normalize(self, state_key: str, locked_scenario: str):
        w = self.weights[state_key]
        total = w.scenario_a + w.scenario_b + w.scenario_c
        if abs(total - 1.0) < 0.001:
            return
        if locked_scenario == "A":
            scale = (1.0 - w.scenario_a) / (w.scenario_b + w.scenario_c) if (w.scenario_b + w.scenario_c) > 0 else 1.0
            w.scenario_b *= scale
            w.scenario_c *= scale
        elif locked_scenario == "B":
            scale = (1.0 - w.scenario_b) / (w.scenario_a + w.scenario_c) if (w.scenario_a + w.scenario_c) > 0 else 1.0
            w.scenario_a *= scale
            w.scenario_c *= scale
        elif locked_scenario == "C":
            scale = (1.0 - w.scenario_c) / (w.scenario_a + w.scenario_b) if (w.scenario_a + w.scenario_b) > 0 else 1.0
            w.scenario_a *= scale
            w.scenario_b *= scale
        else:
            if total > 0:
                w.scenario_a /= total
                w.scenario_b /= total
                w.scenario_c /= total
