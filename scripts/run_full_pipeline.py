#!/usr/bin/env python3
"""完整流水线：拉取数据 → 运行分析 → 生成Dashboard → 回测优化。

用法: python3 scripts/run_full_pipeline.py [date]
"""
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime


def main():
    date_str = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y-%m-%d")
    print(f"趋势跟随系统 — 完整流水线 — {date_str}")
    print("=" * 70)

    # ── Step 1: 回测优化（使用历史数据找到最优参数） ──
    print("\n[Step 1] 回测优化...")
    try:
        from src.backtest.engine import BacktestEngine
        from src.backtest.optimizer import ParameterOptimizer
        from src.data.fetcher import DataFetcher

        fetcher = DataFetcher()
        sectors = fetcher.load_all_sectors()

        if sectors:
            print(f"   已加载 {len(sectors)} 个板块数据用于回测")
            optimizer = ParameterOptimizer()
            best_configs = optimizer.optimize(sectors, top_n=3)

            if best_configs:
                print(f"   最优参数: {best_configs[0]['config']}")
                print(f"   年化收益: {best_configs[0].get('annual_return', 'N/A')}%")
                print(f"   最大回撤: {best_configs[0].get('max_drawdown', 'N/A')}%")
                print(f"   夏普比率: {best_configs[0].get('sharpe_ratio', 'N/A')}")
            else:
                print("   回测未产出有效结果（数据不足或无可交易信号）")

            # 保存回测结果
            os.makedirs("dashboard/data", exist_ok=True)
            with open("dashboard/data/backtest_results.json", "w") as f:
                json.dump({
                    "date": date_str,
                    "best_config": best_configs[0] if best_configs else None,
                    "all_results": optimizer.results[:10],
                }, f, ensure_ascii=False, indent=2, default=str)
            print(f"   回测结果已保存: dashboard/data/backtest_results.json")
        else:
            print("   本地无板块数据，跳过回测。请先运行 init_db 拉取历史数据。")
    except Exception as e:
        print(f"   回测失败: {e}")

    # ── Step 2: 运行当日分析 ──
    print(f"\n[Step 2] 运行{date_str}分析...")
    try:
        from src.cli import cmd_run
        snapshot = cmd_run(date_str)
        print("   分析完成")
    except Exception as e:
        print(f"   分析失败: {e}")
        print("   尝试使用模拟数据生成演示Dashboard...")
        _generate_demo_snapshot(date_str)

    # ── Step 3: 输出Dashboard路径 ──
    print(f"\n[Step 3] Dashboard就绪")
    print(f"   数据文件: dashboard/data/trend_snapshot_{date_str}.json")
    print(f"   回测结果: dashboard/data/backtest_results.json")
    print(f"   Dashboard: src/display/dashboard.html")
    print(f"\n流水线完成!")


