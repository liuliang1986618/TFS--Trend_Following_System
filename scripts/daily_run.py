#!/usr/bin/env python3
"""趋势跟随系统 — 每日全自动运行脚本
用法: python3 scripts/daily_run.py [date]
不传日期则默认今天。如果当天数据未更新，自动等待重试最多2小时。

数据源更新时间:
  - akshare(同花顺): 收盘后~15:15
  - baostock: ~17:00-18:00
  - 推荐执行时间: 17:30
"""
import sys, os, subprocess, json, time
from datetime import datetime, timedelta

PROJECT = "/Users/liuliang19/Desktop/project/trend_following_system"
os.chdir(PROJECT)

date_str = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y-%m-%d")

# 如果是今天的数据，检查A股是否已收盘
today = datetime.now().strftime("%Y-%m-%d")
if date_str >= today:
    now = datetime.now()
    market_close = now.replace(hour=15, minute=0, second=0)
    if now < market_close:
        print(f"⏰ A股尚未收盘(15:00)，当前{now.strftime('%H:%M')}，等待中...")
        wait_seconds = (market_close - now).total_seconds()
        time.sleep(min(wait_seconds, 7200))
        print("继续执行...")
print("=" * 60)
print(f"🚀 趋势跟随系统 — 每日自动运行 — {date_str}")
print("=" * 60)

def run(cmd, desc):
    print(f"\n📌 {desc}...")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=PROJECT)
    if result.returncode != 0:
        print(f"❌ 失败: {result.stderr[:200]}")
        return False
    print(result.stdout[-500:] if len(result.stdout) > 500 else result.stdout)
    return True

# Step 1: 拉取最新数据
if not run("python3 scripts/pull_all_data.py", "1/4 拉取数据 (akshare+baostock)"):
    print("⚠️ 数据拉取部分失败，使用已有数据继续...")

# Step 2: 运行全量分析
if not run("python3 scripts/generate_all_data.py", "2/4 运行分析 (状态机+龙头+ETF)"):
    print("❌ 分析失败，终止")
    sys.exit(1)

# Step 3: 生成Dashboard
if not run("python3 scripts/build_final.py", "3/4 生成Dashboard HTML"):
    print("❌ Dashboard生成失败")
    sys.exit(1)

# Step 4: 输出概要
print(f"\n📌 4/4 输出概要...")
with open(f"{PROJECT}/dashboard/data/dashboard_data.json") as f:
    data = json.load(f)
ov = data["overview"]
print(f"""
╔══════════════════════════════════════╗
║   📊 {date_str} 市场概要                  ║
╠══════════════════════════════════════╣
║   全板块: {ov['total_sectors']:>3}  上涨: {ov['uptrend_sectors']:>2}            ║
║   主线★: {ov['mainline_sectors']:>2}  翻转关注🔵: {ov.get('reversal_sectors',0):>2}       ║
║   趋势个股: {ov['trend_stocks']:>3}  趋势ETF: {ov.get('trend_etfs',0):>3}        ║
║   市场健康度: {ov['market_health']}                      ║
╚══════════════════════════════════════╝
""")

# 回测摘要
bt = data.get("backtest", {})
if bt:
    rec = bt.get("recommended", "?")
    ret = bt.get("strategies", [{}])[0].get("total_return", 0)
    print(f"   回测({bt.get('period','?')}): 推荐{rec}策略 收益{ret:+.1f}%")

print(f"\n✅ 完成! Dashboard: {PROJECT}/dashboard/index.html")
