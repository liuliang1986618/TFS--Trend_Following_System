"""生成 Dashboard 内嵌数据 JSON — 全量板块+个股分析结果。

对全部90个板块和39只个股进行状态机分类+三条件+前高前低分析，
输出为 dashboard_data.json 供 Dashboard HTML 内嵌使用。
"""
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from src.engine.state_machine import StateMachine
from src.engine.conditions import TrendConditions
from src.engine.pivots import PivotDetector

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "dashboard", "data")
date_str = sys.argv[1] if len(sys.argv) > 1 else "2026-05-31"

# ── 加载板块列表 ──────────────────────────────────────────
sectors_df = pd.read_json(os.path.join(DATA_DIR, "sector_list.json"))
print(f"板块列表: {len(sectors_df)} 个")

all_sectors = []
for _, row in sectors_df.iterrows():
    code = str(row["code"]).zfill(6)
    name = row["name"]
    path = os.path.join(DATA_DIR, f"sector_{code}.parquet")
    if not os.path.exists(path):
        print(f"  跳过 {code} {name}: 数据文件不存在")
        continue

    df = pd.read_parquet(path)
    if len(df) < 20:
        print(f"  跳过 {code} {name}: 数据不足({len(df)}日)")
        continue

    ts = StateMachine.classify(df)

    # MA20偏离
    ma20 = float(df["close"].rolling(20).mean().iloc[-1])
    price = float(df["close"].iloc[-1])
    ma_deviation = round((price / ma20 - 1) * 100, 1)

    # 近20日涨跌
    ret20 = round((price / float(df["close"].iloc[-21]) - 1) * 100, 1) if len(df) > 20 else 0

    # 量比 (上涨日均量 / 下跌日均量)
    recent = df.iloc[-20:]
    up_mask = recent["close"] > recent["open"]
    down_mask = recent["close"] < recent["open"]
    up_vol = float(recent.loc[up_mask, "volume"].mean()) if up_mask.sum() > 0 else 0
    down_vol = float(recent.loc[down_mask, "volume"].mean()) if down_mask.sum() > 0 else 0
    vol_ratio = round(up_vol / down_vol, 2) if down_vol > 0 else 99

    # 阳线统计
    yang = int(up_mask.sum())
    yin = int(down_mask.sum())

    # 连阳检测
    is_yang = recent["close"] > recent["open"]
    max_cons = 0
    cur = 0
    for v in is_yang:
        if bool(v):
            cur += 1
            max_cons = max(max_cons, cur)
        else:
            cur = 0

    # 前高前低
    ph = PivotDetector.recent_high(df)
    pl = PivotDetector.recent_low(df)

    # 主线判断: 不在此处计算，等全部板块汇总后取 state=4 的 Top2

    # 综合得分（优化版：量能分级评分 + state=3 基础分提升）
    score = 0
    if ts.state == 4:
        score += 70
    elif ts.state == 5:
        score += 55
    elif ts.state == 3:
        score += 50
    elif ts.state == 2:
        score += 15
    if ts.conditions["structure"].pass_:
        score += 10
    # 量能分级评分
    vol_detail = ts.conditions["volume"].detail if ts.conditions["volume"].pass_ else ""
    if "[强势]" in vol_detail:
        score += 15   # 涨时放量，最强
    elif "[健康]" in vol_detail or "[企稳]" in vol_detail:
        score += 10   # 涨时缩量/跌时缩量，偏强
    # 持续性：连阳按天数加分（越强越多）
    if ts.conditions["persistence"].pass_:
        score += 10
        score += max_cons  # 连阳几天加几分
    # 涨幅加分
    if ret20 > 20:
        score += 10
    elif ret20 > 10:
        score += 5

    # 判断状态原因
    reasons = []
    if ts.state == 1:
        if not ts.conditions["structure"].pass_:
            reasons.append("结构条件不通过")
        if not ts.conditions["volume"].pass_:
            reasons.append("量能条件不通过")
        if not ts.conditions["persistence"].pass_:
            reasons.append("持续性条件不通过")
        if ts.consecutive_drop:
            reasons.append("连续下跌")
        if not ts.above_ma20:
            reasons.append("价格在MA20下方(空头排列)")
        if ts.broke_prev_low:
            reasons.append("已跌破前低")
        if not reasons:
            reasons.append("多个条件均不满足, 空头市场")
    elif ts.state == 2:
        if ts.consecutive_rise:
            reasons.append("连续上涨(反弹中)")
        if ts.broke_prev_high:
            reasons.append("已突破前高")
        if not ts.broke_prev_high and ts.above_ma20:
            reasons.append("站上MA20但未破前高")
        if not ts.above_ma20 and ts.consecutive_rise:
            reasons.append("均线下方反弹, 力度待观察")
        if not ts.broke_prev_high and not ts.above_ma20 and not ts.consecutive_rise:
            reasons.append("均线下方整理, 等待反弹信号")
        if ts.conditions["structure"].pass_ and not ts.conditions["volume"].pass_:
            reasons.append("结构好转但量能不足")
        if ts.above_ma20 and ts.broke_prev_high:
            reasons.append("站上均线+突破前高, 接近翻转")
        if not reasons:
            reasons.append("下跌中的反弹, 等待确认信号")
    elif ts.state == 3:
        reasons.append("突破前高, 翻转确认中")
        if ts.above_ma20:
            reasons.append("站上MA20")
        if ts.conditions["structure"].pass_ and ts.conditions["volume"].pass_:
            reasons.append("结构+量能均通过, 即将进入上涨")
        if ts.conditions["structure"].pass_ and not ts.conditions["volume"].pass_:
            reasons.append("结构通过但量能待确认")
        if not ts.above_ma20:
            reasons.append("均线下方, 翻转尚早")
    elif ts.state == 4:
        reasons.append("三条件全满, 强势上涨")
        if ts.broke_prev_high:
            reasons.append("再创新高")
        if ts.consecutive_rise:
            reasons.append("连续上攻, 趋势加速")
    elif ts.state == 5:
        reasons.append("上涨趋势中正常回调")
        if ts.consecutive_drop:
            reasons.append("连续下跌调整")
        if ts.volume_shrink:
            reasons.append("缩量回调(正常调整信号)")
        if ts.volume_surge:
            reasons.append("放量调整(需关注)")
        if not ts.broke_prev_low:
            reasons.append("未破前低, 趋势完好")
    elif ts.state == "3'":
        reasons.append("转跌确认中")
        if ts.broke_prev_low:
            reasons.append("跌破前低")
        if ts.volume_surge:
            reasons.append("放量下跌(危险)")
        if ts.consecutive_drop:
            reasons.append("连续下跌")
    else:
        reasons.append(f"状态{ts.state}: 系统判定")

    all_sectors.append({
        "code": code,
        "name": name,
        "type": "sector",
        "state": ts.state,
        "state_label": ts.state_label,
        "position": ts.position_ratio,
        "conditions": {
            "structure": {"pass": ts.conditions["structure"].pass_, "detail": ts.conditions["structure"].detail},
            "volume": {"pass": ts.conditions["volume"].pass_, "detail": ts.conditions["volume"].detail},
            "persistence": {"pass": ts.conditions["persistence"].pass_, "detail": ts.conditions["persistence"].detail},
        },
        "ma20": round(ma20, 1) if not np.isnan(ma20) else None,
        "price": price,
        "ma_deviation": ma_deviation,
        "ret_20d": ret20,
        "vol_ratio": vol_ratio,
        "yang": yang,
        "yin": yin,
        "max_consecutive_yang": max_cons,
        "prev_high": {"price": round(ph["price"], 2), "date": str(ph["date"])[:10]} if ph else None,
        "prev_low": {"price": round(pl["price"], 2), "date": str(pl["date"])[:10]} if pl else None,
        "is_mainline": False,  # 等全部板块汇总后重新判定
        "link": f"https://q.10jqka.com.cn/thshy/detail/code/{code}/",
        "score": score,
        "reasons": reasons,
        "signals": {
            "above_ma20": ts.above_ma20,
            "volume_surge": ts.volume_surge,
            "volume_shrink": ts.volume_shrink,
            "consecutive_drop": ts.consecutive_drop,
            "consecutive_rise": ts.consecutive_rise,
            "broke_prev_high": ts.broke_prev_high,
            "broke_prev_low": ts.broke_prev_low,
        },
    })

