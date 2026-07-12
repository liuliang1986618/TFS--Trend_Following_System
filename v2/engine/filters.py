"""Trend quality filters for TFS v2.

包含涨跌停日过滤。
"""

from __future__ import annotations


def apply_trend_filters(state, indicators: dict, daily_df=None) -> tuple[bool, list[str]]:
    """应用趋势过滤条件。
    
    参数:
        state: 当前趋势状态
        indicators: 技术指标字典
        daily_df: 日K线数据（可选，用于涨跌停过滤）
    
    返回:
        (是否通过过滤, 过滤原因列表)
    """
    reasons: list[str] = []
    
    # 现有过滤条件
    if state in (1, 2, "3'"):
        reasons.append("defensive_state")
    if state == 3 and indicators.get("pct_20d", 0.0) < -3:
        reasons.append("weak_midterm_momentum")
    if state == 5 and indicators.get("ma_death_cross"):
        reasons.append("pullback_with_death_cross")
    
    # 新增：涨跌停日过滤
    if daily_df is not None and len(daily_df) > 0:
        from v2.engine.levels import _is_limit_day
        if _is_limit_day(daily_df, len(daily_df) - 1):
            reasons.append("limit_up_down_day")
    
    return len(reasons) == 0, reasons
