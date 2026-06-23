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

# === 数据源 AB 开关 ===
# 默认使用新数据管理模块 (src/data_mgr)
# 设置环境变量 USE_NEW_DATA_MGR=0 回退老管道 (src/data)
USE_NEW_DATA_MGR = os.environ.get("USE_NEW_DATA_MGR", "1") != "0"

def _get_fetcher():
    """根据 AB 开关返回 DataFetcher。"""
    if USE_NEW_DATA_MGR:
        from src.data_mgr.fetcher import DataFetcher
    else:
        from src.data.fetcher import DataFetcher
    return DataFetcher()


# === 融合层导入（可通过 config 禁用） ===
try:
    from src.fusion import FusionOrchestrator
    FUSION_AVAILABLE = True
except ImportError:
    FUSION_AVAILABLE = False


def cmd_run(date_str: str = None):
    """执行一次完整分析。"""
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")

    print(f"🔍 趋势跟随系统 — 分析日期: {date_str}")
    print(f"   数据源: {'新 data_mgr' if USE_NEW_DATA_MGR else '老 src/data'}")
    print("=" * 60)

    # 1. 数据获取
    print("📡 [1/5] 获取数据...")
    fetcher = _get_fetcher()

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
    etf_data = fetcher.load_all_etfs()
    # 漏斗懒加载：从活跃题材提取成分股，只加载需要的个股
    constituent_symbols = set()
    for gn_code in theme_data:
        constituent_symbols.update(fetcher.mapping.get_theme_symbols(gn_code))
    # 也加入板块成分股
    for bk_code in sector_data:
        constituent_symbols.update(fetcher.mapping.get_sector_symbols(bk_code))

    if constituent_symbols:
        stock_data = fetcher.load_stocks_by_symbols(list(constituent_symbols))
    else:
        # 降级：成分股映射为空时（如东方财富IP被封），回退全量加载
        print("   ⚠️ 成分股映射为空，回退全量加载个股...")
        stock_data = fetcher.load_all_stocks()
    print(f"   板块: {len(sector_data)}, 题材: {len(theme_data)}, 个股: {len(stock_data)} (候选{len(constituent_symbols)}只), ETF: {len(etf_data)}")

    # 2.5 融合层：市场环境门控
    fusion_regime = None
    fusion_orchestrator = None
    if FUSION_AVAILABLE:
        import yaml
        fusion_config = {}
        config_path = "config.yaml"
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                cfg = yaml.safe_load(f) or {}
                fusion_config = cfg.get("fusion", {})

        if fusion_config.get("enabled", True):
            fusion_orchestrator = FusionOrchestrator(fusion_config)
            # 用上证指数数据做市场门控
            index_df = fetcher.load_index("sh000001")
            if index_df is not None and len(index_df) >= 60:
                breadth_raw = fetcher.load_market_breadth(date_str)
                fusion_regime = fusion_orchestrator.assess_market(
                    index_df,
                    up_count=breadth_raw.get("up_count", 0),
                    down_count=breadth_raw.get("down_count", 0),
                    limit_up_count=breadth_raw.get("limit_up_count", 0),
                    limit_down_count=breadth_raw.get("limit_down_count", 0),
                )
                print(f"   🚦 市场门控: {fusion_regime.level}灯 | {fusion_regime.reason}")

                # 红灯快速路径：跳过后续分析
                if fusion_regime.level == "red":
                    print(f"   🛑 红灯! 强制空仓，跳过趋势引擎")
                    from src.display.snapshot import SnapshotGenerator
                    gen = SnapshotGenerator()
                    snapshot = gen.generate_red_light(date_str, fusion_regime)
                    print(f"\n✅ 红灯快照已保存")
                    return snapshot

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

    # 5.5 融合层：对趋势个股执行V3增强 + 仓位优化
    fusion_results = {}
    if fusion_orchestrator and fusion_regime and fusion_regime.level != "red":
        from src.engine.key_points import KeyPointDetector
        total_position = 0.0
        if positions:
            total_position = sum(p.get("ratio", 0) for p in positions.values())

        for symbol, trend_state in stock_results.items():
            daily_df = stock_data.get(symbol)
            if daily_df is None or len(daily_df) < 20:
                continue

            # 获取前一日状态用于检测操作点
            prev_state = None
            if prev_snapshot:
                prev_stocks = prev_snapshot.get("stocks", {})
                prev_item = prev_stocks.get(symbol, {})
                prev_state = prev_item.get("state")

            # 操作点检测（原TFS逻辑，不修改）
            key_point = None
            if prev_state is not None:
                key_point = KeyPointDetector.detect(prev_state, trend_state.state)

            # 融合分析
            fused = fusion_orchestrator.analyze_symbol(
                symbol=symbol,
                daily_df=daily_df,
                state_value=trend_state.state,
                key_point=key_point,
                regime=fusion_regime,
                current_total_position=total_position,
            )
            fusion_results[symbol] = fused

            # 更新总仓位（累加已确认的仓位）
            if fused.optimal_position.final_ratio > 0:
                total_position += fused.optimal_position.final_ratio

        print(f"   🔬 融合分析: {len(fusion_results)}只标的")
        confirmed = sum(1 for f in fusion_results.values() if f.key_point is not None)
        print(f"   ✅ 确认操作点: {confirmed}个")

    gen = SnapshotGenerator()
    snapshot = gen.generate(date_str, sector_results, theme_results, stock_results, etf_results,
                           previous_snapshot=prev_snapshot, positions=positions,
                           fusion_results=fusion_results if fusion_results else None)

    print(f"\n✅ 分析完成! 快照已保存: dashboard/data/trend_snapshot_{date_str}.json")
    print(f"   上涨板块: {snapshot['market_overview']['uptrend_sectors']}")
    print(f"   活跃题材: {snapshot['market_overview']['active_themes']}")
    print(f"   趋势个股: {snapshot['market_overview']['trend_stocks']}")
    print(f"   趋势ETF: {snapshot['market_overview']['trend_etfs']}")
    print(f"   关键操作: {len(snapshot['key_actions'])}个")

    return snapshot


def cmd_dashboard():
    """打开HTML Dashboard（内嵌数据版，无需服务器，双击即开）。"""
    # 优先使用内嵌数据的独立版
    dashboard_path = os.path.join(os.path.dirname(__file__), "..", "dashboard", "index.html")
    if not os.path.exists(dashboard_path):
        # 回退到模板版
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
