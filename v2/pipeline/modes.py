"""Pipeline mode contracts for TFS v2."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PipelineMode(str, Enum):
    DAILY = "daily"
    BACKFILL = "backfill"
    EVAL = "eval"
    DISPLAY_ONLY = "display_only"


@dataclass
class PipelineOptions:
    target_date: str | None = None
    mode: str = PipelineMode.DAILY
    scope: str = "all"
    run_evaluation: bool = False
    render_display: bool = False
    open_browser: bool = False
    allow_partial_data: bool = False
    allow_demo_data: bool = False
