"""Relation storage for TFS v2."""

from __future__ import annotations

import json
from pathlib import Path

from .config import DATA_DIR


class RelationStore:
    """Read current sector/theme relation mappings."""

    def __init__(self, data_dir: str | Path | None = None):
        self.data_dir = Path(data_dir or DATA_DIR)

    def get_constituents(self, kind: str, code: str) -> list[str]:
        relations = self._load_current()
        if kind == "sector":
            return list(relations.get("sector_members", {}).get(code, []))
        if kind == "theme":
            return list(relations.get("theme_members", {}).get(code, []))
        raise ValueError(f"unsupported relation kind: {kind}")

    def get_relation_version(self) -> str | None:
        return self._load_current().get("version")

    def get_stock_profile(self, code: str) -> dict:
        return dict(self._load_current().get("stock_profiles", {}).get(code, {}))

    def get_relation_names(self) -> dict:
        relations = self._load_current()
        return {
            "sectors": {item.get("code"): item.get("name") for item in relations.get("sectors", []) if item.get("code")},
            "themes": {item.get("code"): item.get("name") for item in relations.get("themes", []) if item.get("code")},
        }

    def _load_current(self) -> dict:
        path = self.data_dir / "meta" / "relations" / "current.json"
        if not path.exists():
            return {}
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"relation current must be object: {path}")
        return data
