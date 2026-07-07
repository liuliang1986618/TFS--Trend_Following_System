import json
from pathlib import Path

from v2.display.builder import DisplayPayloadBuilder
from v2.display.nav import NavPayloadBuilder
from v2.display.renderer import DisplayRenderer
from v2.display.schema import validate_display_payload, validate_nav_payload
from v2.engine.signal import StrategySignal


class FakeRelationDataLayer:
    def get_relation_names(self):
        return {
            "sectors": {"BK0448": "通信设备"},
            "themes": {"BK0999": "AI算力"},
        }

    def get_stock_profile(self, code, relation_version=None):
        if code == "603065":
            return {"name": "宿迁联盛", "sectors": ["BK0448"], "themes": ["BK0999"]}
        return {}

    def get_etf_names(self):
        return {"588710": "科创创业人工智能ETF"}


def _signal(code="300308", name="中际旭创", dtype="stock", score=86.0, relations=None):
    return StrategySignal(
        code=code,
        name=name,
        dtype=dtype,
        market_date="2026-06-26",
        relation_version="2026-W27",
        state=4,
        state_label="上涨趋势",
        score=score,
        confidence=0.82,
        action_hint="观察回踩后的延续机会",
        position_hint={"suggested_ratio": 0.2, "max_ratio": 0.3},
        relations=relations or {"sector": "通信设备", "theme": "AI算力"},
        risk_flags=["短线涨幅偏大"],
    )


def test_display_payload_builder_outputs_regions_and_card_templates_without_html():
    payload = DisplayPayloadBuilder().build(
        date="2026-06-26",
        run_id="2026-06-26_171822",
        signals=[_signal(), _signal(code="512760", name="半导体设备ETF", dtype="etf", score=78.0)],
        evaluation_report={"total": 2, "exact_accuracy": 0.5},
        health={"market": {"status": "warning"}, "relation": {"status": "complete"}},
    )

    validated = validate_display_payload(payload)

    assert validated["meta"]["date"] == "2026-06-26"
    assert [region["id"] for region in validated["regions"]] == ["overview", "strong_tracking", "steady_recommend", "sector_focus", "signal_groups", "evaluation"]
    assert {card["type"] for card in validated["cards"]} >= {"metric_card", "action_card", "signal_card", "sector_focus_card"}
    assert all("<" not in str(card) and ">" not in str(card) for card in validated["cards"])
    assert validated["cards_by_id"]["signal_stock_300308"]["body"]["relations"]["theme"] == "AI算力"


def _trade_plan():
    return {
        "code": "300308",
        "name": "中际旭创",
        "dtype": "stock",
        "market_date": "2026-06-26",
        "current_state": "4",
        "base_position_pct": 0.08,
        "target_position_pct": 0.08,
        "triggers": [
            {
                "scenario_label": "A",
                "action_type": "hold",
                "expected_next_state": "4",
                "target_position_pct": 0.08,
                "trigger_conditions": ["继续沿MA20上方运行", "无异常信号"],
                "risk_controls": ["短线涨幅偏大"],
                "evidence": {"scenario_weight": 0.6, "frequency": 0.794, "support": 7289},
            },
            {
                "scenario_label": "B",
                "action_type": "add",
                "expected_next_state": "5",
                "target_position_pct": 0.10,
                "trigger_conditions": ["缩量回调", "不破前低"],
                "risk_controls": ["短线涨幅偏大"],
                "evidence": {"scenario_weight": 0.3},
            },
        ],
        "risk_controls": ["短线涨幅偏大"],
        "evidence": {"source": "legacy_state_transition_and_portfolio_target_pct"},
    }


def test_display_payload_builder_attaches_trade_plan_to_matching_action_card():
    payload = DisplayPayloadBuilder().build(
        date="2026-06-26",
        run_id="2026-06-26_171822",
        signals=[_signal(), _signal(code="512760", name="半导体设备ETF", dtype="etf")],
        evaluation_report={"total": 2, "trade_plans": {"300308": _trade_plan()}},
        health={"market": {"status": "complete"}, "relation": {"status": "complete"}},
    )

    action_card = validate_display_payload(payload)["cards_by_id"]["action_stock_300308"]

    assert action_card["body"]["trade_plan"]["target_position_pct"] == 0.08
    assert action_card["body"]["trade_plan"]["triggers"][1]["action_type"] == "add"
    assert action_card["body"]["trade_plan"]["triggers"][1]["trigger_conditions"] == ["缩量回调", "不破前低"]


