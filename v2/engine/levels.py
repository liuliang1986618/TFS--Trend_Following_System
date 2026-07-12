"""Support, resistance, stop, and key-level calculations for TFS v2.

包含PivotDetector（前高/前低识别器）和涨跌停处理。
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from typing import List, Optional, Dict


def _is_limit_day(df: pd.DataFrame, idx: int) -> bool:
    """判断某日是否为涨跌停日。
    
    A股涨跌停定义：
    - 普通股票：涨跌幅 > 9.5% 或 < -9.5%
    - 创业板/科创板(30x/68x)：涨跌幅 > 19.5% 或 < -19.5%
    - ST股票：涨跌幅 > 4.5% 或 < -4.5%
    
    注意：实际涨跌停判断需要考虑前收盘价，这里简化处理。
    """
    if idx < 0 or idx >= len(df):
        return False
    
    row = df.iloc[idx]
    open_price = row.get("open", 0)
    close_price = row.get("close", 0)
    
    if open_price <= 0:
        return False
    
    # 计算日内涨跌幅
    change_pct = abs(close_price - open_price) / open_price * 100
    
    # 根据股票代码判断板块
    code = str(row.get("code", ""))
    if code.startswith(("30", "68")):  # 创业板/科创板
        return change_pct > 19.5
    else:  # 主板
        return change_pct > 9.5


class PivotDetector:
    """前高/前低识别器 — 纯numpy滚动窗口比较法。
    
    基于v1实现，增加了涨跌停日跳过功能。
    """

    @staticmethod
    def find_highs(daily_df: pd.DataFrame, window: int = 3) -> pd.DataFrame:
        """找出所有局部高点（该日最高价高于前后各window日的最高价）。
        
        涨跌停日跳过：涨跌停日产生的高点不应作为技术参考。
        """
        highs = daily_df["high"].values
        n = len(highs)
        pivot_indices = []
        
        for i in range(window, n - window):
            # 跳过涨跌停日
            if _is_limit_day(daily_df, i):
                continue
            
            left_max = np.max(highs[i - window:i])
            right_max = np.max(highs[i + 1:i + window + 1])
            if highs[i] > left_max and highs[i] > right_max:
                pivot_indices.append(i)
        
        return daily_df.iloc[pivot_indices].copy()

    @staticmethod
    def find_lows(daily_df: pd.DataFrame, window: int = 3) -> pd.DataFrame:
        """找出所有局部低点。
        
        涨跌停日跳过：涨跌停日产生的低点不应作为技术参考。
        """
        lows = daily_df["low"].values
        n = len(lows)
        pivot_indices = []
        
        for i in range(window, n - window):
            # 跳过涨跌停日
            if _is_limit_day(daily_df, i):
                continue
            
            left_min = np.min(lows[i - window:i])
            right_min = np.min(lows[i + 1:i + window + 1])
            if lows[i] < left_min and lows[i] < right_min:
                pivot_indices.append(i)
        
        return daily_df.iloc[pivot_indices].copy()

    @staticmethod
    def recent_high(daily_df: pd.DataFrame, max_age: int = 60) -> Optional[Dict]:
        """获取最近一个有效前高。
        
        max_age: 最大有效交易日数（设计文档§2.3: ≤60个交易日）
        
        Returns:
            {"date": Timestamp, "price": float} 或 None
        """
        pivot_highs = PivotDetector.find_highs(daily_df)
        if len(pivot_highs) == 0:
            return None
        
        last_date = daily_df.index[-1]
        for idx in reversed(pivot_highs.index):
            # 使用交易日计数（索引位置差）而非日历日
            trading_days_diff = len(daily_df.loc[idx:last_date]) - 1
            if trading_days_diff <= max_age:
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
            # 使用交易日计数（索引位置差）而非日历日
            trading_days_diff = len(daily_df.loc[idx:last_date]) - 1
            if trading_days_diff <= max_age:
                return {
                    "date": idx,
                    "price": float(pivot_lows.loc[idx, "low"]),
                }
        return None

    @staticmethod
    def get_last_n_highs(daily_df: pd.DataFrame, n: int = 2, max_age: int = 60) -> List[Dict]:
        """获取最近n个有效前高（按时间升序）。
        
        max_age: 最大有效交易日数（设计文档§2.3: ≤60个交易日）
        
        → 多赚钱：2个更高高=完整上涨结构=状态3→4的买点确认。
          这是仓位从1/3加到100%的核心依据。
        """
        pivot_highs = PivotDetector.find_highs(daily_df)
        if len(pivot_highs) == 0:
            return []
        
        last_date = daily_df.index[-1]
        valid = []
        for idx in pivot_highs.index:
            # 使用交易日计数（索引位置差）而非日历日
            trading_days_diff = len(daily_df.loc[idx:last_date]) - 1
            if trading_days_diff <= max_age:
                valid.append({
                    "date": idx,
                    "price": float(pivot_highs.loc[idx, "high"]),
                })
        
        valid.sort(key=lambda x: x["date"])
        return valid[-n:] if len(valid) >= n else valid

    @staticmethod
    def get_last_n_lows(daily_df: pd.DataFrame, n: int = 2, max_age: int = 60) -> List[Dict]:
        """获取最近n个有效前低（按时间升序）。
        
        max_age: 最大有效交易日数（设计文档§2.3: ≤60个交易日）
        
        → 少亏钱：2个更高低=上涨结构完整。前低依次抬高=回调深度在收窄，
          趋势越来越健康。前低不再抬高=上涨结构松动=预警信号。
        """
        pivot_lows = PivotDetector.find_lows(daily_df)
        if len(pivot_lows) == 0:
            return []
        
        last_date = daily_df.index[-1]
        valid = []
        for idx in pivot_lows.index:
            # 使用交易日计数（索引位置差）而非日历日
            trading_days_diff = len(daily_df.loc[idx:last_date]) - 1
            if trading_days_diff <= max_age:
                valid.append({
                    "date": idx,
                    "price": float(pivot_lows.loc[idx, "low"]),
                })
        
        valid.sort(key=lambda x: x["date"])
        return valid[-n:] if len(valid) >= n else valid


def calculate_key_levels(daily_df, indicators: dict) -> dict:
    close = float(daily_df["close"].iloc[-1])
    return {
        "support": indicators.get("low_20d", close),
        "resistance": indicators.get("high_20d", close),
        "stop_loss": round(close * 0.92, 3),
        "current": close,
    }
