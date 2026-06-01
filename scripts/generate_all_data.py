#!/usr/bin/env python3
"""全量数据生成: 板块+题材+个股+ETF 四层漏斗完整分析"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from src.engine.state_machine import StateMachine
from src.engine.conditions import TrendConditions
from src.engine.pivots import PivotDetector

date_str = "2026-05-31"
data_dir = "dashboard/data"

def make_item(code, name, item_type, ts, price, ma20, ma_deviation, ret20, vol_ratio, yang, yin, max_cons, ph, pl, reasons, market="sh"):
    conds = ts.conditions
    score = 0
    if ts.state == 4: score += 70
    elif ts.state == 3: score += 40
    if conds["structure"].pass_: score += 10
    if conds["volume"].pass_: score += 10
    if conds["persistence"].pass_: score += 10

    is_mainline = (ts.state == 4 and conds["structure"].pass_ and conds["volume"].pass_ and conds["persistence"].pass_)

    if item_type == "sector":
        link = f"https://q.10jqka.com.cn/thshy/detail/code/{code}/"
    elif item_type == "theme":
        link = f"https://q.10jqka.com.cn/gn/detail/code/{code}/"
    else:
        link = f"https://quote.eastmoney.com/{market}{code}.html"

    stop_loss = round(pl["price"] * 0.995, 2) if pl else None

    return {
        "code": code, "name": name, "type": item_type,
        "state": ts.state, "state_label": ts.state_label,
        "position": ts.position_ratio, "score": score,
        "price": price, "ma20": round(ma20, 1), "ma_deviation": ma_deviation,
        "ret_20d": ret20, "vol_ratio": vol_ratio,
        "yang": yang, "yin": yin, "max_consecutive_yang": max_cons,
        "conditions": {
            "structure": {"pass": conds["structure"].pass_, "detail": conds["structure"].detail},
            "volume": {"pass": conds["volume"].pass_, "detail": conds["volume"].detail},
            "persistence": {"pass": conds["persistence"].pass_, "detail": conds["persistence"].detail},
        },
        "signals": {
            "above_ma20": bool(ts.above_ma20),
            "volume_surge": bool(ts.volume_surge),
            "volume_shrink": bool(ts.volume_shrink),
        },
        "prev_high": {"price": round(ph["price"],2), "date": str(ph["date"])[:10]} if ph else None,
        "prev_low": {"price": round(pl["price"],2), "date": str(pl["date"])[:10]} if pl else None,
        "stop_loss": stop_loss,
        "is_mainline": is_mainline,
        "link": link, "reasons": reasons,
    }

def analyze_df(df):
    """对DataFrame运行完整分析，返回所有指标"""
    ts = StateMachine.classify(df)
    price = float(df["close"].iloc[-1])
    ma20 = float(df["close"].rolling(20).mean().iloc[-1])
    if np.isnan(ma20): ma20 = price
    ma_deviation = round((price/ma20 - 1)*100, 1)
    ret20 = round((price/float(df["close"].iloc[-21]) - 1)*100, 1) if len(df) > 20 else 0

    recent = df.iloc[-20:]
    up_mask = recent["close"] > recent["open"]
    down_mask = recent["close"] < recent["open"]
    up_vol = float(recent.loc[up_mask, "volume"].mean()) if up_mask.sum() > 0 else 0
    down_vol = float(recent.loc[down_mask, "volume"].mean()) if down_mask.sum() > 0 else 0
    vol_ratio = round(up_vol/down_vol, 2) if down_vol > 0 else 99
    yang = int(up_mask.sum())
    yin = int(down_mask.sum())
    is_yang = recent["close"] > recent["open"]
    max_cons = cur = 0
    for v in is_yang:
        if bool(v): cur += 1; max_cons = max(max_cons, cur)
        else: cur = 0

    ph = PivotDetector.recent_high(df)
    pl = PivotDetector.recent_low(df)

    reasons = []
    if ts.state == 4: reasons = ["三条件全满, 上涨趋势确认", "标准仓位持股"]
    elif ts.state == 3: reasons = ["翻转确认中", "试探仓位, 等待再创新高"]
    elif ts.state == 2:
        reasons = ["下跌中的反弹"]
        if not ts.conditions["structure"].pass_: reasons.append("结构条件未满足")
        if not ts.conditions["volume"].pass_: reasons.append("量能不足")
        if not ts.above_ma20: reasons.append("价格在MA20下方")
    elif ts.state == 1: reasons = ["下跌趋势", "空仓观望"]

    return ts, price, ma20, ma_deviation, ret20, vol_ratio, yang, yin, max_cons, ph, pl, reasons


# ====== 1. 板块层 ======
print("=" * 60)
print("1. 板块层 (90个)")
print("=" * 60)
sectors_df = pd.read_json(f"{data_dir}/sector_list.json")
all_sectors = []
for _, row in sectors_df.iterrows():
    code = str(row["code"])
    name = row["name"]
    path = f"{data_dir}/sector_{code}.parquet"
    if not os.path.exists(path): continue
    df = pd.read_parquet(path)
    if len(df) < 20: continue
    try:
        ts, price, ma20, ma_dev, ret20, vr, yang, yin, mc, ph, pl, reasons = analyze_df(df)
        all_sectors.append(make_item(code, name, "sector", ts, price, ma20, ma_dev, ret20, vr, yang, yin, mc, ph, pl, reasons))
    except: pass
all_sectors.sort(key=lambda x: (isinstance(x["state"],str), -x["score"] if x["state"] in (3,4,5) else x["score"]))
print(f"  板块: {len(all_sectors)}个 | 状态4: {sum(1 for s in all_sectors if s['state']==4)} | 状态3: {sum(1 for s in all_sectors if s['state']==3)}")

# ====== 2. 题材层 ======
print("\n2. 题材层 (20个)")
theme_files = sorted([f for f in os.listdir(data_dir) if f.startswith("theme_") and f.endswith(".parquet")])
themes_df = pd.read_json(f"{data_dir}/theme_list.json")
theme_name_map = {str(row["code"]): row["theme_name"] for _, row in themes_df.iterrows()}

all_themes = []
for f in theme_files:
    code = f.replace("theme_","").replace(".parquet","")
    name = theme_name_map.get(code, code)
    path = f"{data_dir}/{f}"
    df = pd.read_parquet(path)
    if len(df) < 20: continue
    try:
        ts, price, ma20, ma_dev, ret20, vr, yang, yin, mc, ph, pl, reasons = analyze_df(df)
        all_themes.append(make_item(code, name, "theme", ts, price, ma20, ma_dev, ret20, vr, yang, yin, mc, ph, pl, reasons))
    except: pass
all_themes.sort(key=lambda x: (isinstance(x["state"],str), -x["score"]))
print(f"  题材: {len(all_themes)}个 | 状态4: {sum(1 for t in all_themes if t['state']==4)} | 状态3: {sum(1 for t in all_themes if t['state']==3)}")

# ====== 3. 个股层 ======
print("\n3. 个股层 (39只)")
stock_name_map = {
    "600519":"贵州茅台","000858":"五粮液","688981":"中芯国际","002415":"海康威视",
    "300750":"宁德时代","000001":"平安银行","601138":"工业富联","002230":"科大讯飞",
    "600036":"招商银行","000333":"美的集团","601318":"中国平安","600030":"中信证券",
    "601012":"隆基绿能","000725":"京东方A","002594":"比亚迪","300059":"东方财富",
    "000651":"格力电器","300124":"汇川技术","000568":"泸州老窖","300308":"中际旭创",
    "300502":"新易盛","688012":"中微公司","688111":"金山办公","688036":"传音控股",
    "300274":"阳光电源","601899":"紫金矿业","600276":"恒瑞医药","600900":"长江电力",
    "000063":"中兴通讯","000568":"泸州老窖","002475":"立讯精密","300433":"蓝思科技",
    "002371":"北方华创","002714":"牧原股份","600031":"三一重工","600809":"山西汾酒",
    "601012":"隆基绿能","688008":"澜起科技","688561":"奇安信",
}
stock_files = [(f.replace("stock_","").replace(".parquet",""), f"{data_dir}/{f}") for f in os.listdir(data_dir) if f.startswith("stock_") and f.endswith(".parquet")]

all_stocks = []
for code, filepath in stock_files:
    name = stock_name_map.get(code, code)
    df = pd.read_parquet(filepath)
    if len(df) < 20: continue
    try:
        ts, price, ma20, ma_dev, ret20, vr, yang, yin, mc, ph, pl, reasons = analyze_df(df)
        market = "sh" if code.startswith("6") else "sz"
        all_stocks.append(make_item(code, name, "stock", ts, price, ma20, ma_dev, ret20, vr, yang, yin, mc, ph, pl, reasons, market))
    except: pass
# 只保留状态3/4/5的个股
trend_stocks = [s for s in all_stocks if s["state"] in (3,4,5)]
trend_stocks.sort(key=lambda x: -x["score"])
print(f"  个股: {len(all_stocks)}只 | 趋势: {len(trend_stocks)}只 | 状态4: {sum(1 for s in trend_stocks if s['state']==4)}")

# ====== 4. 漏斗统计 ======
mainline = [s for s in all_sectors if s["is_mainline"]]
uptrend_sectors = sum(1 for s in all_sectors if s["state"] in (3,4,5))
state4_themes = sum(1 for t in all_themes if t["state"] == 4)
state3_themes = sum(1 for t in all_themes if t["state"] == 3)
state4_stocks = sum(1 for s in all_stocks if s["state"] == 4)

# 市场健康度
if uptrend_sectors >= 15 and len(mainline) >= 5:
    health = "强势"
elif uptrend_sectors >= 8:
    health = "正常"
else:
    health = "弱势"

data = {
    "date": date_str,
    "generated_at": "2026-06-01T00:00:00",
    "overview": {
        "total_sectors": len(all_sectors),
        "uptrend_sectors": uptrend_sectors,
        "mainline_sectors": len(mainline),
        "state4_sectors": sum(1 for s in all_sectors if s["state"] == 4),
        "total_themes": len(all_themes),
        "active_themes": state4_themes + state3_themes,
        "trend_stocks": len(trend_stocks),
        "state4_stocks": state4_stocks,
        "market_health": health,
    },
    "funnel": {
        "layers": [
            {"name": "全市场板块", "count": len(all_sectors), "color": "#8b949e"},
            {"name": "上涨板块(状态3/4/5)", "count": uptrend_sectors, "color": "#58a6ff"},
            {"name": "主线板块(三条件全满)", "count": len(mainline), "color": "#d29922"},
            {"name": "活跃题材(状态3/4)", "count": state4_themes + state3_themes, "color": "#a371f7"},
            {"name": "趋势个股(状态3/4/5)", "count": len(trend_stocks), "color": "#3fb950"},
        ]
    },
    "mainline": mainline,
    "sectors": all_sectors,
    "themes": all_themes,
    "stocks": trend_stocks,
}

with open(f"{data_dir}/dashboard_data.json", "w") as f:
    json.dump(data, f, ensure_ascii=False, default=str)

print(f"\n{'='*60}")
print(f"市场健康度: {health}")
print(f"漏斗: {len(all_sectors)}板块 → {uptrend_sectors}上涨 → {len(mainline)}主线 → {state4_themes+state3_themes}题材 → {len(trend_stocks)}个股")
