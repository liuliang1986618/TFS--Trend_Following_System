"""市场宽度指标 — 判断整体市场健康度。

设计文档§9.6:
  上涨板块数变化、状态4标的数变化、趋势质量

为什么需要市场宽度？
→ 多赚钱：宽度扩大=趋势扩散=机会增多=可以更积极。
→ 少亏钱：宽度收窄=趋势集中在少数板块=风险加大=应该保守。
"""
from typing import Dict
from ..engine.state_machine import TrendState


class MarketBreadth:
    """市场宽度指标计算。"""

    @staticmethod
    def calculate(sector_results: Dict[str, TrendState],
                  stock_results: Dict[str, TrendState],
                  etf_results: Dict[str, TrendState]) -> dict:
        """计算市场宽度指标。

        Returns:
            {
                "uptrend_sectors": N,       # 上涨板块数(状态3/4/5)
                "state4_sectors": N,        # 状态4板块数(最健康)
                "uptrend_stocks": N,         # 趋势个股数
                "uptrend_etfs": N,           # 趋势ETF数
                "market_health": "强势"|"正常"|"弱势",
            }
        """
        uptrend_sectors = sum(1 for ts in sector_results.values() if ts.state in {3, 4, 5})
        state4_sectors = sum(1 for ts in sector_results.values() if ts.state == 4)
        uptrend_stocks = sum(1 for ts in stock_results.values() if ts.state in {3, 4, 5})
        uptrend_etfs = sum(1 for ts in etf_results.values() if ts.state in {3, 4, 5})

        # 市场健康度判定
        if uptrend_sectors >= 15 and state4_sectors >= 8:
            health = "强势"
        elif uptrend_sectors >= 8:
            health = "正常"
        else:
            health = "弱势"

        return {
            "uptrend_sectors": uptrend_sectors,
            "state4_sectors": state4_sectors,
            "uptrend_stocks": uptrend_stocks,
            "uptrend_etfs": uptrend_etfs,
            "market_health": health,
        }

    @staticmethod
    def compare(current_breadth: dict, previous_breadth: dict) -> dict:
        """对比两天的市场宽度变化。

        → 多赚钱：宽度持续扩大=行情走好=可以加仓。
        → 少亏钱：宽度持续收窄=行情转弱=应该减仓。
        """
        if not previous_breadth:
            return {"breadth_trend": "首次计算"}

        changes = {}
        for key in ["uptrend_sectors", "state4_sectors", "uptrend_stocks", "uptrend_etfs"]:
            prev = previous_breadth.get(key, 0)
            curr = current_breadth.get(key, 0)
            changes[key] = curr - prev

        # 综合判定
        total_change = sum(changes.values())
        if total_change > 3:
            trend = "扩大 ↑"
        elif total_change < -3:
            trend = "收窄 ↓"
        else:
            trend = "持平 →"

        changes["breadth_trend"] = trend
        return changes
