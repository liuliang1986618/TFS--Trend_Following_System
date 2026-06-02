import pytest
from src.analysis.scenario import ScenarioEngine, Scenario
from src.engine.state_machine import StateMachine


class TestScenarioEngine:
    def test_state4_generates_three_scenarios(self, uptrend_daily):
        ts = StateMachine.classify(uptrend_daily)
        scenarios = ScenarioEngine.generate(ts)
        assert len(scenarios) >= 2
        for s in scenarios:
            assert hasattr(s, 'weight')
            assert 0.0 <= s.weight <= 1.0

    def test_state1_generates_scenarios(self, downtrend_daily):
        ts = StateMachine.classify(downtrend_daily)
        scenarios = ScenarioEngine.generate(ts)
        assert len(scenarios) >= 1

    def test_generate_with_weights_param(self, uptrend_daily):
        ts = StateMachine.classify(uptrend_daily)
        custom_weights = {"A": 0.70, "B": 0.20, "C": 0.10}
        scenarios = ScenarioEngine.generate(ts, weights=custom_weights)
        assert len(scenarios) >= 2
        assert scenarios[0].weight == 0.70

    def test_generate_without_weights_uses_default(self, uptrend_daily):
        ts = StateMachine.classify(uptrend_daily)
        scenarios = ScenarioEngine.generate(ts)
        assert scenarios[0].weight > 0

    def test_all_states_have_weight_field(self, uptrend_daily):
        ts = StateMachine.classify(uptrend_daily)
        for ws in [None, {"A": 0.50, "B": 0.30, "C": 0.20}]:
            scenarios = ScenarioEngine.generate(ts, weights=ws)
            for s in scenarios:
                assert isinstance(s.weight, float)


class TestScenarioWithWeights:
    def test_weight_preserved_in_scenarios(self, uptrend_daily):
        ts = StateMachine.classify(uptrend_daily)
        weights = {"A": 0.80, "B": 0.15, "C": 0.05}
        scenarios = ScenarioEngine.generate(ts, weights=weights)
        total = sum(s.weight for s in scenarios)
        assert abs(total - 1.0) < 0.1
