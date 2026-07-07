"""Fixed-date regression smoke tests that do not depend on generated artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from v2.engine.signal import StrategySignal
from v2.evaluation.metrics import EvaluationReport
from v2.pipeline.runner import PipelineRunner
from v2.pipeline.stages import StageStatus


REGRESSION_DATES = ("2026-06-12", "2026-06-22")


class FixedDateDataLayer:
    def check_market_health(self, date=None):
        status = "warning" if date == "2026-06-22" else "complete"
        return {
            "status": status,
            "date": date,
            "checks": {
                "stock": {"count_ok": True, "actual_count": 5506, "min_count": 4300},
                "etf": {"count_ok": True, "actual_count": 1521, "min_count": 600},
            },
            "allowed": {"stock_recommendation": status == "complete", "etf_recommendation": status == "complete"},
            "issues": [] if status == "complete" else ["historical date is behind latest market date"],
        }

    def check_relation_health(self, relation_version=None):
        return {"status": "complete", "version": relation_version or "2026-W27", "issues": []}

    def get_relation_names(self):
        return {"sectors": {"BK0448": "通信设备"}, "themes": {"BK0999": "AI算力"}}

    def get_etf_names(self):
        return {"512760": "半导体设备ETF"}


class FixedDateEngine:
    def scan_stock_full(self, date=None, max_candidates=50):
        return [_signal("300308", "中际旭创", "stock", date, 88.0)]

    def scan_etf_direct(self, date=None, max_candidates=50):
        return [_signal("512760", "半导体设备ETF", "etf", date, 78.0)]


class FixedDateEvaluation:
    def generate_report(self, signals):
        return EvaluationReport(scope="signals", total=len(signals))


def _signal(code: str, name: str, dtype: str, date: str | None, score: float) -> StrategySignal:
    return StrategySignal(
        code=code,
        name=name,
        dtype=dtype,
        market_date=date or "2026-06-26",
        relation_version="2026-W27",
        state=4,
        state_label="上涨趋势",
        score=score,
        confidence=0.82,
        relations={"sector": "通信设备", "theme": "AI算力"},
        action_hint="观察回踩后的延续机会",
        position_hint={"suggested_ratio": 0.2, "max_ratio": 0.3},
    )


def _run_fixed_date(tmp_path: Path, date: str):
    runner = PipelineRunner(
        data_layer=FixedDateDataLayer(),
        engine=FixedDateEngine(),
        evaluation=FixedDateEvaluation(),
        output_dir=tmp_path / date,
    )
    return runner.run(date=date, mode="daily", render_display=True, max_candidates=2)


def test_old_system_actions_exist():
    root = Path(__file__).resolve().parents[2]
    old_data_dir = root / "dashboard" / "data"
    available = [date for date in REGRESSION_DATES if (old_data_dir / f"actions_{date}.json").exists()]

    assert available, "At least one old fixed-date actions file should remain as a regression baseline"


def test_v2_display_payloads_exist(tmp_path):
    manifest = _run_fixed_date(tmp_path, "2026-06-12")

    display_payload = Path(manifest.artifacts["display_payload_path"])
    assert display_payload.exists()
    assert display_payload.parent.name.startswith("2026-06-12_")


def test_v2_manifests_exist(tmp_path):
    manifest = _run_fixed_date(tmp_path, "2026-06-12")

    manifest_path = Path(manifest.artifacts["manifest_path"])
    assert manifest_path.exists()
    assert manifest_path.name.startswith("run_manifest_2026-06-12_")


def test_v2_display_payload_structure(tmp_path):
    manifest = _run_fixed_date(tmp_path, "2026-06-22")
    payload = json.loads(Path(manifest.artifacts["display_payload_path"]).read_text(encoding="utf-8"))

    assert payload["meta"]["date"] == "2026-06-22"
    assert payload["regions"]
    assert payload["cards"]
    assert {"meta", "overview", "regions", "cards"}.issubset(payload)


def test_v2_html_files_exist(tmp_path):
    manifest = _run_fixed_date(tmp_path, "2026-06-12")
    output_dir = Path(manifest.artifacts["index_html_path"]).parent
    html_files = list(output_dir.glob("*.html"))

    assert html_files


def test_v2_index_html_structure(tmp_path):
    manifest = _run_fixed_date(tmp_path, "2026-06-22")
    content = Path(manifest.artifacts["index_html_path"]).read_text(encoding="utf-8")

    assert "<!DOCTYPE html>" in content or "<html" in content
    assert "iframe" in content.lower()
    assert "data-card-type=\"date_nav_card\"" in content


def test_v2_trend_dashboard_html_structure(tmp_path):
    manifest = _run_fixed_date(tmp_path, "2026-06-22")
    content = Path(manifest.artifacts["daily_html_path"]).read_text(encoding="utf-8")

    assert "<!DOCTYPE html>" in content or "<html" in content
    assert "趋势" in content or "trend" in content.lower()
    assert "data-card-type=\"action_card\"" in content


def test_v2_manifest_success_status(tmp_path):
    manifest = _run_fixed_date(tmp_path, "2026-06-22")

    assert manifest.status == "success"
    assert manifest.stages
    assert all(stage.status in {StageStatus.SUCCESS, StageStatus.WARNING} for stage in manifest.stages)


def test_v2_engine_produced_signals(tmp_path):
    manifest = _run_fixed_date(tmp_path, "2026-06-22")
    engine_stage = next(stage for stage in manifest.stages if stage.name == "engine")

    assert engine_stage.outputs["stock_signal_count"] > 0
    assert engine_stage.outputs["etf_signal_count"] > 0


def test_v2_evaluation_completed(tmp_path):
    manifest = _run_fixed_date(tmp_path, "2026-06-22")
    evaluation_stage = next(stage for stage in manifest.stages if stage.name == "evaluation")

    assert evaluation_stage.status == StageStatus.SUCCESS
    assert evaluation_stage.outputs["report_total"] == 2


def test_regression_date_coverage(tmp_path):
    manifests = [_run_fixed_date(tmp_path, date) for date in REGRESSION_DATES]

    assert {manifest.target_date for manifest in manifests} == set(REGRESSION_DATES)
    assert all(Path(manifest.artifacts["index_html_path"]).exists() for manifest in manifests)
