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
        body = "\n".join(
            [
                '<div class="display-shell">',
                f'  <aside class="display-sidebar">{cards}</aside>',
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
        decision_data = body.get("decision_data") if isinstance(body.get("decision_data"), dict) else {}
        trade_plan = body.get("trade_plan") if isinstance(body.get("trade_plan"), dict) else None
        sections = []
        sections.append(self._action_summary(body, trade_plan))
        sections.append(self._decision_section("趋势大背景", self._trend_context_text(decision_data.get("trend_context", {})), "trend"))
        sections.append(self._decision_section("今日定位", self._today_position_text(decision_data.get("today_position", {})), "today"))
        sections.append(self._decision_section("策略总纲", decision_data.get("strategy_summary", ""), "strategy"))
        sections.append(self._decision_section("明日行情推演", self._projection_items(decision_data.get("projection", {})), "projection", "list"))
        sections.append(self._decision_section("明日最佳买卖区间", self._buy_sell_zone_items(decision_data.get("buy_sell_zone", {})), "zone", "zones"))
        sections.append(self._decision_section("关键价位", self._key_level_items(decision_data.get("key_levels", [])), "levels", "levels"))
        sections.append(self._decision_section("盯盘场景", self._watch_scenario_items(decision_data.get("watch_scenarios", [])), "watch", "list"))
        sections.append(self._decision_section("仓位管理", self._position_plan_items(decision_data.get("position_plan", [])), "position", "list"))
        return "".join(section for section in sections if section)

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

    def _render_template(self, template_path: Path, context: dict) -> str:
        template = template_path.read_text(encoding="utf-8")
        for key, value in context.items():
            escaped = value if key in {"badges", "risks", "body", "metrics"} else self._escape(value)
            template = template.replace("{{ " + key + " }}", str(escaped))
        return template

    def _render_date_nav_card(self, card: dict) -> str:
        line_time = card.get("line_time", {})
        line_market = card.get("line_market", {})
        line_leaders = card.get("line_leaders", {})
        leaders = " / ".join(value for value in [line_leaders.get("sector"), line_leaders.get("theme"), line_leaders.get("stock"), line_leaders.get("etf")] if value)
        context = {
            "date": card.get("date", ""),
            "target": card.get("target", ""),
            "line_time": " ".join(value for value in [line_time.get("date", ""), line_time.get("weekday", "")] if value),
            "line_market": " ".join(value for value in [line_market.get("label", ""), line_market.get("summary", "")] if value),
            "line_leaders": leaders,
            "tag": "当日" if card.get("is_current") else "历史",
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
