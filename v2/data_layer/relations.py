"""Relation storage for TFS v2."""

from __future__ import annotations

import json
from pathlib import Path

from .config import DATA_DIR, V1_DATA_DIR


class RelationStore:
    """Read current sector/theme relation mappings."""

    def __init__(self, data_dir: str | Path | None = None):
        self.data_dir = Path(data_dir or DATA_DIR)
        self._enable_v1_fallback = self.data_dir.resolve() == Path(DATA_DIR).resolve()
        self._v1_cache: dict | None = None

    def get_constituents(self, kind: str, code: str) -> list[str]:
        relations = self._load_current()
        if kind == "sector":
            return list(relations.get("sector_members", {}).get(code, []))
        if kind == "theme":
            return list(relations.get("theme_members", {}).get(code, []))
        raise ValueError(f"unsupported relation kind: {kind}")

    def get_relation_version(self) -> str | None:
        ver = self._load_current().get("version")
        if ver:
            return ver
        # v1 fallback 无版本概念，返回固定标识
        if self._enable_v1_fallback and self._load_v1():
            return "v1-legacy"
        return None

    def get_stock_profile(self, code: str) -> dict:
        relations = self._load_current()
        profile = relations.get("stock_profiles", {}).get(code)
        if profile:
            return dict(profile)
        # v1 fallback：从 constituent_map.reverse 取
        if self._enable_v1_fallback:
            v1 = self._load_v1()
            reverse = v1.get("reverse", {})
            entry = reverse.get(code, {})
            if entry:
                return {"sectors": list(entry.get("sectors", [])), "themes": list(entry.get("themes", []))}
        return {}

    def get_relation_names(self) -> dict:
        relations = self._load_current()
        names = {
            "sectors": {item.get("code"): item.get("name") for item in relations.get("sectors", []) if item.get("code")},
            "themes": {item.get("code"): item.get("name") for item in relations.get("themes", []) if item.get("code")},
        }
        if names["sectors"] or names["themes"]:
            return names
        # v1 fallback：从 sector_list.json / theme_list.json 取
        if self._enable_v1_fallback:
            return self._load_v1_names()
        return names

    def _load_current(self) -> dict:
        path = self.data_dir / "meta" / "relations" / "current.json"
        if not path.exists():
            return {}
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"relation current must be object: {path}")
        return data

    def _load_v1(self) -> dict:
        """加载 v1 constituent_map.json（成分股双向映射）。"""
        if self._v1_cache is not None:
            return self._v1_cache
        path = Path(V1_DATA_DIR) / "constituent_map.json"
        if not path.exists():
            self._v1_cache = {}
            return self._v1_cache
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            self._v1_cache = data if isinstance(data, dict) else {}
        except Exception:
            self._v1_cache = {}
        return self._v1_cache

    def _load_v1_names(self) -> dict:
        """从 v1 sector_list.json / theme_list.json 取板块/题材名映射。"""
        sectors: dict[str, str] = {}
        themes: dict[str, str] = {}
        v1 = Path(V1_DATA_DIR)
        for fname, target in [("sector_list.json", sectors), ("theme_list.json", themes)]:
            path = v1 / fname
            if not path.exists():
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                items = data if isinstance(data, list) else data.get("data", data.get("items", []))
                for item in items:
                    if isinstance(item, dict):
                        code = str(item.get("code") or item.get("symbol") or "")
                        name = item.get("name") or item.get("title") or code
                        if code:
                            target[code] = name
                    elif isinstance(item, str):
                        target[item] = item
            except Exception:
                pass
        return {"sectors": sectors, "themes": themes}

