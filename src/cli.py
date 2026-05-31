"""CLI入口 — run/dashboard/status 三个命令。

设计文档 Phase 6:
  run: 执行一次完整分析，产出当日JSON快照
  dashboard: 打开HTML Dashboard
  status: 输出文本概要（持仓+今日操作点）
"""
import sys
import os
import json
import webbrowser
from datetime import datetime, timedelta


def cmd_run(date_str: str = None):
    """执行一次完整分析。"""
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")

    print(f"🔍 趋势跟随系统 — 分析日期: {date_str}")
    print("=" * 60)

    # 1. 数据获取
    print("📡 [1/5] 获取数据...")
    from src.data.fetcher import DataFetcher
    fetcher = DataFetcher()

    # 检查是否已有本地数据，没有则初始化
    if not fetcher.local_db.list_symbols("sector"):
        print("   ⚠️ 本地数据库为空，先初始化...")
        stats = fetcher.init_db(date_str)
        print(f"   板块: {stats['sectors']}, 题材: {stats['themes']}, ETF: {stats['etfs']}")
        if stats.get('errors'):
            print(f"   ⚠️ 错误: {len(stats['errors'])}个")
    else:
        result = fetcher.update_daily(date_str)
        print(f"   更新: 板块{result['sectors']}, ETF{result['etfs']}")

    # 2. 加载数据
    print("📊 [2/5] 加载数据...")
    sector_data = fetcher.load_all_sectors()
    theme_data = fetcher.load_all_themes()
    stock_data = fetcher.load_all_stocks()
    etf_data = fetcher.load_all_etfs()
    print(f"   板块: {len(sector_data)}, 题材: {len(theme_data)}, 个股: {len(stock_data)}, ETF: {len(etf_data)}")

    # 3. 运行趋势引擎
    print("⚙️  [3/5] 运行趋势引擎...")
    from src.funnel.sector_filter import SectorFilter
    from src.funnel.theme_filter import ThemeFilter
    from src.funnel.stock_filter import StockFilter
    from src.funnel.etf_filter import ETFFilter

    sector_results = SectorFilter.filter(sector_data)
    theme_results = ThemeFilter.filter(theme_data)
    stock_results = StockFilter.filter(stock_data)
    etf_results = ETFFilter.filter(etf_data)

    print(f"   上涨板块: {len(sector_results)}, 活跃题材: {len(theme_results)}")
    print(f"   趋势个股: {len(stock_results)}, 趋势ETF: {len(etf_results)}")

    # 4. 运行分析
    print("📈 [4/5] 运行分析推演...")
    from src.analysis.breadth import MarketBreadth
    breadth = MarketBreadth.calculate(sector_results, stock_results, etf_results)
    print(f"   市场健康度: {breadth['market_health']}")

    # 5. 生成快照
    print("📝 [5/5] 生成快照...")
    from src.display.snapshot import SnapshotGenerator

    # 加载前一日快照用于对比
    prev_date = (datetime.strptime(date_str, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
    prev_snapshot = None
    prev_path = f"dashboard/data/trend_snapshot_{prev_date}.json"
    if os.path.exists(prev_path):
        with open(prev_path, "r") as f:
            prev_snapshot = json.load(f)

    # 加载持仓
    positions = None
    pos_path = "dashboard/positions.json"
    if os.path.exists(pos_path):
        with open(pos_path, "r") as f:
            positions = json.load(f)

    gen = SnapshotGenerator()
    snapshot = gen.generate(date_str, sector_results, theme_results, stock_results, etf_results,
                           previous_snapshot=prev_snapshot, positions=positions)

    print(f"\n✅ 分析完成! 快照已保存: dashboard/data/trend_snapshot_{date_str}.json")
    print(f"   上涨板块: {snapshot['market_overview']['uptrend_sectors']}")
    print(f"   活跃题材: {snapshot['market_overview']['active_themes']}")
    print(f"   趋势个股: {snapshot['market_overview']['trend_stocks']}")
    print(f"   趋势ETF: {snapshot['market_overview']['trend_etfs']}")
    print(f"   关键操作: {len(snapshot['key_actions'])}个")

    return snapshot


def cmd_dashboard():
    """打开HTML Dashboard。"""
    dashboard_path = os.path.join(os.path.dirname(__file__), "display", "dashboard.html")
    if not os.path.exists(dashboard_path):
        print("❌ Dashboard文件不存在，请先运行 `run` 命令")
        return
    print(f"📊 打开Dashboard: {dashboard_path}")
    webbrowser.open(f"file://{os.path.abspath(dashboard_path)}")


def cmd_status():
    """输出文本概要。"""
    # 找到最新的快照文件
    data_dir = "dashboard/data"
    if not os.path.exists(data_dir):
        print("❌ 无分析数据，请先运行 `run` 命令")
        return

    snapshots = sorted([f for f in os.listdir(data_dir) if f.startswith("trend_snapshot_")])
    if not snapshots:
        print("❌ 无快照文件，请先运行 `run` 命令")
        return

    latest = snapshots[-1]
    with open(os.path.join(data_dir, latest), "r") as f:
        snap = json.load(f)

    date_str = snap["meta"]["date"]
    overview = snap["market_overview"]

    print(f"📊 趋势跟随系统 — {date_str} 概要")
    print("=" * 50)
    print(f"上涨板块: {overview['uptrend_sectors']} | 活跃题材: {overview['active_themes']}")
    print(f"趋势个股: {overview['trend_stocks']} | 趋势ETF: {overview['trend_etfs']}")
    print(f"市场健康度: {snap.get('market_breadth', {}).get('market_health', 'N/A')}")
    print()

    # 关键操作点
    actions = snap.get("key_actions", [])
    if actions:
        print(f"⚠️  今日关键操作 ({len(actions)}个):")
        for a in actions:
            print(f"  {a['priority']} {a['symbol']} — {a['action']} ({a['position_action']})")
    else:
        print("✅ 今日无关键操作点，持仓不变")

    # 板块排行
    sectors = snap.get("sectors", [])[:5]
    if sectors:
        print(f"\n📋 板块Top5:")
        for s in sectors:
            print(f"  {s['state_label']} | {s['name']} | 得分:{s['score']}")

    # 持仓
    positions = snap.get("positions", {})
    holdings = positions.get("holdings", [])
    if holdings:
        print(f"\n💼 当前持仓 ({len(holdings)}个):")
        total_weight = sum(h.get("current_weight", 0) for h in holdings)
        print(f"  总仓位: {total_weight*100:.0f}%")
        for h in holdings:
            print(f"  {h['name']}({h['symbol']}) | 权重:{h.get('current_weight',0)*100:.0f}%")


def main():
    if len(sys.argv) < 2:
        print("趋势跟随交易系统 CLI")
        print("用法: python3 -m src.cli <command>")
        print("  run [date]    — 执行完整分析 (默认今天)")
        print("  dashboard     — 打开HTML Dashboard")
        print("  status        — 显示当前持仓和操作点")
        return

    cmd = sys.argv[1]
    date_arg = sys.argv[2] if len(sys.argv) > 2 else None

    if cmd == "run":
        cmd_run(date_arg)
    elif cmd == "dashboard":
        cmd_dashboard()
    elif cmd == "status":
        cmd_status()
    else:
        print(f"未知命令: {cmd}")
        print("可用命令: run, dashboard, status")


if __name__ == "__main__":
    main()
