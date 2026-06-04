#!/usr/bin/env python3
"""为所有缺失的历史日期生成dashboard HTML。

从 history_states_full.json 读取90板块的状态数据，
为 date_nav.json 中每个缺少 dashboard 的日期生成 HTML。
"""
import json
import os
from collections import Counter

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "dashboard", "data")
DASHBOARD_DIR = os.path.join(PROJECT_ROOT, "dashboard")


def load_sector_names() -> dict[str, str]:
    with open(os.path.join(DATA_DIR, "sector_list.json")) as f:
        sectors = json.load(f)
    return {s["code"]: s["name"] for s in sectors}


def load_history() -> tuple[dict, dict]:
    with open(os.path.join(DATA_DIR, "history_states_full.json")) as f:
        data = json.load(f)

    by_date: dict[str, dict] = {}
    for code, records in data["sectors"].items():
        for r in records:
            d = r["date"]
            if d not in by_date:
                by_date[d] = {}
            by_date[d][code] = r

    return by_date, data["meta"]


def state_badge(state, label):
    colors = {
        "1": ("rgba(110,118,129,0.2)", "#b0b5c0"),
        "2": ("rgba(110,118,129,0.25)", "#b0b5c0"),
        "3": ("rgba(66,165,245,0.25)", "#64b5f6"),
        "4": ("#238636", "#fff"),
        "5": ("rgba(255,112,67,0.2)", "#ff8a65"),
        "3p": ("rgba(218,54,51,0.2)", "#ef5350"),
    }
    bg, fg = colors.get(str(state), ("#6e7681", "#b0b5c0"))
    return f'<span style="display:inline-block;padding:2px 10px;border-radius:12px;font-size:12px;font-weight:700;background:{bg};color:{fg};white-space:nowrap">{label}</span>'


def score_bar(s):
    c = "#26a69a" if s >= 70 else "#d29922" if s >= 40 else "#6e7681"
    return f'<div style="display:flex;align-items:center;gap:6px"><span style="font-weight:700;font-size:12px;color:{c}">{s}</span><div style="height:4px;width:50px;background:#21262d;border-radius:2px"><div style="height:100%;width:{min(s,100)}%;background:{c};border-radius:2px"></div></div></div>'


def cond_dot(p):
    return f'<span style="color:{"#26a69a" if p else "#ef5350"};font-size:14px">{"●" if p else "○"}</span>'


