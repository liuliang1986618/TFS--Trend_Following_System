"""Single renderer boundary for TFS v2 display outputs."""

from __future__ import annotations

import html
import json
import shutil
from pathlib import Path

from .schema import validate_display_payload, validate_nav_payload


class DisplayRenderer:
    """Render v2 display payloads through the single display entrypoint."""

    CARD_TEMPLATE_DIR = Path(__file__).parent / "templates" / "cards"
    ASSET_DIR = Path(__file__).parent / "assets"

    def render_daily(self, payload_path: str, output_path: str) -> str:
        payload = self._read_json(payload_path)
        view = validate_display_payload(payload)
        cards_by_id = view["cards_by_id"]
        sections = []
        for region in view["regions"]:
            rendered_cards = [self._render_card(cards_by_id[card_id]) for card_id in region["card_ids"]]
            sections.append(
                "\n".join(
                    [
                        f'<section class="display-region" data-region="{self._escape(region["id"])}">',
                        '  <header class="display-region__header">',
                        '    <div class="display-region__title">',
                        f'      <h2>{self._escape(region["title"])}</h2>',
                        f'      <p>{self._escape(self._region_caption(region["id"]))}</p>',
                        '    </div>',
                        f'    <span class="display-region__count">{len(rendered_cards)} 张卡片</span>',
                        '  </header>',
                        '  <div class="display-card-grid">',
                        *[f"    {card}" for card in rendered_cards],
                        "  </div>",
                        "</section>",
                    ]
                )
            )
        meta = view["meta"]
        html_text = self._page(
            title=f'TFS {meta["date"]}',
            body="\n".join(
                [
                    '<main class="daily-dashboard">',
                    f'  <h1>趋势跟随 {self._escape(meta["date"])}</h1>',
                    *sections,
                    "</main>",
                ]
            ),
        )
        self._copy_assets(output_path)
        return self._write(output_path, html_text)

    def render_index(self, nav_payload_path: str, output_path: str) -> str:
        nav_payload = validate_nav_payload(self._read_json(nav_payload_path))
        cards = "\n".join(self._render_date_nav_card(item) for item in nav_payload["items"])
        default_date = nav_payload.get("default_date") or ""
        iframe_src = f"trend_dashboard_{default_date}.html" if default_date else ""
        report_count = nav_payload.get("report_count", 0)
        sidebar_header = (
            '<div class="sidebar-inner">'
            '<div class="sidebar-header">'
            '<button class="sidebar-toggle" onclick="toggleSidebar()">◀</button>'
            '<h1>📊 趋势跟随</h1>'
            f'<div class="sub">{report_count} 个交易日</div>'
            '</div>'
            '<div class="sidebar-list">'
            f'{cards}'
            '</div>'
            '</div>'
        )
        body = "\n".join(
            [
                f'<div class="display-shell" data-default-date="{self._escape(default_date)}">',
                f'  <aside class="display-sidebar">{sidebar_header}</aside>',
                f'  <section class="display-frame-wrap"><iframe src="{iframe_src}"></iframe></section>',
                "</div>",
            ]
        )
        self._copy_assets(output_path)
        return self._write(output_path, self._page(title="TFS Dashboard", body=body))

    def render_index_bundle(self, nav_payload_path: str, daily_html_paths: list[str], output_dir: str) -> str:

        output = Path(output_dir)
        output.mkdir(parents=True, exist_ok=True)
        for daily_path in daily_html_paths:
            source = Path(daily_path)
            shutil.copy2(source, output / source.name)
        return self.render_index(nav_payload_path, str(output / "index.html"))

    @staticmethod
    def _region_caption(region_id: str) -> str:
        captions = {
            "overview": "数据完整性与候选池概览",
            "strong_tracking": "高分趋势标的，优先盯盘与仓位跟踪",
            "steady_recommend": "回调确认与低风险延续机会",
            "sector_focus": "板块共振、概率推演与龙头线索",
            "signal_groups": "入选主线、题材关系与评分分布",
            "evaluation": "推演命中与样本验证摘要",
        }
        return captions.get(region_id, "结构化卡片区")

    def _render_card(self, card: dict) -> str:
        card_type = card.get("type", "empty_card")
        if card_type == "action_card":
            body_text = self._render_action_body(card.get("body", {}))
        elif card_type == "metric_card":
            body_text = self._render_metrics(card.get("metrics", []))
        elif card_type == "signal_card":
            body_text = self._render_signal_body(card)
        elif card_type == "sector_focus_card":
            body_text = self._render_sector_focus_body(card.get("body", {}))
        elif card_type == "watchlist_card":
            body_text = self._render_watchlist_body(card.get("body", {}))
        elif card_type == "funnel_deep_dive_card":
            body_text = self._render_funnel_deep_dive_body(card.get("body", {}))
        elif card_type == "focus_sector_card":
            body_text = self._render_focus_sector_body(card.get("body", {}))
        elif card_type == "observation_card":
            body_text = self._render_observation_body(card.get("body", {}))
        elif card_type == "stock_table_card":
            body_text = self._render_table_body(card.get("body", {}), "stock")
        elif card_type == "etf_table_card":
            body_text = self._render_table_body(card.get("body", {}), "etf")
        else:
            body_text = self._compact(card.get("body") or card.get("metrics") or card.get("subtitle") or "")
        context = {
            "card_type": card_type,
            "title": card.get("title", ""),
            "subtitle": card.get("subtitle", ""),
            "body": body_text,
            "score": self._score_text(card.get("score", "")),
            "metrics": self._render_metrics(card.get("metrics", [])),
            "badges": " ".join(f'<span class="display-badge">{self._escape(item)}</span>' for item in card.get("badges", [])),
            "risks": " ".join(f'<span class="display-risk">{self._escape(item)}</span>' for item in card.get("risks", [])),
        }
        return self._render_template(self.CARD_TEMPLATE_DIR / f"{card_type}.html", context)

    def _render_action_body(self, body: dict) -> str:
        if not isinstance(body, dict):
            return ""
        # 优先用 builder 准备好的 sections（details 折叠结构）
        sections = body.get("sections") or []
        if sections:
            return self._render_action_sections(sections)
        # 兼容旧格式：从 decision_data 重新构造
        decision_data = body.get("decision_data") if isinstance(body.get("decision_data"), dict) else {}
        trade_plan = body.get("trade_plan") if isinstance(body.get("trade_plan"), dict) else None
        parts = []
        parts.append(self._action_summary(body, trade_plan))
        parts.append(self._decision_section("趋势大背景", self._trend_context_text(decision_data.get("trend_context", {})), "trend"))
        parts.append(self._decision_section("今日定位", self._today_position_text(decision_data.get("today_position", {})), "today"))
        parts.append(self._decision_section("策略总纲", decision_data.get("strategy_summary", ""), "strategy"))
        parts.append(self._decision_section("明日行情推演", self._projection_items(decision_data.get("projection", {})), "projection", "list"))
        parts.append(self._decision_section("明日最佳买卖区间", self._buy_sell_zone_items(decision_data.get("buy_sell_zone", {})), "zone", "zones"))
        parts.append(self._decision_section("关键价位", self._key_level_items(decision_data.get("key_levels", [])), "levels", "levels"))
        parts.append(self._decision_section("盯盘场景", self._watch_scenario_items(decision_data.get("watch_scenarios", [])), "watch", "list"))
        parts.append(self._decision_section("仓位管理", self._position_plan_items(decision_data.get("position_plan", [])), "position", "list"))
        return "".join(part for part in parts if part)

    def _render_action_sections(self, sections: list) -> str:
        """渲染 8 段 details 折叠项（对应 v1 的 6 Widget）。"""
        html_parts = []
        for section in sections:
            if not isinstance(section, dict):
                continue
            key = section.get("key", "")
            title = self._escape(section.get("title", ""))
            summary = self._escape(section.get("summary", ""))
            data = section.get("data", {})
            content = self._render_section_content(key, data)
            if not content and not summary:
                continue
            summary_html = f'<span class="widget-summary">{summary}</span>' if summary else ""
            html_parts.append(
                f'<details class="widget-details action-card__section action-card__section--{self._escape(key)}">'
                f'<summary>{title}{summary_html}</summary>'
                f'<div class="widget-content">{content}</div>'
                f'</details>'
            )
        return "".join(html_parts)

    def _render_section_content(self, key: str, data) -> str:
        """按 section key 渲染内容。"""
        if key == "plan":
            if not isinstance(data, dict) or not data:
                return ""
            target = f"目标仓位 {self._pct(data.get('target_position_pct'))}" if data.get("target_position_pct") is not None else ""
            triggers = data.get("triggers", []) or []
            rows = []
            for trigger in triggers:
                if not isinstance(trigger, dict):
                    continue
                action = self._action_label(trigger.get("action_type", ""))
                position = self._pct(trigger.get("target_position_pct"))
                label = " ".join(str(x) for x in [trigger.get("scenario_label", ""), action, position] if x)
                conditions = "、".join(str(x) for x in trigger.get("trigger_conditions", []) if x)
                rows.append(self._pill_row(label, conditions))
            content = f'<div class="action-card__plan-lead">{self._escape(target)}</div>' if target else ""
            content += self._list_block(rows)
            return content
        if key == "trend":
            return self._trend_context_text(data if isinstance(data, dict) else {})
        if key == "today":
            return self._today_position_text(data if isinstance(data, dict) else {})
        if key == "strategy":
            text = data.get("text", "") if isinstance(data, dict) else str(data)
            return f'<p>{self._escape(text)}</p>' if text else ""
        if key == "projection":
            return self._projection_items(data if isinstance(data, dict) else {})
        if key == "zone":
            return self._buy_sell_zone_items(data if isinstance(data, dict) else {})
        if key == "levels":
            return self._key_level_items(data if isinstance(data, list) else [])
        if key == "watch":
            return self._watch_scenario_items(data if isinstance(data, list) else [])
        if key == "position":
            return self._position_plan_items(data if isinstance(data, list) else [])
        return ""

    def _action_summary(self, body: dict, trade_plan: dict | None) -> str:
        lead = body.get("action_hint", "")
        target = ""
        trigger_rows = []
        if trade_plan:
            target = f"目标仓位 {self._pct(trade_plan.get('target_position_pct'))}"
            for trigger in trade_plan.get("triggers", []):
                if not isinstance(trigger, dict):
                    continue
                action = self._action_label(trigger.get("action_type", ""))
                position = self._pct(trigger.get("target_position_pct"))
                label = " ".join(str(item) for item in [trigger.get("scenario_label", ""), action, position] if item)
                conditions = "、".join(str(item) for item in trigger.get("trigger_conditions", []) if item)
                trigger_rows.append(self._pill_row(label, conditions))
        summary = " / ".join(str(item) for item in [lead, target] if item)
        content = "".join(
            [
                f'<div class="action-card__plan-lead">{self._escape(summary)}</div>' if summary else "",
                self._list_block(trigger_rows),
            ]
        )
        return self._decision_section("操作计划", content, "plan", "html")

    def _decision_section(self, title: str, content, section_type: str = "default", content_kind: str = "text") -> str:
        if not content:
            return ""
        extra_class = " action-card__levels" if section_type == "levels" else ""
        rendered = content if isinstance(content, str) and content.startswith("<") else f'<p>{self._escape(content)}</p>'
        if content_kind == "text" and isinstance(content, str) and not content.startswith("<"):
            rendered = f'<p>{self._escape(content)}</p>'
        return f'<section class="action-card__section action-card__section--{self._escape(section_type)}{extra_class}"><h3>{self._escape(title)}</h3>{rendered}</section>'

    def _render_metrics(self, metrics) -> str:
        if not isinstance(metrics, list):
            return self._escape(self._compact(metrics))
        items = []
        for metric in metrics:
            if not isinstance(metric, dict):
                continue
            label = metric.get("label", "")
            value = metric.get("value", "")
            items.append(
                f'<span class="metric-card__item"><small>{self._escape(label)}</small><strong>{self._escape(value)}</strong></span>'
            )
        return "".join(items)

    def _render_signal_body(self, card: dict) -> str:
        body = card.get("body", {}) if isinstance(card.get("body"), dict) else {}
        relations = body.get("relations", {}) if isinstance(body.get("relations"), dict) else {}
        relation_text = " / ".join(str(value) for value in relations.values() if value)
        metrics = self._render_metrics(card.get("metrics", []))
        parts = [metrics]
        if relation_text:
            parts.append(f'<p class="signal-card__relations">{self._escape(relation_text)}</p>')
        return "".join(parts)

    def _render_sector_focus_body(self, body: dict) -> str:
        if not isinstance(body, dict):
            return ""
        strip = "".join(f'<span>{self._escape(item)}</span>' for item in body.get("status_strip", []) if item)
        metrics = []
        for item in body.get("key_metrics", []):
            if isinstance(item, dict):
                metrics.append(self._pill_row(str(item.get("label", "")), str(item.get("value", ""))))
        projections = []
        for item in body.get("projection", []):
            if isinstance(item, dict):
                pct = self._pct(item.get("probability")) if item.get("probability") is not None else ""
                projections.append(self._pill_row(str(item.get("label", "")), pct))
        leaders = []
        for leader in body.get("leaders", []):
            if isinstance(leader, dict):
                leader_meta = " / ".join(str(item) for item in [leader.get("code", ""), self._score_text(leader.get("score", "")), leader.get("reason", "")] if item)
                leaders.append(self._pill_row(str(leader.get("name", "")), leader_meta))
        return "".join(
            [
                f'<div class="sector-focus-card__strip">{strip}</div>' if strip else "",
                self._sector_block("核心指标", "sector-focus-card__metrics", self._list_block(metrics)) if metrics else "",
                self._sector_block("明日推演", "sector-focus-card__projection", self._list_block(projections)) if projections else "",
                self._sector_block("龙头线索", "sector-focus-card__leaders", self._list_block(leaders)) if leaders else "",
            ]
        )

    def _sector_block(self, title: str, class_name: str, content: str) -> str:
        return f'<section class="sector-focus-card__block {self._escape(class_name)}"><h3>{self._escape(title)}</h3>{content}</section>'

    @staticmethod
    def _trend_context_text(value: dict) -> str:
        if not isinstance(value, dict):
            return ""
        direction = value.get("direction") or value.get("state_family")
        if direction == "uptrend":
            direction = "上升趋势"
        elif direction == "defensive":
            direction = "防御状态"
        stage = value.get("stage")
        stage_label = {"early": "趋势初期", "continuation": "趋势延续", "late": "趋势后段"}.get(stage, stage)
        parts = [
            direction,
            stage_label,
            f"已运行 {value.get('days_running')} 天" if value.get("days_running") is not None else "",
            f"累计 {value.get('total_return_pct')}%" if value.get("total_return_pct") is not None else "",
            f"20日 {float(value.get('pct_20d')):.1f}%" if isinstance(value.get("pct_20d"), (int, float)) else "",
            f"60日 {float(value.get('pct_60d')):.1f}%" if isinstance(value.get("pct_60d"), (int, float)) else "",
            value.get("ma_status"),
        ]
        return " / ".join(str(item) for item in parts if item)

    @staticmethod
    def _today_position_text(value: dict) -> str:
        if not isinstance(value, dict):
            return ""
        return " / ".join(str(item) for item in [value.get("label"), value.get("narrative")] if item)

    def _projection_items(self, value: dict) -> str:
        if not isinstance(value, dict):
            return ""
        items = []
        for scenario in value.get("scenarios", []):
            if not isinstance(scenario, dict):
                continue
            probability = scenario.get("probability")
            pct = f"{float(probability) * 100:.0f}%" if isinstance(probability, (int, float)) else scenario.get("probability_label", "")
            label = " ".join(str(item) for item in [scenario.get("label"), scenario.get("title")] if item)
            meta = " ".join(str(item) for item in [pct, scenario.get("range")] if item)
            items.append(self._pill_row(label, meta))
        return self._list_block(items)

    def _buy_sell_zone_items(self, value: dict) -> str:
        if not isinstance(value, dict):
            return ""
        buy = value.get("buy_zone", {}) if isinstance(value.get("buy_zone"), dict) else {}
        sell = value.get("sell_zone", {}) if isinstance(value.get("sell_zone"), dict) else {}
        items = []
        if buy:
            items.append(self._zone_item("买入区", f"{buy.get('low')} ~ {buy.get('high')}", buy.get("logic", "")))
        if sell:
            items.append(self._zone_item("卖出区", f"{sell.get('low')} ~ {sell.get('high')}", sell.get("logic", "")))
        return f'<div class="action-card__zone-grid">{"".join(items)}</div>' if items else ""

    def _key_level_items(self, value: list) -> str:
        if not isinstance(value, list):
            return ""
        items = []
        for item in value:
            if isinstance(item, dict) and item.get("label"):
                items.append(self._pill_row(str(item.get("label")), str(item.get("price", ""))))
        return self._list_block(items)

    def _watch_scenario_items(self, value: list) -> str:
        if not isinstance(value, list):
            return ""
        items = []
        for item in value:
            if not isinstance(item, dict):
                continue
            signals = "、".join(str(signal) for signal in item.get("signals", []) if signal)
            position = self._pct(item.get("position_pct")) if item.get("position_pct") is not None else ""
            action = self._action_label(item.get("action", ""))
            label = " ".join(str(part) for part in [item.get("level"), action, position] if part)
            items.append(self._pill_row(label, signals))
        return self._list_block(items)

    def _position_plan_items(self, value: list) -> str:
        if not isinstance(value, list):
            return ""
        items = []
        for item in value:
            if not isinstance(item, dict):
                continue
            target = self._pct(item.get("target_position_pct")) if item.get("target_position_pct") is not None else ""
            label = " ".join(str(part) for part in [item.get("step"), target] if part)
            items.append(self._pill_row(label, item.get("condition", "")))
        return self._list_block(items)

    def _list_block(self, items: list[str]) -> str:
        return f'<div class="action-card__list">{"".join(items)}</div>' if items else ""

    def _pill_row(self, label: str, value: str) -> str:
        return f'<div class="action-card__row"><strong>{self._escape(label)}</strong><span>{self._escape(value)}</span></div>'

    def _zone_item(self, label: str, price: str, logic: str) -> str:
        return f'<div class="action-card__zone"><small>{self._escape(label)}</small><strong>{self._escape(price)}</strong><span>{self._escape(logic)}</span></div>'

    # ── Step 3 新增渲染方法 ─────────────────────────────────────

    def _render_5d_state_bar(self, states: list) -> str:
        """渲染 5d 状态条（5个色点）。"""
        if not states:
            return ""
        dots = []
        for s in states[-5:]:
            cls = {4: "state-up", 5: "state-up", 3: "state-mid", 2: "state-down", 1: "state-down"}.get(s, "state-mid")
            if s == "3'":
                cls = "state-risk"
            dots.append(f'<span class="state-dot {cls}" title="{self._escape(str(s))}"></span>')
        return f'<span class="state-bar-5d">{"".join(dots)}</span>'

    def _render_sparkline(self, scores: list) -> str:
        """渲染 sparkline SVG（5日得分折线）。"""
        if not scores or len(scores) < 2:
            return ""
        vals = [float(s) for s in scores[-5:] if s is not None]
        if len(vals) < 2:
            return ""
        w, h = 80, 18
        mn, mx = min(vals), max(vals)
        rng = mx - mn if mx > mn else 1
        pts = []
        for i, v in enumerate(vals):
            x = (w / (len(vals) - 1)) * i
            y = h - ((v - mn) / rng) * h
            pts.append(f"{x:.1f},{y:.1f}")
        return f'<svg class="sparkline" width="{w}" height="{h}" viewBox="0 0 {w} {h}"><polyline points="{" ".join(pts)}" fill="none" stroke="#06b6d4" stroke-width="1.5"/></svg>'

    def _render_watchlist_body(self, body: dict) -> str:
        items = body.get("items", []) if isinstance(body, dict) else []
        if not items:
            return '<p class="empty-state">关注列表为空</p>'
        rows = []
        for item in items:
            code = self._escape(str(item.get("code", "")))
            name = self._escape(str(item.get("name", "")))
            rows.append(f'<tr><td>{name}</td><td>{code}</td></tr>')
        return f'<table class="watchlist-table"><thead><tr><th>标的</th><th>代码</th></tr></thead><tbody>{"".join(rows)}</tbody></table>'

    def _render_funnel_deep_dive_body(self, body: dict) -> str:
        if not isinstance(body, dict):
            return ""
        abc = body.get("abc", {}) or {}
        best_etf = body.get("best_etf") or {}
        leaders = body.get("leaders", []) or []
        recent_states = body.get("recent_states", [])
        recent_scores = body.get("recent_scores", [])
        parts = []
        # ABC 三条件
        abc_lines = []
        for key, label in [("structure", "A 结构"), ("volume", "B 量能"), ("persistence", "C 持续性")]:
            text = abc.get(key, "")
            if text:
                abc_lines.append(f'<div class="funnel-abc-line">{self._escape(text)}</div>')
        if abc_lines:
            parts.append(f'<div class="funnel-abc">{"".join(abc_lines)}</div>')
        # 5d 状态条 + sparkline
        bar = self._render_5d_state_bar(recent_states)
        spark = self._render_sparkline(recent_scores)
        if bar or spark:
            parts.append(f'<div class="funnel-trend-strip">{bar}{spark}</div>')
        # 最佳 ETF
        if best_etf:
            etf_name = self._escape(str(best_etf.get("name", "")))
            etf_score = self._score_text(best_etf.get("score", ""))
            parts.append(f'<div class="funnel-best-etf"><span>📊 最佳ETF: </span><strong>{etf_name}</strong> <span>{etf_score}</span></div>')
        # 龙头
        if leaders:
            leader_items = []
            for ld in leaders[:3]:
                name = self._escape(str(ld.get("name", ld.get("code", ""))))
                score = self._score_text(ld.get("score", ""))
                leader_items.append(f'<span class="funnel-leader">{name} <sup>{score}</sup></span>')
            parts.append(f'<div class="funnel-leaders">{"".join(leader_items)}</div>')
        return "".join(parts)

    def _render_focus_sector_body(self, body: dict) -> str:
        if not isinstance(body, dict):
            return ""
        abc = body.get("abc", {}) or {}
        best_etf = body.get("best_etf") or {}
        leaders = body.get("leaders", []) or []
        recent_states = body.get("recent_states", [])
        recent_scores = body.get("recent_scores", [])
        projection = body.get("projection", []) or []
        sector_stats = body.get("sector_stats", {}) or {}
        parts = []
        # 5d 状态条 + sparkline
        bar = self._render_5d_state_bar(recent_states)
        spark = self._render_sparkline(recent_scores)
        if bar or spark:
            parts.append(f'<div class="focus-trend-strip">{bar}{spark}</div>')
        # 推演概率
        if projection:
            proj_items = []
            for p in projection:
                label = self._escape(str(p.get("label", "")))
                prob = p.get("probability", 0)
                pct = f"{prob*100:.0f}%" if isinstance(prob, (int, float)) else str(prob)
                proj_items.append(f'<span class="focus-proj-item">{label} {self._escape(pct)}</span>')
            parts.append(f'<div class="focus-projection">{"".join(proj_items)}</div>')
        # ABC
        abc_lines = []
        for key, label in [("structure", "A 结构"), ("volume", "B 量能"), ("persistence", "C 持续性")]:
            text = abc.get(key, "")
            if text:
                abc_lines.append(f'<div class="focus-abc-line">{self._escape(text)}</div>')
        if abc_lines:
            parts.append(f'<div class="focus-abc">{"".join(abc_lines)}</div>')
        # 板块统计
        stats_items = []
        for k, label in [("avg_uptrend_days", "平均上涨"), ("max_uptrend_days", "最长上涨"), ("tomorrow_prob", "明日概率"), ("expected_return", "预期收益")]:
            v = sector_stats.get(k)
            if v is not None:
                stats_items.append(f'<span class="focus-stat"><small>{label}</small><strong>{self._escape(str(v))}</strong></span>')
        if stats_items:
            parts.append(f'<div class="focus-stats">{"".join(stats_items)}</div>')
        # 指标行
        pct_20d = body.get("pct_20d")
        vol_ratio = body.get("vol_ratio")
        if pct_20d is not None or vol_ratio is not None:
            ind_parts = []
            if pct_20d is not None:
                ind_parts.append(f'<span>20日 {pct_20d:+.1f}%</span>')
            if vol_ratio is not None:
                ind_parts.append(f'<span>量比 {vol_ratio:.2f}</span>')
            parts.append(f'<div class="focus-indicators">{"".join(ind_parts)}</div>')
        # 最佳 ETF
        if best_etf:
            etf_name = self._escape(str(best_etf.get("name", "")))
            parts.append(f'<div class="focus-best-etf"><span>📊 最佳ETF: </span><strong>{etf_name}</strong></div>')
        # 龙头
        if leaders:
            leader_items = []
            for ld in leaders[:4]:
                name = self._escape(str(ld.get("name", ld.get("code", ""))))
                score = self._score_text(ld.get("score", ""))
                leader_items.append(f'<span class="focus-leader">{name} <sup>{score}</sup></span>')
            parts.append(f'<div class="focus-leaders">{"".join(leader_items)}</div>')
        return "".join(parts)

    def _render_observation_body(self, body: dict) -> str:
        leaders = body.get("leaders", []) if isinstance(body, dict) else []
        if not leaders:
            return '<p class="empty-state">暂无观察区板块</p>'
        items = []
        for ld in leaders[:5]:
            name = self._escape(str(ld.get("name", ld.get("code", ""))))
            score = self._score_text(ld.get("score", ""))
            items.append(f'<span class="observation-leader">{name} <sup>{score}</sup></span>')
        return f'<div class="observation-leaders">{"".join(items)}</div>'

    def _render_table_body(self, body: dict, table_type: str) -> str:
        if not isinstance(body, dict):
            return ""
        rows = body.get("rows", []) or []
        if not rows:
            return '<p class="empty-state">暂无数据</p>'
        # 搜索框
        search_id = f"{table_type}_search"
        table_id = f"{table_type}_table"
        # 表头
        headers = {"code": "代码", "name": "标的", "sector": "板块", "theme": "题材",
                   "state": "状态", "state_label": "趋势", "score": "评分",
                   "pct_20d": "20日", "vol_ratio": "量比"}
        columns = body.get("columns", ["code", "name", "state_label", "score", "pct_20d"])
        ths = "".join(f'<th>{self._escape(headers.get(c, c))}</th>' for c in columns)
        # 行
        trs = []
        for row in rows:
            tds = []
            for c in columns:
                v = row.get(c, "")
                if c == "state":
                    v = self._render_5d_state_bar([v]) or str(v)
                elif isinstance(v, float):
                    v = f"{v:.1f}" if c == "score" else str(v)
                tds.append(f'<td>{self._escape(str(v)) if c != "state" else v}</td>')
            trs.append(f'<tr>{" ".join(tds)}</tr>')
        search = f'<input type="text" class="table-search" id="{search_id}" placeholder="搜索..." oninput="filterTable(\'{table_id}\', this.value)">'
        table = f'<table class="data-table" id="{table_id}"><thead><tr>{ths}</tr></thead><tbody>{"".join(trs)}</tbody></table>'
        return f'{search}<div class="table-scroll">{table}</div>'

    def _render_template(self, template_path: Path, context: dict) -> str:
        template = template_path.read_text(encoding="utf-8")
        for key, value in context.items():
            escaped = value if key in {"badges", "risks", "body", "metrics", "line_market", "line_time", "line_leaders"} else self._escape(value)
            template = template.replace("{{ " + key + " }}", str(escaped))
        return template

    def _render_date_nav_card(self, card: dict) -> str:
        line_time = card.get("line_time", {})
        line_market = card.get("line_market", {})
        line_leaders = card.get("line_leaders", {})

        # 第一行：日期 + 周几 + today/monday 标签
        date_label = line_time.get("label", "")
        weekday = line_time.get("weekday", "")
        status = line_time.get("status", "")
        tags_html = ""
        if card.get("is_current"):
            tags_html += '<span class="day-tag today">今天</span>'
        # 周一标记
        if weekday == "周一":
            tags_html += '<span class="day-tag monday">周一</span>'
        # 市场状态标签
        health_label = {"强势": "强势", "正常": "正常", "弱势": "弱势", "complete": "强势", "warning": "弱势"}.get(status, status or "")
        health_cls = {"强势": "strong", "正常": "normal", "弱势": "weak"}.get(health_label, "weak")
        tags_html += f'<span class="day-tag {health_cls}">{health_label}</span>'
        # ↑数量
        up_count = line_market.get("up_count")
        if up_count is not None:
            tags_html += f'<span class="day-tag up-count">↑{up_count}</span>'
        line_time_html = f'{date_label} {weekday}{tags_html}'

        # 第二行：指数涨跌
        indices = line_market.get("indices", []) or []
        idx_parts = []
        for idx in indices:
            name = str(idx.get("name", ""))
            pct = idx.get("pct", 0)
            if isinstance(pct, (int, float)):
                sign = "+" if pct >= 0 else ""
                color = "#f85149" if pct >= 0 else "#3fb950"
                short_name = name[:2] if len(name) >= 2 else name
                idx_parts.append(f'<span style="color:{color}">{short_name}{sign}{pct:.2f}%</span>')
        line_market_html = " ".join(idx_parts)

        # 第三行：龙头
        etf_name = line_leaders.get("etf", "")
        sector = line_leaders.get("sector", "")
        theme = line_leaders.get("theme", "")
        stock = line_leaders.get("stock", "")
        leader_parts = []
        if etf_name:
            leader_parts.append(etf_name)
        if stock:
            leader_parts.append(stock)
        leaders_line = " / ".join(leader_parts) if leader_parts else ""
        # 主线板块行（含 sector 和 theme）
        sector_line = ""
        sector_parts = []
        if sector:
            sector_parts.append(sector)
        if theme:
            sector_parts.append(theme)
        if sector_parts:
            sector_line = '★ ' + ' · '.join(sector_parts)
        line_leaders_html = leaders_line
        if sector_line:
            line_leaders_html = f'{leaders_line}{" " if leaders_line else ""}{sector_line}'

        context = {
            "date": card.get("date", ""),
            "target": card.get("target", ""),
            "line_time": line_time_html,
            "line_market": line_market_html,
            "line_leaders": line_leaders_html,
        }
        return self._render_template(self.CARD_TEMPLATE_DIR / "date_nav_card.html", context)

    @staticmethod
    def _page(title: str, body: str) -> str:
        return "\n".join(
            [
                "<!doctype html>",
                '<html lang="zh-CN">',
                "<head>",
                '  <meta charset="utf-8">',
                '  <meta name="viewport" content="width=device-width, initial-scale=1">',
                f"  <title>{html.escape(title)}</title>",
                '  <link rel="stylesheet" href="assets/display.css">',
                '  <script src="assets/display.js"></script>',
                "</head>",
                "<body>",
                body,
                "</body>",
                "</html>",
            ]
        )

    def _copy_assets(self, output_path: str) -> None:
        target = Path(output_path).parent / "assets"
        target.mkdir(parents=True, exist_ok=True)
        for asset in self.ASSET_DIR.iterdir():
            if asset.is_file():
                shutil.copy2(asset, target / asset.name)

    @staticmethod
    def _read_json(path: str) -> dict:
        return json.loads(Path(path).read_text(encoding="utf-8"))

    @staticmethod
    def _write(path: str, content: str) -> str:
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding="utf-8")
        return str(output)

    @staticmethod
    def _escape(value) -> str:
        return html.escape(str(value), quote=True)

    @staticmethod
    def _pct(value) -> str:
        try:
            return f"{float(value) * 100:.0f}%"
        except (TypeError, ValueError):
            return "N/A"

    @staticmethod
    def _action_label(action_type: str) -> str:
        return {
            "buy": "买入",
            "add": "加仓",
            "reduce": "减仓",
            "exit": "清仓",
            "hold": "持有",
            "watch": "观察",
        }.get(action_type, action_type)

    @staticmethod
    def _score_text(value) -> str:
        try:
            return f"{float(value):.1f}"
        except (TypeError, ValueError):
            return str(value)

    @staticmethod
    def _compact(value) -> str:
        if isinstance(value, dict):
            return " / ".join(f"{key}: {val}" for key, val in value.items() if val not in (None, "", [], {}))
        if isinstance(value, list):
            return " / ".join(str(item) for item in value)
        return str(value)
