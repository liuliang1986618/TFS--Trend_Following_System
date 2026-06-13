#!/usr/bin/env python3
"""每日收盘后一条命令: python3 pipeline.py [YYYY-MM-DD]

自动产出完整 Dashboard: 市场概览 + 操作建议(ETF/个股Top5) + 焦点板块 + 全板块列表。

流程: 增量拉取sector数据 → 加载缓存 → 全市场扫描 → 存档 → 生成Dashboard
"""
import sys
import os
import json
import subprocess
import pickle
import numpy as np
from datetime import datetime
from typing import Optional

# 确保项目根目录在 sys.path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(PROJECT_ROOT)
sys.path.insert(0, PROJECT_ROOT)

from src.fusion.scanner import MarketScanner, ETF_NAME_MAP, ScanResult


def load_cached_etfs(data_dir: str = "data") -> dict[str, dict]:
    """加载所有 ETF pkl 缓存，返回 {code: {col: np.ndarray}}。"""
    etf_dir = os.path.join(data_dir, "etf_stocks")
    result = {}
    if not os.path.isdir(etf_dir):
        print(f"  ⚠️ ETF 缓存目录不存在: {etf_dir}")
        return result
    for fname in sorted(os.listdir(etf_dir)):
        if not fname.endswith(".pkl"):
            continue
        code = fname.replace("etf_", "").replace(".pkl", "")
        try:
            df = pickle.load(open(os.path.join(etf_dir, fname), "rb"))
            if len(df) >= 30:
                result[code] = {col: df[col].values for col in df.columns}
        except Exception:
            pass
    return result


def load_cached_stocks(data_dir: str = "data") -> dict[str, dict]:
    """加载全量个股 pkl 缓存，返回 {code: {col: np.ndarray}}。

    全量加载，不设上限。市场有多少只就加载多少只。
    """
    stock_dir = os.path.join(data_dir, "massive_stocks")
    result = {}
    if not os.path.isdir(stock_dir):
        print(f"  ⚠️ 个股缓存目录不存在: {stock_dir}")
        return result
    files = sorted(os.listdir(stock_dir))
    for fname in files:
        if not fname.endswith(".pkl"):
            continue
        code = fname.replace(".pkl", "")
        try:
            df = pickle.load(open(os.path.join(stock_dir, fname), "rb"))
            if len(df) >= 30:
                result[code] = {col: df[col].values for col in df.columns}
        except Exception:
            pass
    return result


def load_cached_index(data_dir: str = "data") -> Optional[np.ndarray]:
    """加载指数缓存（上证综指）。"""
    idx_path = os.path.join(data_dir, "backtest_stocks", "index.pkl")
    if os.path.exists(idx_path):
        try:
            df = pickle.load(open(idx_path, "rb"))
            if "close" in df.columns:
                return df["close"].values
        except Exception:
            pass
    return None


def load_stock_names(data_dir: str = "data") -> dict[str, str]:
    """加载个股名称缓存。无缓存时尝试从 akshare 构建。"""
    cache_path = os.path.join(data_dir, "stock_names.json")
    if os.path.exists(cache_path):
        try:
            with open(cache_path) as f:
                return json.load(f)
        except Exception:
            pass
    # 缓存不存在，尝试从 akshare 构建
    try:
        import akshare as ak
        df = ak.stock_info_a_code_name()
        name_map = {}
        for _, row in df.iterrows():
            name_map[str(row["code"]).zfill(6)] = str(row["name"]).strip()
        with open(cache_path, "w") as f:
            json.dump(name_map, f, ensure_ascii=False)
        print(f"  📛 从 akshare 构建了个股名称缓存: {len(name_map)} 只")
        return name_map
    except Exception as e:
        print(f"  ⚠️ 无法构建个股名称缓存: {e}")
        return {}


