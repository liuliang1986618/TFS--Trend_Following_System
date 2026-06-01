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
theme_name_map = {str(row["code"]): row["name"] for _, row in themes_df.iterrows()}

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


# ====== 个股名称 + 板块映射 + 龙头计算（永久固化）======
print("\n5. 个股名称+板块映射+龙头...")
import baostock as _bs, re as _re
_bs.login()
_rs = _bs.query_stock_basic()
_code_name = {}
while (_rs.error_code=='0') & _rs.next():
    _row = _rs.get_row_data()
    _code_name[_row[0].replace("sh.","").replace("sz.","")] = _row[1]
_rs2 = _bs.query_stock_industry()
_stock_ind = {}
while (_rs2.error_code=='0') & _rs2.next():
    _row = _rs2.get_row_data()
    _code = _row[1].replace("sh.","").replace("sz.","")
    _ind = _row[3]
    _m = _re.match(r'[A-Z]\d+(.+)', _ind) if _ind else None
    _stock_ind[_code] = _m.group(1) if _m else _ind
_bs.logout()

# 名称填充
for _s in all_stocks:
    _s["name"] = _code_name.get(_s["code"], _s["code"])

# baostock→板块映射（完整版）
_bs_map = {
    "计算机、通信和其他电子设备制造业": ["半导体","元件","光学光电子","消费电子","电子化学品","其他电子"],
    "酒、饮料和精制茶制造业": ["白酒","饮料制造","食品饮料"],
    "货币金融服务": ["银行"],"资本市场服务": ["证券"],"保险业": ["保险"],
    "电力、热力生产和供应业": ["电力","燃气"],
    "电气机械和器材制造业": ["电机","白色家电","电池","光伏设备","风电设备","电网设备","其他电源设备","家电","小家电","黑色家电"],
    "汽车制造业": ["汽车整车","汽车零部件"],
    "软件和信息技术服务业": ["软件开发","IT服务","计算机应用","计算机设备"],
    "医药制造业": ["医药生物","化学制药","中药","生物制品"],
    "专用设备制造业": ["医疗器械","自动化设备","工程机械","轨交设备","环保设备","农化制品","专用设备"],
    "煤炭开采和洗选业": ["煤炭开采加工"],"黑色金属冶炼和压延加工业": ["钢铁"],
    "有色金属冶炼和压延加工业": ["工业金属","小金属","金属新材料","能源金属"],
    "有色金属矿采选业": ["贵金属","工业金属"],
    "石油和天然气开采业": ["油气开采及服务","石油加工贸易"],
    "化学原料和化学制品制造业": ["化学制品","化学原料","化学纤维","塑料","橡胶制品","塑料制品"],
    "非金属矿物制品业": ["建筑材料","非金属材料"],
    "房地产业": ["房地产开发","房地产服务"],
    "生态保护和环境治理业": ["环境治理","环保"],
    "铁路、船舶、航空航天和其他运输设备制造业": ["军工装备","军工电子","轨交设备"],
    "电信、广播电视和卫星传输服务": ["通信服务","通信设备"],
    "互联网和相关服务": ["互联网电商"],"零售业": ["零售","贸易"],"批发业": ["贸易","零售"],
    "食品制造业": ["食品加工制造","调味品"],"农副食品加工业": ["农产品加工","养殖业"],
    "农业": ["种植业与林业"],"畜牧业": ["养殖业"],"渔业": ["养殖业"],
    "纺织业": ["纺织制造"],"纺织服装、服饰业": ["服装家纺"],
    "造纸和纸制品业": ["造纸","包装印刷"],"印刷和记录媒介复制业": ["包装印刷"],
    "家具制造业": ["家居用品"],"化学纤维制造业": ["化学纤维"],
    "橡胶和塑料制品业": ["塑料","橡胶制品"],"通用设备制造业": ["通用设备","自动化设备"],
    "金属制品业": ["金属新材料"],"道路运输业": ["公路铁路运输","物流"],
    "水上运输业": ["港口航运"],"航空运输业": ["机场航运"],
    "仓储业": ["物流"],"邮政业": ["物流"],"住宿业": ["酒店餐饮"],"餐饮业": ["酒店餐饮"],
    "租赁业": ["其他社会服务"],"商务服务业": ["其他社会服务"],
    "研究和试验发展": ["医疗服务"],"专业技术服务业": ["其他社会服务"],
    "卫生": ["医疗器械","医疗服务"],"新闻和出版业": ["文化传媒","传媒"],
    "广播、电视、电影和影视录音制作业": ["影视院线","文化传媒"],
    "娱乐业": ["游戏","旅游及酒店"],"综合": ["综合"],"废弃资源综合利用业": ["环保"],
    "建筑装饰和其他建筑业": ["建筑装饰"],"房屋建筑业": ["建筑装饰"],"土木工程建筑业": ["建筑装饰"],
    "教育": ["教育"],
}
# 个股→板块
for _s in all_stocks:
    _ind = _stock_ind.get(_s["code"], "")
    _s["sectors"] = _bs_map.get(_ind, ["未分类"])
    _s["themes"] = []

