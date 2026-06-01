#!/usr/bin/env python3
"""全量数据管道 - 多层降级, 自动重试, 绝不停在单个失败上"""
import time, os, sys, json, traceback

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dashboard", "data")
os.makedirs(DATA_DIR, exist_ok=True)

class Retry:
    """自动重试 + 多源降级"""
    @staticmethod
    def run(sources, name, max_retries=3):
        """依次尝试多个数据源, 每个源重试max_retries次, 直到有一个成功"""
        for i, (source_name, source_fn) in enumerate(sources):
            for attempt in range(max_retries):
                try:
                    result = source_fn()
                    if result is not None and (not hasattr(result, '__len__') or len(result) > 0):
                        return result
                    time.sleep(0.5 * (attempt + 1))
                except Exception as e:
                    if attempt < max_retries - 1:
                        time.sleep(1 * (attempt + 1))
                    else:
                        pass  # 最后一个attempt失败, 继续下一个source
        return None

def pull_sector_list():
    """板块列表: akshare同花顺"""
    def ths():
        import akshare as ak
        df = ak.stock_board_industry_name_ths()
        df.columns = ["name","code"]
        return df
    return Retry.run([("akshare-ths", ths)], "板块列表")

def pull_sector_daily(name, code, start, end):
    """板块日K: akshare同花顺 → akshare东财"""
    def ths():
        import akshare as ak
        df = ak.stock_board_industry_index_ths(symbol=name, start_date=start, end_date=end)
        df = df.rename(columns={"日期":"date","开盘价":"open","最高价":"high","最低价":"low","收盘价":"close","成交量":"volume","成交额":"amount"})
        df["date"] = pd.to_datetime(df["date"])
        df.set_index("date", inplace=True)
        return df[["open","high","low","close","volume"]]
    return Retry.run([("akshare-ths", ths)], "板块日K(%s)"%name, max_retries=5)

def pull_sector_constituents(name):
    """板块成分股: akshare → baostock行业映射"""
    def ths_cons():
        import akshare as ak
        df = ak.stock_board_industry_cons_ths(symbol=name)
        return df
    return Retry.run([("akshare-cons", ths_cons)], "成分股(%s)"%name, max_retries=2)

def pull_concept_list():
    """题材列表"""
    def ths():
        import akshare as ak
        df = ak.stock_board_concept_name_ths()
        df.columns = ["name","code"]
        return df
    return Retry.run([("akshare-ths", ths)], "题材列表")

def pull_concept_daily(name, start, end):
    """题材日K"""
    def ths():
        import akshare as ak
        df = ak.stock_board_concept_index_ths(symbol=name, start_date=start, end_date=end)
        df = df.rename(columns={"日期":"date","开盘价":"open","最高价":"high","最低价":"low","收盘价":"close","成交量":"volume"})
        df["date"] = pd.to_datetime(df["date"])
        df.set_index("date", inplace=True)
        return df[["open","high","low","close","volume"]]
    return Retry.run([("akshare-ths", ths)], "题材日K(%s)"%name, max_retries=5)

def pull_stock_list_baostock():
    """个股列表: baostock全A股"""
    def bs_stocks():
        import baostock as bs
        bs.login()
        # 沪深300
        stocks = {}
        rs = bs.query_hs300_stocks()
        while (rs.error_code == '0') & rs.next():
            row = rs.get_row_data()
            code = row[1].replace("sh.","").replace("sz.","")
            stocks[code] = row[2]
        # 中证500
        rs = bs.query_zz500_stocks()
        while (rs.error_code == '0') & rs.next():
            row = rs.get_row_data()
            code = row[1].replace("sh.","").replace("sz.","")
            if code not in stocks:
                stocks[code] = row[2]
        bs.logout()
        return stocks
    return Retry.run([("baostock", bs_stocks)], "个股列表")