def update_sector_data(target_date: str, data_dir: str = "dashboard/data",
                       max_sectors: int = 90) -> bool:
    """增量拉取 sector 板块日K数据到 parquet。

    只拉取本地缺失的日期段，已存在则跳过。
    每个 sector 拉取间隔 0.3s 防止封 IP。
    返回 True 表示数据已就绪。
    """
    import time as _time
    import akshare as ak
    import pandas as pd

    sector_file = os.path.join(data_dir, "sector_list.json")
    if not os.path.exists(sector_file):
        print("  ⚠️ sector_list.json 不存在，跳过 sector 更新")
        return False

    sectors = pd.read_json(sector_file)
    total = min(len(sectors), max_sectors)
    updated = 0
    skipped = 0
    failed = 0

    for i, (_, row) in enumerate(sectors.iterrows()):
        if i >= max_sectors:
            break
        code = str(row["code"]).zfill(6)
        name = row["name"]
        path = os.path.join(data_dir, f"sector_{code}.parquet")

        # 检查是否已有目标日期数据
        if os.path.exists(path):
            try:
                existing = pd.read_parquet(path)
                if target_date in existing.index.astype(str).values:
                    skipped += 1
                    continue
                last_date = str(existing.index.max())[:10]
            except Exception:
                last_date = "20230101"
        else:
            last_date = "20230101"

        # 拉取增量数据
        try:
            new_df = ak.stock_board_industry_index_ths(
                symbol=name,
                start_date=last_date.replace("-", ""),
                end_date=target_date.replace("-", ""),
            )
        except Exception as e:
            failed += 1
            if failed <= 3:
                print(f"    ⚠️ {name}({code}) 拉取失败: {e}")
            continue

        if new_df is None or len(new_df) == 0:
            skipped += 1
            continue

        # 转换为统一格式（英文列名，date为索引）
        col_map = {"日期": "date", "开盘价": "open", "最高价": "high",
                    "最低价": "low", "收盘价": "close", "成交量": "volume"}
        new_df = new_df.rename(columns=col_map)
        if "date" in new_df.columns:
            new_df["date"] = pd.to_datetime(new_df["date"])
            new_df = new_df.set_index("date")

        # 合并已有数据
        if os.path.exists(path):
            try:
                combined = pd.concat([existing, new_df])
                combined = combined[~combined.index.duplicated(keep="last")]
                combined = combined.sort_index()
            except Exception:
                combined = new_df
        else:
            combined = new_df

        combined.to_parquet(path)
        updated += 1
        _time.sleep(0.3)  # 防封 IP

    print(f"  📊 Sector 更新: {updated} 已更新, {skipped} 已是最新, {failed} 失败 (共{total}板块)")
    return updated + skipped > 0


def _update_pkl_caches(target_date: str):
    """增量更新 ETF 和个股 pkl 缓存（仅拉取缺失日期）。

    全量更新，不设上限。遍历所有已有 ETF/个股 pkl 文件。
    新增 ETF 发现：对比 akshare 全量 ETF 列表，自动下载缺失的 ETF。
    """
    import time as _time
    import akshare as ak
    import pandas as _pd

    target_dt = _pd.Timestamp(target_date)

    # --- ETF ---
    etf_dir = 'data/etf_stocks'
    if os.path.isdir(etf_dir):
        etf_files = sorted([f for f in os.listdir(etf_dir) if f.endswith('.pkl')])
        u, s, f = 0, 0, 0
        for i, fname in enumerate(etf_files):
            code = fname.replace('etf_', '').replace('.pkl', '')
            path = os.path.join(etf_dir, fname)
            try:
                df = _pd.read_pickle(path)
                df['date'] = _pd.to_datetime(df['date'])
            except Exception:
                f += 1; continue
            if target_dt in df['date'].values:
                s += 1; continue
            try:
                from src.data.fallback import fetch_etf_daily_multisource
                new = fetch_etf_daily_multisource(code)
            except Exception:
                f += 1; continue
            if new is None or len(new) == 0:
                f += 1; continue
            new['date'] = _pd.to_datetime(new['date'])
            new = new[new['date'] > df['date'].max()]
            if len(new) == 0:
                s += 1; continue
            _pd.concat([df, new], ignore_index=True).to_pickle(path)
            u += 1
            _time.sleep(0.2)
        print(f"   ETF: {u}更新 {s}最新 {f}失败")

    # --- 个股 ---
    stock_dir = 'data/massive_stocks'
    if os.path.isdir(stock_dir):
        stock_files = sorted([f for f in os.listdir(stock_dir) if f.endswith('.pkl')])
        u, s, f = 0, 0, 0
        for i, fname in enumerate(stock_files):
            code = fname.replace('.pkl', '')
            path = os.path.join(stock_dir, fname)
            try:
                df = _pd.read_pickle(path)
                df['date'] = _pd.to_datetime(df['date'])
            except Exception:
                f += 1; continue
            if target_dt in df['date'].values:
                s += 1; continue
            try:
                new = ak.stock_zh_a_daily(symbol=f'sz{code}', adjust='qfq')
            except Exception:
                try:
                    new = ak.stock_zh_a_daily(symbol=f'sh{code}', adjust='qfq')
                except Exception:
                    f += 1; continue
            if new is None or len(new) == 0:
                f += 1; continue
            new['date'] = _pd.to_datetime(new['date'])
            new = new[new['date'] > df['date'].max()]
            if len(new) == 0:
                s += 1; continue
            _pd.concat([df, new], ignore_index=True).to_pickle(path)
            u += 1
            if (i + 1) % 500 == 0:
                print(f"   个股进度: {i+1}/{len(stock_files)}")
            _time.sleep(0.08)
        print(f"   个股: {u}更新 {s}最新 {f}失败")


