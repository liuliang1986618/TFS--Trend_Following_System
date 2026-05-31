"""个股趋势判断 — 漏斗第三层。

设计文档§3.1 第三层：
  输入: 个股日K (~300-500只，活跃题材内成分股)
  逻辑: 跑状态机，输出状态+关键点信号
  输出: 趋势个股 + 交易信号 (~5-20只)

为什么个股放最后一层？
→ 少亏钱：前两层已过滤80-90%噪声，第三层只处理300-500只个股。
  如果直接在全市场5000个股跑状态机，会产出大量"技术形态好看但无板块支撑"的假信号。
  有板块支撑的趋势个股=更有持续性=更不容易被套。
"""
from ..engine.state_machine import StateMachine, TrendState
from typing import Dict, List
import pandas as pd


class StockFilter:
    """个股趋势判断 — 漏斗第三层。"""

    TARGET_STATES = {3, 4, 5}

    @staticmethod
    def filter(stock_data: Dict[str, pd.DataFrame]) -> Dict[str, TrendState]:
        """筛选处于上涨趋势的个股。

        → 多赚钱：只在上涨板块+活跃题材的成分股中选股，双重背书=高胜率。
        """
        results = {}
        for sym, df in stock_data.items():
            state_result = StateMachine.classify(df)
            if state_result.state in StockFilter.TARGET_STATES:
                results[sym] = state_result
        return results

    @staticmethod
    def rank(results: Dict[str, TrendState]) -> List[tuple]:
        """按操作价值排序个股。状态4>5>3，结构完整度>量能>持续性。"""
        def score(item):
            code, ts = item
            state_score = {4: 100, 5: 85, 3: 70}
            base = state_score.get(ts.state, 0)
            if ts.conditions["structure"].pass_: base += 10
            if ts.conditions["volume"].pass_: base += 10
            if ts.conditions["persistence"].pass_: base += 10
            return base
        return sorted(results.items(), key=score, reverse=True)
