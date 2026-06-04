#!/usr/bin/env python3
"""生成Dashboard导航壳页面 — 左侧侧边栏 + 右侧iframe加载每日报告。

从date_nav.json读取全部126个交易日，通过akshare拉取指数数据和股票名称映射，
生成 dashboard/index.html。侧边栏固定280px，每项显示日期/指数涨跌/市场状态/龙头。
"""
import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "dashboard", "data")
DASHBOARD_DIR = os.path.join(PROJECT_ROOT, "dashboard")


def load_date_nav() -> list[dict]:
    """加载日期导航数据。"""
    path = os.path.join(DATA_DIR, "date_nav.json")
    with open(path) as f:
        data = json.load(f)
    return data["dates"]


def fetch_index_data(dates: list[str]) -> dict[str, dict]:
    """从akshare拉取上证/科创/创业板日线数据，返回 date→{sh_pct, kc_pct, cy_pct}。

    akshare的stock_zh_index_daily返回的date列是datetime.date对象。
    """
    import akshare as ak

    result: dict[str, dict] = {}
    # 预先创建所有日期的datetime.date对象用于查找
    date_map: dict[datetime, str] = {}
    for d in dates:
        try:
            date_map[datetime.strptime(d, "%Y-%m-%d").date()] = d
        except ValueError:
            pass

    index_map = {
        "sh": "sh000001",
        "kc": "sh000688",
        "cy": "sz399006",
    }

    for key, symbol in index_map.items():
        print(f"  📥 拉取 {key.upper()} 指数数据 ({symbol})...")
        try:
            df = ak.stock_zh_index_daily(symbol=symbol)
            # date列是datetime.date，直接设为索引
            df = df.set_index("date")
            for date_obj, date_str in date_map.items():
                if date_obj in df.index:
                    row = df.loc[date_obj]
                    idx = df.index.get_loc(date_obj)
                    if idx > 0:
                        prev_close = df.iloc[idx - 1]["close"]
                        pct = (row["close"] - prev_close) / prev_close * 100
                    else:
                        pct = 0.0
                    if date_str not in result:
                        result[date_str] = {}
                    result[date_str][f"{key}_pct"] = round(pct, 2)
                else:
                    if date_str not in result:
                        result[date_str] = {}
                    result[date_str][f"{key}_pct"] = 0.0
            print(f"     ✅ {key.upper()} 完成 ({len(date_map)}天)")
        except Exception as e:
            print(f"     ⚠️ {key.upper()} 失败: {e}")
            for date_str in dates:
                if date_str not in result:
                    result[date_str] = {}
                result[date_str][f"{key}_pct"] = 0.0

    return result


def build_stock_name_map(leader_codes: set[str]) -> dict[str, str]:
    """从akshare获取股票代码→名称映射。"""
    import akshare as ak

    if not leader_codes:
        return {}

    print(f"  📥 拉取股票名称映射 ({len(leader_codes)} 只)...")
    try:
        # stock_info_a_code_name 返回全部A股 code+name，比spot接口更稳定
        df = ak.stock_info_a_code_name()
        name_map = {}
        for _, row in df.iterrows():
            code = str(row["code"])
            name = str(row["name"])
            name_map[code] = name

        found = len([c for c in leader_codes if c in name_map])
        print(f"     ✅ 命中 {found}/{len(leader_codes)} 只")
        return name_map
    except Exception as e:
        print(f"     ⚠️ stock_info_a_code_name失败: {e}")
        # 回退: spot接口
        try:
            df = ak.stock_zh_a_spot_em()
            name_map = {}
            for _, row in df.iterrows():
                code = str(row["代码"])
                name = str(row["名称"])
                name_map[code] = name
            found = len([c for c in leader_codes if c in name_map])
            print(f"     ✅ 回退命中 {found}/{len(leader_codes)} 只")
            return name_map
        except Exception as e2:
            print(f"     ⚠️ 回退也失败: {e2}")
            return {}


def collect_all_leader_codes(dates_data: list[dict]) -> set[str]:
    """收集所有日期中出现的leader股票代码。"""
    codes = set()
    for d in dates_data:
        leaders = d.get("leaders", {})
        if isinstance(leaders, dict):
            for sector_code, stock_list in leaders.items():
                if isinstance(stock_list, list):
                    for s in stock_list:
                        if isinstance(s, dict) and "code" in s:
                            codes.add(s["code"])
    return codes


