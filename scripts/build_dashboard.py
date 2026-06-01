#!/usr/bin/env python3
"""生成完整的 Dashboard HTML，内嵌分析数据JSON。"""
import json
from datetime import datetime

PROJECT_ROOT = "/Users/liuliang19/Desktop/project/trend_following_system"

# 读取分析数据
with open(f"{PROJECT_ROOT}/dashboard/data/dashboard_data.json") as f:
    data = json.load(f)

json_str = json.dumps(data, ensure_ascii=False, default=str)
# 防止 </script> 破坏 HTML script 标签
json_str = json_str.replace("</script>", "<\\/script>").replace("</Script>", "<\\/Script>")

html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>趋势跟随交易系统 — Dashboard</title>
<style>
/* ========== 全局 ========== */
:root {{
  --bg-primary: #0f1117;
  --bg-card: #161b22;
  --bg-card-hover: #1c2128;
  --bg-elevated: #21262d;
  --border: #30363d;
  --border-light: #484f58;
  --text-primary: #e6edf3;
  --text-secondary: #8b949e;
  --text-muted: #6e7681;
  --green: #238636;
  --green-bg: rgba(35,134,54,0.15);
  --red: #da3633;
  --red-bg: rgba(218,54,51,0.15);
  --gold: #d29922;
  --gold-bg: rgba(210,153,34,0.15);
  --blue: #58a6ff;
  --blue-bg: rgba(88,166,255,0.12);
  --teal: #39d353;
  --orange: #f0883e;
  --radius: 8px;
  --font-mono: 'SF Mono', 'Menlo', 'Monaco', 'Consolas', monospace;
  --font-sans: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans SC', sans-serif;
}}

* {{ margin:0; padding:0; box-sizing:border-box; }}

body {{
  background: var(--bg-primary);
  color: var(--text-primary);
  font-family: var(--font-sans);
  line-height: 1.6;
  min-height: 100vh;
}}

/* ========== Header ========== */
.header {{
  background: linear-gradient(135deg, #161b22 0%, #0d1117 100%);
  border-bottom: 1px solid var(--border);
  padding: 16px 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  position: sticky;
  top: 0;
  z-index: 100;
}}
.header-left h1 {{
  font-size: 20px;
  font-weight: 700;
  background: linear-gradient(90deg, #58a6ff, #3fb950);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}}
.header-left .subtitle {{
  font-size: 12px;
  color: var(--text-secondary);
}}
.header-right {{
  display: flex;
  align-items: center;
  gap: 16px;
}}
.health-badge {{
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  border-radius: 20px;
  font-size: 14px;
  font-weight: 600;
}}
.health-strong {{ background: var(--green-bg); color: var(--teal); border: 1px solid var(--green); }}
.health-normal {{ background: var(--gold-bg); color: var(--gold); border: 1px solid var(--gold); }}
.health-weak {{ background: var(--red-bg); color: var(--red); border: 1px solid var(--red); }}
.health-dot {{
  width: 10px; height: 10px;
  border-radius: 50%;
  display: inline-block;
  animation: pulse 2s infinite;
}}
@keyframes pulse {{
  0%,100% {{ opacity:1; transform:scale(1); }}
  50% {{ opacity:0.5; transform:scale(0.8); }}
}}
.health-dot.green {{ background: var(--teal); }}
.health-dot.gold {{ background: var(--gold); }}
.health-dot.red {{ background: var(--red); }}

/* ========== Container ========== */
.container {{
  max-width: 1400px;
  margin: 0 auto;
  padding: 20px 24px;
}}

/* ========== Overview Cards ========== */
.overview-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
  margin-bottom: 24px;
}}
.overview-card {{
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 16px;
  text-align: center;
  transition: border-color 0.2s;
}}
.overview-card:hover {{ border-color: var(--border-light); }}
.overview-card .number {{
  font-size: 32px;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
}}
.overview-card .label {{
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 4px;
}}
.number.green {{ color: var(--teal); }}
.number.gold {{ color: var(--gold); }}
.number.blue {{ color: var(--blue); }}
.number.red {{ color: var(--red); }}

/* ========== Mainline Section ========== */
.section-title {{
  font-size: 16px;
  font-weight: 700;
  margin: 24px 0 12px;
  display: flex;
  align-items: center;
  gap: 8px;
}}
.section-title .icon {{ font-size: 18px; }}
.mainline-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px;
  margin-bottom: 24px;
}}
.mainline-card {{
  background: linear-gradient(135deg, rgba(210,153,34,0.08) 0%, rgba(210,153,34,0.02) 100%);
  border: 2px solid var(--gold);
  border-radius: var(--radius);
  padding: 16px;
  position: relative;
  overflow: hidden;
  transition: transform 0.15s, box-shadow 0.15s;
}}
.mainline-card:hover {{
  transform: translateY(-2px);
  box-shadow: 0 4px 20px rgba(210,153,34,0.15);
}}
.mainline-card::before {{
  content: '★ 主线';
  position: absolute;
  top: 8px;
  right: 10px;
  font-size: 11px;
  color: var(--gold);
  font-weight: 700;
}}
.mainline-card .sector-name {{
  font-size: 16px;
  font-weight: 700;
  margin-bottom: 8px;
}}
.mainline-card .sector-name a {{
  color: var(--gold);
  text-decoration: none;
}}
.mainline-card .sector-name a:hover {{ text-decoration: underline; }}
.mainline-card .indicators {{
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}}
.indicator-tag {{
  font-size: 11px;
  padding: 3px 8px;
  border-radius: 12px;
  font-weight: 600;
}}
.tag-pass {{ background: var(--green-bg); color: var(--teal); border: 1px solid rgba(35,134,54,0.4); }}
.tag-fail {{ background: var(--red-bg); color: var(--red); border: 1px solid rgba(218,54,51,0.4); }}