def pull_stock_daily(bs_code, code, start, end):
    """个股日K: baostock"""
    def bs_daily():
        import baostock as bs, pandas as pd
        bs.login()
        rs = bs.query_history_k_data_plus(bs_code, "date,open,high,low,close,volume",
            start_date=start, end_date=end, frequency="d", adjustflag="2")
        data = []
        while (rs.error_code == '0') & rs.next():
            row = rs.get_row_data()
            if row[1] == '' or row[4] == '': continue
            data.append(row)
        bs.logout()
        if len(data) >= 20:
            df = pd.DataFrame(data, columns=rs.fields)
            df["date"] = pd.to_datetime(df["date"])
            df.set_index("date", inplace=True)
            for c in ["open","high","low","close","volume"]: df[c] = pd.to_numeric(df[c], errors='coerce')
            return df.dropna()
        return None
    return Retry.run([("baostock", bs_daily)], "个股日K(%s)"%code, max_retries=3)

def pull_etf_list():
    """ETF列表: akshare"""
    def ak_etf():
        import akshare as ak
        df = ak.fund_etf_spot_em()
        df = df[["代码","名称"]].copy()
        df.columns = ["symbol","name"]
        broad = ["沪深300","中证500","上证50","创业板","科创50","红利","低波","国债","转债"]
        df["etf_type"] = df["name"].apply(lambda n: "C" if any(k in n for k in broad) else "A")
        return df[df["etf_type"] != "C"]
    return Retry.run([("akshare", ak_etf)], "ETF列表")

def pull_etf_daily(code, start, end):
    """ETF日K: akshare → baostock"""
    def ak_etf():
        import akshare as ak, pandas as pd
        df = ak.fund_etf_hist_em(symbol=code, period="daily", start_date=start, end_date=end, adjust="qfq")
        df = df.rename(columns={"日期":"date","开盘":"open","最高":"high","最低":"low","收盘":"close","成交量":"volume"})
        df["date"] = pd.to_datetime(df["date"])
        df.set_index("date", inplace=True)
        return df[["open","high","low","close","volume"]]
    def bs_etf():
        import baostock as bs, pandas as pd
        bs_code = "sh.%s" % code if code.startswith("5") else "sz.%s" % code
        bs.login()
        rs = bs.query_history_k_data_plus(bs_code, "date,open,high,low,close,volume",
            start_date=start, end_date=end, frequency="d", adjustflag="2")
        data = []
        while (rs.error_code == '0') & rs.next():
            row = rs.get_row_data()
            if row[1] == '' or row[4] == '': continue
            data.append(row)
        bs.logout()
        if len(data) >= 20:
            df = pd.DataFrame(data, columns=rs.fields)
            df["date"] = pd.to_datetime(df["date"])
            df.set_index("date", inplace=True)
            for c in ["open","high","low","close","volume"]: df[c] = pd.to_numeric(df[c], errors='coerce')
            return df.dropna()
        return None
    return Retry.run([("akshare", ak_etf), ("baostock", bs_etf)], "ETF日K(%s)"%code, max_retries=2)


