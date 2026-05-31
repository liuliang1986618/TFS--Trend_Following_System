"""趋势变化对比 — vs 昨日/3日前/上周。

设计文档§9.6:
  新进入上涨趋势 ▲
  退出上涨趋势 ▼
  状态不变但趋势变化 ●

为什么需要对比？
→ 多赚钱：趋势是动态过程，今天的上涨板块昨天可能还没启动。
  对比变化=发现新机会(新进入)+规避风险(退出)+监控趋势质量(变化)。
"""
from typing import Dict, List
from ..engine.state_machine import TrendState


class TrendComparison:
    """对比不同日期的趋势分析结果。"""

    @staticmethod
    def compare(current: Dict[str, TrendState],
                previous: Dict[str, TrendState]) -> dict:
        """对比两个日期的趋势结果。

        Returns: {
            "new_uptrend": [(code, prev_state, curr_state), ...],   # 新进入
            "exited_uptrend": [(code, prev_state, curr_state), ...], # 退出
            "state_changed": [(code, prev_state, curr_state), ...],  # 状态变化
            "same_state": [(code, state), ...],                      # 状态不变
        }
        """
        new_uptrend = []
        exited_uptrend = []
        state_changed = []
        same_state = []

        # 新进入: 之前不在上涨状态，现在在
        uptrend_states = {3, 4, 5}
        for code, curr in current.items():
            if code in previous:
                prev = previous[code]
                prev_in_uptrend = prev.state in uptrend_states
                curr_in_uptrend = curr.state in uptrend_states

                if not prev_in_uptrend and curr_in_uptrend:
                    new_uptrend.append((code, prev.state, curr.state))
                elif prev_in_uptrend and not curr_in_uptrend:
                    exited_uptrend.append((code, prev.state, curr.state))
                elif prev.state != curr.state:
                    state_changed.append((code, prev.state, curr.state))
                else:
                    same_state.append((code, curr.state))
            else:
                # 新标的（首次出现）
                if curr.state in uptrend_states:
                    new_uptrend.append((code, "NEW", curr.state))

        return {
            "new_uptrend": new_uptrend,
            "exited_uptrend": exited_uptrend,
            "state_changed": state_changed,
            "same_state": same_state,
        }
