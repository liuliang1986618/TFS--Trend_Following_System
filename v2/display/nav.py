"""Date navigation payload builder for TFS v2 display outputs."""

from __future__ import annotations

from datetime import datetime


class NavPayloadBuilder:
    """Build DateNavCard payloads from display payloads."""

    def build(self, display_payloads: list[dict], current_date: str | None = None) -> dict:
        ordered = sorted(display_payloads, key=lambda item: item.get("meta", {}).get("date", ""), reverse=True)
        latest_date = ordered[0].get("meta", {}).get("date") if ordered else None
        items = [self._date_card(payload, current_date=current_date, latest_date=latest_date) for payload in ordered]
        return {
            "default_date": current_date or latest_date,
            "report_count": len(items),
            "items": items,
        }

    def _date_card(self, payload: dict, current_date: str | None, latest_date: str | None) -> dict:
        meta = payload.get("meta", {})
        date = meta.get("date", "")
        leaders = payload.get("leader_summary") or self._leaders(payload.get("signals", []))
        market = self._market(payload)
        data_status = self._data_status(payload)
        return {
            "id": f"nav_{date}",
            "type": "date_nav_card",
            "date": date,
            "target": f"trend_dashboard_{date}.html" if date else "",
            "is_current": date == current_date,
            "is_latest": date == latest_date,
            "data_status": data_status,
            "line_time": {
                "date": date,
                "label": self._short_date(date),
                "weekday": self._weekday(date),
                "status": data_status,
            },
            "line_market": market,
            "line_leaders": leaders,
        }

    @staticmethod
    def _market(payload: dict) -> dict:
        health = payload.get("overview", {}).get("health", {})
        market_status = health.get("market", {}).get("status", "unknown")
        return {
            "label": market_status,
            "level": "normal" if market_status == "complete" else "warning",
            "summary": f"market {market_status}",
            "indices": [],
        }

    @staticmethod
    def _data_status(payload: dict) -> str:
        health = payload.get("overview", {}).get("health", {})
        statuses = [item.get("status") for item in health.values() if isinstance(item, dict)]
        if not statuses:
            return "unknown"
        if all(status == "complete" for status in statuses):
            return "complete"
        return "warning"

    @staticmethod
    def _leaders(signals: list[dict]) -> dict:
        leaders = {"sector": "", "theme": "", "stock": "", "etf": ""}
        sorted_signals = sorted(signals, key=lambda item: item.get("score", 0), reverse=True)
        for signal in sorted_signals:
            relations = signal.get("relations", {}) if isinstance(signal, dict) else {}
            if not leaders["sector"]:
                leaders["sector"] = relations.get("sector", "")
            if not leaders["theme"]:
                leaders["theme"] = relations.get("theme", "")
            if signal.get("dtype") == "stock" and not leaders["stock"]:
                leaders["stock"] = signal.get("name", "")
            if signal.get("dtype") == "etf" and not leaders["etf"]:
                leaders["etf"] = signal.get("name", "")
        return leaders

    @staticmethod
    def _short_date(date: str) -> str:
        parts = date.split("-")
        if len(parts) == 3:
            return f"{parts[1]}-{parts[2]}"
        return date

    @staticmethod
    def _weekday(date: str) -> str:
        names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        try:
            return names[datetime.strptime(date, "%Y-%m-%d").weekday()]
        except ValueError:
            return ""


class DateNavBuilder(NavPayloadBuilder):
    """Backward-compatible name for the v2 navigation payload builder."""
