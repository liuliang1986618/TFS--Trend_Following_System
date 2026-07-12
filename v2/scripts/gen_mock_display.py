"""Generate mock display payload with all 11 regions for visual testing."""
import json
from pathlib import Path

MOCK_PAYLOAD = {
    "meta": {"date": "2026-06-22", "run_id": "mock_20260622", "source": "mock", "created_at": "2026-06-22T09:00:00"},
    "overview": {"health": {"market": {"status": "warning"}, "relation": {"status": "complete"}}, "indices": []},
    "regions": [
        {"id": "overview", "title": "市场概览", "layout": "grid", "card_ids": ["metric_health", "metric_count"]},
        {"id": "funnel_deep_dive", "title": "强势板块深度穿透", "layout": "grid", "card_ids": [f"funnel_{i}" for i in range(6)]},
        {"id": "steady_recommend", "title": "稳健推荐", "layout": "grid", "card_ids": [f"action_steady_{i}" for i in range(5)]},
        {"id": "strong_tracking", "title": "强势追踪", "layout": "grid", "card_ids": [f"action_strong_{i}" for i in range(5)]},
        {"id": "focus_sectors", "title": "焦点板块", "layout": "grid", "card_ids": [f"focus_{i}" for i in range(5)]},
        {"id": "observation", "title": "观察区", "layout": "grid", "card_ids": [f"obs_{i}" for i in range(5)]},
        {"id": "stock_table", "title": "趋势个股", "layout": "grid", "card_ids": ["stock_table"]},
        {"id": "etf_table", "title": "ETF直筛", "layout": "grid", "card_ids": ["etf_table"]},
    ],
    "cards": [],
    "signals": [],
    "leader_summary": {"sector": "电子", "theme": "半导体", "stock": "富信科技", "etf": "稀土ETF"},
    "data_pool": {},
    "screening": {},
    "evaluation": {"total": 10, "exact_accuracy": 0.6},
    "nav": {},
    "warnings": [],
}

SECTOR_NAMES = ["电子", "有色金属", "机械设备", "医药生物", "计算机"]
ETF_NAMES = ["稀土ETF嘉实", "稀有金属ETF华富", "稀土ETF华泰柏瑞", "科创芯片ETF", "半导体ETF"]
STOCK_NAMES = ["富信科技", "惠丰钻石", "胜科纳米", "联瑞新材", "中船特气", "宿迁联盛", "北方华创", "中微公司"]