# ====== 板块龙头: baostock全覆盖 + 关键词兜底 ======
_kw_fallback = {
    "教育": ["中公","学大","昂立","凯文","传智","行动教育","教育","培训"],
    "汽车服务及其他": ["广汇","中升","永达","美东","中国汽研","汽车服务"],
    "医药商业": ["大参林","老百姓","益丰","一心堂","国药","上海医药","九州通","药房"],
    "包装印刷": ["裕同","合兴","美盈森","劲嘉","永新","奥瑞金","印刷","包装"],
    "多元金融": ["中航产融","中油资本","五矿资本","国投资本","金融"],
    "房地产": ["万科","保利","招商蛇口","金地","新城","滨江","华发","地产","房产"],
    "旅游及酒店": ["中免","锦江","首旅","中青旅","宋城","天目湖","黄山","旅游","酒店"],
    "游戏": ["三七","世纪华通","完美","吉比特","掌趣","巨人","恺英","游族","游戏"],
    "厨卫电器": ["老板","华帝","万和","美大","火星人","亿田","帅丰","厨卫"],
    "美容护理": ["珀莱雅","贝泰妮","上海家化","丸美","华熙","爱美客","美容","护理"],
    "影视院线": ["万达","中国电影","光线","华谊","横店","金逸","幸福蓝海","影视","院线"],
    "零售": ["永辉","王府井","百联","重庆百货","家家悦","红旗","天虹","步步高","超市","百货","零售","连锁","商店","购物"],
    "专用设备": ["先导智能","迈为股份","捷佳伟创","晶盛机电","奥特维","专用设备"],
    "计算机设备": ["中国长城","浪潮信息","中科曙光","广电运通","新北洋","证通电子","计算机"],
    "建筑装饰": ["中国建筑","中国中铁","中国铁建","中国交建","中国电建","隧道股份","宏润建设","装饰","建筑"],
    "塑料制品": ["金发科技","普利特","道恩股份","国恩股份","银禧科技","南京聚隆","塑料"],
}
for _s in all_sectors:
    _sname = _s["name"]
    _candidates = []
    for _code in _code_name:
        _ind = _stock_ind.get(_code, "")
        _matched = _bs_map.get(_ind, [])
        if _sname in _matched:
            _path = f"{data_dir}/stock_{_code}.parquet"
            if os.path.exists(_path):
                _df = pd.read_parquet(_path)
                if len(_df) >= 20:
                    _ts = StateMachine.classify(_df)
                    _price = float(_df["close"].iloc[-1])
                    _ret20 = (_price / float(_df["close"].iloc[-21]) - 1) * 100
                    _candidates.append({"code":_code,"name":_code_name.get(_code,_code),"ret20":round(_ret20,1),"state":_ts.state,"state_label":_ts.state_label})
    # 关键词兜底
    if not _candidates:
        _kws = _kw_fallback.get(_sname, [_sname])
        for _code, _name in _code_name.items():
            if any(_kw in _name for _kw in _kws):
                _path = f"{data_dir}/stock_{_code}.parquet"
                if os.path.exists(_path):
                    _df = pd.read_parquet(_path)
                    if len(_df) >= 20:
                        _ts = StateMachine.classify(_df)
                        _price = float(_df["close"].iloc[-1])
                        _ret20 = (_price / float(_df["close"].iloc[-21]) - 1) * 100
                        _candidates.append({"code":_code,"name":_name,"ret20":round(_ret20,1),"state":_ts.state,"state_label":_ts.state_label})
    _candidates.sort(key=lambda x: (-(x["state"] in (3,4,5)), -x["ret20"]))
    _s["leaders"] = _candidates[:5]
    _s["related_stocks"] = [_c["code"] for _c in _candidates[:10]]

_empty = sum(1 for _s in all_sectors if not _s.get("leaders"))
print(f"  板块龙头: {len(all_sectors)-_empty}/{len(all_sectors)} 有数据")


# 市场健康度
if uptrend_sectors >= 15 and len(mainline) >= 5:
    health = "强势"
elif uptrend_sectors >= 8:
    health = "正常"
else:
    health = "弱势"


# ====== 龙头计算：baostock行业全覆盖 ======
print("\n计算板块龙头...")
import baostock as bs_l, re as re_l
bs_l.login()
rs_l = bs_l.query_stock_industry()
stock_ind_l = {}
while (rs_l.error_code=='0') & rs_l.next():
    row = rs_l.get_row_data()
    code = row[1].replace("sh.","").replace("sz.","")
    ind = row[3]
    m = re_l.match(r'[A-Z]\d+(.+)', ind) if ind else None
    stock_ind_l[code] = m.group(1) if m else ind

rs2_l = bs_l.query_stock_basic()
code_name_l = {}
while (rs2_l.error_code=='0') & rs2_l.next():
    row = rs2_l.get_row_data()
    code_name_l[row[0].replace("sh.","").replace("sz.","")] = row[1]
bs_l.logout()

