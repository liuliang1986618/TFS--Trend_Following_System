"""题材趋势判断 — 漏斗第二层。

设计文档§3.1 第二层：
  输入: 题材日K OHLCV (上涨板块内的题材)
  逻辑: 跑状态机，筛出状态3/4的题材
  输出: 活跃题材列表 (~3-8个)

为什么题材在板块之后？
→ 多赚钱：题材通常比板块更窄、更热、弹性更大。板块确认大的方向后，
  题材提供更精确的alpha来源——同一板块内，高景气题材涨幅往往是板块的2-3倍。
"""
from ..engine.state_machine import StateMachine, TrendState
from typing import Dict, List
import pandas as pd


class ThemeFilter:
    """题材趋势判断 — 漏斗第二层。"""

    TARGET_STATES = {3, 4}  # 题材只看状态3/4（发展期/高潮期）

    @staticmethod
    def filter(theme_data: Dict[str, pd.DataFrame]) -> Dict[str, TrendState]:
        """筛选处于发展期/高潮期的题材（状态3/4）。

        → 多赚钱：题材比板块更精准，只关注状态3/4的活跃题材。
          状态5(回调)的题材不参与——回调题材的个股选出来也很难持续。
        """
        results = {}
        for gn_code, df in theme_data.items():
            state_result = StateMachine.classify(df)
            if state_result.state in ThemeFilter.TARGET_STATES:
                results[gn_code] = state_result
        return results

    @staticmethod
    def rank(results: Dict[str, TrendState]) -> List[tuple]:
        """按活跃度排序题材。

        → 多赚钱：题材活跃度=赚钱效应。状态4>状态3，结构完整度>量能>持续性。
        """
        def score(item):
            code, ts = item
            state_score = {4: 100, 3: 60}
            base = state_score.get(ts.state, 0)
            if ts.conditions["structure"].pass_: base += 15
            if ts.conditions["volume"].pass_: base += 10
            if ts.conditions["persistence"].pass_: base += 10
            return base
        return sorted(results.items(), key=score, reverse=True)