def _decision_pool():
    return {
        "symbols": {
            "300308": {
                "trend_context": {"direction": "上升趋势", "days_running": 22, "total_return_pct": 12.6},
                "today_position": {"label": "横盘休整", "narrative": "缩量整理，趋势结构未破坏"},
                "strategy_summary": "上升趋势完好，顺势持有，回调到支撑位再加仓。",
                "projection": {
                    "sample_count": 7289,
                    "scenarios": [
                        {"label": "A", "probability": 0.60, "title": "继续上涨", "range": "+0.8%~+2.2%"},
                        {"label": "B", "probability": 0.30, "title": "缩量回调", "range": "-1.5%~0%"},
                    ],
                },
                "buy_sell_zone": {
                    "buy_zone": {"low": 118.2, "high": 121.4, "logic": "回踩 MA20 附近"},
                    "sell_zone": {"low": 132.0, "high": 136.5, "logic": "接近布林上轨"},
                },
                "key_levels": [{"label": "支撑位", "price": 118.2, "source": "MA20"}],
                "watch_scenarios": [{"level": "A", "action": "add", "position_pct": 0.10, "signals": ["缩量回调", "不破前低"]}],
                "position_plan": [{"step": "首仓", "target_position_pct": 0.08, "condition": "站稳 MA20"}],
            }
        }
    }


def test_display_payload_builder_creates_reference_style_regions_and_sector_focus_card():
    payload = DisplayPayloadBuilder().build(
        date="2026-06-26",
        run_id="2026-06-26_171822",
        signals=[
            _signal(code="300308", score=92.0),
            _signal(code="688662", name="富信科技", score=86.0, relations={"sector": "电子", "theme": "5G概念"}),
            _signal(code="512760", name="半导体设备ETF", dtype="etf", score=78.0),
        ],
        evaluation_report={"total": 3, "display_data_pool": _decision_pool(), "trade_plans": {"300308": _trade_plan()}},
        health={"market": {"status": "complete"}, "relation": {"status": "complete"}},
    )
    validated = validate_display_payload(payload)
    sector_card = validated["cards_by_id"]["sector_focus_0"]

    assert validated["regions"][1]["id"] == "strong_tracking"
    assert validated["regions"][1]["title"] == "强势追踪"
    assert validated["regions"][2]["id"] == "steady_recommend"
    assert validated["regions"][2]["title"] == "稳健推荐"
    assert validated["regions"][3]["id"] == "sector_focus"
    assert sector_card["type"] == "sector_focus_card"
    assert sector_card["title"] == "通信设备"
    assert sector_card["body"]["leaders"][0]["name"] == "中际旭创"
    assert sector_card["body"]["leaders"][0]["reason"] == "上涨趋势 / AI算力"
    assert sector_card["body"]["status_strip"] == ["4", "4"]
    assert sector_card["body"]["key_metrics"][:2] == [{"label": "板块强度", "value": 85.0}, {"label": "趋势标的", "value": 2}]
    assert sector_card["body"]["projection"][0]["probability"] == 0.82


def test_display_payload_builder_exposes_shared_data_pool_and_action_card_consumes_it():
    payload = DisplayPayloadBuilder().build(
        date="2026-06-26",
        run_id="2026-06-26_171822",
        signals=[_signal()],
        evaluation_report={"total": 1, "display_data_pool": _decision_pool(), "trade_plans": {"300308": _trade_plan()}},
        health={"market": {"status": "complete"}, "relation": {"status": "complete"}},
    )

    action_card = validate_display_payload(payload)["cards_by_id"]["action_stock_300308"]

    assert payload["data_pool"]["symbols"]["300308"]["trend_context"]["days_running"] == 22
    assert action_card["body"]["decision_data"]["today_position"]["label"] == "横盘休整"
    assert action_card["body"]["decision_data"]["projection"]["scenarios"][0]["title"] == "继续上涨"
    assert action_card["body"]["decision_data"]["buy_sell_zone"]["buy_zone"]["low"] == 118.2
    assert action_card["body"]["decision_data"]["key_levels"][0]["label"] == "支撑位"
    assert action_card["body"]["decision_data"]["watch_scenarios"][0]["action"] == "add"
    assert action_card["body"]["decision_data"]["position_plan"][0]["condition"] == "站稳 MA20"


