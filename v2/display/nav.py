"""Date navigation payload builder for TFS v2 display outputs.

从 v1 date_nav.json 加载全部历史日期，合并 v2 当日 payload，
生成完整侧边栏（120+ 日期项），含指数涨跌/市场状态/龙头摘要。
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path


_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_V1_DATE_NAV = _PROJECT_ROOT / "dashboard" / "data" / "date_nav.json"
_V2_INDEX_PCT = _PROJECT_ROOT / "v2" / "data" / "derived" / "index_pct.json"


class NavPayloadBuilder:
    """Build DateNavCard payloads from display payloads + v1 historical dates."""

    def __init__(self, data_layer=None):
        self.data_layer = data_layer
        self._v1_dates_cache: list | None = None
        self._index_pct_cache: dict | None = None

    def build(self, display_payloads: list[dict], current_date: str | None = None) -> dict:
        # 加载 v1 历史日期
        v1_dates = self._load_v1_dates()
        # 加载指数涨跌
        index_pct = self._load_index_pct()

        # v2 当日 payload
        v2_items = []
        v2_dates = set()
        for payload in display_payloads:
            card = self._date_card_from_payload(payload, current_date, index_pct)
            if card:
                v2_items.append(card)
                v2_dates.add(card["date"])

        # 合并 v1 历史日期（跳过 v2 已有的）
        v1_items = []
        for vd in v1_dates:
            date = vd.get("date", "")
            if date in v2_dates:
                continue
            card = self._date_card_from_v1(vd, index_pct)
            if card:
                v1_items.append(card)

        # 合并 + 按日期降序
        all_items = v2_items + v1_items
        all_items.sort(key=lambda x: x["date"], reverse=True)

        latest_date = all_items[0]["date"] if all_items else current_date
        return {
            "default_date": current_date or latest_date,
            "report_count": len(all_items),
            "items": all_items,
        }

    def _date_card_from_payload(self, payload: dict, current_date: str | None, index_pct: dict) -> dict | None:
        meta = payload.get("meta", {})
        date = meta.get("date", "")
        if not date:
            return None
        leaders = payload.get("leader_summary") or self._leaders(payload.get("signals", []))
        market = self._market(payload, index_pct, date)
        data_status = self._data_status(payload)
        return {
            "id": f"nav_{date}",
            "type": "date_nav_card",
            "date": date,
            "target": f"trend_dashboard_{date}.html",
            "is_current": date == current_date,
            "is_latest": False,
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

    def _date_card_from_v1(self, vd: dict, index_pct: dict) -> dict | None:
        date = vd.get("date", "")
        if not date:
            return None
        # 市场状态
        health = vd.get("health", "弱势")
        # 指数涨跌
        indices = index_pct.get(date, {})
        idx_list = [{"code": k, "name": v.get("name", k), "pct": v.get("pct", 0.0)} for k, v in indices.items()]
        # 龙头
        leaders_raw = vd.get("leaders", {}) or {}
        leaders = self._v1_leaders(leaders_raw, vd.get("top_sectors", []))
        # ↑数量
        up_count = vd.get("uptrend_count", 0)
        return {
            "id": f"nav_{date}",
            "type": "date_nav_card",
            "date": date,
            "target": f"trend_dashboard_{date}.html",
            "is_current": False,
            "is_latest": False,
            "data_status": "complete" if health in ("强势", "正常") else "warning",
            "line_time": {
                "date": date,
                "label": self._short_date(date),
                "weekday": vd.get("weekday", self._weekday(date)),
                "status": health,
            },
            "line_market": {
                "label": health,
                "level": "normal" if health in ("强势", "正常") else "warning",
                "summary": f"↑{up_count}",
                "indices": idx_list,
                "up_count": up_count,
            },
            "line_leaders": leaders,
        }

    @staticmethod
    def _v1_leaders(leaders_raw: dict, top_sectors: list) -> dict:
        """从 v1 leaders 字典提取龙头摘要。"""
        result = {"sector": "", "theme": "", "stock": "", "etf": ""}
        # 板块名
        if top_sectors:
            result["sector"] = top_sectors[0].get("name", "") if isinstance(top_sectors[0], dict) else str(top_sectors[0])
        # ETF 龙头
        for sector_name, items in leaders_raw.items():
            if not result["sector"]:
                result["sector"] = sector_name
            if items and isinstance(items, list) and isinstance(items[0], dict):
                etf_name = items[0].get("name", "")
                if etf_name and not result["etf"]:
                    result["etf"] = etf_name
                break
        # 主线板块
        if top_sectors and len(top_sectors) > 1:
            result["theme"] = " · ".join(
                (s.get("name", "") if isinstance(s, dict) else str(s)) for s in top_sectors[:3] if s
            )
        return result

    @staticmethod
    def _market(payload: dict, index_pct: dict, date: str) -> dict:
        health = payload.get("overview", {}).get("health", {})
        market_status = health.get("market", {}).get("status", "unknown")
        indices = payload.get("overview", {}).get("indices", []) or []
        if not indices and date in index_pct:
            indices = [{"code": k, "name": v.get("name", k), "pct": v.get("pct", 0.0)} for k, v in index_pct[date].items()]
        return {
            "label": market_status,
            "level": "normal" if market_status == "complete" else "warning",
            "summary": f"market {market_status}",
            "indices": indices,
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

    def _load_v1_dates(self) -> list:
        if self._v1_dates_cache is not None:
            return self._v1_dates_cache
        if not _V1_DATE_NAV.exists():
            self._v1_dates_cache = []
            return self._v1_dates_cache
        try:
            data = json.loads(_V1_DATE_NAV.read_text(encoding="utf-8"))
            self._v1_dates_cache = data.get("dates", []) if isinstance(data, dict) else []
        except Exception:
            self._v1_dates_cache = []
        return self._v1_dates_cache

    def _load_index_pct(self) -> dict:
        if self._index_pct_cache is not None:
            return self._index_pct_cache
        self._index_pct_cache = {}
        if _V2_INDEX_PCT.exists():
            try:
                for item in json.loads(_V2_INDEX_PCT.read_text(encoding="utf-8")):
                    if isinstance(item, dict) and item.get("date"):
                        self._index_pct_cache[item["date"]] = item.get("indices", {})
            except Exception:
                pass
        return self._index_pct_cache


class DateNavBuilder(NavPayloadBuilder):
    """Backward-compatible name for the v2 navigation payload builder."""