# 排序：状态4>3>5>2>"3'">1，同状态按得分降序
state_order = {4: 0, 3: 1, 5: 2, 2: 3, "3'": 4, 1: 5}
all_sectors.sort(key=lambda x: (state_order.get(x["state"], 99), -x["score"]))

# ── 加载个股 ──────────────────────────────────────────────
stock_files = []
for f in os.listdir(DATA_DIR):
    if f.startswith("stock_") and f.endswith(".parquet"):
        code = f.replace("stock_", "").replace(".parquet", "")
        stock_files.append((code, os.path.join(DATA_DIR, f)))

print(f"个股文件: {len(stock_files)} 个")

# 个股名称映射 (从代码推断常用名称)
stock_name_map = {
    "000001": "平安银行", "000063": "中兴通讯", "000333": "美的集团",
    "000568": "泸州老窖", "000651": "格力电器", "000725": "京东方A",
    "000858": "五粮液", "002230": "科大讯飞", "002371": "北方华创",
    "002415": "海康威视", "002475": "立讯精密", "002594": "比亚迪",
    "002714": "牧原股份", "300059": "东方财富", "300124": "汇川技术",
    "300274": "阳光电源", "300308": "中际旭创", "300433": "蓝思科技",
    "300474": "景嘉微", "300502": "新易盛", "300750": "宁德时代",
    "600030": "中信证券", "600031": "三一重工", "600036": "招商银行",
    "600276": "恒瑞医药", "600519": "贵州茅台", "600585": "海螺水泥",
    "600809": "山西汾酒", "600900": "长江电力", "601012": "隆基绿能",
    "601138": "工业富联", "601318": "中国平安", "601899": "紫金矿业",
    "603259": "药明康德", "688008": "澜起科技", "688036": "传音控股",
    "688111": "金山办公", "688561": "奇安信", "688981": "中芯国际",
}

