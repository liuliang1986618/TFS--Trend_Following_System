"""ETF直筛路径 — 与漏斗主路径并行运行。

设计文档§3.2：
  ETF池(~100-200只) → 直接跑状态机 → 筛出上涨趋势ETF
  类型A(板块ETF): 板块确认后可交易
  类型B(跨板块): 独立判断
  类型C(宽基): 不适用，跳过

为什么需要ETF直筛？
→ 多赚钱：ETF交易成本低、无暴雷风险。如果ETF自身处于上涨趋势，
  即使没经过板块→题材→个股漏斗，也是好的交易标的。
  低门槛 + 低风险 = 稳健赚钱。
"""
from ..engine.state_machine import StateMachine, TrendState
from typing import Dict, List
import pandas as pd


class ETFFilter:
    """ETF直筛路径。"""

    TARGET_STATES = {3, 4, 5}
    ELIGIBLE_TYPES = {"A", "B"}  # C类宽基不适用

    @staticmethod
    def filter(etf_data: Dict[str, pd.DataFrame], etf_metadata: pd.DataFrame = None) -> Dict[str, TrendState]:
        """对A/B类ETF跑状态机，筛选上涨趋势ETF。

        → 少亏钱：C类宽基(沪深300等)不适用趋势跟随策略，直接跳过。
        """
        results = {}
        for sym, df in etf_data.items():
            # 检查ETF类型
            if etf_metadata is not None:
                meta = etf_metadata[etf_metadata["symbol"] == sym]
                if len(meta) > 0 and meta.iloc[0].get("etf_type") == "C":
                    continue  # 宽基跳过

            state_result = StateMachine.classify(df)
            if state_result.state in ETFFilter.TARGET_STATES:
                results[sym] = state_result
        return results