def _generate_demo_snapshot(date_str):
    """使用模拟数据生成演示快照。

    为什么需要模拟数据？
    → 少亏钱：当网络不可用或数据源故障时，至少能生成可操作的演示Dashboard，
      验证系统各环节都正常工作。真实交易时再切换到实盘数据。
    """
    import numpy as np
    import pandas as pd
    from tests.conftest import make_ohlcv
    from src.engine.state_machine import StateMachine
    from src.funnel.sector_filter import SectorFilter
    from src.funnel.theme_filter import ThemeFilter
    from src.funnel.stock_filter import StockFilter
    from src.funnel.etf_filter import ETFFilter
    from src.display.snapshot import SnapshotGenerator

    n = 80
    dates = pd.date_range("2026-02-01", periods=n, freq="B")
    np.random.seed(42)

    def make_trend(start, end, trend_type="up"):
        """生成模拟日K序列：上涨/下跌/横盘。"""
        if trend_type == "up":
            closes = list(np.linspace(start, end, n))
            # 叠加小波动
            closes = [c + np.random.randn() * 0.1 for c in closes]
            # 阳线为主: open < close
            opens = [c - abs(np.random.randn() * 0.15) - 0.02 for c in closes]
            volumes = [1200000 + int(np.random.random() * 500000) for _ in range(n)]
        elif trend_type == "down":
            closes = list(np.linspace(start, end, n))
            closes = [c + np.random.randn() * 0.1 for c in closes]
            # 阴线为主: open > close
            opens = [c + abs(np.random.randn() * 0.15) + 0.02 for c in closes]
            volumes = [800000 + int(np.random.random() * 300000) for _ in range(n)]
        else:
            closes = [start + np.random.randn() * 0.15 for _ in range(n)]
            opens = [c - np.random.randn() * 0.05 for c in closes]
            volumes = [1000000 + int(np.random.random() * 200000) for _ in range(n)]

        return make_ohlcv(dates, closes, volumes, opens)

    # 生成多个模拟板块：覆盖上涨/下跌/横盘
    sector_data = {
        "BK0477": make_trend(10, 18, "up"),     # 半导体-上涨
        "BK0488": make_trend(15, 13, "down"),   # 银行-下跌
        "BK0499": make_trend(8, 12, "up"),      # AI-上涨
        "BK0500": make_trend(20, 16, "down"),   # 地产-下跌
        "BK0501": make_trend(9, 14, "up"),      # 新能源-上涨
        "BK0502": make_trend(7, 7.5, "flat"),   # 消费-横盘
    }

    sector_names = {
        "BK0477": "半导体", "BK0488": "银行", "BK0499": "AI智能",
        "BK0500": "房地产", "BK0501": "新能源", "BK0502": "消费",
    }

    # 生成模拟题材
    theme_data = {
        "GN001": make_trend(12, 20, "up"),   # 光刻机-上涨
        "GN002": make_trend(9, 15, "up"),    # 机器人-上涨
        "GN003": make_trend(14, 12, "down"), # 白酒-下跌
    }

    theme_names = {
        "GN001": "光刻机", "GN002": "机器人", "GN003": "白酒",
    }

    # 生成模拟个股
    stock_data = {
        "300308": make_trend(100, 180, "up"),  # 中际旭创-上涨
        "002371": make_trend(200, 320, "up"),  # 北方华创-上涨
        "688981": make_trend(50, 80, "up"),    # 中芯国际-上涨
        "600519": make_trend(1800, 1600, "down"), # 贵州茅台-下跌
    }

    stock_names = {
        "300308": "中际旭创", "002371": "北方华创",
        "688981": "中芯国际", "600519": "贵州茅台",
    }

    # 生成模拟ETF
    etf_data = {
        "512480": make_trend(0.7, 1.2, "up"),    # 半导体ETF-上涨
        "159819": make_trend(0.8, 1.35, "up"),   # AI智能ETF-上涨
        "159915": make_trend(2.0, 2.5, "up"),    # 创业板ETF-上涨
        "510300": make_trend(3.5, 3.4, "flat"),  # 沪深300ETF-横盘
    }

    etf_names = {
        "512480": "半导体ETF", "159819": "AI智能ETF",
        "159915": "创业板ETF", "510300": "沪深300ETF",
    }

    etf_types = {
        "512480": "A", "159819": "A", "159915": "B", "510300": "C",
    }

    # 运行各层过滤
    sector_results = SectorFilter.filter(sector_data)
    theme_results = ThemeFilter.filter(theme_data)
    stock_results = StockFilter.filter(stock_data)
    etf_results = ETFFilter.filter(etf_data)

    # 生成快照
    gen = SnapshotGenerator()
    snapshot = gen.generate(
        date_str,
        sector_results,
        theme_results,
        stock_results,
        etf_results,
        sector_names=sector_names,
        theme_names=theme_names,
        stock_names=stock_names,
        etf_names=etf_names,
        etf_types=etf_types,
    )

    print(f"   演示快照已生成: {len(sector_results)}个上涨板块, "
          f"{len(theme_results)}个活跃题材, "
          f"{len(stock_results)}个趋势个股, "
          f"{len(etf_results)}个趋势ETF")

    # 同时生成回测演示数据
    _generate_demo_backtest(date_str, sector_data)


def _generate_demo_backtest(date_str, sector_data):
    """生成演示回测结果。"""
    from src.backtest.engine import BacktestEngine
    from src.backtest.optimizer import ParameterOptimizer

    os.makedirs("dashboard/data", exist_ok=True)

    all_results = []
    for symbol, df in list(sector_data.items())[:4]:
        engine = BacktestEngine(initial_capital=100000)
        metrics = engine.run(df)
        metrics["symbol"] = symbol
        all_results.append(metrics)

    all_results.sort(key=lambda x: x.get("annual_return", -999), reverse=True)

    best_config = {
        "name": "默认值(设计文档推荐)",
        "params": {
            "ma_period": 20,
            "volume_lookback": 20,
            "persistence_lookback": 20,
            "min_consecutive_yang": 3,
            "volume_surge_threshold": 1.2,
            "volume_shrink_threshold": 0.8,
        },
    }

    with open("dashboard/data/backtest_results.json", "w") as f:
        json.dump({
            "date": date_str,
            "note": "演示数据（网络不可用时生成）",
            "best_config": best_config,
            "all_results": all_results,
        }, f, ensure_ascii=False, indent=2, default=str)

    print(f"   演示回测已生成: {len(all_results)}个板块回测结果")


if __name__ == "__main__":
    main()