def enrich_dates(dates_data: list[dict], index_data: dict[str, dict],
                 name_map: dict[str, str]) -> list[dict]:
    """将指数数据和股票名称合并到日期条目中。"""
    result = []
    for d in dates_data:
        date = d["date"]
        entry = {
            "date": date,
            "weekday": d.get("weekday", ""),
            "label": _make_label(date, d.get("weekday", "")),
            "is_today": d.get("is_today", False),
            "is_monday": d.get("is_monday", False),
            "health": d.get("health", ""),
            "uptrend_count": d.get("uptrend_count", 0),
            "downtrend_count": d.get("downtrend_count", 0),
        }

        idx = index_data.get(date, {})
        entry["sh_pct"] = idx.get("sh_pct", 0.0)
        entry["kc_pct"] = idx.get("kc_pct", 0.0)
        entry["cy_pct"] = idx.get("cy_pct", 0.0)

        leaders_raw = d.get("leaders", {})
        if isinstance(leaders_raw, dict) and leaders_raw:
            seen = {}
            for sector_code, stock_list in leaders_raw.items():
                if isinstance(stock_list, list):
                    for s in stock_list:
                        if isinstance(s, dict):
                            code = s.get("code", "")
                            score = s.get("ret20", 0) or s.get("score", 0)
                            if code and code not in seen:
                                seen[code] = {
                                    "code": code,
                                    "name": name_map.get(code, code),
                                    "score": round(float(score), 1),
                                }
            leaders_sorted = sorted(seen.values(), key=lambda x: x["score"], reverse=True)[:5]
            entry["leaders"] = leaders_sorted
        else:
            entry["leaders"] = []

        tops = d.get("top_sectors", [])
        flips = d.get("top_flip", [])
        entry["top_mainline"] = [s["name"] for s in tops[:3]] if tops else []
        entry["top_flip"] = [s["name"] for s in flips[:3]] if flips else []

        result.append(entry)
    return result


def _make_label(date_str: str, weekday: str) -> str:
    """生成显示标签，如 '05-31 周三'。"""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return f"{dt.month:02d}-{dt.day:02d} {weekday}"
    except ValueError:
        return f"{date_str} {weekday}"


