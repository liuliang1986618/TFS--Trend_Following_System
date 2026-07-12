"""进度日志：记录每个标的的拉取状态，支持断点恢复。

存储位置：data/meta/fetch_journal.json
格式：append-only，记录 done/pending/failed/skipped 状态。
崩溃后可从 journal 读取，跳过已完成的标的。
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Literal


class FetchJournal:
    """追踪每个标的的拉取状态。"""

    def __init__(self, data_dir: str | Path):
        self._path = Path(data_dir) / "meta" / "fetch_journal.json"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._data: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            try:
                self._data = json.loads(self._path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self._data = {}

    def _save(self) -> None:
        self._path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def is_done(self, dtype: str, code: str) -> bool:
        key = f"{dtype}:{code}"
        entry = self._data.get(key, {})
        return entry.get("status") == "done" and entry.get("date") == self._today()

    def mark(self, dtype: str, code: str, status: Literal["done", "failed", "skipped"], error: str = "") -> None:
        key = f"{dtype}:{code}"
        self._data[key] = {
            "status": status,
            "date": self._today(),
            "ts": datetime.now().isoformat(timespec="seconds"),
            **({"error": error} if error else {}),
        }
        # 每100条写一次盘，避免频繁IO
        if len(self._data) % 100 == 0:
            self._save()

    def flush(self) -> None:
        """确保写盘。"""
        self._save()

    def stats(self) -> dict[str, int]:
        today = self._today()
        counts = {"done": 0, "failed": 0, "skipped": 0, "stale": 0}
        for entry in self._data.values():
            if entry.get("date") != today:
                counts["stale"] += 1
            elif entry.get("status") in counts:
                counts[entry["status"]] += 1
        return counts

    def clear_stale(self) -> int:
        """清除旧日期的记录，返回清除数量。"""
        today = self._today()
        stale_keys = [k for k, v in self._data.items() if v.get("date") != today]
        for k in stale_keys:
            del self._data[k]
        if stale_keys:
            self._save()
        return len(stale_keys)

    @staticmethod
    def _today() -> str:
        return datetime.now().strftime("%Y-%m-%d")