# ====== MAIN PIPELINE ======
def run_full_pipeline():
    import pandas as pd
    start_date = "2026-01-01"
    end_date = "2026-05-31"
    stats = {"sectors":0, "sector_daily":0, "concepts":0, "concept_daily":0, "stocks":0, "stock_daily":0, "etfs":0, "etf_daily":0}

    print("=" * 60)
    print("全量数据管道 - 开始拉取")
    print("=" * 60)

    # 1. 板块列表
    print("\n1. 板块列表...")
    sectors = pull_sector_list()
    if sectors is not None:
        sectors.to_json("%s/sector_list.json" % DATA_DIR, orient="records", force_ascii=False)
        stats["sectors"] = len(sectors)
        print("   ✅ %d个板块" % len(sectors))

        # 板块日K
        print("\n2. 板块日K...")
        for _, row in sectors.iterrows():
            name, code = row["name"], str(row["code"])
            path = "%s/sector_%s.parquet" % (DATA_DIR, code)
            if os.path.exists(path):
                stats["sector_daily"] += 1
                continue
            df = pull_sector_daily(name, code, start_date.replace("-",""), end_date.replace("-",""))
            if df is not None and len(df) >= 20:
                df.to_parquet(path)
                stats["sector_daily"] += 1
        print("   ✅ %d/%d个板块日K" % (stats["sector_daily"], stats["sectors"]))
    else:
        print("   ❌ 板块列表拉取失败")

    # 2. 题材列表
    print("\n3. 题材列表...")
    concepts = pull_concept_list()
    if concepts is not None:
        concepts.to_json("%s/theme_list.json" % DATA_DIR, orient="records", force_ascii=False)
        stats["concepts"] = len(concepts)
        print("   ✅ %d个题材" % len(concepts))

        # 题材日K (前30个)
        print("\n4. 题材日K (前30)...")
        for _, row in concepts.head(30).iterrows():
            name, code = row["name"], str(row["code"])
            path = "%s/theme_%s.parquet" % (DATA_DIR, code)
            if os.path.exists(path):
                stats["concept_daily"] += 1
                continue
            df = pull_concept_daily(name, start_date, end_date)
            if df is not None and len(df) >= 20:
                df.to_parquet(path)
                stats["concept_daily"] += 1
        print("   ✅ %d个题材日K" % stats["concept_daily"])
    else:
        print("   ❌ 题材列表拉取失败")

    # 3. 个股 (baostock)
    print("\n5. 个股列表 (baostock)...")
    stock_map = pull_stock_list_baostock()
    if stock_map:
        stats["stocks"] = len(stock_map)
        print("   ✅ %d只个股" % len(stock_map))

        print("\n6. 个股日K (全部)...")
        for code, name in stock_map.items():
            path = "%s/stock_%s.parquet" % (DATA_DIR, code)
            if os.path.exists(path):
                stats["stock_daily"] += 1
                continue
            bs_code = "sh.%s" % code if code.startswith("6") else "sz.%s" % code
            df = pull_stock_daily(bs_code, code, start_date.replace("-",""), end_date.replace("-",""))
            if df is not None and len(df) >= 20:
                df.to_parquet(path)
                stats["stock_daily"] += 1
        print("   ✅ %d/%d只个股日K" % (stats["stock_daily"], stats["stocks"]))
    else:
        print("   ❌ 个股列表拉取失败")

    # 4. ETF
    print("\n7. ETF列表...")
    etfs = pull_etf_list()
    if etfs is not None:
        etfs.to_json("%s/etf_list.json" % DATA_DIR, orient="records", force_ascii=False)
        stats["etfs"] = len(etfs)
        print("   ✅ %d只ETF" % len(etfs))

        print("\n8. ETF日K (前50)...")
        for _, row in etfs.head(50).iterrows():
            code, name = row["symbol"], row["name"]
            path = "%s/etf_%s.parquet" % (DATA_DIR, code)
            if os.path.exists(path):
                stats["etf_daily"] += 1
                continue
            df = pull_etf_daily(code, start_date, end_date)
            if df is not None and len(df) >= 20:
                df.to_parquet(path)
                stats["etf_daily"] += 1
        print("   ✅ %d只ETF日K" % stats["etf_daily"])
    else:
        print("   ❌ ETF列表拉取失败")

    # 保存统计
    with open("%s/pipeline_stats.json" % DATA_DIR, "w") as f:
        json.dump(stats, f, ensure_ascii=False)

    print("\n" + "=" * 60)
    print("管道完成: 板块%d/%d 题材%d/%d 个股%d/%d ETF%d/%d" % (
        stats["sector_daily"], stats["sectors"],
        stats["concept_daily"], stats["concepts"],
        stats["stock_daily"], stats["stocks"],
        stats["etf_daily"], stats["etfs"]))
    print("=" * 60)

if __name__ == "__main__":
    run_full_pipeline()
