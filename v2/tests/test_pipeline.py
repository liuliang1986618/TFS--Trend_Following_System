import json
import subprocess
import sys
from pathlib import Path

from v2.engine.signal import StrategySignal
from v2.evaluation.metrics import EvaluationReport
from v2.pipeline.cli import build_parser, main
from v2.pipeline.manifest import RunManifest
from v2.pipeline.runner import PipelineRunner
from v2.pipeline.stages import StageStatus


class FakeDataLayer:
    def __init__(self, health_status="complete", allowed=None):
        self.health_status = health_status
        self.allowed = allowed or {
            "stock_recommendation": health_status == "complete",
            "etf_recommendation": health_status == "complete",
        }

    def check_market_health(self, date=None):
        return {
            "status": self.health_status,
            "date": date,
            "allowed": self.allowed,
            "issues": [] if self.health_status == "complete" else ["stock health is warning"],
        }

    def check_relation_health(self, relation_version=None):
        return {"status": "complete", "version": "2026-W27", "issues": []}


class FakeHistoricalHealthDataLayer(FakeDataLayer):
    def check_market_health(self, date=None):
        return {
            "status": "warning",
            "date": date,
            "checks": {
                "stock": {"status": "warning", "latest_date_ok": False, "count_ok": True, "actual_count": 5506, "min_count": 4300},
                "etf": {"status": "warning", "latest_date_ok": False, "count_ok": True, "actual_count": 1521, "min_count": 600},
                "sector": {"status": "warning", "latest_date_ok": False, "count_ok": False},
                "theme": {"status": "warning", "latest_date_ok": False, "count_ok": False},
            },
            "allowed": {
                "stock_recommendation": False,
                "etf_recommendation": False,
                "sector_confirmation": False,
                "theme_confirmation": False,
            },
            "issues": ["stock health is warning", "etf health is warning", "sector health is warning", "theme health is warning"],
        }


class FakeEngine:
    def scan_stock_full(self, date=None, max_candidates=50):
        return [_signal("300308", "stock", date)]

    def scan_etf_direct(self, date=None, max_candidates=50):
        return [_signal("512760", "etf", date)]


class FakeEvaluation:
    def generate_report(self, signals):
        return {"scope": "signals", "total": len(signals)}


class FakeEvaluationReportObject:
    def generate_report(self, signals):
        return EvaluationReport(scope="signals", total=len(signals))


def _signal(code, dtype, date):
    return StrategySignal(
        code=code,
        name=code,
        dtype=dtype,
        market_date=date or "2026-06-26",
        relation_version="2026-W27",
        state=4,
        state_label="上涨趋势",
        score=70.0,
        confidence=0.7,
    )


def test_pipeline_runner_writes_manifest_for_data_engine_eval_flow(tmp_path):
    runner = PipelineRunner(
        data_layer=FakeDataLayer(),
        engine=FakeEngine(),
        evaluation=FakeEvaluation(),
        output_dir=tmp_path,
    )

    manifest = runner.run(date="2026-06-26", mode="daily", render_display=False, max_candidates=3)

    assert isinstance(manifest, RunManifest)
    assert manifest.status == "success"
    assert [stage.name for stage in manifest.stages] == ["data_health", "engine", "evaluation"]
    assert all(stage.status == StageStatus.SUCCESS for stage in manifest.stages)
    assert manifest.artifacts["manifest_path"].endswith(".json")
    assert Path(manifest.artifacts["manifest_path"]).exists()
    assert manifest.artifacts["stock_signal_count"] == 1
    assert manifest.artifacts["etf_signal_count"] == 1


def test_pipeline_runner_stops_on_health_gate_failure_without_engine_outputs(tmp_path):
    runner = PipelineRunner(
        data_layer=FakeDataLayer(
            health_status="warning",
            allowed={"stock_recommendation": False, "etf_recommendation": False},
        ),
        engine=FakeEngine(),
        evaluation=FakeEvaluation(),
        output_dir=tmp_path,
    )

    manifest = runner.run(date="2026-06-26", mode="daily")

    assert manifest.status == "failed"
    assert [stage.name for stage in manifest.stages] == ["data_health"]
    assert manifest.stages[0].status == StageStatus.FAILED
    assert "stock_signal_count" not in manifest.artifacts


