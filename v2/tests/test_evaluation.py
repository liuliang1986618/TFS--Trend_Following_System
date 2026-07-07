from v2.engine.signal import StrategySignal
from v2.evaluation import Evaluation
from v2.evaluation.projection import ProjectionEngine, ProjectionScenario
from v2.evaluation.trade_plan import TradePlanBuilder
from v2.evaluation.validation import ProjectionValidation
from v2.evaluation.weights import ProjectionWeights


def _signal(state=4, code="300308", date="2026-06-26"):
    return StrategySignal(
        code=code,
        name=code,
        dtype="stock",
        market_date=date,
        relation_version="2026-W27",
        state=state,
        state_label=str(state),
        score=70.0,
        confidence=0.7,
        risk_flags=["volume_divergence"],
    )


def test_projection_engine_reuses_legacy_state_scenarios_without_action_text():
    scenarios = ProjectionEngine().generate(_signal(state=4))

    assert [scenario.label for scenario in scenarios] == ["A", "B", "C"]
    assert [scenario.expected_next_state for scenario in scenarios] == ["4", "5", "3p"]
    assert [scenario.weight for scenario in scenarios] == [0.60, 0.30, 0.10]
    assert scenarios[0].probability_label == "大概率"
    assert "MA20" in scenarios[0].conditions[0]
    assert scenarios[0].action_hint is None
    assert scenarios[0].risk_flags == ["volume_divergence"]


def test_projection_weights_returns_legacy_defaults_by_state():
    weights = ProjectionWeights()

    assert weights.get_weights(1) == {"A": 0.70, "B": 0.30, "C": 0.0}
    assert weights.get_weights(4) == {"A": 0.60, "B": 0.30, "C": 0.10}
    assert weights.get_weights("3'") == {"A": 0.45, "B": 0.30, "C": 0.25}


def test_projection_validation_summarizes_exact_directional_and_error_patterns():
    records = [
        {"date": "2026-06-25", "code": "BK1", "dtype": "sector", "state": "4"},
        {"date": "2026-06-26", "code": "BK1", "dtype": "sector", "state": "5"},
        {"date": "2026-06-25", "code": "BK2", "dtype": "sector", "state": "4"},
        {"date": "2026-06-26", "code": "BK2", "dtype": "sector", "state": "1"},
    ]

    report = ProjectionValidation().validate_records(records)

    assert report.total == 6
    assert report.exact_accuracy == 1 / 6
    assert report.directional_accuracy == 2 / 6
    assert report.by_state["4"].total == 6
    assert report.by_scenario["B"].correct == 1
    assert {item["pattern"] for item in report.top_errors} >= {"4->3p(actual=1)"}


def test_evaluation_generate_report_consumes_strategy_signals():
    report = Evaluation().generate_report([_signal(state=4), _signal(state=5, code="512760")])

    assert report.scope == "signals"
    assert report.total == 2
    assert report.projections["300308"][0].label == "A"
    assert report.projections["512760"][0].expected_next_state == "4"


def test_trade_plan_builder_turns_projection_into_structured_trade_guidance():
    signal = _signal(state=4, code="300308")
    scenarios = ProjectionEngine().generate(signal)

    plan = TradePlanBuilder().build(signal, scenarios)

    assert plan.code == "300308"
    assert plan.dtype == "stock"
    assert plan.current_state == "4"
    assert plan.base_position_pct == 0.08
    assert plan.target_position_pct == 0.08
    assert {trigger.action_type for trigger in plan.triggers} == {"hold", "add", "reduce"}
    assert all(trigger.trigger_conditions for trigger in plan.triggers)
    assert all(trigger.target_position_pct is not None for trigger in plan.triggers)
    assert all("scenario_weight" in trigger.evidence for trigger in plan.triggers)
    assert plan.risk_controls == ["volume_divergence"]


def test_evaluation_report_includes_trade_plans_for_display_consumption():
    report = Evaluation().generate_report([_signal(state=4), _signal(state=5, code="512760", date="2026-06-26")])

    assert report.trade_plans["300308"].triggers[0].scenario_label == "A"
    assert report.trade_plans["512760"].target_position_pct == 0.10


def test_evaluation_report_builds_display_data_pool_for_reusable_action_card_fields():
    signal = _signal(state=4)
    signal.trend_context = {
        "direction": "上升趋势",
        "days_running": 22,
        "total_return_pct": 12.6,
        "key_levels": {"support": 118.2, "resistance": 136.5, "stop_loss": 112.0, "current": 122.0},
    }
    signal.indicators = {"pct_today": -0.2, "vol_ratio": 0.8, "bb": {"upper": 136.5, "lower": 118.2}, "today_close": 122.0}

    report = Evaluation().generate_report([signal])
    data = report.display_data_pool["symbols"]["300308"]

    assert data["trend_context"]["days_running"] == 22
    assert data["today_position"]["label"] == "横盘休整"
    assert "上升趋势" in data["strategy_summary"]
    assert data["projection"]["scenarios"][0]["label"] == "A"
    assert data["buy_sell_zone"]["buy_zone"]["low"] == 118.2
    assert data["buy_sell_zone"]["sell_zone"]["low"] <= data["buy_sell_zone"]["sell_zone"]["high"]
    assert data["key_levels"][0]["label"] == "支撑位"
    assert data["watch_scenarios"][0]["level"] == "A"
    assert data["position_plan"][0]["target_position_pct"] == 0.08