all_stocks = []
for code, filepath in stock_files:
    name = stock_name_map.get(code, code)
    df = pd.read_parquet(filepath)
    if len(df) < 20:
        continue

    ts = StateMachine.classify(df)

    market = "sh" if code.startswith("6") else "sz"
    price = float(df["close"].iloc[-1])
    pl = PivotDetector.recent_low(df)
    stop_loss = round(pl["price"] * 0.995, 2) if pl else None

    # MA20偏离
    ma20 = float(df["close"].rolling(20).mean().iloc[-1])
    ma_deviation = round((price / ma20 - 1) * 100, 1) if not np.isnan(ma20) else 0

    # 近20日涨跌
    ret20 = round((price / float(df["close"].iloc[-21]) - 1) * 100, 1) if len(df) > 20 else 0

    # 量比
    recent = df.iloc[-20:]
    up_mask_s = recent["close"] > recent["open"]
    down_mask_s = recent["close"] < recent["open"]
    up_vol_s = float(recent.loc[up_mask_s, "volume"].mean()) if up_mask_s.sum() > 0 else 0
    down_vol_s = float(recent.loc[down_mask_s, "volume"].mean()) if down_mask_s.sum() > 0 else 0
    vol_ratio = round(up_vol_s / down_vol_s, 2) if down_vol_s > 0 else 99

    # 连阳
    is_yang_s = recent["close"] > recent["open"]
    max_cons_s = 0
    cur_s = 0
    # 阳线阴线计数
    yang_s = int(up_mask_s.sum())
    yin_s = int(down_mask_s.sum())
    # 前高
    ph_s = PivotDetector.recent_high(df)
    # 状态原因
    reasons_s = []
    if ts.state == 4:
        reasons_s.append("三条件全满, 上涨趋势确认")
    elif ts.state == 3:
        reasons_s.append("翻转确认中, 试探仓位")
    elif ts.state == 2:
        reasons_s.append("下跌中的反弹, 等待突破前高确认")
    elif ts.state == 1:
        reasons_s.append("下跌趋势, 空仓观望")
    for v in is_yang_s:
        if bool(v):
            cur_s += 1
            max_cons_s = max(max_cons_s, cur_s)
        else:
            cur_s = 0

    score = 0
    if ts.state == 4:
        score += 70
    elif ts.state == 3:
        score += 40
    if ts.conditions["structure"].pass_:
        score += 10
    if ts.conditions["volume"].pass_:
        score += 10
    if ts.conditions["persistence"].pass_:
        score += 10

    all_stocks.append({
        "code": code,
        "name": name,
        "type": "stock",
        "state": ts.state,
        "state_label": ts.state_label,
        "position": ts.position_ratio,
        "price": price,
        "stop_loss": stop_loss,
        "ma_deviation": ma_deviation,
        "ret_20d": ret20,
        "vol_ratio": vol_ratio,
        "ma20": round(ma20, 1),
        "yang": yang_s,
        "yin": yin_s,
        "max_consecutive_yang": max_cons_s,
        "conditions": {
            "structure": {"pass": ts.conditions["structure"].pass_, "detail": ts.conditions["structure"].detail},
            "volume": {"pass": ts.conditions["volume"].pass_, "detail": ts.conditions["volume"].detail},
            "persistence": {"pass": ts.conditions["persistence"].pass_, "detail": ts.conditions["persistence"].detail},
        },
        "signals": {
            "above_ma20": bool(ts.above_ma20),
            "volume_surge": bool(ts.volume_surge),
            "volume_shrink": bool(ts.volume_shrink),
            "consecutive_drop": bool(ts.consecutive_drop),
            "consecutive_rise": bool(ts.consecutive_rise),
            "broke_prev_high": bool(ts.broke_prev_high) if hasattr(ts, 'broke_prev_high') else False,
            "broke_prev_low": bool(ts.broke_prev_low) if hasattr(ts, 'broke_prev_low') else False,
        },
        "reasons": reasons_s,
        "prev_high": {"price": round(ph["price"], 2), "date": str(ph["date"])[:10]} if ph else None,
        "prev_low": {"price": round(pl["price"], 2), "date": str(pl["date"])[:10]} if pl else None,
        "is_mainline": ts.state == 4 and ts.conditions["structure"].pass_ and ts.conditions["volume"].pass_ and ts.conditions["persistence"].pass_,
        "link": f"https://quote.eastmoney.com/{market}{code}.html",
        "score": score,
    })

