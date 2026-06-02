"""明日推演引擎 — 状态机驱动的场景推演。

Phase B: generate() 支持外部weights参数（向后兼容）
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from ..engine.state_machine import StateMachine, TrendState


@dataclass
class Scenario:
    """单个推演场景。"""
    label: str  # "场景A(大概率)", "场景B(中概率)", "场景C(小概率)"
    probability: str  # "大概率", "中概率", "小概率"
    weight: float  # 权重值 (0.0-1.0)，Phase B新增
    conditions: str  # 触发条件
    action: str  # 对应操作
    next_state: str  # 转换后状态


class ScenarioEngine:
    """明日推演引擎。"""

    @staticmethod
    def generate(ts: TrendState, weights: Optional[Dict[str, float]] = None) -> List[Scenario]:
        """基于当前状态生成明日推演场景。

        Args:
            ts: 当前趋势状态
            weights: 可选权重字典 {"A": 0.60, "B": 0.30, "C": 0.10}
                     若为None则使用默认等权分配（向后兼容）
        """
        state = ts.state

        # 默认权重
        if weights is None:
            weights = {"A": 0.60, "B": 0.30, "C": 0.10}

        w_a = weights.get("A", 0.60)
        w_b = weights.get("B", 0.30)
        w_c = weights.get("C", 0.10)

        # 根据状态选择概率标签
        def prob_label(w, hi, mid, lo):
            if w >= hi: return "大概率"
            if w >= mid: return "中概率"
            return "小概率"

        hi_threshold = max(w_a, w_b, w_c) * 0.8

        scenarios = []

        if state == 4:
            scenarios = [
                Scenario("场景A(大概率)", prob_label(w_a, 0.50, 0.30, 0.15), w_a,
                         "继续沿MA20上方运行, 无异常信号",
                         "仓位不变, 持股待涨", "状态4→4"),
                Scenario("场景B(中概率)", prob_label(w_b, 0.50, 0.30, 0.15), w_b,
                         "缩量回调, 不破前低",
                         "继续持仓, 紧盯前低; 企稳反弹时加仓至1.5倍", "状态4→5"),
                Scenario("场景C(小概率)", prob_label(w_c, 0.50, 0.30, 0.15), w_c,
                         "放量跌破前低, 收盘未收复",
                         "减至1/3仓防守", "状态4→3'"),
            ]
        elif state == 3:
            scenarios = [
                Scenario("场景A(大概率)", prob_label(w_a, 0.40, 0.25, 0.10), w_a,
                         "回调不破前低, 继续整理",
                         "维持试探仓, 等待确认", "状态3→3"),
                Scenario("场景B(中概率)", prob_label(w_b, 0.40, 0.25, 0.10), w_b,
                         "放量再创新高, 结构完整",
                         "加至标准仓(100%)", "状态3→4"),
                Scenario("场景C(小概率)", prob_label(w_c, 0.40, 0.25, 0.10), w_c,
                         "放量跌破前低, 假突破确认",
                         "全部清仓止损", "状态3→1"),
            ]
        elif state == 5:
            scenarios = [
                Scenario("场景A(大概率)", prob_label(w_a, 0.40, 0.25, 0.10), w_a,
                         "缩量企稳反弹, 不破前低",
                         "加仓至1.2~1.5倍", "状态5→4"),
                Scenario("场景B(中概率)", prob_label(w_b, 0.40, 0.25, 0.10), w_b,
                         "继续整理, 方向不明",
                         "持仓不动, 继续观察", "状态5→5"),
                Scenario("场景C(小概率)", prob_label(w_c, 0.40, 0.25, 0.10), w_c,
                         "放量跌破前低",
                         "减至1/3仓防守", "状态5→3'"),
            ]
        elif state == "3'":
            scenarios = [
                Scenario("场景A(大概率)", prob_label(w_a, 0.35, 0.20, 0.10), w_a,
                         "假跌破确认, 快速收复前低",
                         "回补至标准仓", "状态3'→4"),
                Scenario("场景B(中概率)", prob_label(w_b, 0.35, 0.20, 0.10), w_b,
                         "继续在低点附近缩量整理",
                         "维持1/3仓, 继续观察", "状态3'→3'"),
                Scenario("场景C(小概率)", prob_label(w_c, 0.35, 0.20, 0.10), w_c,
                         "继续下跌, 再破新低",
                         "全部清仓", "状态3'→1"),
            ]
        elif state == 2:
            scenarios = [
                Scenario("场景A(大概率)", prob_label(w_a, 0.40, 0.25, 0.10), w_a,
                         "继续反弹, 逐步靠近前高",
                         "不动, 紧盯前高", "状态2→2"),
                Scenario("场景B(中概率)", prob_label(w_b, 0.40, 0.25, 0.10), w_b,
                         "放量突破前高",
                         "1/6试探建仓", "状态2→3"),
                Scenario("场景C(小概率)", prob_label(w_c, 0.40, 0.25, 0.10), w_c,
                         "反弹结束, 回落破前低",
                         "继续空仓, 放弃跟踪", "状态2→1"),
            ]
        elif state == 1:
            scenarios = [
                Scenario("场景A(大概率)", prob_label(w_a, 0.50, 0.30, 0.15), w_a,
                         "继续沿MA20下方运行, 持续下跌",
                         "空仓, 不动", "状态1→1"),
                Scenario("场景B(小概率)", prob_label(w_b, 0.50, 0.30, 0.15), w_b,
                         "出现连续上涨反弹信号",
                         "纳入观察, 盯前高", "状态1→2"),
            ]

        return scenarios
