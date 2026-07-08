"""History store for TFS v2.

提供 5d 状态条、sparkline、板块统计所需的历史序列数据。
过渡期复用 v1 真实积累的 history_states_full.json / sector_stats.json，
同时维护 v2 自身的每日追加（个股级 history，积累中）。
"""

from __future__ import annotations

import json
from pathlib import Path

from .config import DATA_DIR, V1_DATA_DIR


class HistoryStore:
    """读取历史状态序列与板块统计。"""

    def __init__(self, data_dir: str | Path | None = None):
        self.data_dir = Path(data_dir or DATA_DIR)
        self.derived_dir = self.data_dir / "derived"
        self._v1_history_cache: dict | None = None
        self._v1_sector_stats_cache: dict | None = None
        self._index_pct_cache: dict | None = None

    # ── 板块级历史（来自 v1 history_states_full.json）──────────

    def _load_v1_history(self) -> dict:
        if self._v1_history_cache is not None:
            return self._v1_history_cache
        path = Path(V1_DATA_DIR) / "history_states_full.json"
        if not path.exists():
            self._v1_history_cache = {"sectors": {}}
            return self._v1_history_cache
        data = json.loads(path.read_text(encoding="utf-8"))
        self._v1_history_cache = data if isinstance(data, dict) else {"sectors": {}}
        return self._v1_history_cache

    def get_recent_states(self, code: str, n: int = 5) -> list:
        """返回某板块近 n 日 state 序列（用于 5d 状态条）。"""
        history = self._load_v1_history()
        sectors = history.get("sectors", {})
        records = sectors.get(code, sectors.get(str(code), []))
        if not records:
            return []
        recent = records[-n:] if len(records) >= n else records
        return [r.get("state") for r in recent if isinstance(r, dict)]

    def get_recent_scores(self, code: str, n: int = 5) -> list:
        """返回某板块近 n 日 score 序列（用于 sparkline）。"""
        history = self._load_v1_history()
        sectors = history.get("sectors", {})
        records = sectors.get(code, sectors.get(str(code), []))
        if not records:
            return []
        recent = records[-n:] if len(records) >= n else records
        return [r.get("score", 0) for r in recent if isinstance(r, dict)]

    def get_state_history(self, code: str) -> list:
        """返回某板块完整 state 历史（用于轨迹弹窗）。"""
        history = self._load_v1_history()
        sectors = history.get("sectors", {})
        records = sectors.get(code, sectors.get(str(code), []))
        return list(records)

    # ── 板块统计（来自 v1 sector_stats.json）────────────────────

    def _load_v1_sector_stats(self) -> dict:
        if self._v1_sector_stats_cache is not None:
            return self._v1_sector_stats_cache
        path = Path(V1_DATA_DIR) / "sector_stats.json"
        if not path.exists():
            self._v1_sector_stats_cache = {"sectors": {}}
            return self._v1_sector_stats_cache
        data = json.loads(path.read_text(encoding="utf-8"))
        self._v1_sector_stats_cache = data if isinstance(data, dict) else {"sectors": {}}
        return self._v1_sector_stats_cache

    def get_sector_stats(self, sector_id: str) -> dict:
        """返回板块统计：avg_uptrend_days/max_uptrend_days/tomorrow_prob/expected_return 等。"""
        stats = self._load_v1_sector_stats()
        sectors = stats.get("sectors", {})
        return sectors.get(str(sector_id), sectors.get(sector_id, {}))

    def get_sector_prob_matrix(self) -> dict:
        """返回 v2_probs 状态转移概率矩阵（推演概率用）。"""
        stats = self._load_v1_sector_stats()
        meta = stats.get("meta", {})
        return meta.get("v2_probs", {})

    # ── v2 自身追加（个股级，积累中）────────────────────────────

    def append_states(self, date: str, signals: list) -> None:
        """每日 pipeline 跑完后追加个股 state+score（积累 v2 自身历史）。"""
        if not signals:
            return
        dates_dir = self.derived_dir / "dates" / date
        dates_dir.mkdir(parents=True, exist_ok=True)
        path = dates_dir / "history_states.json"
        existing: dict = {}
        if path.exists():
            try:
                existing = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                existing = {}
        if not isinstance(existing, dict):
            existing = {}
        items = existing.get("items", {})
        if not isinstance(items, dict):
            items = {}
        for sig in signals:
            code = getattr(sig, "code", None)
            if not code:
                continue
            items[code] = {
                "date": date,
                "state": getattr(sig, "state", None),
                "score": getattr(sig, "score", 0.0),
                "state_label": getattr(sig, "state_label", ""),
            }
        existing["items"] = items
        existing["date"] = date
        path.write_text(json.dumps(existing, ensure_ascii=False), encoding="utf-8")

    def get_symbol_recent_states(self, code: str, n: int = 5) -> list:
        """读取 v2 自身积累的个股近 n 日 state（积累不足时返回已有）。"""
        dates_dir = self.derived_dir / "dates"
        if not dates_dir.exists():
            return []
        records = []
        for date_dir in sorted(dates_dir.iterdir(), reverse=True):
            path = date_dir / "history_states.json"
            if not path.exists():
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            item = data.get("items", {}).get(code)
            if item:
                records.append(item.get("state"))
            if len(records) >= n:
                break
        return records

    # ── 指数涨跌（来自 v1 index.html 解析的真实积累数据）────────

    def get_index_pct(self, date: str) -> dict:
        """返回某日期的指数涨跌 {code: {name, pct}}。"""
        if self._index_pct_cache is None:
            self._index_pct_cache = {}
            path = self.derived_dir / "index_pct.json"
            if path.exists():
                try:
                    for item in json.loads(path.read_text(encoding="utf-8")):
                        if isinstance(item, dict) and item.get("date"):
                            self._index_pct_cache[item["date"]] = item.get("indices", {})
                except Exception:
                    pass
        return self._index_pct_cache.get(date, {})
