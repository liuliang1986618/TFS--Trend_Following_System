"""前高/前低识别算法 — 局部极值检测。

设计文档§2.3 定义：
  前高/前低: 最近一个明显的局部最高/最低点
  - 局部高/低点: 该日最高价/最低价比前后各3日都高/低
  - 有效期: 距今≤60个交易日
  - 失效后使用次近点

为什么window=3？
→ 多赚钱+少亏钱：3天窗口是经验最优值。太小=噪音干扰多(假极值)，
  太大=漏掉关键拐点(真极值)。漏掉前高=错过状态2→3买点=少赚钱。
  假前低=错误止损位置=过早出局=少赚钱。

为什么max_age=60？
→ 少亏钱：超过60个交易日的极值已失去技术意义。市场环境、资金面、
  情绪面均已变化，旧高点的阻力或旧低点的支撑不再有效。
  参考失效极值=在错误位置设止损=不该亏的钱亏了。
"""
import pandas as pd
import numpy as np
from typing import List, Optional, Dict


class PivotDetector:
    """前高/前低识别器 — 纯numpy滚动窗口比较法。"""

    @staticmethod
    def find_highs(daily_df: pd.DataFrame, window: int = 3) -> pd.DataFrame:
        """找出所有局部高点（该日最高价高于前后各window日的最高价）。

        → 多赚钱：前高是下跌→上涨翻转的确认线。识别前高=确定买点触发位置。
        """
        highs = daily_df["high"].values
        n = len(highs)
        pivot_indices = []

        for i in range(window, n - window):
            left_max = np.max(highs[i - window:i])
            right_max = np.max(highs[i + 1:i + window + 1])
            if highs[i] > left_max and highs[i] > right_max:
                pivot_indices.append(i)

        return daily_df.iloc[pivot_indices].copy()

    @staticmethod
    def find_lows(daily_df: pd.DataFrame, window: int = 3) -> pd.DataFrame:
        """找出所有局部低点。

        → 少亏钱：前低是上涨→转跌的警戒线。跌破前低=趋势可能结束。
          准确的前低位置=有效的止损线=控制亏损。
        """
        lows = daily_df["low"].values
        n = len(lows)
        pivot_indices = []

        for i in range(window, n - window):
            left_min = np.min(lows[i - window:i])
            right_min = np.min(lows[i + 1:i + window + 1])
            if lows[i] < left_min and lows[i] < right_min:
                pivot_indices.append(i)

        return daily_df.iloc[pivot_indices].copy()

    @staticmethod
    def recent_high(daily_df: pd.DataFrame, max_age: int = 60) -> Optional[Dict]:
        """获取最近一个有效前高。

        max_age: 最大有效自然日天数

        Returns:
            {"date": Timestamp, "price": float} 或 None
        """
        pivot_highs = PivotDetector.find_highs(daily_df)
        if len(pivot_highs) == 0:
            return None

        last_date = daily_df.index[-1]
        for idx in reversed(pivot_highs.index):
            days_diff = (last_date - idx).days
            if days_diff <= max_age:
                return {
                    "date": idx,
                    "price": float(pivot_highs.loc[idx, "high"]),
                }
        return None

    @staticmethod
    def recent_low(daily_df: pd.DataFrame, max_age: int = 60) -> Optional[Dict]:
        """获取最近一个有效前低。

        → 少亏钱：止损线设在有效前低下方。如果前低已过期(>60日)，
          使用次近的低点=避免止损线设在已被市场遗忘的位置。
        """
        pivot_lows = PivotDetector.find_lows(daily_df)
        if len(pivot_lows) == 0:
            return None

        last_date = daily_df.index[-1]
        for idx in reversed(pivot_lows.index):
            days_diff = (last_date - idx).days
            if days_diff <= max_age:
                return {
                    "date": idx,
                    "price": float(pivot_lows.loc[idx, "low"]),
                }
        return None

    @staticmethod
    def get_last_n_highs(daily_df: pd.DataFrame, n: int = 2) -> List[Dict]:
        """获取最近n个有效前高（按时间升序）。

        → 多赚钱：2个更高高=完整上涨结构=状态3→4的买点确认。
          这是仓位从1/3加到100%的核心依据。
        """
        pivot_highs = PivotDetector.find_highs(daily_df)
        if len(pivot_highs) == 0:
            return []

        last_date = daily_df.index[-1]
        valid = []
        for idx in pivot_highs.index:
            if (last_date - idx).days <= 60:
                valid.append({
                    "date": idx,
                    "price": float(pivot_highs.loc[idx, "high"]),
                })

        valid.sort(key=lambda x: x["date"])
        return valid[-n:] if len(valid) >= n else valid

    @staticmethod
    def get_last_n_lows(daily_df: pd.DataFrame, n: int = 2) -> List[Dict]:
        """获取最近n个有效前低（按时间升序）。

        → 少亏钱：2个更高低=上涨结构完整。前低依次抬高=回调深度在收窄，
          趋势越来越健康。前低不再抬高=上涨结构松动=预警信号。
        """
        pivot_lows = PivotDetector.find_lows(daily_df)
        if len(pivot_lows) == 0:
            return []

        last_date = daily_df.index[-1]
        valid = []
        for idx in pivot_lows.index:
            if (last_date - idx).days <= 60:
                valid.append({
                    "date": idx,
                    "price": float(pivot_lows.loc[idx, "low"]),
                })

        valid.sort(key=lambda x: x["date"])
        return valid[-n:] if len(valid) >= n else valid