all_stocks.sort(key=lambda x: -x["score"])

# ── 构建完整数据 ──────────────────────────────────────────
# 主线判定: state=4 中 score 最高的 Top2（平局按 20日涨幅排）
s4 = sorted([s for s in all_sectors if s["state"] == 4], key=lambda x: (-x["score"], -x["ret_20d"]))
for s in s4[:2]:
    s["is_mainline"] = True
mainline_sectors = [s for s in all_sectors if s.get("is_mainline")]

data = {
    "date": date_str,
    "generated_at": "2026-05-31T23:59:59",
    "overview": {
        "total_sectors": len(all_sectors),
        "uptrend_sectors": sum(1 for s in all_sectors if s["state"] in {3, 4, 5}),
        "state4_sectors": sum(1 for s in all_sectors if s["state"] == 4),
        "mainline_sectors": len(mainline_sectors),
        "trend_stocks": sum(1 for s in all_stocks if s["state"] in {3, 4, 5}),
        "state4_stocks": sum(1 for s in all_stocks if s["state"] == 4),
        "key_actions": 0,
        "market_health": (
            "强势" if len(mainline_sectors) >= 8 else
            "正常" if len(mainline_sectors) >= 4 else
            "弱势"
        ),
    },
    "mainline": mainline_sectors,
    "sectors": all_sectors,
    "stocks": all_stocks,
}

# 保存数据
output_path = os.path.join(DATA_DIR, "dashboard_data.json")
with open(output_path, "w") as f:
    json.dump(data, f, ensure_ascii=False, default=str)

print(f"\n板块: {len(all_sectors)} | 个股: {len(all_stocks)}")
print(f"上涨板块: {data['overview']['uptrend_sectors']} | 主线板块: {data['overview']['mainline_sectors']}")
print(f"趋势个股: {data['overview']['trend_stocks']} | 状态4个股: {data['overview']['state4_stocks']}")
print(f"市场健康度: {data['overview']['market_health']}")
print(f"\n数据已保存: {output_path}")

# 打印状态分布
for state in [4, 3, 5, 2, "3'", 1]:
    count = sum(1 for s in all_sectors if s["state"] == state)
    print(f"  状态{state}({StateMachine.STATE_LABELS.get(state, '未知')}): {count} 个板块")
