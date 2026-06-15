#!/bin/bash
# 趋势跟随系统 — 每日完整构建+验证
set -e
cd /Users/liuliang19/Desktop/project/trend_following_system
DATE=$(python3 -c "import json;print(json.load(open('dashboard/data/dashboard_data.json'))['date'])")
echo "=== $(date) 构建 $DATE ==="

echo "0/7 date_check"; python3 -c "
import json, os, sys
from datetime import datetime, timedelta
nav = json.load(open('dashboard/data/date_nav.json'))
nav_dates = {e['date'] for e in nav['dates']}
existing = {f.replace('trend_dashboard_','').replace('.html','')
            for f in os.listdir('dashboard') if f.startswith('trend_dashboard_') and f.endswith('.html')}
today = datetime.now()
missing = []
for i in range(30):
    d = (today - timedelta(days=i)).strftime('%Y-%m-%d')
    dt = datetime.strptime(d, '%Y-%m-%d')
    if dt.weekday() >= 5: continue
    if d not in existing or d not in nav_dates:
        missing.append(d)
if missing:
    print(f'❌ 缺失{len(missing)}个交易日: {missing}，请先补齐再构建')
    sys.exit(1)
print(f'✅ 近30天日期完整')
"

echo "1/7 build_final"; python3 scripts/build_final.py
echo "2/7 render_action_panel"; python3 scripts/render_action_panel.py $DATE
echo "3/7 build_funnel_cards"; python3 scripts/build_funnel_cards.py $DATE
echo "4/7 render_funnel_panel"; python3 scripts/render_funnel_panel.py $DATE
echo "5/7 build_nav_index (MUST be last)"; python3 scripts/build_nav_index.py
echo "6/7 verify"; python3 -c "
h=open('dashboard/trend_dashboard_${DATE}.html').read()
for t in ['稳健推荐','强势追踪','强势板块深度穿透','焦点板块','widget-details']:
    assert t in h, f'MISSING: {t}'
assert h.count('WATCHLIST') == 1, f'WATCHLIST={h.count(\"WATCHLIST\")}'
print('✅ 全部验证通过')
"
echo "7/7 serve"; lsof -ti :8765 | xargs kill -9 2>/dev/null
python3 -c "
from http.server import HTTPServer, SimpleHTTPRequestHandler
class H(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cache-Control','no-store,no-cache,must-revalidate,max-age=0')
        self.send_header('Pragma','no-cache');self.send_header('Expires','0')
        super().end_headers()
import os;os.chdir('dashboard');print('no-cache :8765');HTTPServer(('',8765),H).serve_forever()
" &
sleep 1
open "http://localhost:8765/index.html?v=$(date +%s)"
echo "=== $(date) 完成 ==="
