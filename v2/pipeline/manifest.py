"""Run manifest contracts for TFS v2."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class RunManifest:
    run_id: str
    mode: str
    target_date: str
    started_at: str = ""
    finished_at: str | None = None
    status: str = "pending"
    stages: list = field(default_factory=list)
    artifacts: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    def save(self, output_dir: str | Path) -> str:
        output = Path(output_dir)
        output.mkdir(parents=True, exist_ok=True)
        path = output / f"run_manifest_{self.run_id}.json"
        path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        self.artifacts["manifest_path"] = str(path)
        path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        return str(path)