def make_cards():
    cards = []
    # overview
    cards.append({"id": "metric_health", "type": "metric_card", "title": "市场状态", "subtitle": "market health",
                  "metrics": [{"label": "状态", "value": "warning"}], "body": {}, "risks": [], "warnings": []})
    cards.append({"id": "metric_count", "type": "metric_card", "title": "候选数量", "subtitle": "engine signals",
                  "metrics": [{"label": "总数", "value": 10}, {"label": "关系", "value": "complete"}], "body": {}, "risks": [], "warnings": []})
    # funnel_deep_dive x6
    for i in range(6):
        cards.append({
            "id": f"funnel_{i}", "type": "funnel_deep_dive_card", "title": SECTOR_NAMES[i % 5], "subtitle": f"BK{i:04d}",
            "score": round(88 - i * 2.5, 1), "badges": [f"Top{i+1}", "8 标的"],
            "metrics": [{"label": "候选", "value": 8}, {"label": "最高分", "value": round(88 - i * 2.5, 1)}],
            "body": {
                "abc": {"structure": "放量突破前高", "volume": "量能放大1.5倍", "persistence": "连续3日收阳"},
                "best_etf": {"name": ETF_NAMES[i % 5], "score": round(82 - i, 1)},
                "leaders": [{"code": f"6{i:05d}", "name": STOCK_NAMES[i % 8], "score": round(90 - i, 1), "state": 4}],
                "recent_states": [4, 5, 4, 3, 4][:5],
                "recent_scores": [85 + i * 0.5 for i in range(5)],
                "sector_stats": {"avg_uptrend_days": 12, "max_uptrend_days": 28, "tomorrow_prob": 0.62, "expected_return": 2.3},
            }, "risks": [], "warnings": []
        })
    # steady_recommend x5 (action_card)
    for i in range(5):
        cards.append(_action_card(f"action_steady_{i}", STOCK_NAMES[i], f"6{i:05d}", 78 - i * 2, "上涨趋势"))
    # strong_tracking x5 (action_card)
    for i in range(5):
        cards.append(_action_card(f"action_strong_{i}", STOCK_NAMES[(i+3) % 8], f"6{(i+3):05d}", 93 - i * 1.5, "强势追踪"))
    # focus_sectors x5
    for i in range(5):
        cards.append({
            "id": f"focus_{i}", "type": "focus_sector_card", "title": SECTOR_NAMES[i], "subtitle": f"BK{i:04d}",
            "score": round(85 - i * 2, 1), "badges": ["趋势共振", "4 个标的"],
            "metrics": [{"label": "强度", "value": round(85 - i * 2, 1)}, {"label": "标的", "value": 4}],
            "body": {
                "abc": {"structure": "均线多头排列", "volume": "量能温和放大", "persistence": "趋势延续中"},
                "best_etf": {"name": ETF_NAMES[i], "score": round(80 - i, 1)},
                "leaders": [
                    {"code": f"6{i:05d}", "name": STOCK_NAMES[i], "score": round(90 - i, 1), "pct_20d": 15.3 - i * 2, "reason": "上涨趋势 / 趋势延续"},
                    {"code": f"6{i+1:05d}", "name": STOCK_NAMES[(i+1) % 8], "score": round(87 - i, 1), "pct_20d": 12.1 - i * 1.5, "reason": "上涨趋势 / 趋势后段"},
                ],
                "recent_states": [4, 5, 4, 3, 4],
                "recent_scores": [82 + i for i in range(5)],
                "sector_stats": {"avg_uptrend_days": 10, "max_uptrend_days": 25, "tomorrow_prob": 0.58, "expected_return": 1.8},
                "projection": [{"label": "延续", "probability": 0.65}, {"label": "回踩", "probability": 0.25}],
                "pct_20d": 12.5 - i * 2, "vol_ratio": 1.3 + i * 0.1,
            }, "risks": [], "warnings": []
        })
    # observation x5
    for i in range(5):
        cards.append({
            "id": f"obs_{i}", "type": "observation_card", "title": SECTOR_NAMES[i], "subtitle": "反弹中",
            "score": round(72 - i * 3, 1), "badges": ["观察区", "3 标的"],
            "metrics": [{"label": "标的", "value": 3}],
            "body": {"leaders": [
                {"code": f"6{i:05d}", "name": STOCK_NAMES[i], "score": round(75 - i * 2, 1)},
                {"code": f"6{i+1:05d}", "name": STOCK_NAMES[(i+1) % 8], "score": round(70 - i * 2, 1)},
            ]},
            "risks": [], "warnings": []
        })
    # stock_table
    stock_rows = []
    for i in range(30):
        stock_rows.append({
            "code": f"6{i:05d}", "name": STOCK_NAMES[i % 8], "sector": SECTOR_NAMES[i % 5], "theme": "新材料",
            "state": 4, "state_label": "上涨趋势", "score": round(90 - i * 0.8, 1),
            "pct_20d": round(15 - i * 0.5, 1), "vol_ratio": round(1.2 + (i % 5) * 0.1, 2),
        })
    cards.append({
        "id": "stock_table", "type": "stock_table_card", "title": "趋势个股", "subtitle": "30 只",
        "metrics": [{"label": "数量", "value": 30}],
        "body": {"rows": stock_rows, "columns": ["code", "name", "sector", "theme", "state", "state_label", "score", "pct_20d", "vol_ratio"]},
        "risks": [], "warnings": []
    })
    # etf_table
    etf_rows = []
    for i in range(15):
        etf_rows.append({
            "code": f"5{i:05d}", "name": ETF_NAMES[i % 5], "state": 4, "state_label": "上涨趋势",
            "score": round(85 - i * 1.2, 1), "pct_20d": round(8 - i * 0.5, 1), "vol_ratio": round(1.1 + (i % 3) * 0.15, 2),
        })
    cards.append({
        "id": "etf_table", "type": "etf_table_card", "title": "ETF直筛", "subtitle": "15 只",
        "metrics": [{"label": "数量", "value": 15}],
        "body": {"rows": etf_rows, "columns": ["code", "name", "state", "state_label", "score", "pct_20d", "vol_ratio"]},
        "risks": [], "warnings": []
    })
    return cards

