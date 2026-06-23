#!/bin/bash
# 趋势跟随系统 — 环境初始化脚本
# 新设备pull代码后首次运行: bash scripts/setup.sh
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PROJECT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT"

echo "============================================"
echo "  趋势跟随系统 · 环境初始化"
echo "============================================"
echo ""

# ── Step 1: Python环境 ──
echo -n "[1/5] Python环境..."
PYTHON=$(which python3 2>/dev/null || echo "")
if [ -z "$PYTHON" ]; then
    echo -e " ${RED}❌ 未找到python3${NC}"
    echo "  请先安装Python 3.9+: brew install python@3.9"
    exit 1
fi
PY_VER=$($PYTHON --version 2>&1 | awk '{print $2}')
echo -e " ${GREEN}✅ $PY_VER${NC}"

# ── Step 2: 依赖检查 ──
echo ""
echo "[2/5] 依赖检查..."
MISSING=""

check_pkg() {
    $PYTHON -c "import $1" 2>/dev/null && echo -e "  ${GREEN}✅${NC} $1" || { echo -e "  ${YELLOW}⬇${NC} $1 (需安装)"; MISSING="$MISSING $2"; }
}

check_pkg tickflow tickflow==0.1.24
check_pkg akshare akshare
check_pkg pandas pandas
check_pkg numpy numpy
check_pkg playwright playwright

if [ -n "$MISSING" ]; then
    echo ""
    echo -n "  安装缺失依赖..."
    $PYTHON -m pip install $MISSING -q 2>&1 | tail -1
    echo -e " ${GREEN}✅ 依赖安装完成${NC}"
fi

# playwright浏览器
if ! $PYTHON -c "from playwright.sync_api import sync_playwright; sync_playwright().__enter__().chromium.launch(headless=True).close()" 2>/dev/null; then
    echo -n "  安装Playwright Chromium..."
    $PYTHON -m playwright install chromium 2>&1 | tail -1
    echo -e " ${GREEN}✅${NC}"
fi

# ── Step 3: 数据完整性 ──
echo ""
echo "[3/5] 数据完整性检查..."
DATA_DIR="dashboard/data"

STOCK_COUNT=$(ls $DATA_DIR/stock/*.parquet 2>/dev/null | wc -l | tr -d ' ')
ETF_COUNT=$(ls $DATA_DIR/etf/*.parquet 2>/dev/null | wc -l | tr -d ' ')
SECTOR_COUNT=$(ls $DATA_DIR/sector/*.parquet 2>/dev/null | wc -l | tr -d ' ')
THEME_COUNT=$(ls $DATA_DIR/theme/*.parquet 2>/dev/null | wc -l | tr -d ' ')

NEED_DOWNLOAD=false
check_count() {
    local label=$1 count=$2 threshold=$3
    if [ "$count" -ge "$threshold" ]; then
        echo -e "  ${GREEN}✅${NC} $label: ${count}个 (≥${threshold})"
    else
        echo -e "  ${RED}❌${NC} $label: ${count}个 (需≥${threshold})"
        NEED_DOWNLOAD=true
    fi
}

check_count "个股" "$STOCK_COUNT" 4500
check_count "ETF" "$ETF_COUNT" 600
check_count "板块" "$SECTOR_COUNT" 80
check_count "题材" "$THEME_COUNT" 180

# ── Step 4: 数据下载 ──
echo ""
if $NEED_DOWNLOAD; then
    echo "[4/5] 数据下载（首次需1-3小时）..."
    echo "  开始时间: $(date '+%H:%M:%S')"
    $PYTHON -c "
import sys, os, warnings
sys.path.insert(0, '.')
warnings.filterwarnings('ignore')
from src.data_mgr.fetcher import DataFetcher
from datetime import datetime

f = DataFetcher()
today = datetime.now().strftime('%Y-%m-%d')
print(f'  目标日期: {today}')
print('  Phase 1/3: 板块+题材+ETF日K...')
f.init_db_light(today)
print('  Phase 2/3: 全量个股日K（约45批）...')
f.init_db_stocks(today)
print('  Phase 3/3: 完整性验证...')
stats = f.get_db_stats()
for k, v in stats.items():
    print(f'    {k}: {v}')
print('  ✅ 数据下载完成')
" 2>&1
    echo "  结束时间: $(date '+%H:%M:%S')"
else
    echo "[4/5] 数据完整，跳过下载"
fi

# ── Step 5: 生成数据文件 ──
echo ""
echo "[5/5] 生成中间数据..."
$PYTHON -c "
import sys, warnings
sys.path.insert(0, '.')
warnings.filterwarnings('ignore')

from datetime import datetime
today = datetime.now().strftime('%Y-%m-%d')

# stock_sectors.json
import json, os
if not os.path.exists('dashboard/data/stock_sectors.json'):
    cm = json.load(open('dashboard/data/constituent_map.json'))
    rev = cm.get('reverse', {})
    sec_list = json.load(open('dashboard/data/sector_list.json'))
    sec_names = {s['code']: s['name'] for s in sec_list}
    stock_sectors = {}
    for code, info in rev.items():
        sectors = info.get('sectors', [])
        if sectors:
            stock_sectors[code] = sec_names.get(sectors[0], sectors[0])
    json.dump(stock_sectors, open('dashboard/data/stock_sectors.json','w'), ensure_ascii=False)
    print(f'  ✅ stock_sectors.json: {len(stock_sectors)}只')
else:
    print('  ✅ stock_sectors.json 已存在')

# stock_names.json
if not os.path.exists('data/stock_names.json'):
    # 复制到老路径（兼容build_funnel_cards）
    import shutil
    if os.path.exists('dashboard/data/stock_names.json'):
        shutil.copy('dashboard/data/stock_names.json', 'data/stock_names.json')
        print('  ✅ stock_names.json 已复制')
" 2>&1

echo ""
echo "============================================"
echo -e "  ${GREEN}✅ 环境初始化完成！${NC}"
echo ""
echo "  运行系统: bash scripts/render_daily.sh"
echo "  打开页面: open http://localhost:8765/index.html"
echo "============================================"