def test_display_renderer_renders_trade_plan_inside_action_card_template(tmp_path):
    payload = DisplayPayloadBuilder().build(
        date="2026-06-26",
        run_id="2026-06-26_171822",
        signals=[_signal()],
        evaluation_report={"total": 1, "display_data_pool": _decision_pool(), "trade_plans": {"300308": _trade_plan()}},
        health={"market": {"status": "complete"}, "relation": {"status": "complete"}},
    )
    payload_path = tmp_path / "display_payload.json"
    output_path = tmp_path / "trend_dashboard_2026-06-26.html"
    payload_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    result = DisplayRenderer().render_daily(str(payload_path), str(output_path))
    html = Path(result).read_text(encoding="utf-8")

    assert "data-card-type=\"action_card\"" in html
    assert "data-template=\"action-card-template\"" in html
    assert "目标仓位 8%" in html
    assert "action-card__section--plan" in html
    assert "action-card__plan-lead" in html
    assert "A 持有" in html
    assert "B 加仓" in html
    assert "缩量回调" in html
    assert "不破前低" in html
    assert "A 加仓 10%" in html
    assert "趋势大背景" in html
    assert "明日行情推演" in html
    assert "明日最佳买卖区间" in html
    assert "关键价位" in html
    assert "盯盘场景" in html
    assert "仓位管理" in html
    assert "action-card__hero" in html
    assert "action-card__score" in html
    assert "action-card__grid" in html
    assert "action-card__section--projection" in html
    assert "action-card__levels" in html
    assert "核心指标" in html
    assert "明日推演" in html
    assert "龙头线索" in html
    assert (output_path.parent / "assets" / "display.css").exists()


def test_display_payload_validation_rejects_missing_required_card_references():
    payload = {
        "meta": {"date": "2026-06-26", "run_id": "run1"},
        "regions": [{"id": "overview", "title": "概览", "layout": "grid", "card_ids": ["missing_card"]}],
        "cards": [],
    }

    try:
        validate_display_payload(payload)
    except ValueError as exc:
        assert "missing_card" in str(exc)
    else:
        raise AssertionError("missing card reference should fail validation")


def test_nav_payload_builder_creates_three_line_date_nav_cards_from_display_payloads():
    display_payload = DisplayPayloadBuilder().build(
        date="2026-06-26",
        run_id="2026-06-26_171822",
        signals=[_signal(), _signal(code="512760", name="半导体设备ETF", dtype="etf")],
        evaluation_report={"total": 2},
        health={"market": {"status": "complete"}, "relation": {"status": "complete"}},
    )

    nav_payload = NavPayloadBuilder().build([display_payload], current_date="2026-06-26")
    validated = validate_nav_payload(nav_payload)

    card = validated["items"][0]
    assert card["type"] == "date_nav_card"
    assert card["line_time"]["date"] == "2026-06-26"
    assert card["line_time"]["weekday"] == "周五"
    assert card["line_market"]["label"] == "complete"
    assert card["line_leaders"]["sector"] == "通信设备"
    assert card["line_leaders"]["theme"] == "AI算力"
    assert card["line_leaders"]["stock"] == "中际旭创"
    assert card["line_leaders"]["etf"] == "半导体设备ETF"


def test_display_payload_builder_resolves_relation_codes_for_date_nav_leaders():
    display_payload = DisplayPayloadBuilder(data_layer=FakeRelationDataLayer()).build(
        date="2026-06-26",
        run_id="2026-06-26_171822",
        signals=[
            _signal(code="603065", name="603065", relations={"sectors": ["BK0448"], "themes": ["BK0999"]}),
            _signal(code="588710", name="588710", dtype="etf"),
        ],
        evaluation_report={"total": 2},
        health={"market": {"status": "complete"}, "relation": {"status": "complete"}},
    )
    nav_payload = NavPayloadBuilder().build([display_payload], current_date="2026-06-26")
    card = nav_payload["items"][0]

    assert display_payload["leader_summary"]["sector"] == "通信设备"
    assert display_payload["leader_summary"]["theme"] == "AI算力"
    assert card["line_leaders"]["sector"] == "通信设备"
    assert card["line_leaders"]["theme"] == "AI算力"
    assert card["line_leaders"]["stock"] == "宿迁联盛"
    assert card["line_leaders"]["etf"] == "科创创业人工智能ETF"
    assert "BK0448" not in str(card["line_leaders"])
    assert "BK0999" not in str(card["line_leaders"])
    assert "603065" not in str(card["line_leaders"])
    assert "588710" not in str(card["line_leaders"])


