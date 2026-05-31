import pytest
from src.analysis.scenario import ScenarioEngine
from src.engine.state_machine import StateMachine


class TestScenarioEngine:
    def test_state4_generates_three_scenarios(self, uptrend_daily):
        ts = StateMachine.classify(uptrend_daily)
        scenarios = ScenarioEngine.generate(ts)
        assert len(scenarios) >= 2

    def test_state1_generates_scenarios(self, downtrend_daily):
        ts = StateMachine.classify(downtrend_daily)
        scenarios = ScenarioEngine.generate(ts)
        assert len(scenarios) >= 1
