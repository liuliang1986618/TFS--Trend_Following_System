#!/usr/bin/env python3
"""批量修复所有历史Dashboard — 更新actions watchlist + 注入面板"""
import json, os, sys, glob, pickle, subprocess
import pandas as pd
import numpy as np

PROJECT = os.path.dirname(os.path.abspath(__file__))
os.chdir(PROJECT)
sys.path.insert(0, PROJECT)
from src.fusion.scanner import MarketScanner

print("📦 Step 1: 更新所有 actions_*.json 的 watchlist")
scanner = MarketScanner()
with open(os.path.join(PROJECT, "data", "stock_names.json")) as nf:
    nmap = json.load(nf)
with open(os.path.join(PROJECT, "watchlist.json")) as f:
    wl = json.load(f)
codes = wl.get("stocks", [])

afiles = sorted(glob.glob(os.path.join(PROJECT, "dashboard", "data", "actions_*.json")))
for af in afiles:
    with open(af) as f:
        adata = json.load(f)
    ds = adata["date"]
    new_wl = []
    for wcode in codes:
        rpath = os.path.join(PROJECT, "data", "massive_stocks", f"{wcode}.pkl")
        if not os.path.exists(rpath):
            continue
        df = pickle.load(open(rpath, "rb"))
        df["date"] = pd.to_datetime(df["date"])
        md = df["date"] <= pd.Timestamp(ds)
        if md.sum() < 30:
            continue
        idx = int(md.sum() - 1)
        close = df["close"].values[:idx+1].astype(float)
        volume = df["volume"].values[:idx+1].astype(float)
        hcol = "high" if "high" in df.columns else "close"
        lcol = "low" if "low" in df.columns else "close"
        high = df[hcol].values[:idx+1].astype(float)
        low = df[lcol].values[:idx+1].astype(float)
        ind = scanner._calc_indicators(close, volume, high, low)
        score = scanner._score_stock(ind)
        name = nmap.get(wcode, wcode)
        mkt = "sh" if str(wcode).startswith("6") else "sz"
        link = f"https://quote.eastmoney.com/{mkt}{wcode}.html"
        if score is None:
            new_wl.append({"code": wcode, "name": name, "score": 0, "action": "回避",
                           "position_pct": 0, "reason": "趋势过滤未通过", "link": link,
                           "state": scanner._determine_tfs_state(close),
                           "ma_deviation": ind.get("ma_deviation", 0),
                           "ret_20d": ind.get("pct_20d", 0)})
        else:
            res = scanner._result_from_row(wcode, name, score, ind, is_etf=False)
            res.state = scanner._determine_tfs_state(close)
            new_wl.append({"code": res.code, "name": res.name, "score": res.score,
                           "action": res.action, "position_pct": res.position_pct,
                           "reason": res.reason, "link": res.link, "state": res.state,
                           "ma_deviation": res.ma_deviation, "ret_20d": res.ret_20d})
    adata["watchlist"] = new_wl
    with open(af, "w") as f:
        json.dump(adata, f, ensure_ascii=False, indent=2)
    print(f"  ✅ {ds}: {len(new_wl)} 只")

print("\n🏗️  Step 2: 重新生成所有 Dashboard HTML")
subprocess.run([sys.executable, os.path.join(PROJECT, "scripts", "build_final.py")],
               cwd=PROJECT, timeout=120, capture_output=True)
print("  ✅ build_final.py 完成")

print("\n📄 Step 3: 注入面板到最近30天页面")
dash_files = sorted(glob.glob(os.path.join(PROJECT, "dashboard", "trend_dashboard_*.html")))
dash_files = dash_files[-30:]  # 最近30天
for df in dash_files:
    ds = df.split("_")[-1].replace(".html", "")
    r = subprocess.run(
        [sys.executable, os.path.join(PROJECT, "scripts", "render_action_panel.py"), ds],
        cwd=PROJECT, capture_output=True, text=True, timeout=60
    )
    # 只看最后一行输出
    lines = [l for l in r.stdout.strip().split("\n") if l.strip()]
    if lines:
        print(f"  {lines[-1]}")

print("\n📄 Step 4: 重新生成侧边栏导航")
subprocess.run([sys.executable, os.path.join(PROJECT, "scripts", "build_nav_index.py")],
               cwd=PROJECT, timeout=120, capture_output=True)
print("  ✅ build_nav_index.py 完成")
print("\n✅ 全部完成！")