def generate_html(entries: list[dict], output_path: str):
    """生成侧边栏+iframe的壳页面HTML。"""
    entries_sorted = sorted(entries, key=lambda x: x["date"], reverse=True)
    today_entry = next((e for e in entries_sorted if e["is_today"]), None)
    default_date = today_entry["date"] if today_entry else entries_sorted[0]["date"]
    days_json = json.dumps(entries_sorted, ensure_ascii=False)

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>趋势跟随交易系统 · 看板</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{height:100%;overflow:hidden}}
body{{display:flex;background:#0b0b1a;color:#ccc;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Microsoft YaHei',sans-serif}}

.sidebar{{width:280px;min-width:280px;height:100vh;background:#0f0f22;border-right:1px solid #1a1a3a;display:flex;flex-direction:column;transition:width .2s,min-width .2s;position:relative;z-index:10}}
body.nav-collapsed .sidebar{{width:32px;min-width:32px}}
.sidebar-inner{{display:flex;flex-direction:column;height:100%;overflow:hidden}}
body.nav-collapsed .sidebar-inner{{display:none}}
.sidebar-header{{padding:16px 14px 12px;border-bottom:1px solid #1a1a3a;flex-shrink:0;position:relative}}
.sidebar-header h1{{font-size:17px;color:#fff;margin-bottom:2px}}
.sidebar-header .sub{{font-size:11px;color:#666}}
.sidebar-list{{flex:1;overflow-y:auto;padding:6px 0}}
.sidebar-list::-webkit-scrollbar{{width:4px}}
.sidebar-list::-webkit-scrollbar-thumb{{background:#2a2a4a;border-radius:2px}}

.date-item{{padding:10px 14px;cursor:pointer;border-left:3px solid transparent;transition:all .15s;border-bottom:1px solid rgba(26,26,58,0.4)}}
.date-item:hover{{background:#1a1a3a}}
.date-item.active{{background:#1a1a3a;border-left-color:#4ade80}}
.date-item .date-label{{font-size:13px;color:#e0e0e0;font-weight:600;margin-bottom:3px}}
.date-item .date-label .today-tag{{font-size:10px;background:#4ade8022;color:#4ade80;padding:1px 5px;border-radius:3px;margin-left:4px}}
.date-item .date-label .mon-tag{{font-size:10px;background:#58a6ff22;color:#58a6ff;padding:1px 5px;border-radius:3px;margin-left:4px}}
.date-item .sh-line{{font-size:11px;margin-bottom:3px;line-height:1.5}}
.date-item .leaders-line{{font-size:10px;color:#888;line-height:1.7;word-break:break-all}}
.date-item .sector-hint{{font-size:10px;color:#555;margin-top:1px;line-height:1.4}}

.main{{flex:1;height:100vh;display:flex;flex-direction:column;overflow:hidden}}
.main iframe{{flex:1;width:100%;border:none;display:block}}
.main .placeholder{{flex:1;display:flex;align-items:center;justify-content:center;color:#555;font-size:16px}}

.toggle-btn{{position:absolute;top:12px;right:8px;z-index:10;width:26px;height:26px;border-radius:4px;background:#1a1a3a;border:1px solid #2a2a4a;color:#888;cursor:pointer;font-size:13px;line-height:1;display:flex;align-items:center;justify-content:center;transition:all .2s}}
.toggle-btn:hover{{color:#fff;background:#2a2a4a}}
body.nav-collapsed .toggle-btn{{right:auto;left:3px;top:10px}}

/* 快速跳转条: 每个日期一个彩色圆点 */
.quick-bar{{display:flex;gap:2px;padding:6px 8px;border-bottom:1px solid #1a1a3a;flex-wrap:wrap;flex-shrink:0}}
.quick-dot{{width:6px;height:6px;border-radius:50%;cursor:pointer;transition:all .15s;flex-shrink:0}}
.quick-dot:hover{{transform:scale(1.8)}}
.quick-dot.strong{{background:#4ade80}}
.quick-dot.normal{{background:#d29922}}
.quick-dot.weak{{background:#f87171}}

@media (max-width:768px){{
  .sidebar{{width:240px;min-width:240px}}
}}
</style>
</head>
<body>
<div class="sidebar" id="sidebar">
  <button class="toggle-btn" id="toggleBtn" title="收起/展开侧边栏">◀</button>
  <div class="sidebar-inner">
    <div class="sidebar-header">
      <h1>📊 趋势跟随</h1>
      <div class="sub" id="dayCount"></div>
    </div>
    <div class="quick-bar" id="quickBar"></div>
    <div class="sidebar-list" id="dateList"></div>
  </div>
</div>
<div class="main">
  <iframe id="reportFrame" src=""></iframe>
  <div class="placeholder" id="placeholder" style="display:none">← 选择日期查看报告</div>
</div>

<script>
const DAYS = {days_json};
const DEFAULT_DATE = "{default_date}";

(function() {{
    const dateList = document.getElementById('dateList');
    const reportFrame = document.getElementById('reportFrame');
    const dayCount = document.getElementById('dayCount');
    const toggleBtn = document.getElementById('toggleBtn');
    const quickBar = document.getElementById('quickBar');

    toggleBtn.addEventListener('click', function() {{
        document.body.classList.toggle('nav-collapsed');
        toggleBtn.textContent = document.body.classList.contains('nav-collapsed') ? '▶' : '◀';
    }});

    dayCount.textContent = DAYS.length + ' 天报告';

    // 快速跳转点: 一日期一个色点，颜色=市场状态
    quickBar.innerHTML = DAYS.map(function(d) {{
        var cls = d.health === '强势' ? 'strong' : d.health === '弱势' ? 'weak' : 'normal';
        return '<span class="quick-dot ' + cls + '" title="' + d.date + ' ' + d.health + '" data-date="' + d.date + '"></span>';
    }}).join('');

    quickBar.addEventListener('click', function(e) {{
        var dot = e.target.closest('.quick-dot');
        if (!dot) return;
        loadDate(dot.dataset.date);
    }});

    dateList.innerHTML = DAYS.map(function(d) {{
        var shColor = d.sh_pct >= 0 ? '#4ade80' : '#f87171';
        var kcColor = d.kc_pct >= 0 ? '#4ade80' : '#f87171';
        var cyColor = d.cy_pct >= 0 ? '#4ade80' : '#f87171';
        var msColor = d.health === '强势' ? '#4ade80' : d.health === '弱势' ? '#f87171' : '#d29922';

        var leadersHtml = '';
        if (d.leaders && d.leaders.length > 0) {{
            leadersHtml = d.leaders.map(function(l) {{
                var sc = l.score;
                var scColor = sc >= 100 ? '#4ade80' : sc >= 50 ? '#86efac' : sc >= 20 ? '#facc15' : '#f87171';
                return '<span style="color:' + scColor + '">' + l.name + '<sup>' + sc.toFixed(0) + '%</sup></span>';
            }}).join(' · ');
        }} else {{
            leadersHtml = '<span style="color:#555">—</span>';
        }}

        var tags = '';
        if (d.is_today) tags += '<span class="today-tag">今天</span>';
        if (d.is_monday) tags += '<span class="mon-tag">周一</span>';

        var sectorHint = '';
        if (d.top_mainline && d.top_mainline.length > 0) {{
            sectorHint = '<span style="color:#d29922">★</span> ' + d.top_mainline.join(' · ');
        }}

        var isActive = d.date === DEFAULT_DATE;

        return '<div class="date-item' + (isActive?' active':'') + '" data-date="' + d.date + '">'
            + '<div class="date-label">' + d.label + tags + '</div>'
            + '<div class="sh-line">上证<span style="color:' + shColor + ';font-weight:600">' + (d.sh_pct>=0?'+':'') + d.sh_pct.toFixed(2) + '%</span>'
            + ' 科创<span style="color:' + kcColor + ';font-weight:600">' + (d.kc_pct>=0?'+':'') + d.kc_pct.toFixed(2) + '%</span>'
            + ' 创业<span style="color:' + cyColor + ';font-weight:600">' + (d.cy_pct>=0?'+':'') + d.cy_pct.toFixed(2) + '%</span>'
            + ' <span style="color:' + msColor + ';font-size:10px;font-weight:600">' + d.health + '</span>'
            + ' <span style="color:#666;font-size:10px">↑' + d.uptrend_count + '</span></div>'
            + '<div class="leaders-line">' + leadersHtml + '</div>'
            + (sectorHint ? '<div class="sector-hint">' + sectorHint + '</div>' : '')
            + '</div>';
    }}).join('');

    dateList.addEventListener('click', function(e) {{
        var item = e.target.closest('.date-item');
        if (!item) return;
        loadDate(item.dataset.date);
    }});

    window.loadDate = function(dateStr) {{
        var items = document.querySelectorAll('.date-item');
        for (var i = 0; i < items.length; i++) items[i].classList.remove('active');
        var target = document.querySelector('.date-item[data-date="' + dateStr + '"]');
        if (target) {{
            target.classList.add('active');
        }}
        reportFrame.src = 'trend_dashboard_' + dateStr + '.html';
    }};

    loadDate(DEFAULT_DATE);

    // 键盘: ↑↓切换日期, [ 收起侧边栏
    document.addEventListener('keydown', function(e) {{
        if (e.key === 'ArrowUp' || e.key === 'ArrowDown') {{
            e.preventDefault();
            var cur = document.querySelector('.date-item.active');
            if (!cur) return;
            var all = Array.from(document.querySelectorAll('.date-item'));
            var idx = all.indexOf(cur);
            var next = e.key === 'ArrowDown' ? idx + 1 : idx - 1;
            if (next >= 0 && next < all.length) {{
                loadDate(all[next].dataset.date);
            }}
        }}
        if (e.key === '[') {{
            document.body.classList.toggle('nav-collapsed');
            toggleBtn.textContent = document.body.classList.contains('nav-collapsed') ? '▶' : '◀';
        }}
    }});
}})();
</script>
</body>
</html>'''

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✅ 导航壳页面已生成: {output_path}")
    print(f"   文件大小: {len(html):,} 字节 | {len(entries_sorted)} 天")


def main():
    print("=" * 60)
    print("🏗️  生成 Dashboard 导航壳页面")
    print("=" * 60)

    print("\n📂 加载 date_nav.json...")
    dates_data = load_date_nav()
    all_dates = [d["date"] for d in dates_data]
    print(f"   共 {len(dates_data)} 个交易日")

    leader_codes = collect_all_leader_codes(dates_data)
    print(f"   需映射的股票代码: {len(leader_codes)}")

    print("\n📥 拉取股票名称映射...")
    name_map = build_stock_name_map(leader_codes)

    print("\n📈 拉取指数数据...")
    index_data = fetch_index_data(all_dates)

    print("\n🔀 合并数据...")
    enriched = enrich_dates(dates_data, index_data, name_map)

    with_idx = sum(1 for e in enriched if e["sh_pct"] != 0.0)
    with_leaders = sum(1 for e in enriched if e["leaders"])
    print(f"   有指数数据: {with_idx}/{len(enriched)}")
    print(f"   有龙头数据: {with_leaders}/{len(enriched)}")

    print("\n📄 生成HTML...")
    output_path = os.path.join(DASHBOARD_DIR, "index.html")
    generate_html(enriched, output_path)

    print("\n" + "=" * 60)
    print("✅ 完成！启动服务:")
    print(f"   python3 scripts/serve.py")
    print(f"   或: cd dashboard && python3 -m http.server 8765")
    print("=" * 60)


if __name__ == "__main__":
    main()
