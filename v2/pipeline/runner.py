"""Pipeline orchestration boundary for TFS v2."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path

from v2.data_layer import DataLayer
from v2.display.builder import DisplayPayloadBuilder
from v2.display.nav import NavPayloadBuilder
from v2.display.renderer import DisplayRenderer
from v2.engine import TrendEngine
from v2.evaluation import Evaluation

from .manifest import RunManifest
from .stages import StageResult, StageStatus


class PipelineRunner:
    """Run v2 stages in order and record a manifest."""

    def __init__(
        self,
        data_layer=None,
        engine=None,
        evaluation=None,
        output_dir: str | Path | None = None,
        display_builder=None,
        nav_builder=None,
        display_renderer=None,
    ):
        self.data_layer = data_layer or DataLayer()
        self.engine = engine or TrendEngine(self.data_layer)
        self.evaluation = evaluation or Evaluation(data_layer=self.data_layer, engine=self.engine)
        self.output_dir = Path(output_dir or Path("v2") / "data" / "derived" / "runs")
        self.display_builder = display_builder or DisplayPayloadBuilder(data_layer=self.data_layer)
        self.nav_builder = nav_builder or NavPayloadBuilder()
        self.display_renderer = display_renderer or DisplayRenderer()

    def run(
        self,
        date: str | None = None,
        mode: str = "daily",
        render_display: bool = False,
        max_candidates: int = 50,
    ) -> RunManifest:
        target_date = date or datetime.now().strftime("%Y-%m-%d")
        manifest = RunManifest(
            run_id=f"{target_date}_{datetime.now().strftime('%H%M%S')}",
            mode=str(mode),
            target_date=target_date,
            started_at=self._now(),
        )

        data_stage = self._run_data_health(target_date)
        manifest.stages.append(data_stage)
        if data_stage.status == StageStatus.FAILED:
            manifest.status = "failed"
            manifest.finished_at = self._now()
            manifest.save(self.output_dir)
            return manifest

        engine_stage, signals = self._run_engine(target_date, max_candidates=max_candidates)
        manifest.stages.append(engine_stage)
        if engine_stage.status == StageStatus.FAILED:
            manifest.status = "failed"
            manifest.finished_at = self._now()
            manifest.save(self.output_dir)
            return manifest
        manifest.artifacts["stock_signal_count"] = engine_stage.outputs.get("stock_signal_count", 0)
        manifest.artifacts["etf_signal_count"] = engine_stage.outputs.get("etf_signal_count", 0)

        evaluation_report = {}
        if mode in ("daily", "eval"):
            eval_stage, evaluation_report = self._run_evaluation(signals)
            manifest.stages.append(eval_stage)
            if eval_stage.status == StageStatus.FAILED:
                manifest.status = "failed"
                manifest.finished_at = self._now()
                manifest.save(self.output_dir)
                return manifest

        if render_display:
            display_stage = self._run_display(target_date, manifest.run_id, signals, evaluation_report, data_stage.health)
            manifest.stages.append(display_stage)
            manifest.artifacts.update(display_stage.outputs)
            if display_stage.status == StageStatus.FAILED:
                manifest.status = "failed"
                manifest.finished_at = self._now()
                manifest.save(self.output_dir)
                return manifest

        manifest.status = "success"
        manifest.finished_at = self._now()
        manifest.save(self.output_dir)
        return manifest

    def _run_data_health(self, target_date: str) -> StageResult:
        started = self._now()
        health = self.data_layer.check_market_health(target_date)
        relation_health = self.data_layer.check_relation_health() if hasattr(self.data_layer, "check_relation_health") else {}
        issues = list(health.get("issues", [])) + list(relation_health.get("issues", []))
        allowed = health.get("allowed", {})
        recommendation_allowed = self._recommendation_data_available(health)
        if health.get("status") == "complete":
            status = StageStatus.SUCCESS
        elif recommendation_allowed:
            status = StageStatus.WARNING
        else:
            status = StageStatus.FAILED
        return StageResult(
            name="data_health",
            status=status,
            started_at=started,
            finished_at=self._now(),
            inputs={"date": target_date},
            outputs={
                "market_status": health.get("status"),
                "relation_status": relation_health.get("status"),
                "stock_recommendation_allowed": allowed.get("stock_recommendation"),
                "etf_recommendation_allowed": allowed.get("etf_recommendation"),
            },
            health={"market": health, "relation": relation_health},
            errors=issues if status == StageStatus.FAILED else [],
            warnings=issues if status == StageStatus.WARNING else [],
        )

    @staticmethod
    def _recommendation_data_available(health: dict) -> bool:
        allowed = health.get("allowed", {})
        if allowed.get("stock_recommendation") and allowed.get("etf_recommendation"):
            return True
        checks = health.get("checks", {})
        return PipelineRunner._check_has_complete_count(checks.get("stock", {})) and PipelineRunner._check_has_complete_count(checks.get("etf", {}))

    @staticmethod
    def _check_has_complete_count(check: dict) -> bool:
        if not isinstance(check, dict):
            return False
        if check.get("count_ok") is True:
            return True
        actual = check.get("actual_count") or 0
        minimum = check.get("min_count") or 0
        return minimum > 0 and actual >= minimum

    def _run_engine(self, target_date: str, max_candidates: int) -> tuple[StageResult, list]:
        started = self._now()
        try:
            stock_signals = self.engine.scan_stock_full(date=target_date, max_candidates=max_candidates)
            etf_signals = self.engine.scan_etf_direct(date=target_date, max_candidates=max_candidates)
        except Exception as exc:
            return (
                StageResult(
                    name="engine",
                    status=StageStatus.FAILED,
                    started_at=started,
                    finished_at=self._now(),
                    inputs={"date": target_date, "max_candidates": max_candidates},
                    errors=[str(exc)],
                ),
                [],
            )
        signals = list(stock_signals) + list(etf_signals)
        return (
            StageResult(
                name="engine",
                status=StageStatus.SUCCESS,
                started_at=started,
                finished_at=self._now(),
                inputs={"date": target_date, "max_candidates": max_candidates},
                outputs={"stock_signal_count": len(stock_signals), "etf_signal_count": len(etf_signals)},
            ),
            signals,
        )

    def _run_evaluation(self, signals: list) -> tuple[StageResult, dict]:
        started = self._now()
        try:
            report = self.evaluation.generate_report(signals)
            report_dict = self._to_plain_dict(report)
            total = report_dict.get("total", 0)
        except Exception as exc:
            return (
                StageResult(name="evaluation", status=StageStatus.FAILED, started_at=started, finished_at=self._now(), errors=[str(exc)]),
                {},
            )
        return (
            StageResult(
                name="evaluation",
                status=StageStatus.SUCCESS,
                started_at=started,
                finished_at=self._now(),
                inputs={"signal_count": len(signals)},
                outputs={"report_total": total},
            ),
            report_dict,
        )

    def _run_display(self, target_date: str, run_id: str, signals: list, evaluation_report: dict, health: dict) -> StageResult:
        started = self._now()
        run_output_dir = self.output_dir / run_id
        try:
            payload = self.display_builder.build(
                date=target_date,
                run_id=run_id,
                signals=signals,
                evaluation_report=evaluation_report,
                health=health,
            )
            payload_path = run_output_dir / "display_payload.json"
            payload_path.parent.mkdir(parents=True, exist_ok=True)
            payload_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

            nav_payload = self.nav_builder.build([payload], current_date=target_date)
            nav_payload_path = run_output_dir / "nav_payload.json"
            nav_payload_path.write_text(json.dumps(nav_payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

            daily_html_path = run_output_dir / f"trend_dashboard_{target_date}.html"
            index_html_path = run_output_dir / "index.html"
            self.display_renderer.render_daily(str(payload_path), str(daily_html_path))
            self.display_renderer.render_index(str(nav_payload_path), str(index_html_path))
        except Exception as exc:
            return StageResult(name="display", status=StageStatus.FAILED, started_at=started, finished_at=self._now(), errors=[str(exc)])
        return StageResult(
            name="display",
            status=StageStatus.SUCCESS,
            started_at=started,
            finished_at=self._now(),
            inputs={"date": target_date, "run_id": run_id},
            outputs={
                "display_payload_path": str(payload_path),
                "nav_payload_path": str(nav_payload_path),
                "daily_html_path": str(daily_html_path),
                "index_html_path": str(index_html_path),
            },
        )

    @staticmethod
    def _to_plain_dict(report) -> dict:
        if isinstance(report, dict):
            return report
        if is_dataclass(report):
            return asdict(report)
        if hasattr(report, "to_dict"):
            return report.to_dict()
        return {"total": getattr(report, "total", 0)}

    @staticmethod
    def _now() -> str:
        return datetime.now().isoformat(timespec="seconds")
