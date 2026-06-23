#!/bin/bash
# === 每日渲染流程（固化版） ===
# 用法: bash scripts/render_daily.sh [YYYY-MM-DD]
# 默认今天: bash scripts/render_daily.sh
#
# 此脚本已通过 playwright 验证：7 panel布局正确，数据全部来自真实扫描。
# 以后每日只需运行此脚本，不再手动打补丁。

set -e
DATE="${1:-$(date +%Y-%m-%d)}"
PROJECT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT"

echo "=== 趋势跟随系统 每日渲染 [$DATE] ==="

# Step 1: pipeline（生成 actions + dashboard_data）
echo "[1/6] pipeline..."
python3 pipeline.py 2>&1 | tail -3

# Step 2: 全量扫描（enhanced_actions 真实数据）
echo "[2/6] 全量扫描..."
python3 -c "
from src.enhanced_actions import EnhancedActionGenerator
import json, warnings; warnings.filterwarnings('ignore')
gen = EnhancedActionGenerator()
etf, hot_etf = gen._scan_best_etfs('$DATE')
stock, hot_stock = gen._scan_best_stocks('$DATE')
r = {'date':'$DATE','market_regime':'neutral','etf_cards':etf,'stock_cards':stock,'hot_etf_cards':hot_etf,'hot_stock_cards':hot_stock}
json.dump(r, open('dashboard/data/enhanced_actions_$DATE.json','w'), ensure_ascii=False, indent=2)
print(f'  ✅ etf={len(etf)} stock={len(stock)} hot_etf={len(hot_etf)} hot_stock={len(hot_stock)}')
"

# Step 3: build_final（基础 HTML）
echo "[3/6] build_final..."
python3 scripts/build_final.py 2>&1 | tail -1

# Step 4: render_action（注入操作面板模板）
echo "[4/6] render_action..."
python3 scripts/render_action_panel.py 2>&1 | tail -1

# Step 5: render_funnel（注入深度穿透）
echo "[5/6] render_funnel..."
python3 scripts/render_funnel_panel.py 2>&1 | tail -1

# Step 6: 验证（确保面板格式完整，不被覆盖）
echo "[6/6] 验证..."
python3 << PYEOF
import re
date_str = '${DATE}'
with open(f'dashboard/trend_dashboard_{date_str}.html') as f:
    h = f.read()
errors = []
for t in ['稳健推荐','强势追踪','强势板块深度穿透','焦点板块','widget-details']:
    if t not in h:
        errors.append(f'MISSING: {t}')
if errors:
    for e in errors: print(f'  ❌ {e}')
    exit(1)
details_count = len(re.findall(r'<details[\s>]', h))
if details_count < 5:
    print(f'  ❌ 面板格式错误：details标签不足({details_count})，疑似简化格式覆盖了Widget面板')
    exit(1)
wd = h.count('widget-details')
print(f'  ✅ 全部验证通过 (widget-details={wd}, details={details_count})')
PYEOF

# 侧边栏
python3 scripts/build_nav_index.py 2>&1 | tail -1

echo ""
echo "✅ 完成！"
echo "   打开: open http://127.0.0.1:8765/index.html"