def _fix_state_labels():
    """统一翻译 state_label：engine 层保持不变，pipeline 层做映射。"""
    import glob as _glob
    data_dir = os.path.join(PROJECT_ROOT, "dashboard", "data")
    label_map = {"翻转确认中": "趋势转好，突破买入 · 可以买了", "转跌确认中": "趋势转差，破位减仓 · 赶紧卖", "下跌趋势": "持续下跌 · 别碰", "下跌反弹": "跌多了弹一下 · 再等等", "上涨趋势": "持续上涨 · 拿着别动", "上涨回调": "涨多了歇一下 · 准备加仓"}

    files = _glob.glob(os.path.join(data_dir, "*.json"))
    updated = 0
    for path in files:
        try:
            with open(path) as f:
                content = f.read()
            new_content = content
            for old, new in label_map.items():
                new_content = new_content.replace(old, new)
            if new_content != content:
                with open(path, "w") as f:
                    f.write(new_content)
                updated += 1
        except Exception:
            pass
    if updated > 0:
        print(f"   🏷️ state_label 已修正: {updated} 个文件")


def _sync_date_data(target_date: str):
    """同步 date_full_data.json 和 date_nav.json，确保新日期被 Dashboard 侧边栏识别。"""
    import pandas as _pd

    data_dir = os.path.join(PROJECT_ROOT, "dashboard", "data")
    target_dt = _pd.Timestamp(target_date)
    wd_map = {0: "周一", 1: "周二", 2: "周三", 3: "周四", 4: "周五", 5: "周六", 6: "周日"}
    wd = wd_map[target_dt.dayofweek]

    # --- 1. 更新 date_full_data.json ---
    dfd_path = os.path.join(data_dir, "date_full_data.json")
    uptrend, downtrend, health = 0, 90, "正常"
    if os.path.exists(dfd_path):
        with open(dfd_path) as f:
            dfd = json.load(f)
        if target_date not in dfd.get("dates", {}):
            # 对每个 sector parquet 做 StateMachine.classify
            from src.engine.state_machine import StateMachine
            sector_files = sorted([f for f in os.listdir(data_dir)
                                   if f.startswith("sector_") and f.endswith(".parquet")])
            entry = {"total": len(sector_files), "uptrend": 0, "downtrend": 0,
                     "health": "正常", "sectors": {}}
            for sf in sector_files:
                code = sf.replace("sector_", "").replace(".parquet", "")
                try:
                    sdf = _pd.read_parquet(os.path.join(data_dir, sf))
                    sdf = sdf[sdf.index <= target_dt]
                    if len(sdf) < 20:
                        continue
                    ts = StateMachine.classify(sdf)
                    entry["sectors"][code] = {"state": ts.state, "state_label": ts.state_label}
                    if ts.state == 4:
                        entry["uptrend"] += 1
                    elif ts.state == 1:
                        entry["downtrend"] += 1
                except Exception:
                    pass
            if entry["uptrend"] >= 30:
                entry["health"] = "强势"
            elif entry["uptrend"] >= 8:
                entry["health"] = "正常"
            else:
                entry["health"] = "弱势"
            dfd["dates"][target_date] = entry
            with open(dfd_path, "w") as f:
                json.dump(dfd, f, ensure_ascii=False)
            print(f"   📊 date_full_data +{target_date} ↑{entry['uptrend']} ↓{entry['downtrend']}")
        else:
            info = dfd["dates"][target_date]
            uptrend = info.get("uptrend", 0)
            downtrend = info.get("downtrend", 90)
            health = info.get("health", "正常")

    # --- 2. 从 actions_{date}.json 提取每日期独立的 leaders（与推荐同源） ---
    leaders_dict = {}
    top_sectors_list = []
    actions_path = os.path.join(data_dir, f"actions_{target_date}.json")
    if os.path.exists(actions_path):
        try:
            with open(actions_path) as f:
                actions = json.load(f)
            # 个股 Top5 作为 leaders（与操作建议面板完全一致）
            stocks_top = actions.get("stock_top5", [])
            for s in stocks_top:
                code = s.get("code", "")
                if code:
                    # enrich_dates 用 ret20 或 score 作为分数
                    leaders_dict.setdefault("_scanner_top5", []).append({
                        "name": s.get("name", code),
                        "code": code,
                        "ret20": s.get("score", 0),
                    })
            # ETF Top5 名称作为 top_sectors
            etf_top = actions.get("etf_top5", [])
            top_sectors_list = [{"name": e["name"], "code": e["code"]} for e in etf_top[:5]]
        except Exception:
            pass

    # 如果 actions JSON 不存在，回退到 dashboard_data.json
    if not leaders_dict:
        dash_path = os.path.join(data_dir, "dashboard_data.json")
        if os.path.exists(dash_path):
            try:
                with open(dash_path) as f:
                    dash = json.load(f)
                stocks = dash.get("stocks", [])
                for s in stocks:
                    code = s.get("code", "")
                    secs = s.get("sectors", [])
                    if secs and code:
                        sec_name = secs[0] if isinstance(secs, list) else str(secs)
                        leaders_dict.setdefault(sec_name, []).append({
                            "name": s.get("name", code),
                            "code": code,
                            "ret20": s.get("ret_20d", 0) or 0,
                        })
                sectors = dash.get("sectors", [])
                top_sectors_list = [{"name": s["name"], "code": s["code"]}
                                   for s in sectors if s.get("state") == 4][:5]
            except Exception:
                pass

    # --- 3. 更新 date_nav.json ---
    nav_path = os.path.join(data_dir, "date_nav.json")
    if not os.path.exists(nav_path):
        return

    with open(nav_path) as f:
        dnav = json.load(f)

    nav_item = {
        "date": target_date, "weekday": wd,
        "uptrend_count": uptrend, "downtrend_count": downtrend,
        "health": health,
        "top_sectors": top_sectors_list, "top_flip": [],
        "leaders": leaders_dict,
        "is_today": True, "is_monday": (wd == "周一"),
    }

    dates = dnav.get("dates", [])
    for item in dates:
        item["is_today"] = False

    if target_date not in {e["date"] for e in dates}:
        dates.insert(0, nav_item)
        dnav["total_dates"] = len(dates)
        print(f"   📅 date_nav +{target_date} ({wd}) leaders={len(leaders_dict)}板块 top={len(top_sectors_list)}")
    else:
        for item in dates:
            if item["date"] == target_date:
                item.update(nav_item)

    with open(nav_path, "w") as f:
        json.dump(dnav, f, ensure_ascii=False)