def _action_card(card_id, name, code, score, badge):
    return {
        "id": card_id, "type": "action_card", "title": name, "subtitle": code,
        "score": round(score, 1), "badges": [badge],
        "metrics": [{"label": "状态", "value": 4}, {"label": "信心", "value": 0.8}],
        "body": {
            "action_hint": "持有",
            "sections": [
                {"key": "plan", "title": "操作计划", "summary": "持有 / 目标仓位 8%", "data": {
                    "target_position_pct": 0.08,
                    "triggers": [
                        {"scenario_label": "A", "action_type": "hold", "target_position_pct": 0.08, "trigger_conditions": ["继续沿MA20上方运行"]},
                        {"scenario_label": "B", "action_type": "add", "target_position_pct": 0.10, "trigger_conditions": ["缩量回调, 不破前低"]},
                        {"scenario_label": "C", "action_type": "reduce", "target_position_pct": 0.03, "trigger_conditions": ["放量跌破前低"]},
                    ]
                }},
                {"key": "trend", "title": "趋势大背景", "summary": "上升趋势", "data": {"direction": "uptrend", "stage": "late", "pct_20d": 160.4, "pct_60d": 332.9}},
                {"key": "today", "title": "今日定位", "summary": "顺势上涨", "data": {"label": "顺势上涨", "narrative": "今日涨跌 20.0%，量比 1.15"}},
                {"key": "strategy", "title": "策略总纲", "summary": "顺势持有", "data": {"text": "上升趋势完好，顺势持有，回调到支撑位再考虑加仓。"}},
                {"key": "projection", "title": "明日行情推演", "summary": "3 场景", "data": {
                    "scenarios": [
                        {"label": "A", "title": "大概率", "probability": 0.60, "range": "继续上涨"},
                        {"label": "B", "title": "中概率", "probability": 0.30, "range": "横盘震荡"},
                        {"label": "C", "title": "小概率", "probability": 0.10, "range": "回调"},
                    ]
                }},
                {"key": "zone", "title": "明日最佳买卖区间", "summary": "", "data": {
                    "buy_zone": {"low": 30.265, "high": 171.49, "logic": "回踩支撑区"},
                    "sell_zone": {"low": 155.007, "high": 171.49, "logic": "接近压力区"},
                }},
                {"key": "levels", "title": "关键价位", "summary": "5 个价位", "data": [
                    {"label": "支撑位", "price": 155.0}, {"label": "阻力位", "price": 171.5},
                    {"label": "止损位", "price": 145.0}, {"label": "昨收", "price": 162.3}, {"label": "当前", "price": 168.2},
                ]},
                {"key": "watch", "title": "盯盘场景", "summary": "3 个场景", "data": [
                    {"level": "A", "action": "hold", "position_pct": 0.08, "signals": ["MA20上方运行"]},
                    {"level": "B", "action": "add", "position_pct": 0.10, "signals": ["缩量回调"]},
                    {"level": "C", "action": "reduce", "position_pct": 0.03, "signals": ["放量跌破"]},
                ]},
                {"key": "position", "title": "仓位管理", "summary": "3 步", "data": [
                    {"step": "初始", "target_position_pct": 0.05, "condition": "突破确认"},
                    {"step": "加仓", "target_position_pct": 0.08, "condition": "趋势延续"},
                    {"step": "减仓", "target_position_pct": 0.03, "condition": "跌破支撑"},
                ]},
            ],
        },
        "risks": [], "warnings": []
    }

def main():
    output_dir = Path("v2/data/derived/display_runs/mock_2026-06-22")
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "assets").mkdir(exist_ok=True)

    payload = MOCK_PAYLOAD.copy()
    payload["cards"] = make_cards()

    payload_path = output_dir / "display_payload.json"
    payload_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"Payload written: {payload_path}")

    # Render
    from v2.display.renderer import DisplayRenderer
    from v2.display.nav import NavPayloadBuilder

    renderer = DisplayRenderer()
    daily_path = str(output_dir / "trend_dashboard_2026-06-22.html")
    renderer.render_daily(str(payload_path), daily_path)
    print(f"Daily HTML: {daily_path}")

    # Nav
    nav_builder = NavPayloadBuilder()
    nav_payload = nav_builder.build([payload], current_date="2026-06-22")
    nav_path = output_dir / "nav_payload.json"
    nav_path.write_text(json.dumps(nav_payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    index_path = str(output_dir / "index.html")
    renderer.render_index(str(nav_path), index_path)
    print(f"Index HTML: {index_path}")
    print("Done!")

if __name__ == "__main__":
    main()
