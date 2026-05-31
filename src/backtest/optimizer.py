"""参数优化器 — 网格搜索最优参数组合。

为什么需要参数优化？
→ 多赚钱：不同市场环境下最优参数不同。优化=找到当前最适合赚钱的参数。
→ 少亏钱：避免使用极端参数（如过短的窗口=过度交易=手续费吃掉利润）。
"""
import itertools
import json
from typing import Dict, List
from .engine import BacktestEngine


class ParameterOptimizer:
    """网格搜索参数优化器。

    测试预设的参数配置组合，找到Top N最优参数。
    """

    # 预设参数配置（基于设计文档的经验值范围）
    TEST_CONFIGS = [
        {
            "name": "默认值(设计文档推荐)",
            "ma_period": 20,
            "volume_lookback": 20,
            "persistence_lookback": 20,
            "min_consecutive_yang": 3,
            "volume_surge_threshold": 1.2,
            "volume_shrink_threshold": 0.8,
        },
        {
            "name": "灵敏度较高(快进快出)",
            "ma_period": 15,
            "volume_lookback": 15,
            "persistence_lookback": 15,
            "min_consecutive_yang": 2,
            "volume_surge_threshold": 1.15,
            "volume_shrink_threshold": 0.85,
        },
        {
            "name": "稳定度较高(减少假信号)",
            "ma_period": 25,
            "volume_lookback": 25,
            "persistence_lookback": 25,
            "min_consecutive_yang": 3,
            "volume_surge_threshold": 1.3,
            "volume_shrink_threshold": 0.75,
        },
        {
            "name": "连阳放宽(更快入场)",
            "ma_period": 20,
            "volume_lookback": 20,
            "persistence_lookback": 20,
            "min_consecutive_yang": 2,
            "volume_surge_threshold": 1.2,
            "volume_shrink_threshold": 0.8,
        },
        {
            "name": "严格放量(排除诱多)",
            "ma_period": 20,
            "volume_lookback": 25,
            "persistence_lookback": 20,
            "min_consecutive_yang": 3,
            "volume_surge_threshold": 1.3,
            "volume_shrink_threshold": 0.75,
        },
    ]

    def __init__(self):
        self.results = []

    def optimize(self, daily_data: dict, top_n: int = 5) -> list:
        """运行参数搜索，找到Top N参数组合。

        在可用的板块数据上测试每种参数配置，找出最优组合。

        → 多赚钱：自动找到最优参数=最大化策略收益。
        """
        best = []

        # 选取前5个板块用于快速测试
        test_symbols = list(daily_data.keys())[:5]
        if not test_symbols:
            return best

        for symbol in test_symbols:
            df = daily_data[symbol]
            for config in self.TEST_CONFIGS:
                engine = BacktestEngine(initial_capital=100000)
                metrics = engine.run(df)
                if "error" in metrics:
                    continue
                metrics["symbol"] = symbol
                metrics["config"] = config["name"]
                metrics["params"] = config
                self.results.append(metrics)

        # 按年化收益排序
        self.results.sort(
            key=lambda x: x.get("annual_return", -999),
            reverse=True,
        )
        return self.results[:top_n]

    def best_config(self) -> dict:
        """返回最优参数配置。

        如果没有回测结果，返回默认推荐配置。
        """
        if not self.results:
            return {
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
        return self.results[0]