def _open_dashboard():
    """启动 HTTP 服务并打开浏览器。"""
    import subprocess as _sp
    dashboard_dir = os.path.join(PROJECT_ROOT, "dashboard")
    index_path = os.path.join(dashboard_dir, "index.html")

    # 先尝试直接打开文件（macOS）
    try:
        _sp.run(["open", index_path], timeout=5)
        print("🌐 浏览器已打开 Dashboard")
        return
    except Exception:
        pass

    # 备选：启动 HTTP 服务
    try:
        _sp.Popen([sys.executable, "-m", "http.server", "8888"],
                  cwd=dashboard_dir, stdout=_sp.DEVNULL, stderr=_sp.DEVNULL)
        _sp.run(["open", "http://localhost:8888"], timeout=5)
        print("🌐 http://localhost:8888")
    except Exception:
        print("⚠️ 无法自动打开浏览器，请手动打开 dashboard/index.html")


def _fill_history_gaps(target_date: str, scanner: MarketScanner,
                       stock_names: dict[str, str], lookback: int = 10):
    """检查最近 N 个交易日是否有缺失，自动补齐。"""
    import pandas as _pd

    # 获取最近 lookback 个交易日（跳过周末）
    today = _pd.Timestamp(target_date)
    # 生成最近 N 个工作日
    all_dates = _pd.bdate_range(end=today, periods=lookback)
    all_dates = [str(d.date()) for d in all_dates]

    filled = 0
    for d in all_dates:
        actions_path = os.path.join(PROJECT_ROOT, "dashboard", "data",
                                     f"actions_{d}.json")
        if os.path.exists(actions_path):
            continue  # 已有，跳过

        print(f"   📌 补齐缺失日期: {d}")
        try:
            etf_r = scanner.scan_etfs(d, top_n=5, min_score=5.0)
            stock_r = scanner.scan_stocks(d, top_n=5, min_score=5.0,
                                          name_map=stock_names)
            regime = scanner.assess_market(
                load_cached_index()) if load_cached_index() is not None else "neutral"
            save_actions(d, etf_r, stock_r, regime)
            filled += 1
        except Exception as e:
            print(f"      ⚠️ 补齐 {d} 失败: {e}")

    if filled > 0:
        print(f"   ✅ 补齐了 {filled} 个缺失日期")
    else:
        print(f"   ✅ 历史数据完整，无需补齐")



