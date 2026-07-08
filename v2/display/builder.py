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
        funnel_cards: list | None = None,
        all_signals: list | None = None,
    ) -> dict:
        signals = list(signals or [])
        all_signals = list(all_signals or signals)
        funnel_cards = list(funnel_cards or [])
        health = health or {}
        evaluation_report = evaluation_report or {}
        relation_names = self._relation_names()
        etf_names = self._etf_names()
        trade_plans = self._trade_plans(evaluation_report)
        data_pool = self._data_pool(evaluation_report, signals)
        leader_summary = self._leader_summary(signals, relation_names, etf_names)
        cards = []
        regions = []

        # 1. overview
        overview_cards = self._overview_cards(health, signals)
        cards.extend(overview_cards)
        regions.append(self._region("overview", "市场概览", [card["id"] for card in overview_cards]))

        # 2-3. steady_recommend + strong_tracking（action_card 改 details 折叠，限制各 top10=5ETF+5个股）
        ranked_signals = sorted(signals, key=lambda item: item.score, reverse=True)
        action_cards = [self._action_card(signal, etf_names, trade_plans.get(signal.code), data_pool) for signal in ranked_signals]
        action_cards_by_code = {card["id"].split("_")[-1]: card for card in action_cards}
        # 按 dtype 分组取 top5
        stock_strong = [s for s in ranked_signals if s.dtype == "stock" and s.score >= 85 and s.code in action_cards_by_code][:5]
        etf_strong = [s for s in ranked_signals if s.dtype == "etf" and s.score >= 85 and s.code in action_cards_by_code][:5]
        strong_signals = stock_strong + etf_strong
        stock_steady = [s for s in ranked_signals if s.dtype == "stock" and s.score < 85 and s.code in action_cards_by_code][:5]
        etf_steady = [s for s in ranked_signals if s.dtype == "etf" and s.score < 85 and s.code in action_cards_by_code][:5]
        steady_signals = stock_steady + etf_steady
        if not steady_signals and strong_signals:
            steady_signals = strong_signals[3:]
            strong_signals = strong_signals[:3]
        strong_cards = [action_cards_by_code[s.code] for s in strong_signals if s.code in action_cards_by_code]
        steady_cards = [action_cards_by_code[s.code] for s in steady_signals if s.code in action_cards_by_code]
        cards.extend(action_cards)
        regions.append(self._region("strong_tracking", "强势追踪", [card["id"] for card in strong_cards]))
        regions.append(self._region("steady_recommend", "稳健推荐", [card["id"] for card in steady_cards]))

        # 4. watchlist（静态读 watchlist.json）
        watchlist_cards = self._watchlist_cards()
        cards.extend(watchlist_cards)
        regions.append(self._region("watchlist", "特别关注", [card["id"] for card in watchlist_cards]))

        # 5. funnel_deep_dive（强势板块深度穿透 Top6）
        funnel_cards_display = self._funnel_deep_dive_cards(funnel_cards)
        cards.extend(funnel_cards_display)
        regions.append(self._region("funnel_deep_dive", "强势板块深度穿透", [card["id"] for card in funnel_cards_display]))

        # 6. focus_sectors（焦点板块，state∈{3,4} 去重漏斗后，完整指标版）
        focus_cards = self._focus_sector_cards(funnel_cards, signals, relation_names, etf_names)
        cards.extend(focus_cards)
        regions.append(self._region("focus_sectors", "焦点板块", [card["id"] for card in focus_cards]))

        # 7. observation（观察区，state==2 接近突破板块）
        observation_cards = self._observation_cards(signals, relation_names)
        cards.extend(observation_cards)
        regions.append(self._region("observation", "观察区", [card["id"] for card in observation_cards]))

        # 8. stock_table（趋势个股表，全量 state∈{3,4,5} 个股）
        stock_table_cards = self._stock_table_cards(all_signals, relation_names, etf_names)
        cards.extend(stock_table_cards)
        regions.append(self._region("stock_table", "趋势个股", [card["id"] for card in stock_table_cards]))

        # 9. etf_table（ETF直筛表）
        etf_table_cards = self._etf_table_cards(all_signals, etf_names)
        cards.extend(etf_table_cards)
        regions.append(self._region("etf_table", "ETF直筛", [card["id"] for card in etf_table_cards]))

        # 10. signal_groups（主线与关注，保留）
        signal_cards = [self._signal_card(signal, etf_names) for signal in ranked_signals]
        cards.extend(signal_cards)
        regions.append(self._region("signal_groups", "主线与关注", [card["id"] for card in signal_cards]))

        # 11. evaluation（推演评估，保留）
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
            "overview": {"health": health, "indices": self._overview_indices(date)},
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
        decision_data = self._symbol_decision_data(signal, data_pool or {})
        # 8 段 decision 数据，每段为 details 折叠项
        sections = self._action_sections(signal, decision_data, trade_plan)
        body = {
            "action_hint": signal.action_hint,
            "position_hint": signal.position_hint,
            "relations": signal.relations,
            "decision_data": decision_data,
            "sections": sections,
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

    @staticmethod
    def _action_sections(signal, decision_data: dict, trade_plan: dict | None) -> list[dict]:
        """构造 8 段 details 折叠项（对应 v1 的 6 Widget）。"""
        trend_ctx = decision_data.get("trend_context", {}) or {}
        today_pos = decision_data.get("today_position", {}) or {}
        strategy = decision_data.get("strategy_summary", "")
        projection = decision_data.get("projection", {}) or {}
        buy_sell = decision_data.get("buy_sell_zone", {}) or {}
        key_levels = decision_data.get("key_levels", []) or []
        watch_scn = decision_data.get("watch_scenarios", []) or []
        position_plan = decision_data.get("position_plan", []) or []
        sections = [
            {"key": "plan", "title": "操作计划", "summary": signal.action_hint, "data": trade_plan or {}},
            {"key": "trend", "title": "趋势大背景", "summary": trend_ctx.get("direction", ""), "data": trend_ctx},
            {"key": "today", "title": "今日定位", "summary": today_pos.get("label", ""), "data": today_pos},
            {"key": "strategy", "title": "策略总纲", "summary": strategy[:30] if strategy else "", "data": {"text": strategy}},
            {"key": "projection", "title": "明日行情推演", "summary": f"{len(projection.get('scenarios', []))} 场景", "data": projection},
            {"key": "zone", "title": "明日最佳买卖区间", "summary": "", "data": buy_sell},
            {"key": "levels", "title": "关键价位", "summary": f"{len(key_levels)} 个价位", "data": key_levels},
            {"key": "watch", "title": "盯盘场景", "summary": f"{len(watch_scn)} 个场景", "data": watch_scn},
            {"key": "position", "title": "仓位管理", "summary": f"{len(position_plan)} 步", "data": position_plan},
        ]
        return sections

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

    # ── Step 2 新增卡片方法 ─────────────────────────────────────

    def _overview_indices(self, date: str) -> list[dict]:
        """从 history.get_index_pct 取指数涨跌。"""
        if not self.data_layer or not hasattr(self.data_layer, "history"):
            return []
        pct = self.data_layer.history.get_index_pct(date)
        return [{"code": k, "name": v.get("name", k), "pct": v.get("pct", 0.0)} for k, v in pct.items()]

    def _watchlist_cards(self) -> list[dict]:
        """静态读 watchlist.json 渲染特别关注表格。"""
        import json
        from pathlib import Path
        items = []
        for p in [Path("watchlist.json"), Path("data/watchlist.json")]:
            if p.exists():
                try:
                    data = json.loads(p.read_text(encoding="utf-8"))
                    items = data.get("stocks", data) if isinstance(data, dict) else data
                    break
                except Exception:
                    pass
        return [{
            "id": "watchlist_card",
            "type": "watchlist_card",
            "variant": "watchlist",
            "status": "info",
            "title": "特别关注",
            "subtitle": f"{len(items)} 只关注",
            "metrics": [{"label": "数量", "value": len(items)}],
            "body": {"items": [{"code": str(it.get("code", "")), "name": str(it.get("name", it.get("code", "")))} for it in items if isinstance(it, dict)]},
            "risks": [],
            "warnings": [] if items else ["关注列表为空"],
        }]

    def _funnel_deep_dive_cards(self, funnel_cards: list) -> list[dict]:
        """强势板块深度穿透 Top6（从 engine.funnel.scan_stock_funnel 的 funnel_cards 取）。"""
        cards = []
        for idx, fc in enumerate(funnel_cards[:6]):
            abc = fc.get("abc", {}) or {}
            best_etf = fc.get("best_etf") or {}
            leaders = fc.get("leaders", []) or []
            stats = fc.get("sector_stats", {}) or {}
            cards.append({
                "id": f"funnel_deep_dive_{idx}",
                "type": "funnel_deep_dive_card",
                "variant": "sector",
                "status": "watch",
                "title": fc.get("name", fc.get("code", "")),
                "subtitle": fc.get("code", ""),
                "score": round(fc.get("top_score", 0), 1),
                "badges": [f"Top{idx+1}", f"{fc.get('candidate_count', 0)} 标的"],
                "metrics": [
                    {"label": "候选", "value": fc.get("candidate_count", 0)},
                    {"label": "最高分", "value": round(fc.get("top_score", 0), 1)},
                ],
                "body": {
                    "abc": abc,
                    "best_etf": best_etf,
                    "leaders": leaders,
                    "recent_states": fc.get("recent_states", []),
                    "recent_scores": fc.get("recent_scores", []),
                    "sector_stats": stats,
                },
                "risks": [],
                "warnings": [],
            })
        return cards

    def _focus_sector_cards(self, funnel_cards: list, signals: list, relation_names: dict, etf_names: dict) -> list[dict]:
        """焦点板块（state∈{3,4} 去重漏斗后，完整指标版）。"""
        # 从 funnel_cards 取 state∈{3,4} 的板块
        focus = []
        funnel_codes = {fc.get("code") for fc in funnel_cards}
        for fc in funnel_cards:
            abc = fc.get("abc", {}) or {}
            state = abc.get("state")
            if state not in (3, 4):
                continue
            stats = fc.get("sector_stats", {}) or {}
            best_etf = fc.get("best_etf") or {}
            leaders = fc.get("leaders", []) or []
            # 从 signals 补该板块的候选个股
            sector_code = fc.get("code", "")
            sector_name = fc.get("name", sector_code)
            sector_signals = [s for s in signals if sector_code in (s.relations or {}).get("sectors", []) or sector_name == (s.relations or {}).get("sector")]
            # 板块完整指标
            pct_20d = abc.get("pct_20d", 0)
            vol_ratio = abc.get("vol_ratio", 1.0)
            continuation = min(0.82, max(0.45, (fc.get("top_score", 50)) / 100))
            pullback = max(0.12, min(0.40, 1 - continuation - 0.08))
            focus.append({
                "id": f"focus_sector_{sector_code}",
                "type": "focus_sector_card",
                "variant": "sector",
                "status": "watch",
                "title": sector_name,
                "subtitle": sector_code,
                "score": round(fc.get("top_score", 0), 1),
                "badges": [abc.get("structure", "")[:6], f"20日 {pct_20d:+.1f}%"],
                "metrics": [
                    {"label": "强度", "value": round(fc.get("top_score", 0), 1)},
                    {"label": "标的", "value": fc.get("candidate_count", 0)},
                    {"label": "持续", "value": stats.get("streak_days", "-")},
                ],
                "body": {
                    "abc": abc,
                    "best_etf": best_etf,
                    "leaders": leaders,
                    "recent_states": fc.get("recent_states", []),
                    "recent_scores": fc.get("recent_scores", []),
                    "sector_stats": stats,
                    "projection": [
                        {"label": "延续", "probability": round(continuation, 2)},
                        {"label": "回踩", "probability": round(pullback, 2)},
                    ],
                    "pct_20d": pct_20d,
                    "vol_ratio": vol_ratio,
                    "avg_uptrend_days": stats.get("avg_uptrend_days"),
                    "max_uptrend_days": stats.get("max_uptrend_days"),
                    "tomorrow_prob": stats.get("tomorrow_prob"),
                    "expected_return": stats.get("expected_return"),
                    "up_probability": stats.get("up_probability"),
                },
                "risks": [],
                "warnings": [],
            })
        return focus

    def _observation_cards(self, signals: list, relation_names: dict) -> list[dict]:
        """观察区（state==2 接近突破板块）。"""
        # 按板块分组 state==2 的个股
        groups: dict[str, dict] = {}
        for signal in signals:
            if signal.state != 2:
                continue
            readable = self._readable_relations(signal.relations, relation_names)
            sector = readable.get("sector") or "未归类"
            group = groups.setdefault(sector, {"sector": sector, "leaders": [], "scores": []})
            group["leaders"].append({"code": signal.code, "name": signal.name, "score": signal.score})
            group["scores"].append(signal.score)
        cards = []
        for sector, group in sorted(groups.items(), key=lambda x: max(x[1]["scores"]) if x[1]["scores"] else 0, reverse=True)[:5]:
            cards.append({
                "id": f"observation_{sector}",
                "type": "observation_card",
                "variant": "sector",
                "status": "info",
                "title": sector,
                "subtitle": "反弹中",
                "score": round(max(group["scores"]), 1) if group["scores"] else 0,
                "badges": ["观察区", f"{len(group['leaders'])} 标的"],
                "metrics": [{"label": "标的", "value": len(group["leaders"])}],
                "body": {"leaders": group["leaders"][:5]},
                "risks": [],
                "warnings": [],
            })
        return cards

    def _stock_table_cards(self, all_signals: list, relation_names: dict, etf_names: dict) -> list[dict]:
        """趋势个股表（全量 state∈{3,4,5} 个股）。"""
        rows = []
        for signal in all_signals:
            if signal.dtype != "stock":
                continue
            if signal.state not in (3, 4, 5):
                continue
            readable = self._readable_relations(signal.relations, relation_names)
            indicators = getattr(signal, "indicators", {}) or {}
            rows.append({
                "code": signal.code,
                "name": signal.name,
                "sector": readable.get("sector", ""),
                "theme": readable.get("theme", ""),
                "state": signal.state,
                "state_label": signal.state_label,
                "score": round(signal.score, 1),
                "pct_20d": round(indicators.get("pct_20d", 0), 1),
                "vol_ratio": round(indicators.get("vol_ratio", 1.0), 2),
            })
        rows.sort(key=lambda x: x["score"], reverse=True)
        return [{
            "id": "stock_table_card",
            "type": "stock_table_card",
            "variant": "stock",
            "status": "watch",
            "title": "趋势个股",
            "subtitle": f"{len(rows)} 只",
            "metrics": [{"label": "数量", "value": len(rows)}],
            "body": {"rows": rows, "columns": ["code", "name", "sector", "theme", "state", "state_label", "score", "pct_20d", "vol_ratio"]},
            "risks": [],
            "warnings": [] if rows else ["无趋势个股"],
        }]

    def _etf_table_cards(self, all_signals: list, etf_names: dict) -> list[dict]:
        """ETF直筛表（全量 ETF signals）。"""
        rows = []
        for signal in all_signals:
            if signal.dtype != "etf":
                continue
            indicators = getattr(signal, "indicators", {}) or {}
            rows.append({
                "code": signal.code,
                "name": signal.name,
                "state": signal.state,
                "state_label": signal.state_label,
                "score": round(signal.score, 1),
                "pct_20d": round(indicators.get("pct_20d", 0), 1),
                "vol_ratio": round(indicators.get("vol_ratio", 1.0), 2),
            })
        rows.sort(key=lambda x: x["score"], reverse=True)
        return [{
            "id": "etf_table_card",
            "type": "etf_table_card",
            "variant": "etf",
            "status": "watch",
            "title": "ETF直筛",
            "subtitle": f"{len(rows)} 只",
            "metrics": [{"label": "数量", "value": len(rows)}],
            "body": {"rows": rows, "columns": ["code", "name", "state", "state_label", "score", "pct_20d", "vol_ratio"]},
            "risks": [],
            "warnings": [] if rows else ["无ETF信号"],
        }]
