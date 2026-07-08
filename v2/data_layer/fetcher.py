"""Data update orchestration boundary for TFS v2."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable

from .config import DATA_DIR, INDEX_CODES
from .providers.akshare_em import AkshareEMProvider
from .storage import MarketDataStore


class DataFetcher:
    """Owner for market data writes under the v2 data directory."""

    def __init__(self, data_dir: str | Path | None = None, provider: AkshareEMProvider | None = None):
        self.data_dir = Path(data_dir or DATA_DIR)
        self.provider = provider or AkshareEMProvider()

    def update_market_daily(
        self,
        date: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        dtypes: Iterable[str] = ("stock", "etf"),
    ) -> dict:
        end = end_date or date or self._default_end_date()
        start = start_date or self._default_start_date(end)
        result = {"status": "completed", "start_date": start, "end_date": end, "checks": {}}
        for dtype in dtypes:
            if dtype == "stock":
                universe = self.provider.fetch_stock_universe()
                fetch_daily = self.provider.fetch_stock_daily
            elif dtype == "etf":
                universe = self.provider.fetch_etf_universe()
                fetch_daily = self.provider.fetch_etf_daily
            elif dtype == "index":
                universe = [{"code": c, "name": n} for c, n in INDEX_CODES.items()]
                fetch_daily = self.provider.fetch_index_daily
            else:
                raise ValueError(f"unsupported update dtype: {dtype}")

            self._write_universe(dtype, universe)
            check = {"total": len(universe), "success": 0, "skipped": 0, "failed": 0, "errors": []}
            for item in universe:
                code = str(item["code"])
                try:
                    if self._has_current_daily(dtype, code, end):
                        check["skipped"] += 1
                        continue
                    daily = fetch_daily(code, start_date=start, end_date=end)
                    self._write_daily(dtype, code, daily)
                    check["success"] += 1
                except Exception as exc:  # pragma: no cover - real data failures are reported, not hidden
                    check["failed"] += 1
                    if len(check["errors"]) < 20:
                        check["errors"].append({"code": code, "error": str(exc)})
            result["checks"][dtype] = check
            if check["failed"]:
                result["status"] = "partial"
        return result

    def update_relations_weekly(self, week: str | None = None, sources: Iterable[str] = ("eastmoney",)) -> dict:
        version = week or self._default_relation_version()
        source_list = list(sources)
        result = {"status": "completed", "version": version, "sources": source_list, "checks": {}, "active_source": None}
        completed_sources: list[tuple[str, dict]] = []

        for source in source_list:
            relation, source_result = self._build_relation_source(version, source)
            result["checks"][source] = source_result["checks"]
            if source_result["status"] == "completed":
                self._write_relations(version, relation, source=source)
                completed_sources.append((source, relation))
            else:
                result["status"] = "partial"

        if completed_sources:
            active_source, active_relation = completed_sources[0]
            fallback = [source for source, _ in completed_sources[1:]]
            self._write_active_relations(version, active_source, fallback, active_relation)
            result["active_source"] = active_source
        else:
            result["status"] = "partial"
        return result

    def _build_relation_source(self, version: str, source: str) -> tuple[dict, dict]:
        sectors = self._fetch_relation_universe(source, "sector")
        themes = self._fetch_relation_universe(source, "theme")
        relation = {
            "version": version,
            "source": source,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "sectors": sectors,
            "themes": themes,
            "sector_members": {},
            "theme_members": {},
            "stock_profiles": {},
        }
        result = {
            "status": "completed",
            "checks": {
                "sector": {"total": len(sectors), "success": 0, "failed": 0, "errors": []},
                "theme": {"total": len(themes), "success": 0, "failed": 0, "errors": []},
            },
        }
        for item in sectors:
            code = str(item["code"])
            try:
                members = self._fetch_relation_members(source, "sector", item)
                symbols = [member["code"] for member in members]
                relation["sector_members"][code] = symbols
                for member in members:
                    profile = relation["stock_profiles"].setdefault(member["code"], {"name": member["name"], "sectors": [], "themes": []})
                    if code not in profile["sectors"]:
                        profile["sectors"].append(code)
                result["checks"]["sector"]["success"] += 1
            except Exception as exc:
                result["checks"]["sector"]["failed"] += 1
                if len(result["checks"]["sector"]["errors"]) < 20:
                    result["checks"]["sector"]["errors"].append({"code": code, "name": item.get("name"), "error": str(exc)})
        for item in themes:
            code = str(item["code"])
            try:
                members = self._fetch_relation_members(source, "theme", item)
                symbols = [member["code"] for member in members]
                relation["theme_members"][code] = symbols
                for member in members:
                    profile = relation["stock_profiles"].setdefault(member["code"], {"name": member["name"], "sectors": [], "themes": []})
                    if code not in profile["themes"]:
                        profile["themes"].append(code)
                result["checks"]["theme"]["success"] += 1
            except Exception as exc:
                result["checks"]["theme"]["failed"] += 1
                if len(result["checks"]["theme"]["errors"]) < 20:
                    result["checks"]["theme"]["errors"].append({"code": code, "name": item.get("name"), "error": str(exc)})
        for profile in relation["stock_profiles"].values():
            profile["sectors"].sort()
            profile["themes"].sort()
        if result["checks"]["sector"]["failed"] or result["checks"]["theme"]["failed"]:
            result["status"] = "partial"
        return relation, result

    def _fetch_relation_universe(self, source: str, kind: str) -> list[dict[str, str]]:
        method = getattr(type(self.provider), "fetch_relation_universe", None)
        if method is not None and method is not AkshareEMProvider.fetch_relation_universe:
            return self.provider.fetch_relation_universe(source, kind)
        if isinstance(self.provider, AkshareEMProvider) and getattr(self.provider, "_uses_default_ak", False):
            return self.provider.fetch_relation_universe(source, kind)
        if kind == "sector":
            return self.provider.fetch_sector_universe()
        if kind == "theme":
            return self.provider.fetch_theme_universe()
        raise ValueError(f"unsupported relation kind: {kind}")

    def _fetch_relation_members(self, source: str, kind: str, item: dict) -> list[dict[str, str]]:
        method = getattr(type(self.provider), "fetch_relation_members", None)
        if method is not None and method is not AkshareEMProvider.fetch_relation_members:
            return self.provider.fetch_relation_members(source, kind, item)
        if isinstance(self.provider, AkshareEMProvider) and getattr(self.provider, "_uses_default_ak", False):
            return self.provider.fetch_relation_members(source, kind, item)
        if kind == "sector":
            return self.provider.fetch_sector_members(item["name"])
        if kind == "theme":
            return self.provider.fetch_theme_members(item["name"])
        raise ValueError(f"unsupported relation kind: {kind}")

    def _write_universe(self, dtype: str, universe: list[dict[str, str]]) -> None:
        path = self.data_dir / "meta" / "universe" / f"{dtype}_list.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(universe, ensure_ascii=False, indent=2), encoding="utf-8")

    def _write_daily(self, dtype: str, code: str, daily) -> None:
        path = self.data_dir / dtype / f"{code}.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        MarketDataStore._validate_daily_schema(daily, path)
        daily.to_parquet(path, index=False)

    def _has_current_daily(self, dtype: str, code: str, end_date: str) -> bool:
        path = self.data_dir / dtype / f"{code}.parquet"
        if not path.exists():
            return False
        try:
            df = MarketDataStore(self.data_dir).load_daily(dtype, code)
        except Exception:
            return False
        if df.empty:
            return False
        return df["date"].iloc[-1] >= self._latest_expected_trading_day(end_date)

    def _write_relations(self, version: str, relation: dict, source: str) -> None:
        path = self.data_dir / "meta" / "relations" / source / f"{version}.json"
        current = self.data_dir / "meta" / "relations" / source / "current.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        content = json.dumps(relation, ensure_ascii=False, indent=2)
        path.write_text(content, encoding="utf-8")
        current.write_text(content, encoding="utf-8")

    def _write_active_relations(self, version: str, primary: str, fallback: list[str], relation: dict) -> None:
        relations_dir = self.data_dir / "meta" / "relations"
        relations_dir.mkdir(parents=True, exist_ok=True)
        active = {"version": version, "primary": primary, "fallback": fallback}
        (relations_dir / "active.json").write_text(json.dumps(active, ensure_ascii=False, indent=2), encoding="utf-8")
        (relations_dir / "current.json").write_text(json.dumps(relation, ensure_ascii=False, indent=2), encoding="utf-8")

    def update_index_pct(self) -> dict:
        """从 v1 index.html 解析真实指数涨跌数据，写入 v2/data/derived/index_pct.json。

        过渡期数据源：v1 build_nav_index.py 已用 akshare 拉取并渲染到 index.html，
        此方法解析该 HTML 提取每日期指数涨跌，作为 v2 侧边栏指数涨跌的真实数据来源。
        """
        import re
        from .config import V1_DATA_DIR
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            return {"status": "failed", "error": "beautifulsoup4 not installed"}

        index_html = Path(V1_DATA_DIR).parent / "index.html"
        if not index_html.exists():
            return {"status": "failed", "error": f"v1 index.html not found: {index_html}"}

        html = index_html.read_text(encoding="utf-8")
        soup = BeautifulSoup(html, "html.parser")
        results = []
        seen = {}
        for el in soup.find_all(string=lambda t: t and "上证" in t):
            container = el.parent
            for _ in range(5):
                if container.get("onclick") and "loadDate" in str(container.get("onclick")):
                    break
                container = container.parent
            onclick = container.get("onclick", "")
            m = re.search(r"loadDate\('(\d{4}-\d{2}-\d{2})'\)", onclick)
            if not m:
                continue
            date = m.group(1)
            text = container.get_text(" ", strip=True)
            sh = re.search(r"上证\s*([+-]?\d+\.?\d*)\s*%", text)
            kc = re.search(r"科创\s*([+-]?\d+\.?\d*)\s*%", text)
            cy = re.search(r"创业\s*([+-]?\d+\.?\d*)\s*%", text)
            seen[date] = {
                "date": date,
                "indices": {
                    "000001": {"name": "上证综指", "pct": float(sh.group(1)) if sh else 0.0},
                    "000688": {"name": "科创50", "pct": float(kc.group(1)) if kc else 0.0},
                    "399006": {"name": "创业板指", "pct": float(cy.group(1)) if cy else 0.0},
                },
            }
        final = sorted(seen.values(), key=lambda x: x["date"])
        out = self.data_dir / "derived" / "index_pct.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(final, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"status": "completed", "count": len(final), "path": str(out)}

    @staticmethod
    def _default_relation_version() -> str:
        iso = date.today().isocalendar()
        return f"{iso.year}-W{iso.week:02d}"

    @staticmethod
    def _latest_expected_trading_day(end_date: str):
        target = DataFetcher._to_timestamp(end_date)
        while target.weekday() >= 5:
            target = target - timedelta(days=1)
        return target

    @staticmethod
    def _to_timestamp(value: str):
        import pandas as pd

        return pd.to_datetime(value)

    @staticmethod
    def _default_end_date() -> str:
        return date.today().strftime("%Y%m%d")

    @staticmethod
    def _default_start_date(end_date: str) -> str:
        compact = end_date.replace("-", "")
        end = date(int(compact[:4]), int(compact[4:6]), int(compact[6:8]))
        return (end - timedelta(days=730)).strftime("%Y%m%d")