bs_to_sector_l = {
    "计算机、通信和其他电子设备制造业": ["半导体","元件","光学光电子","消费电子","电子化学品","其他电子"],
    "酒、饮料和精制茶制造业": ["白酒","饮料制造","食品饮料"],
    "货币金融服务": ["银行"],"资本市场服务": ["证券"],"保险业": ["保险"],
    "电力、热力生产和供应业": ["电力","燃气"],
    "电气机械和器材制造业": ["电机","白色家电","电池","光伏设备","风电设备","电网设备","其他电源设备","家电","小家电","黑色家电"],
    "汽车制造业": ["汽车整车","汽车零部件"],
    "软件和信息技术服务业": ["软件开发","IT服务","计算机应用"],
    "医药制造业": ["医药生物","化学制药","中药","生物制品"],
    "专用设备制造业": ["医疗器械","自动化设备","工程机械","轨交设备","环保设备","农化制品"],
    "煤炭开采和洗选业": ["煤炭开采加工"],"黑色金属冶炼和压延加工业": ["钢铁"],
    "有色金属冶炼和压延加工业": ["工业金属","小金属","金属新材料","能源金属"],
    "有色金属矿采选业": ["贵金属","工业金属"],
    "石油和天然气开采业": ["油气开采及服务","石油加工贸易"],
    "化学原料和化学制品制造业": ["化学制品","化学原料","化学纤维","塑料","橡胶制品"],
    "非金属矿物制品业": ["建筑材料","非金属材料"],
    "房地产业": ["房地产开发","房地产服务"],
    "生态保护和环境治理业": ["环境治理","环保"],
    "铁路、船舶、航空航天和其他运输设备制造业": ["军工装备","军工电子","轨交设备"],
    "电信、广播电视和卫星传输服务": ["通信服务","通信设备"],
    "互联网和相关服务": ["互联网电商"],"零售业": ["零售","贸易"],"批发业": ["贸易","零售"],
    "食品制造业": ["食品加工制造","调味品"],"农副食品加工业": ["农产品加工","养殖业"],
    "农业": ["种植业与林业"],"畜牧业": ["养殖业"],"渔业": ["养殖业"],
    "纺织业": ["纺织制造"],"纺织服装、服饰业": ["服装家纺"],
    "造纸和纸制品业": ["造纸"],"印刷和记录媒介复制业": ["包装印刷"],
    "家具制造业": ["家居用品"],"化学纤维制造业": ["化学纤维"],
    "橡胶和塑料制品业": ["塑料","橡胶制品"],"通用设备制造业": ["通用设备","自动化设备"],
    "金属制品业": ["金属新材料"],"道路运输业": ["公路铁路运输","物流"],
    "水上运输业": ["港口航运"],"航空运输业": ["机场航运"],
    "仓储业": ["物流"],"邮政业": ["物流"],"住宿业": ["酒店餐饮"],"餐饮业": ["酒店餐饮"],
    "租赁业": ["其他社会服务"],"商务服务业": ["其他社会服务"],
    "研究和试验发展": ["医疗服务"],"专业技术服务业": ["其他社会服务"],
    "卫生": ["医疗器械","医疗服务"],"新闻和出版业": ["文化传媒","传媒"],
    "广播、电视、电影和影视录音制作业": ["影视院线","文化传媒"],
    "娱乐业": ["游戏","旅游及酒店"],"综合": ["综合"],"废弃资源综合利用业": ["环保"],
}

for s_l in all_sectors:
    sname = s_l["name"]
    candidates = []
    for code in code_name_l:
        ind = stock_ind_l.get(code, "")
        matched = bs_to_sector_l.get(ind, [])
        if sname not in matched: continue
        path = f"{data_dir}/stock_{code}.parquet"
        if not os.path.exists(path): continue
        df = pd.read_parquet(path)
        if len(df) < 20: continue
        ts = StateMachine.classify(df)
        price = float(df["close"].iloc[-1])
        ret20 = (price / float(df["close"].iloc[-21]) - 1) * 100
        candidates.append({
            "code":code,"name":code_name_l.get(code,code),"ret20":round(ret20,1),
            "state":ts.state,"state_label":ts.state_label,
        })
    candidates.sort(key=lambda x: (-(x["state"] in (3,4,5)), -x["ret20"]))
    s_l["leaders"] = candidates[:5]
    s_l["related_stocks"] = [c["code"] for c in candidates[:10]]

empty_ldr = sum(1 for s_l in all_sectors if not s_l.get("leaders"))
print(f"  板块龙头: {len(all_sectors)-empty_ldr}/{len(all_sectors)} 有数据")

# ETF→板块关联 (从etf_results.json加载)
if os.path.exists(f"{data_dir}/etf_results.json"):
    import json as _json
    with open(f"{data_dir}/etf_results.json") as _f:
        _all_etfs = _json.load(_f).get("all", [])
    for s_l in all_sectors:
        s_l["etfs"] = []
        for e_l in _all_etfs:
            ec = e_l.get("code", e_l.get("symbol", ""))
            if s_l["name"] in e_l["name"] or any(kw in e_l["name"] for kw in s_l["name"]):
                s_l["etfs"].append({"symbol":ec,"name":e_l["name"],"state":e_l["state"],"state_label":e_l["state_label"]})

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
