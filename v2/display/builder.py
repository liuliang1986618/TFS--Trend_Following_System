"""Display payload builder for TFS v2."""

from __future__ import annotations

from datetime import datetime


class DisplayPayloadBuilder:
    """Build structured display payloads without generating HTML."""

    def __init__(self, data_layer=None):
        self.data_layer = data_layer

    def build(
        self,
        date: str,
        run_id: str,
        signals: list | None = None,
        evaluation_report: dict | None = None,
        health: dict | None = None,
    ) -> dict:
        signals = list(signals or [])
        health = health or {}
        evaluation_report = evaluation_report or {}
        relation_names = self._relation_names()
        etf_names = self._etf_names()
        trade_plans = self._trade_plans(evaluation_report)
        data_pool = self._data_pool(evaluation_report, signals)
        leader_summary = self._leader_summary(signals, relation_names, etf_names)
        cards = []
        regions = []

        overview_cards = self._overview_cards(health, signals)
        cards.extend(overview_cards)
        regions.append(self._region("overview", "市场概览", [card["id"] for card in overview_cards]))

        ranked_signals = sorted(signals, key=lambda item: item.score, reverse=True)
        action_cards = [self._action_card(signal, etf_names, trade_plans.get(signal.code), data_pool) for signal in ranked_signals]
        action_cards_by_code = {card["id"].split("_")[-1]: card for card in action_cards}
        strong_cards = [action_cards_by_code[signal.code] for signal in ranked_signals if signal.score >= 85 and signal.code in action_cards_by_code]
        steady_cards = [action_cards_by_code[signal.code] for signal in ranked_signals if signal.score < 85 and signal.code in action_cards_by_code]
        if not steady_cards:
            steady_cards = strong_cards[3:]
            strong_cards = strong_cards[:3] if steady_cards else strong_cards
        cards.extend(action_cards)
        regions.append(self._region("strong_tracking", "强势追踪", [card["id"] for card in strong_cards]))
        regions.append(self._region("steady_recommend", "稳健推荐", [card["id"] for card in steady_cards]))

        sector_cards = self._sector_focus_cards(ranked_signals, relation_names, etf_names)
        cards.extend(sector_cards)
        regions.append(self._region("sector_focus", "焦点板块", [card["id"] for card in sector_cards]))

        signal_cards = [self._signal_card(signal, etf_names) for signal in ranked_signals]
        cards.extend(signal_cards)
        regions.append(self._region("signal_groups", "主线与关注", [card["id"] for card in signal_cards]))

        evaluation_cards = self._evaluation_cards(evaluation_report)
        cards.extend(evaluation_cards)
        regions.append(self._region("evaluation", "推演评估", [card["id"] for card in evaluation_cards]))

        return {
            "meta": {
                "date": date,
                "run_id": run_id,
                "source": "v2.display.builder",
                "created_at": datetime.now().isoformat(timespec="seconds"),
            },
            "overview": {"health": health},
            "regions": regions,
            "cards": cards,
            "signals": [self._signal_summary(signal, relation_names, etf_names) for signal in signals],
            "leader_summary": leader_summary,
            "data_pool": data_pool,
            "screening": {},
            "evaluation": evaluation_report,
            "nav": {},
            "warnings": self._health_warnings(health),
        }

    @staticmethod
    def _region(region_id: str, title: str, card_ids: list[str]) -> dict:
        return {"id": region_id, "title": title, "layout": "grid", "card_ids": card_ids}

    def _overview_cards(self, health: dict, signals: list) -> list[dict]:
        market_status = health.get("market", {}).get("status", "unknown")
        relation_status = health.get("relation", {}).get("status", "unknown")
        return [
            {
                "id": "metric_market_status",
                "type": "metric_card",
                "variant": "market",
                "status": market_status,
                "title": "市场状态",
                "subtitle": "market health",
                "metrics": [{"label": "状态", "value": market_status}],
                "body": {},
                "warnings": [],
            },
            {
                "id": "metric_signal_count",
                "type": "metric_card",
                "variant": "signals",
                "status": "complete",
                "title": "候选数量",
                "subtitle": "engine signals",
                "metrics": [
                    {"label": "总数", "value": len(signals)},
                    {"label": "关系", "value": relation_status},
                ],
                "body": {},
                "warnings": [],
            },
        ]

    def _action_card(self, signal, etf_names: dict, trade_plan: dict | None = None, data_pool: dict | None = None) -> dict:
        card_id = f"action_{signal.dtype}_{signal.code}"
        body = {
            "action_hint": signal.action_hint,
            "position_hint": signal.position_hint,
            "relations": signal.relations,
            "decision_data": self._symbol_decision_data(signal, data_pool or {}),
        }
        if trade_plan:
            body["trade_plan"] = trade_plan
        return {
            "id": card_id,
            "type": "action_card",
            "variant": signal.dtype,
            "status": "watch",
            "title": self._display_name(signal, etf_names),
            "subtitle": signal.code,
            "score": signal.score,
            "badges": [signal.state_label],
            "metrics": [
                {"label": "状态", "value": signal.state},
                {"label": "信心", "value": signal.confidence},
            ],
            "body": body,
            "risks": list(signal.risk_flags),
            "warnings": [],
        }

    def _sector_focus_cards(self, signals: list, relation_names: dict, etf_names: dict) -> list[dict]:
        grouped = {}
        for signal in signals:
            readable = self._readable_relations(signal.relations, relation_names)
            sector = readable.get("sector") or "未归类"
            group = grouped.setdefault(sector, {"sector": sector, "themes": set(), "leaders": [], "scores": [], "states": []})
            if readable.get("theme"):
                group["themes"].add(readable["theme"])
            trend_context = getattr(signal, "trend_context", {}) or {}
            indicators = getattr(signal, "indicators", {}) or {}
            leader = {
                "code": signal.code,
                "name": self._display_name(signal, etf_names),
                "score": signal.score,
                "state": signal.state_label,
                "reason": self._leader_reason(signal, readable),
                "pct_20d": trend_context.get("pct_20d"),
                "pct_60d": trend_context.get("pct_60d"),
                "vol_ratio": indicators.get("vol_ratio"),
            }
            group["leaders"].append(leader)
            group["scores"].append(signal.score)
            group["states"].append(str(signal.state))
        cards = []
        for index, group in enumerate(sorted(grouped.values(), key=lambda item: max(item["scores"]), reverse=True)[:3]):
            avg_score = sum(group["scores"]) / len(group["scores"])
            leaders = sorted(group["leaders"], key=lambda item: item["score"], reverse=True)
            continuation = min(0.82, max(0.45, avg_score / 100))
            pullback = max(0.12, min(0.40, 1 - continuation - 0.08))
            status_strip = group["states"][:5]
            key_metrics = self._sector_key_metrics(group, avg_score)
            cards.append(
                {
                    "id": f"sector_focus_{index}",
                    "type": "sector_focus_card",
                    "variant": "sector",
                    "status": "watch",
                    "title": group["sector"],
                    "subtitle": " / ".join(sorted(group["themes"])[:2]) or "板块焦点",
                    "score": round(avg_score, 1),
                    "badges": ["趋势共振", f"{len(group['leaders'])} 个标的"],
                    "metrics": [
                        {"label": "强度", "value": round(avg_score, 1)},
                        {"label": "标的", "value": len(group["leaders"])},
                        {"label": "最高分", "value": round(max(group["scores"]), 1)},
                    ],
                    "body": {
                        "status_strip": status_strip,
                        "key_metrics": key_metrics,
                        "projection": [
                            {"label": "延续", "probability": round(continuation, 2)},
                            {"label": "回踩", "probability": round(pullback, 2)},
                        ],
                        "leaders": leaders[:4],
                    },
                    "risks": [],
                    "warnings": [],
                }
            )
        return cards

    @staticmethod
    def _sector_key_metrics(group: dict, avg_score: float) -> list[dict]:
        leaders = group.get("leaders", [])
        pct_20d_values = [item.get("pct_20d") for item in leaders if isinstance(item.get("pct_20d"), (int, float))]
        pct_60d_values = [item.get("pct_60d") for item in leaders if isinstance(item.get("pct_60d"), (int, float))]
        vol_values = [item.get("vol_ratio") for item in leaders if isinstance(item.get("vol_ratio"), (int, float))]
        metrics = [
            {"label": "板块强度", "value": round(avg_score, 1)},
            {"label": "趋势标的", "value": len(leaders)},
        ]
        if pct_20d_values:
            metrics.append({"label": "20日均涨", "value": f"{sum(pct_20d_values) / len(pct_20d_values):.1f}%"})
        if pct_60d_values:
            metrics.append({"label": "60日均涨", "value": f"{sum(pct_60d_values) / len(pct_60d_values):.1f}%"})
        if vol_values:
            metrics.append({"label": "量能", "value": f"{sum(vol_values) / len(vol_values):.2f}x"})
        return metrics

    @staticmethod
    def _leader_reason(signal, readable_relations: dict) -> str:
        parts = [signal.state_label]
        if readable_relations.get("theme"):
            parts.append(readable_relations["theme"])
        trend_context = getattr(signal, "trend_context", {}) or {}
        if isinstance(trend_context, dict):
            stage = trend_context.get("stage")
            stage_label = {"early": "趋势初期", "continuation": "趋势延续", "late": "趋势后段"}.get(stage, stage)
            if stage_label:
                parts.append(stage_label)
        return " / ".join(str(part) for part in parts if part)

    def _signal_card(self, signal, etf_names: dict) -> dict:
        card_id = f"signal_{signal.dtype}_{signal.code}"
        return {
            "id": card_id,
            "type": "signal_card",
            "variant": signal.dtype,
            "status": "watch",
            "title": self._display_name(signal, etf_names),
            "subtitle": signal.code,
            "score": signal.score,
            "badges": [signal.state_label],
            "metrics": [
                {"label": "状态", "value": signal.state},
                {"label": "评分", "value": signal.score},
            ],
            "body": {
                "dtype": signal.dtype,
                "relations": signal.relations,
                "trend_context": signal.trend_context,
            },
            "risks": list(signal.risk_flags),
            "warnings": [],
        }

    @staticmethod
    def _trade_plans(evaluation_report: dict) -> dict:
        trade_plans = evaluation_report.get("trade_plans", {}) if isinstance(evaluation_report, dict) else {}
        return dict(trade_plans) if isinstance(trade_plans, dict) else {}

    @staticmethod
    def _data_pool(evaluation_report: dict, signals: list) -> dict:
        pool = evaluation_report.get("display_data_pool", {}) if isinstance(evaluation_report, dict) else {}
        symbols = dict(pool.get("symbols", {})) if isinstance(pool, dict) else {}
        for signal in signals:
            symbols.setdefault(
                signal.code,
                {
                    "trend_context": dict(getattr(signal, "trend_context", {}) or {}),
                    "key_levels": list((getattr(signal, "trend_context", {}) or {}).get("key_levels", [])),
                },
            )
        return {"symbols": symbols}

    @staticmethod
    def _symbol_decision_data(signal, data_pool: dict) -> dict:
        symbols = data_pool.get("symbols", {}) if isinstance(data_pool, dict) else {}
        data = dict(symbols.get(signal.code, {})) if isinstance(symbols.get(signal.code, {}), dict) else {}
        if "key_levels" not in data and isinstance(data.get("trend_context"), dict):
            data["key_levels"] = data["trend_context"].get("key_levels", [])
        return data

    @staticmethod
    def _evaluation_cards(evaluation_report: dict) -> list[dict]:
        if not evaluation_report:
            return [
                {
                    "id": "evaluation_empty",
                    "type": "empty_card",
                    "variant": "evaluation",
                    "status": "missing",
                    "title": "推演评估",
                    "subtitle": "暂无评估数据",
                    "metrics": [],
                    "body": {},
                    "warnings": ["evaluation report is empty"],
                }
            ]
        return [
            {
                "id": "evaluation_summary",
                "type": "metric_card",
                "variant": "evaluation",
                "status": "complete",
                "title": "推演评估",
                "subtitle": "evaluation summary",
                "metrics": [
                    {"label": "样本", "value": evaluation_report.get("total", 0)},
                    {"label": "准确率", "value": evaluation_report.get("exact_accuracy", "N/A")},
                ],
                "body": dict(evaluation_report),
                "warnings": [],
            }
        ]

    def _signal_summary(self, signal, relation_names: dict, etf_names: dict) -> dict:
        return {
            "code": signal.code,
            "name": self._display_name(signal, etf_names),
            "dtype": signal.dtype,
            "score": signal.score,
            "state": signal.state,
            "state_label": signal.state_label,
            "relations": self._readable_relations(signal.relations, relation_names),
            "risk_flags": list(signal.risk_flags),
        }

    def _relation_names(self) -> dict:
        if not self.data_layer or not hasattr(self.data_layer, "get_relation_names"):
            return {"sectors": {}, "themes": {}}
        names = self.data_layer.get_relation_names()
        return {
            "sectors": dict(names.get("sectors", {})),
            "themes": dict(names.get("themes", {})),
        }

    def _etf_names(self) -> dict:
        if not self.data_layer or not hasattr(self.data_layer, "get_etf_names"):
            return {}
        return dict(self.data_layer.get_etf_names())

    def _leader_summary(self, signals: list, relation_names: dict, etf_names: dict) -> dict:
        leaders = {"sector": "", "theme": "", "stock": "", "etf": ""}
        for signal in sorted(signals, key=lambda item: item.score, reverse=True):
            readable = self._readable_relations(signal.relations, relation_names)
            if not leaders["sector"]:
                leaders["sector"] = readable.get("sector", "")
            if not leaders["theme"]:
                leaders["theme"] = readable.get("theme", "")
            if signal.dtype == "stock" and not leaders["stock"]:
                leaders["stock"] = self._display_name(signal, etf_names)
            if signal.dtype == "etf" and not leaders["etf"]:
                leaders["etf"] = self._display_name(signal, etf_names)
        return leaders

    def _display_name(self, signal, etf_names: dict) -> str:
        if signal.dtype == "etf":
            return etf_names.get(signal.code) or signal.name
        if signal.dtype == "stock" and self.data_layer and hasattr(self.data_layer, "get_stock_profile"):
            profile = self.data_layer.get_stock_profile(signal.code)
            return profile.get("name") or signal.name
        return signal.name

    @staticmethod
    def _readable_relations(relations: dict, relation_names: dict) -> dict:
        if not isinstance(relations, dict):
            return {}
        sector = relations.get("sector") or DisplayPayloadBuilder._first_named(relations.get("sectors"), relation_names.get("sectors", {}))
        theme = relations.get("theme") or DisplayPayloadBuilder._first_named(relations.get("themes"), relation_names.get("themes", {}))
        result = dict(relations)
        if sector:
            result["sector"] = sector
        if theme:
            result["theme"] = theme
        return result

    @staticmethod
    def _first_named(codes, names: dict) -> str:
        if isinstance(codes, str):
            codes = [codes]
        for code in codes or []:
            name = names.get(code)
            if name:
                return name
        return ""

    @staticmethod
    def _health_warnings(health: dict) -> list[str]:
        warnings = []
        for key, item in health.items():
            if isinstance(item, dict) and item.get("status") not in (None, "complete"):
                warnings.append(f"{key} status is {item.get('status')}")
        return warnings