def test_display_renderer_uses_card_templates_for_daily_html(tmp_path):
    payload = DisplayPayloadBuilder().build(
        date="2026-06-26",
        run_id="2026-06-26_171822",
        signals=[_signal()],
        evaluation_report={"total": 1},
        health={"market": {"status": "complete"}, "relation": {"status": "complete"}},
    )
    payload_path = tmp_path / "display_payload.json"
    output_path = tmp_path / "trend_dashboard_2026-06-26.html"
    payload_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    result = DisplayRenderer().render_daily(str(payload_path), str(output_path))
    html = Path(result).read_text(encoding="utf-8")

    assert result == str(output_path)
    assert "data-region=\"overview\"" in html
    assert "data-card-type=\"signal_card\"" in html
    assert "display-region__header" in html
    assert "display-region__title" in html
    assert "display-region__count" in html
    assert "数据完整性与候选池概览" in html
    assert "中际旭创" in html
    assert "观察回踩后的延续机会" in html
    assert "build_final" not in html
    assert "render_action_panel" not in html


def test_display_renderer_uses_date_nav_card_template_for_index_html(tmp_path):
    payload = DisplayPayloadBuilder().build(
        date="2026-06-26",
        run_id="2026-06-26_171822",
        signals=[_signal(), _signal(code="512760", name="半导体设备ETF", dtype="etf")],
        evaluation_report={"total": 2},
        health={"market": {"status": "complete"}, "relation": {"status": "complete"}},
    )
    nav_payload = NavPayloadBuilder().build([payload], current_date="2026-06-26")
    nav_path = tmp_path / "nav_payload.json"
    output_path = tmp_path / "index.html"
    nav_path.write_text(json.dumps(nav_payload, ensure_ascii=False), encoding="utf-8")

    result = DisplayRenderer().render_index(str(nav_path), str(output_path))
    html = Path(result).read_text(encoding="utf-8")

    assert result == str(output_path)
    assert "data-card-type=\"date_nav_card\"" in html
    assert "data-template=\"date-nav-card-template\"" in html
    assert "date-nav-card__meta" in html
    assert "date-nav-card__tag" in html
    assert "2026-06-26" in html
    assert "周五" in html
    assert "通信设备" in html
    assert "AI算力" in html
    assert "中际旭创" in html
    assert "<iframe" in html


def test_card_template_directory_contains_core_card_templates():
    cards_dir = Path("v2/display/templates/cards")

    assert (cards_dir / "date_nav_card.html").exists()
    assert (cards_dir / "metric_card.html").exists()
    assert (cards_dir / "signal_card.html").exists()
    assert (cards_dir / "action_card.html").exists()
    assert (cards_dir / "sector_focus_card.html").exists()
    assert (cards_dir / "empty_card.html").exists()


def test_display_renderer_bundles_weekly_index_with_daily_html_files(tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    daily_a = source_dir / "trend_dashboard_2026-06-26.html"
    daily_b = source_dir / "trend_dashboard_2026-06-25.html"
    daily_a.write_text("<html>2026-06-26</html>", encoding="utf-8")
    daily_b.write_text("<html>2026-06-25</html>", encoding="utf-8")
    nav_payload = NavPayloadBuilder().build(
        [
            DisplayPayloadBuilder().build(date="2026-06-26", run_id="run1", signals=[_signal()], health={"market": {"status": "complete"}}),
            DisplayPayloadBuilder().build(date="2026-06-25", run_id="run2", signals=[_signal()], health={"market": {"status": "complete"}}),
        ],
        current_date="2026-06-26",
    )
    nav_path = tmp_path / "nav_payload.json"
    nav_path.write_text(json.dumps(nav_payload, ensure_ascii=False), encoding="utf-8")
    output_dir = tmp_path / "weekly"

    index_path = DisplayRenderer().render_index_bundle(
        nav_payload_path=str(nav_path),
        daily_html_paths=[str(daily_a), str(daily_b)],
        output_dir=str(output_dir),
    )

    assert Path(index_path).exists()
    assert (output_dir / "trend_dashboard_2026-06-26.html").exists()
    assert (output_dir / "trend_dashboard_2026-06-25.html").exists()
    assert 'src="trend_dashboard_2026-06-26.html"' in Path(index_path).read_text(encoding="utf-8")
