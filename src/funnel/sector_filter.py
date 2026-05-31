"""板块趋势判断 — 漏斗第一层。

设计文档§3.1 第一层：
  输入: 板块日K OHLCV (~60-90个)
  逻辑: 跑状态机，筛出状态3/4/5的板块
  输出: 上涨板块列表 (~5-15个)

为什么从板块开始？
→ 多赚钱：A股70%以上的个股波动由板块驱动。先确定哪些板块在上涨趋势中，
  再在上涨板块中选个股，大幅提高选股成功率。逆板块趋势的个股即使涨也难持续。
"""
from typing import List, Dict
import pandas as pd
from ..engine.state_machine import StateMachine, TrendState


class SectorFilter:
    """板块趋势判断 — 漏斗第一层。

    遍历所有板块日K数据，运行状态机，筛选处于上涨趋势的板块。
    """

    TARGET_STATES = {3, 4, 5}  # 只关注上涨趋势相关状态

    @staticmethod
    def filter(sector_data: Dict[str, pd.DataFrame]) -> Dict[str, TrendState]:
        """筛选处于上涨趋势的板块。

        → 多赚钱：在全市场60-90个板块中筛选出5-15个上涨板块，
          把选股范围从5000+缩小到300-500只，大幅提高命中率。
        """
        results = {}
        for bk_code, df in sector_data.items():
            state_result = StateMachine.classify(df)
            if state_result.state in SectorFilter.TARGET_STATES:
                results[bk_code] = state_result
        return results

    @staticmethod
    def rank(results: Dict[str, TrendState]) -> List[tuple]:
        """按趋势强度排序板块。

        排序规则（多赚钱）：
          1. 状态4 > 状态5 > 状态3（趋势越强越优先）
          2. 同状态：结构完整度 > 量能比 > 持续性
        """
        def score(item):
            code, ts = item
            state_score = {4: 100, 5: 80, 3: 60}
            base = state_score.get(ts.state, 0)
            if ts.conditions["structure"].pass_: base += 10
            if ts.conditions["volume"].pass_: base += 10
            if ts.conditions["persistence"].pass_: base += 10
            return base

        return sorted(results.items(), key=score, reverse=True)