def load_watchlist() -> dict:
    """加载关注列表配置。"""
    path = os.path.join(PROJECT_ROOT, "watchlist.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {"stocks": [], "notes": {}}


def scan_watchlist(target_date: str, scanner: MarketScanner,
                   name_map: dict[str, str]) -> list[ScanResult]:
    """扫描关注列表中的个股。"""
    import pandas as _pd2
    wl = load_watchlist()
    codes = wl.get("stocks", [])
    if not codes:
        return []

    results = []
    stock_dir = os.path.join(PROJECT_ROOT, "data", "massive_stocks")
    for code in codes:
        path = os.path.join(stock_dir, f"{code}.pkl")
        if not os.path.exists(path):
            continue
        try:
            df = pickle.load(open(path, "rb"))
            df["date"] = _pd2.to_datetime(df["date"])
            target_dt = _pd2.Timestamp(target_date)
            mask = df["date"] <= target_dt
            if mask.sum() < 30:
                continue
            idx = int(mask.sum() - 1)
            close = df["close"].values[:idx + 1].astype(float)
            volume = df["volume"].values[:idx + 1].astype(float)
            high_col = "high" if "high" in df.columns else "close"
            low_col = "low" if "low" in df.columns else "close"
            high = df[high_col].values[:idx + 1].astype(float)
            low = df[low_col].values[:idx + 1].astype(float)

            ind = scanner._calc_indicators(close, volume, high, low)
            score = scanner._score_stock(ind)
            name = name_map.get(code, code)
            note = wl.get("notes", {}).get(code, "")

            mkt = "sh" if str(code).startswith("6") else "sz"
            link = f"https://quote.eastmoney.com/{mkt}{code}.html"

            if score is None:
                results.append(ScanResult(
                    code=code, name=name, score=0, action="回避",
                    position_pct=0, reason=f"趋势过滤未通过 | {note}" if note else "趋势过滤未通过",
                    link=link,
                    state=scanner._determine_tfs_state(close),
                    ma_deviation=ind.get("ma_deviation", 0),
                    ret_20d=ind.get("pct_20d", 0),
                ))
            else:
                result = scanner._result_from_row(code, name, score, ind, is_etf=False)
                if note:
                    result.reason += f" | {note}"
                result.state = scanner._determine_tfs_state(close)
                results.append(result)
        except Exception:
            pass

    return results


def save_actions(date_str: str, etf_results: list[ScanResult],
                 stock_results: list[ScanResult], market_regime: str,
                 watchlist_results: list[ScanResult] = None, output_dir: str = "dashboard/data"):
    """保存操作建议到 actions_{date}.json。"""
    os.makedirs(output_dir, exist_ok=True)

    def result_to_dict(r: ScanResult) -> dict:
        return {
            "code": r.code, "name": r.name, "score": r.score,
            "action": r.action, "position_pct": r.position_pct,
            "reason": r.reason, "link": r.link,
            "state": r.state, "ma_deviation": r.ma_deviation,
            "ret_20d": r.ret_20d,
        }

    data = {
        "date": date_str,
        "generated_at": datetime.now().isoformat(),
        "market_regime": market_regime,
        "etf_top5": [result_to_dict(r) for r in etf_results],
        "stock_top5": [result_to_dict(r) for r in stock_results],
        "watchlist": [result_to_dict(r) for r in (watchlist_results or [])],
    }

    path = os.path.join(output_dir, f"actions_{date_str}.json")
    with open(path, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  ✅ 已保存: {path}")
    return path


def run_pipeline(target_date: str = None):
    """主流程: 加载缓存 → 全市场扫描 → 存档 → 触发生成Dashboard。"""
    if target_date is None:
        target_date = datetime.now().strftime("%Y-%m-%d")

    print("=" * 60)
    print(f"🚀 趋势跟随 Pipeline — {target_date}")
    print("=" * 60)

    # Step -1: 增量更新 ETF/个股 pkl 缓存
    print("\n📥 Step -1: 增量更新 ETF/个股 pkl 缓存...")
    _update_pkl_caches(target_date)

    # Step 0: 增量更新 sector 数据
    print("\n📡 Step 0: 增量更新 Sector 板块数据...")
    sector_ok = update_sector_data(target_date, max_sectors=90)
    if not sector_ok:
        print("   ⚠️ Sector 数据更新不完整，Dashboard 可能缺板块数据")

    # Step 0.5: 生成 Dashboard 核心数据（dashboard_data.json + date_full_data.json）
    print("\n📊 Step 0.5: 生成 Dashboard 核心数据...")
    gen_all = os.path.join(PROJECT_ROOT, "scripts", "generate_all_data.py")
    if os.path.exists(gen_all):
        r = subprocess.run([sys.executable, gen_all, target_date],
                           capture_output=True, text=True, cwd=PROJECT_ROOT, timeout=300)
        if r.returncode == 0:
            print(r.stdout[-300:] if len(r.stdout) > 300 else r.stdout)
        else:
            print(f"   ⚠️ generate_all_data 返回非零: {r.returncode}")
            if r.stderr:
                print(f"   {r.stderr[:200]}")
    else:
        print(f"   ⚠️ 未找到 {gen_all}")

    # Step 0.55: 修正 state_label（engine 层不改，在 pipeline 层统一翻译）
    _fix_state_labels()

    # Step 0.6: 同步 date_nav.json（确保新日期出现在侧边栏）
    _sync_date_data(target_date)

    # Step 1: 加载缓存
    print("\n📦 Step 1: 加载缓存数据...")
    stock_names = load_stock_names()
    etfs = load_cached_etfs()
    stocks = load_cached_stocks()
    index_close = load_cached_index()
    print(f"   ETF: {len(etfs)} 只 | 个股: {len(stocks)} 只 | 名称缓存: {len(stock_names)} 只 | 指数: {'✅' if index_close is not None else '❌'}")

    # Step 2: 市场环境评估
    print("\n📊 Step 2: 市场环境评估...")
    scanner = MarketScanner()
    market_regime = scanner.assess_market(index_close) if index_close is not None else "neutral"
    regime_cn = {"strong_bull": "强牛", "weak_bull": "弱牛", "neutral": "震荡",
                  "weak_bear": "弱熊", "strong_bear": "强熊"}
    print(f"   市场状态: {regime_cn.get(market_regime, market_regime)}")

    # Step 3: 全市场扫描
    print(f"\n🔍 Step 3: 全市场扫描评分 (target={target_date})...")
    etf_results = scanner.scan_etfs(target_date, top_n=5, min_score=5.0)
    stock_results = scanner.scan_stocks(target_date, top_n=5, min_score=5.0, name_map=stock_names)

    print(f"\n   📈 ETF Top{len(etf_results)}:")
    for r in etf_results:
        print(f"      {r.name}({r.code}) 评分{r.score} 操作:{r.action} 仓位:{r.position_pct}% 原因:{r.reason}")

    print(f"\n   📊 个股 Top{len(stock_results)}:")
    for r in stock_results:
        print(f"      {r.name}({r.code}) 评分{r.score} 操作:{r.action} 仓位:{r.position_pct}% 原因:{r.reason}")

    # Step 3.5: 扫描关注列表
    print(f"\n👁️  Step 3.5: 扫描特别关注列表...")
    watchlist_results = scan_watchlist(target_date, scanner, stock_names)
    if watchlist_results:
        for r in watchlist_results:
            print(f"      {r.name}({r.code}) 评分{r.score} 操作:{r.action}")
    else:
        print(f"      (关注列表为空)")

    # Step 4: 存档 actions JSON
    print(f"\n💾 Step 4: 存档操作建议...")
    save_actions(target_date, etf_results, stock_results, market_regime, watchlist_results)

    # Step 4.5: 自动补齐近期缺失的交易日
    print(f"\n🔧 Step 4.5: 检查并补齐缺失日期...")
    _fill_history_gaps(target_date, scanner, stock_names)

    # Step 5: 生成 Dashboard（调已有脚本）
    print(f"\n📄 Step 5: 生成 Dashboard...")
    build_final = os.path.join(PROJECT_ROOT, "scripts", "build_final.py")
    build_nav = os.path.join(PROJECT_ROOT, "scripts", "build_nav_index.py")

    if os.path.exists(build_final):
        print("   执行 build_final.py...")
        r = subprocess.run([sys.executable, build_final], capture_output=True, text=True,
                           cwd=PROJECT_ROOT, timeout=120)
        if r.returncode == 0:
            print(r.stdout[-500:] if len(r.stdout) > 500 else r.stdout)
        else:
            print(f"   ⚠️ build_final 返回非零: {r.returncode}")
            if r.stderr:
                print(f"   {r.stderr[:300]}")
    else:
        print(f"   ⚠️ 未找到 {build_final}")

    if os.path.exists(build_nav):
        print("   执行 build_nav_index.py...")
        r = subprocess.run([sys.executable, build_nav], capture_output=True, text=True,
                           cwd=PROJECT_ROOT, timeout=120)
        if r.returncode == 0:
            print(r.stdout[-300:] if len(r.stdout) > 300 else r.stdout)
        else:
            print(f"   ⚠️ build_nav_index 返回非零: {r.returncode}")
    else:
        print(f"   ⚠️ 未找到 {build_nav}")

    print(f"\n{'=' * 60}")
    print(f"✅ Pipeline 完成 — {target_date}")
    print(f"{'=' * 60}")

    # 自动打开浏览器
    _open_dashboard()

    return True


if __name__ == "__main__":
    date_arg = sys.argv[1] if len(sys.argv) > 1 else None
    success = run_pipeline(date_arg)
    sys.exit(0 if success else 1)