def generate_dashboard(date_str: str, date_records: dict, sector_names: dict[str, str]) -> str:
    items = []
    for code, r in date_records.items():
        name = sector_names.get(code, code)
        c = r["conditions"]
        items.append({
            "code": code,
            "name": name,
            "state": r["state"],
            "state_label": r["state_label"],
            "score": r["score"],
            "position_ratio": r.get("position_ratio", 0),
            "structure": c.get("structure", False),
            "volume": c.get("volume", False),
            "persistence": c.get("persistence", False),
        })

    items.sort(key=lambda x: x["score"], reverse=True)

    counts = Counter(i["state_label"] for i in items)
    uptrend = sum(1 for i in items if i["state"] in ("4", "5", "3"))
    mainline = sum(1 for i in items if i["state"] == "4" and i["structure"] and i["volume"] and i["persistence"])

    rows = ""
    for item in items:
        pos_pct = f'{item["position_ratio"]*100:.0f}%'
        rows += f'''<tr>
<td><span style="color:#58a6ff;font-weight:600">{item["name"]}</span></td>
<td style="color:#8b949e;font-size:12px">{item["code"]}</td>
<td>{state_badge(item["state"], item["state_label"])}</td>
<td>{score_bar(item["score"])}</td>
<td>{cond_dot(item["structure"])}</td>
<td>{cond_dot(item["volume"])}</td>
<td>{cond_dot(item["persistence"])}</td>
<td style="font-weight:600">{pos_pct}</td>
</tr>'''

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>趋势跟随 · {date_str}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#0d1117;color:#e6edf3;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;font-size:13px;padding:16px}}
.header{{margin-bottom:16px}}
.header h1{{font-size:18px;color:#e6edf3}}
.header .sub{{font-size:11px;color:#8b949e;margin-top:4px}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:8px;margin-bottom:16px}}
.card{{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:10px;text-align:center}}
.card .val{{font-size:20px;font-weight:800}}
.card .lbl{{font-size:10px;color:#8b949e;margin-top:2px}}
.table-wrap{{overflow-x:auto;border:1px solid #30363d;border-radius:8px}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
thead th{{background:#21262d;padding:7px 10px;text-align:left;font-size:11px;color:#8b949e;border-bottom:2px solid #30363d;font-weight:600;white-space:nowrap;position:sticky;top:0;z-index:10}}
tbody td{{padding:5px 10px;border-bottom:1px solid #21262d;white-space:nowrap}}
tbody tr:hover{{background:rgba(88,166,255,0.04)}}
.footer{{margin-top:16px;padding-top:12px;border-top:1px solid #30363d;text-align:center;color:#8b949e;font-size:10px}}
</style>
</head>
<body>
<div class="header">
<h1>趋势跟随交易系统</h1>
<div class="sub">{date_str} · 历史回放 · 共{len(items)}板块</div>
</div>
<div class="cards">
<div class="card"><div class="val" style="color:#8b949e">{len(items)}</div><div class="lbl">全板块</div></div>
<div class="card"><div class="val" style="color:#58a6ff">{uptrend}</div><div class="lbl">上涨趋势(3/4/5)</div></div>
<div class="card"><div class="val" style="color:#d29922">{mainline}</div><div class="lbl">★主线(全满)</div></div>
<div class="card"><div class="val" style="color:#3fb950">{counts.get("上涨趋势(4)", 0)}</div><div class="lbl">状态4</div></div>
<div class="card"><div class="val" style="color:#42a5f5">{counts.get("翻转确认中(3)", 0)}</div><div class="lbl">状态3(翻转)</div></div>
<div class="card"><div class="val" style="color:#da3633">{counts.get("下跌趋势(1)", 0)}</div><div class="lbl">状态1(下跌)</div></div>
</div>
<div class="table-wrap">
<table>
<thead><tr>
<th>板块名称</th><th>代码</th><th>状态</th><th>得分</th><th>A(结构)</th><th>B(量能)</th><th>C(持续性)</th><th>仓位</th>
</tr></thead>
<tbody>
{rows}
</tbody>
</table>
</div>
<div class="footer">趋势跟随交易系统 · 历史回放 · {date_str} · 数据来源: history_states_full.json</div>
</body>
</html>'''
    return html


def main():
    print("=" * 60)
    print("🏗️  生成历史Dashboard HTML")
    print("=" * 60)

    print("\n📂 加载数据...")
    sector_names = load_sector_names()
    print(f"   {len(sector_names)} 个板块名称")

    by_date, meta = load_history()
    print(f"   {len(by_date)} 个日期, {meta['total_symbols']} 板块")

    with open(os.path.join(DATA_DIR, "date_nav.json")) as f:
        nav = json.load(f)
    target_dates = [d["date"] for d in nav["dates"]]
    print(f"   {len(target_dates)} 个目标日期")

    generated = 0
    skipped = 0
    missing_data = 0

    for date_str in target_dates:
        output_path = os.path.join(DASHBOARD_DIR, f"trend_dashboard_{date_str}.html")

        if os.path.exists(output_path):
            skipped += 1
            continue

        if date_str not in by_date:
            missing_data += 1
            print(f"   ⚠️ {date_str}: 无历史数据, 跳过")
            continue

        html = generate_dashboard(date_str, by_date[date_str], sector_names)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)
        generated += 1

    print(f"\n📊 结果: 生成 {generated} | 已有 {skipped} | 无数据 {missing_data}")
    print(f"   总计 dashboard 文件: {generated + skipped}")
    print("=" * 60)


if __name__ == "__main__":
    main()
