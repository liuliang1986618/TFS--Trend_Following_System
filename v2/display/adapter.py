"""Display payload to legacy dashboard data adapter boundary."""

from __future__ import annotations


class DisplayAdapter:
    def export_legacy_json(self, payload_path: str, dashboard_data_dir: str) -> dict:
        raise NotImplementedError("Task 8 implements legacy dashboard JSON export")
