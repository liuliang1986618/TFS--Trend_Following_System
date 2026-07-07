"""Data health and lifecycle checks for TFS v2."""

from __future__ import annotations

import json
from pathlib import Path

from .config import COMPLETENESS, DATA_DIR, VALID_DTYPES
from .storage import MarketDataStore


class LifecycleManager:
    """Check whether v2 data is usable by upper layers."""

    def __init__(self, data_dir: str | Path | None = None):
        self.data_dir = Path(data_dir or DATA_DIR)
        self.store = MarketDataStore(self.data_dir)

    def check_market_health(self, date: str | None = None) -> dict:
        checks = {}
        issues: list[str] = []
        for dtype in sorted(VALID_DTYPES):
            symbols = self.store.load_universe(dtype)
            latest_ok_count = 0
            checked_count = 0
            dtype_issues: list[str] = []
            for code in symbols:
                try:
                    df = self.store.load_daily(dtype, code)
                    checked_count += 1
                    if not df.empty:
                        latest = df["date"].iloc[-1].strftime("%Y-%m-%d")
                        if date is None or latest == date:
                            latest_ok_count += 1
                except Exception as exc:
                    dtype_issues.append(f"{code}: {exc}")
            expected_count = len(symbols)
            min_count = COMPLETENESS.get(f"{dtype}_min", 1)
            count_ok = expected_count >= min_count and checked_count >= min_count
            latest_date_ok = checked_count == latest_ok_count if checked_count else False
            status = "complete" if count_ok and latest_date_ok and not dtype_issues else "warning"
            issues_for_dtype = list(dtype_issues[:10])
            if expected_count < min_count:
                issues_for_dtype.append(f"expected_count {expected_count} below minimum {min_count}")
            checks[dtype] = {
                "status": status,
                "expected_count": expected_count,
                "actual_count": checked_count,
                "missing_count": max(expected_count - checked_count, 0),
                "latest_date_ok": latest_date_ok,
                "count_ok": count_ok,
                "min_count": min_count,
                "issues": issues_for_dtype,
            }
            if status != "complete":
                issues.append(f"{dtype} health is {status}")

        return {
            "date": date,
            "status": "complete" if not issues else "warning",
            "checks": checks,
            "allowed": {
                "stock_recommendation": checks.get("stock", {}).get("status") == "complete",
                "etf_recommendation": checks.get("etf", {}).get("status") == "complete",
                "sector_confirmation": checks.get("sector", {}).get("status") == "complete",
                "theme_confirmation": checks.get("theme", {}).get("status") == "complete",
            },
            "issues": issues,
        }

    def check_relation_health(self, relation_version: str | None = None) -> dict:
        current = self.data_dir / "meta" / "relations" / "current.json"
        if not current.exists():
            return {
                "version": relation_version,
                "status": "missing",
                "current_path": str(current),
                "checks": {},
                "issues": ["relation current.json missing"],
            }

        issues: list[str] = []
        try:
            relation = json.loads(current.read_text(encoding="utf-8"))
        except Exception as exc:
            return {
                "version": relation_version,
                "status": "warning",
                "current_path": str(current),
                "checks": {},
                "issues": [f"relation current.json unreadable: {exc}"],
            }
        if not isinstance(relation, dict):
            return {
                "version": relation_version,
                "status": "warning",
                "current_path": str(current),
                "checks": {},
                "issues": ["relation current.json must be object"],
            }

        actual_version = relation.get("version")
        if relation_version is not None and actual_version != relation_version:
            issues.append(f"relation version mismatch: expected {relation_version}, got {actual_version}")

        sectors = relation.get("sectors", [])
        themes = relation.get("themes", [])
        sector_members = relation.get("sector_members", {})
        theme_members = relation.get("theme_members", {})
        stock_profiles = relation.get("stock_profiles", {})
        checks = {
            "sector_count": len(sectors) if isinstance(sectors, list) else 0,
            "theme_count": len(themes) if isinstance(themes, list) else 0,
            "sector_member_groups": len(sector_members) if isinstance(sector_members, dict) else 0,
            "theme_member_groups": len(theme_members) if isinstance(theme_members, dict) else 0,
            "stock_profile_count": len(stock_profiles) if isinstance(stock_profiles, dict) else 0,
        }

        if checks["sector_count"] < COMPLETENESS["sector_min"]:
            issues.append(f"sector_count {checks['sector_count']} below minimum {COMPLETENESS['sector_min']}")
        if checks["theme_count"] < COMPLETENESS["theme_min"]:
            issues.append(f"theme_count {checks['theme_count']} below minimum {COMPLETENESS['theme_min']}")
        if checks["sector_member_groups"] < checks["sector_count"]:
            issues.append("sector member groups incomplete")
        if checks["theme_member_groups"] < checks["theme_count"]:
            issues.append("theme member groups incomplete")
        if not checks["stock_profile_count"]:
            issues.append("stock_profiles empty")

        if isinstance(sector_members, dict) and isinstance(stock_profiles, dict):
            for sector_code, members in sector_members.items():
                if not isinstance(members, list) or not members:
                    issues.append(f"sector {sector_code} has no members")
                    continue
                for stock_code in members[:20]:
                    profile = stock_profiles.get(stock_code, {})
                    if sector_code not in profile.get("sectors", []):
                        issues.append(f"{stock_code} missing sector reverse {sector_code}")
                        break
        if isinstance(theme_members, dict) and isinstance(stock_profiles, dict):
            for theme_code, members in theme_members.items():
                if not isinstance(members, list) or not members:
                    issues.append(f"theme {theme_code} has no members")
                    continue
                for stock_code in members[:20]:
                    profile = stock_profiles.get(stock_code, {})
                    if theme_code not in profile.get("themes", []):
                        issues.append(f"{stock_code} missing theme reverse {theme_code}")
                        break

        return {
            "version": actual_version,
            "source": relation.get("source"),
            "status": "complete" if not issues else "warning",
            "current_path": str(current),
            "checks": checks,
            "issues": issues[:50],
        }