def test_pipeline_runner_allows_warning_when_required_recommendation_data_is_usable(tmp_path):
    runner = PipelineRunner(
        data_layer=FakeDataLayer(
            health_status="warning",
            allowed={"stock_recommendation": True, "etf_recommendation": True},
        ),
        engine=FakeEngine(),
        evaluation=FakeEvaluation(),
        output_dir=tmp_path,
    )

    manifest = runner.run(date="2026-06-26", mode="daily")

    assert manifest.status == "success"
    assert manifest.stages[0].status == StageStatus.WARNING
    assert manifest.artifacts["stock_signal_count"] == 1


def test_pipeline_runner_allows_historical_replay_when_stock_and_etf_counts_are_complete(tmp_path):
    runner = PipelineRunner(
        data_layer=FakeHistoricalHealthDataLayer(),
        engine=FakeEngine(),
        evaluation=FakeEvaluation(),
        output_dir=tmp_path,
    )

    manifest = runner.run(date="2026-06-22", mode="daily", render_display=True)

    assert manifest.status == "success"
    assert manifest.stages[0].status == StageStatus.WARNING
    assert manifest.artifacts["stock_signal_count"] == 1
    assert Path(manifest.artifacts["index_html_path"]).exists()


def test_pipeline_runner_render_display_writes_payload_and_html_artifacts_to_run_output(tmp_path):
    runner = PipelineRunner(
        data_layer=FakeDataLayer(),
        engine=FakeEngine(),
        evaluation=FakeEvaluation(),
        output_dir=tmp_path,
    )

    manifest = runner.run(date="2026-06-26", mode="daily", render_display=True, max_candidates=2)

    assert manifest.status == "success"
    assert [stage.name for stage in manifest.stages] == ["data_health", "engine", "evaluation", "display"]
    assert manifest.stages[-1].status == StageStatus.SUCCESS
    display_payload_path = Path(manifest.artifacts["display_payload_path"])
    nav_payload_path = Path(manifest.artifacts["nav_payload_path"])
    daily_html_path = Path(manifest.artifacts["daily_html_path"])
    index_html_path = Path(manifest.artifacts["index_html_path"])
    assert display_payload_path.exists()
    assert nav_payload_path.exists()
    assert daily_html_path.exists()
    assert index_html_path.exists()
    assert str(daily_html_path).startswith(str(tmp_path))
    assert "dashboard/trend_dashboard" not in str(daily_html_path)
    payload = json.loads(display_payload_path.read_text(encoding="utf-8"))
    assert payload["meta"]["date"] == "2026-06-26"
    assert "data-card-type=\"date_nav_card\"" in index_html_path.read_text(encoding="utf-8")


def test_pipeline_runner_accepts_evaluation_report_dataclass_for_display_stage(tmp_path):
    runner = PipelineRunner(
        data_layer=FakeDataLayer(),
        engine=FakeEngine(),
        evaluation=FakeEvaluationReportObject(),
        output_dir=tmp_path,
    )

    manifest = runner.run(date="2026-06-26", mode="daily", render_display=True, max_candidates=2)

    assert manifest.status == "success"
    payload = json.loads(Path(manifest.artifacts["display_payload_path"]).read_text(encoding="utf-8"))
    assert payload["evaluation"]["total"] == 2


def test_cli_parser_accepts_daily_no_render_command():
    parser = build_parser()

    args = parser.parse_args(["daily", "--date", "2026-06-26", "--no-render", "--max-candidates", "2"])

    assert args.command == "daily"
    assert args.date == "2026-06-26"
    assert args.render_display is False
    assert args.max_candidates == 2


def test_cli_main_returns_zero_for_help():
    assert main(["help"]) == 0


def test_cli_module_invocation_executes_main():
    result = subprocess.run(
        [sys.executable, "-m", "v2.pipeline.cli", "help"],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "run the daily v2 pipeline" in result.stdout