/* ========== Table ========== */
.table-wrapper {{
  overflow-x: auto;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  margin-bottom: 24px;
  background: var(--bg-card);
}}
table {{
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}}
thead {{
  position: sticky;
  top: 0;
  z-index: 10;
}}
th {{
  background: var(--bg-elevated);
  color: var(--text-secondary);
  font-weight: 600;
  text-align: left;
  padding: 10px 12px;
  border-bottom: 2px solid var(--border);
  white-space: nowrap;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}}
th.sortable {{
  cursor: pointer;
  user-select: none;
}}
th.sortable:hover {{ color: var(--text-primary); }}
th.sortable .sort-arrow {{ font-size: 10px; margin-left: 4px; }}
td {{
  padding: 8px 12px;
  border-bottom: 1px solid var(--border);
  vertical-align: middle;
}}
tr.row-main {{ cursor: pointer; transition: background 0.15s; }}
tr.row-main:hover {{ background: var(--bg-card-hover); }}
tr.row-expanded {{ background: var(--bg-card-hover); }}
tr.row-main.mainline-row {{
  background: linear-gradient(90deg, rgba(210,153,34,0.06) 0%, transparent 100%);
  border-left: 3px solid var(--gold);
}}

/* State badges */
.state-badge {{
  display: inline-block;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 700;
  white-space: nowrap;
}}
.state-1 {{ background: rgba(110,118,129,0.2); color: var(--text-muted); }}
.state-2 {{ background: var(--orange); color: #000; }}
.state-3 {{ background: rgba(57,211,83,0.2); color: var(--teal); border: 1px solid rgba(57,211,83,0.3); }}
.state-4 {{ background: var(--green); color: #fff; }}
.state-5 {{ background: var(--gold-bg); color: var(--gold); border: 1px solid rgba(210,153,34,0.3); }}
.state-3p {{ background: var(--red-bg); color: var(--red); border: 1px solid rgba(218,54,51,0.3); }}

/* Score bar */
.score-bar {{
  height: 6px;
  background: var(--bg-elevated);
  border-radius: 3px;
  overflow: hidden;
  min-width: 50px;
}}
.score-fill {{
  height: 100%;
  border-radius: 3px;
  transition: width 0.3s;
}}

/* Condition dots */
.condition-dots {{
  display: flex;
  gap: 4px;
}}
.cond-dot {{
  width: 8px; height: 8px;
  border-radius: 50%;
}}
.cond-dot.pass {{ background: var(--teal); }}
.cond-dot.fail {{ background: var(--red); }}
.cond-dot.na {{ background: var(--text-muted); }}

/* Links */
a.symbol-link {{
  color: var(--blue);
  text-decoration: none;
  font-weight: 600;
}}
a.symbol-link:hover {{ text-decoration: underline; }}
a.symbol-link:visited {{ color: #79c0ff; }}

/* Expand detail panel */
.expand-panel {{
  background: #0d1117;
  border-top: 1px solid var(--border);
  padding: 16px 24px;
}}
.expand-panel .detail-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 12px;
}}
.detail-card {{
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 12px;
}}
.detail-card h4 {{
  font-size: 12px;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 8px;
}}
.detail-card p {{
  font-size: 13px;
  color: var(--text-primary);
  line-height: 1.5;
}}
.reason-list {{
  list-style: none;
  padding: 0;
}}
.reason-list li {{
  font-size: 13px;
  padding: 4px 0;
  padding-left: 16px;
  position: relative;
  color: var(--text-secondary);
}}
.reason-list li::before {{
  content: '>';
  position: absolute;
  left: 0;
  color: var(--blue);
  font-weight: 700;
}}
.price-data {{
  font-family: var(--font-mono);
  font-size: 13px;
  color: var(--blue);
}}

/* Arrow indicators */
.arrow-up {{ color: var(--teal); }}
.arrow-down {{ color: var(--red); }}

/* Expand icon */
.expand-icon {{
  display: inline-block;
  transition: transform 0.2s;
  font-size: 12px;
  color: var(--text-muted);
  margin-left: 4px;
}}
.expand-icon.open {{ transform: rotate(90deg); }}

/* Footer */
.footer {{
  border-top: 1px solid var(--border);
  padding: 16px 24px;
  text-align: center;
  color: var(--text-muted);
  font-size: 12px;
  margin-top: 32px;
}}

/* Search */
.search-box {{
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 20px;
  padding: 6px 14px;
  color: var(--text-primary);
  font-size: 13px;
  width: 220px;
  outline: none;
  transition: border-color 0.2s;
}}
.search-box:focus {{ border-color: var(--blue); }}
.search-box::placeholder {{ color: var(--text-muted); }}

/* Tab navigation */
.tabs {{
  display: flex;
  gap: 0;
  border-bottom: 2px solid var(--border);
  margin-bottom: 16px;
}}
.tab {{
  padding: 8px 16px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
  cursor: pointer;
  border: none;
  background: none;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  transition: color 0.2s, border-color 0.2s;
}}
.tab:hover {{ color: var(--text-primary); }}
.tab.active {{
  color: var(--blue);
  border-bottom-color: var(--blue);
}}

/* Empty state */
.empty-state {{
  text-align: center;
  padding: 32px;
  color: var(--text-muted);
}}
.empty-state .icon {{ font-size: 32px; margin-bottom: 8px; }}

/* Responsive */
@media (max-width: 768px) {{
  .header {{ flex-direction: column; align-items: flex-start; }}
  .overview-grid {{ grid-template-columns: repeat(2, 1fr); }}
  .mainline-grid {{ grid-template-columns: 1fr; }}
  th {{ font-size: 11px; padding: 8px 6px; }}
  td {{ font-size: 12px; padding: 6px 8px; }}
}}

/* Tooltip */
.tooltip-hint {{
  border-bottom: 1px dotted var(--text-muted);
  cursor: help;
}}

/* Summary row */
.summary-row td {{
  background: var(--bg-elevated);
  font-weight: 700;
  font-size: 12px;
  color: var(--text-secondary);
  padding: 6px 12px;
}}

/* ========== Print ========== */
@media print {{
  body {{ background: white; color: black; }}
  .header {{ position: static; }}
}}
</style>
</head>
<body>

<div class="header">
  <div class="header-left">
    <h1>趋势跟随交易系统</h1>
    <div class="subtitle">Dashboard &bull; {data['date']} &bull; 生成时间 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
  </div>
  <div class="header-right">
    <input type="text" class="search-box" placeholder="搜索板块/个股..." id="searchInput" oninput="handleSearch()">
    <div class="health-badge { 'health-strong' if data['overview']['market_health'] == '强势' else 'health-normal' if data['overview']['market_health'] == '正常' else 'health-weak' }">
      <span class="health-dot { 'green' if data['overview']['market_health'] == '强势' else 'gold' if data['overview']['market_health'] == '正常' else 'red' }"></span>
      市场健康度: {data['overview']['market_health']}
    </div>
  </div>
</div>

<div class="container">
  <!-- 概览卡片 -->
  <div class="overview-grid">
    <div class="overview-card">
      <div class="number blue">{data['overview']['total_sectors']}</div>
      <div class="label">全板块总数</div>
    </div>
    <div class="overview-card">
      <div class="number green">{data['overview']['uptrend_sectors']}</div>
      <div class="label">上涨趋势板块 (状态3/4/5)</div>
    </div>
    <div class="overview-card">
      <div class="number gold">{data['overview']['mainline_sectors']}</div>
      <div class="label">市场主线板块 ★</div>
    </div>
    <div class="overview-card">
      <div class="number green">{data['overview']['state4_sectors']}</div>
      <div class="label">状态4 (上涨趋势)</div>
    </div>
    <div class="overview-card">
      <div class="number blue">{data['overview']['trend_stocks']}</div>
      <div class="label">趋势个股 (状态3/4/5)</div>
    </div>
    <div class="overview-card">
      <div class="number green">{data['overview']['state4_stocks']}</div>
      <div class="label">状态4个股</div>
    </div>
  </div>

  <!-- 市场主线板块 -->
  <div class="section-title"><span class="icon">⭐</span> 市场主线板块 <span style="color:var(--text-muted);font-weight:400;font-size:12px;">（状态4 + 三条件全满）</span></div>
  <div id="mainlineContainer"></div>

  <!-- Tabs -->
  <div class="tabs">
    <button class="tab active" onclick="switchTab('sectors')" id="tabSectors">板块分析 (90)</button>
    <button class="tab" onclick="switchTab('stocks')" id="tabStocks">个股分析 ({ len(data['stocks']) })</button>
  </div>

  <!-- 板块表格 -->
  <div id="sectorsPanel">
    <div class="section-title"><span class="icon">📊</span> 全板块状态表 <span style="color:var(--text-muted);font-weight:400;font-size:12px;">点击行展开详情</span></div>
    <div class="table-wrapper">
      <table id="sectorsTable">
        <thead>
          <tr>
            <th style="width:40px"></th>
            <th>板块名称</th>
            <th>代码</th>
            <th>状态</th>
            <th>得分</th>
            <th title="结构/量能/持续性">三条件</th>
            <th>当前价</th>
            <th>MA20偏离</th>
            <th>20日涨跌</th>
            <th>量比</th>
            <th>连阳</th>
            <th>仓位</th>
          </tr>
        </thead>
        <tbody id="sectorsTbody"></tbody>
      </table>
    </div>
  </div>

  <!-- 个股表格 -->
  <div id="stocksPanel" style="display:none">
    <div class="section-title"><span class="icon">📈</span> 趋势个股 <span style="color:var(--text-muted);font-weight:400;font-size:12px;">点击行展开详情</span></div>
    <div class="table-wrapper">
      <table id="stocksTable">
        <thead>
          <tr>
            <th style="width:40px"></th>
            <th>股票名称</th>
            <th>代码</th>
            <th>状态</th>
            <th>得分</th>
            <th title="结构/量能/持续性">三条件</th>
            <th>当前价</th>
            <th>MA20偏离</th>
            <th>20日涨跌</th>
            <th>止损价</th>
            <th>仓位</th>
          </tr>
        </thead>
        <tbody id="stocksTbody"></tbody>
      </table>
    </div>
  </div>
</div>

<div class="footer">
  趋势跟随交易系统 &copy; 2026 &bull; 基于状态机 + 三条件验证 &bull; 数据截止 {data['date']} &bull; 本系统仅供学习参考，不构成投资建议
</div>

<script>
const DATA = {json_str};

// ── Helpers ──
function fmtPrice(v) {{ return typeof v === 'number' ? v.toLocaleString('zh-CN', {{ minimumFractionDigits: 2, maximumFractionDigits: 2 }}) : v; }}
function fmtPct(v) {{ return typeof v === 'number' ? (v >= 0 ? '+' : '') + v.toFixed(1) + '%' : v; }}
function fmtRatio(v) {{ return typeof v === 'number' ? v.toFixed(2) : v; }}
function stateClass(s) {{ return s === "3'" ? 'state-3p' : 'state-' + s; }}

function getScoreColor(s) {{
  if (s >= 80) return 'var(--teal)';
  if (s >= 60) return 'var(--blue)';
  if (s >= 40) return 'var(--gold)';
  if (s >= 20) return 'var(--orange)';
  return 'var(--red)';
}}

function condDots(c) {{
  return `<div class="condition-dots">${{['structure','volume','persistence'].map(k =>
    `<span class="cond-dot ${{c[k].pass ? 'pass' : 'fail'}}" title="${{c[k].detail}}"></span>`
  ).join('')}}</div>`;
}}

function posLabel(p) {{
  if (p === 1.0) return '100%';
  if (p === 0) return '0%';
  if (p === 0.166) return '1/6';
  if (p === 0.333) return '1/3';
  return (p*100).toFixed(0)+'%';
}}

// ── Render Mainline ──
(function() {{
  const ml = DATA.mainline;
  const container = document.getElementById('mainlineContainer');
  if (ml.length === 0) {{
    container.innerHTML = '<div class="empty-state"><div class="icon">🔍</div>暂无主线板块（状态4+三条件全满）</div>';
    return;
  }}
  container.innerHTML = '<div class="mainline-grid">' + ml.map(s => `
    <div class="mainline-card">
      <div class="sector-name"><a href="${{s.link}}" target="_blank" rel="noopener">${{s.name}}</a> <span style="font-size:11px;color:var(--text-muted)">${{s.code}}</span></div>
      <div style="font-size:13px;color:var(--text-secondary);margin-bottom:8px">
        <span>${{fmtPrice(s.price)}}</span>
        <span class="${{s.ma_deviation >= 0 ? 'arrow-up' : 'arrow-down'}}">MA20偏离 ${{fmtPct(s.ma_deviation)}}</span>
        <span class="${{s.ret_20d >= 0 ? 'arrow-up' : 'arrow-down'}}">20日 ${{fmtPct(s.ret_20d)}}</span>
      </div>
      <div class="indicators">
        <span class="indicator-tag tag-pass">结构: ${{s.conditions.structure.pass ? '通过' : '未通过'}}</span>
        <span class="indicator-tag tag-pass">量能: ${{s.conditions.volume.pass ? '通过' : '未通过'}}</span>
        <span class="indicator-tag tag-pass">持续性: ${{s.conditions.persistence.pass ? '通过' : '未通过'}}</span>
        <span class="indicator-tag tag-pass">得分: ${{s.score}}/100</span>
      </div>
      <div style="margin-top:8px;font-size:12px;color:var(--text-muted)">
        ${{s.prev_high ? '前高: '+s.prev_high.price.toLocaleString() : '无前高'}} |
        ${{s.prev_low ? '前低: '+s.prev_low.price.toLocaleString() : '无前低'}}
      </div>
    </div>
  `).join('') + '</div>';
}})();

// ── Render Sectors Table ──
(function() {{
  const tbody = document.getElementById('sectorsTbody');
  const sectors = DATA.sectors;
  let html = '';
  sectors.forEach((s, idx) => {{
    const isMain = s.is_mainline;
    const pctClass = s.ma_deviation >= 0 ? 'arrow-up' : 'arrow-down';
    const retClass = s.ret_20d >= 0 ? 'arrow-up' : 'arrow-down';
    const scoreColor = getScoreColor(s.score);
    html += `<tr class="row-main ${{isMain ? 'mainline-row' : ''}}" onclick="toggleExpand(this, 'sector', ${{idx}})" id="sectorRow${{idx}}">
      <td><span class="expand-icon" id="sectorIcon${{idx}}">▶</span></td>
      <td><a href="${{s.link}}" target="_blank" rel="noopener" class="symbol-link" onclick="event.stopPropagation()">${{s.name}}</a></td>
      <td style="color:var(--text-muted);font-size:12px">${{s.code}}</td>
      <td><span class="state-badge ${{stateClass(s.state)}}">${{s.state_label}}</span></td>
      <td>
        <div style="display:flex;align-items:center;gap:6px">
          <span style="color:${{scoreColor}};font-weight:700;font-size:12px">${{s.score}}</span>
          <div class="score-bar"><div class="score-fill" style="width:${{s.score}}%;background:${{scoreColor}}"></div></div>
        </div>
      </td>
      <td>${{condDots(s.conditions)}}</td>
      <td style="font-family:var(--font-mono)">${{fmtPrice(s.price)}}</td>
      <td class="${{pctClass}}" style="font-family:var(--font-mono)">${{fmtPct(s.ma_deviation)}}</td>
      <td class="${{retClass}}" style="font-family:var(--font-mono)">${{fmtPct(s.ret_20d)}}</td>
      <td style="font-family:var(--font-mono)">${{fmtRatio(s.vol_ratio)}}</td>
      <td style="font-family:var(--font-mono)">${{s.max_consecutive_yang}}天</td>
      <td style="font-family:var(--font-mono);font-weight:600">${{posLabel(s.position)}}</td>
    </tr>`;
    // Expanded detail row
    html += `<tr class="row-expanded" id="sectorDetail${{idx}}" style="display:none"><td colspan="12"><div class="expand-panel"><div class="detail-grid">
      <div class="detail-card">
        <h4>📐 条件A: 结构判断</h4>
        <p class="${{s.conditions.structure.pass ? '' : 'arrow-down'}}">${{s.conditions.structure.pass ? '<span class="arrow-up">通过</span>' : '<span class="arrow-down">未通过</span>'}} — ${{s.conditions.structure.detail}}</p>
      </div>
      <div class="detail-card">
        <h4>📊 条件B: 量能判断</h4>
        <p class="${{s.conditions.volume.pass ? '' : 'arrow-down'}}">${{s.conditions.volume.pass ? '<span class="arrow-up">通过</span>' : '<span class="arrow-down">未通过</span>'}} — ${{s.conditions.volume.detail}}</p>
      </div>
      <div class="detail-card">
        <h4>⏱ 条件C: 持续性判断</h4>
        <p class="${{s.conditions.persistence.pass ? '' : 'arrow-down'}}">${{s.conditions.persistence.pass ? '<span class="arrow-up">通过</span>' : '<span class="arrow-down">未通过</span>'}} — ${{s.conditions.persistence.detail}}</p>
      </div>
      <div class="detail-card">
        <h4>📍 前高 / 前低</h4>
        <p>
          ${{s.prev_high ? '<span style="color:var(--teal)">前高: <span class="price-data">'+s.prev_high.price.toLocaleString()+'</span> ('+s.prev_high.date+')</span>' : '<span class="arrow-down">未检测到前高</span>'}}
          <br>
          ${{s.prev_low ? '<span style="color:var(--red)">前低: <span class="price-data">'+s.prev_low.price.toLocaleString()+'</span> ('+s.prev_low.date+')</span>' : '<span class="arrow-down">未检测到前低</span>'}}
        </p>
      </div>
      <div class="detail-card">
        <h4>💡 状态判定原因</h4>
        <ul class="reason-list">
          ${{(s.reasons || []).map(r => '<li>'+r+'</li>').join('')}}
        </ul>
      </div>
      <div class="detail-card">
        <h4>📋 技术指标</h4>
        <p style="font-size:12px;line-height:1.8">
          MA20: ${{s.ma20 ? s.ma20.toLocaleString() : 'N/A'}}<br>
          均线上方: ${{s.signals.above_ma20 ? '<span class="arrow-up">是</span>' : '<span class="arrow-down">否</span>'}}<br>
          放量: ${{s.signals.volume_surge ? '<span class="arrow-up">是</span>' : '否'}} |
          缩量: ${{s.signals.volume_shrink ? '是' : '否'}}<br>
          连跌: ${{s.signals.consecutive_drop ? '<span class="arrow-down">是</span>' : '否'}} |
          连涨: ${{s.signals.consecutive_rise ? '<span class="arrow-up">是</span>' : '否'}}<br>
          突破前高: ${{s.signals.broke_prev_high ? '<span class="arrow-up">是</span>' : '否'}} |
          跌破前低: ${{s.signals.broke_prev_low ? '<span class="arrow-down">是</span>' : '否'}}<br>
          近20日: 阳${{s.yang}}/阴${{s.yin}}
        </p>
      </div>
    </div></div></td></tr>`;
  }});
  tbody.innerHTML = html;
}})();

// ── Render Stocks Table ──
(function() {{
  const tbody = document.getElementById('stocksTbody');
  const stocks = DATA.stocks;
  let html = '';
  stocks.forEach((s, idx) => {{
    const isMain = s.is_mainline;
    const pctClass = s.ma_deviation >= 0 ? 'arrow-up' : 'arrow-down';
    const retClass = s.ret_20d >= 0 ? 'arrow-up' : 'arrow-down';
    const scoreColor = getScoreColor(s.score);
    html += `<tr class="row-main ${{isMain ? 'mainline-row' : ''}}" onclick="toggleExpand(this, 'stock', ${{idx}})" id="stockRow${{idx}}">
      <td><span class="expand-icon" id="stockIcon${{idx}}">▶</span></td>
      <td><a href="${{s.link}}" target="_blank" rel="noopener" class="symbol-link" onclick="event.stopPropagation()">${{s.name}}</a></td>
      <td style="color:var(--text-muted);font-size:12px">${{s.code}}</td>
      <td><span class="state-badge ${{stateClass(s.state)}}">${{s.state_label}}</span></td>
      <td>
        <div style="display:flex;align-items:center;gap:6px">
          <span style="color:${{scoreColor}};font-weight:700;font-size:12px">${{s.score}}</span>
          <div class="score-bar"><div class="score-fill" style="width:${{s.score}}%;background:${{scoreColor}}"></div></div>
        </div>
      </td>
      <td>${{condDots(s.conditions)}}</td>
      <td style="font-family:var(--font-mono)">${{fmtPrice(s.price)}}</td>
      <td class="${{pctClass}}" style="font-family:var(--font-mono)">${{fmtPct(s.ma_deviation)}}</td>
      <td class="${{retClass}}" style="font-family:var(--font-mono)">${{fmtPct(s.ret_20d)}}</td>
      <td style="font-family:var(--font-mono);color:var(--red)">${{s.stop_loss ? fmtPrice(s.stop_loss) : 'N/A'}}</td>
      <td style="font-family:var(--font-mono);font-weight:600">${{posLabel(s.position)}}</td>
    </tr>`;
    html += `<tr class="row-expanded" id="stockDetail${{idx}}" style="display:none"><td colspan="11"><div class="expand-panel"><div class="detail-grid">
      <div class="detail-card">
        <h4>📐 条件A: 结构判断</h4>
        <p>${{s.conditions.structure.detail}}</p>
      </div>
      <div class="detail-card">
        <h4>📊 条件B: 量能判断</h4>
        <p>${{s.conditions.volume.detail}}</p>
      </div>
      <div class="detail-card">
        <h4>⏱ 条件C: 持续性判断</h4>
        <p>${{s.conditions.persistence.detail}}</p>
      </div>
      <div class="detail-card">
        <h4>🛡 止损价格</h4>
        <p>${{s.stop_loss ? '<span style="color:var(--red);font-size:18px;font-weight:700;font-family:var(--font-mono)">'+s.stop_loss.toLocaleString('zh-CN', {{minimumFractionDigits:2}})+'</span><br><span style="font-size:11px;color:var(--text-muted)">前低 < '+s.stop_loss.toLocaleString('zh-CN', {{minimumFractionDigits:2}}) < 止损</span>' : '无前低参考'}}</p>
      </div>
      <div class="detail-card">
        <h4>📋 交易指标</h4>
        <p style="font-size:12px;line-height:1.8">
          当前价: <span style="font-family:var(--font-mono);color:var(--blue)">${{fmtPrice(s.price)}}</span><br>
          MA20偏离: <span class="${{pctClass}}">${{fmtPct(s.ma_deviation)}}</span><br>
          20日涨跌: <span class="${{retClass}}">${{fmtPct(s.ret_20d)}}</span><br>
          量比: <span style="font-family:var(--font-mono)">${{fmtRatio(s.vol_ratio)}}</span><br>
          最大连阳: ${{s.max_consecutive_yang}}天
        </p>
      </div>
    </div></div></td></tr>`;
  }});
  tbody.innerHTML = html;
}})();

// ── Expand/Collapse ──
function toggleExpand(row, type, idx) {{
  const detailRow = document.getElementById(type + 'Detail' + idx);
  const icon = document.getElementById(type + 'Icon' + idx);
  if (detailRow.style.display === 'none' || detailRow.style.display === '') {{
    detailRow.style.display = '';
    icon.classList.add('open');
  }} else {{
    detailRow.style.display = 'none';
    icon.classList.remove('open');
  }}
}}

// ── Tabs ──
let currentTab = 'sectors';
function switchTab(tab) {{
  currentTab = tab;
  document.getElementById('tabSectors').classList.toggle('active', tab === 'sectors');
  document.getElementById('tabStocks').classList.toggle('active', tab === 'stocks');
  document.getElementById('sectorsPanel').style.display = tab === 'sectors' ? '' : 'none';
  document.getElementById('stocksPanel').style.display = tab === 'stocks' ? '' : 'none';
}}

// ── Search ──
function handleSearch() {{
  const query = document.getElementById('searchInput').value.toLowerCase().trim();
  if (currentTab === 'sectors') {{
    filterTable('sector', DATA.sectors, query);
  }} else {{
    filterTable('stock', DATA.stocks, query);
  }}
}}

function filterTable(type, items, query) {{
  for (let i = 0; i < items.length; i++) {{
    const item = items[i];
    const match = !query || item.name.toLowerCase().includes(query) || item.code.includes(query);
    const mainRow = document.getElementById(type + 'Row' + i);
    const detailRow = document.getElementById(type + 'Detail' + i);
    if (mainRow) mainRow.style.display = match ? '' : 'none';
    if (detailRow && !match) {{
      detailRow.style.display = 'none';
      const icon = document.getElementById(type + 'Icon' + i);
      if (icon) icon.classList.remove('open');
    }}
  }}
}}

// ── Keyboard: Escape closes all details ──
document.addEventListener('keydown', function(e) {{
  if (e.key === 'Escape') {{
    const type = currentTab === 'sectors' ? 'sector' : 'stock';
    const items = currentTab === 'sectors' ? DATA.sectors : DATA.stocks;
    for (let i = 0; i < items.length; i++) {{
      const detailRow = document.getElementById(type + 'Detail' + i);
      const icon = document.getElementById(type + 'Icon' + i);
      if (detailRow) detailRow.style.display = 'none';
      if (icon) icon.classList.remove('open');
    }}
  }}
}});
</script>
</body>
</html>"""

output_path = f"{PROJECT_ROOT}/dashboard/index.html"
with open(output_path, "w") as f:
    f.write(html)

print(f"Dashboard HTML 已生成: {output_path}")
print(f"文件大小: {len(html):,} 字节")
print(f"包含 {len(data['sectors'])} 个板块, {len(data['stocks'])} 只个股")
print(f"主线板块: {len(data['mainline'])}")
