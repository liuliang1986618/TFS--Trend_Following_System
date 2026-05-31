"""明日推演引擎 — 状态机驱动的场景推演。

设计文档§9.8:
  场景A(大概率): 延续当前趋势
  场景B(中概率): 出现回调/反弹
  场景C(小概率): 关键位被突破

为什么需要推演？
→ 少亏钱：提前推演明日可能的场景=提前制定操作预案。
  市场变化时不需要临时判断(情绪干扰)，按预案执行即可。
→ 多赚钱：场景推演帮你提前识别"最佳加仓"和"最佳止盈"时机。
"""
from dataclasses import dataclass, field
from typing import List, Optional
from ..engine.state_machine import StateMachine, TrendState


@dataclass
class Scenario:
    """单个推演场景。"""
    label: str  # "场景A(大概率)", "场景B(中概率)", "场景C(小概率)"
    probability: str  # "大概率", "中概率", "小概率"
    conditions: str  # 触发条件
    action: str  # 对应操作
    next_state: str  # 转换后状态


class ScenarioEngine:
    """明日推演引擎。"""

    @staticmethod
    def generate(ts: TrendState) -> List[Scenario]:
        """基于当前状态生成明日推演场景。

        → 少亏钱：每种状态都有最坏情况的预案=永远不会被打个措手不及。
        """
        state = ts.state
        scenarios = []

        if state == 4:
            scenarios = [
                Scenario("场景A(大概率)", "大概率",
                         "继续沿MA20上方运行, 无异常信号",
                         "仓位不变, 持股待涨", "状态4→4"),
                Scenario("场景B(中概率)", "中概率",
                         "缩量回调, 不破前低",
                         "继续持仓, 紧盯前低; 企稳反弹时加仓至1.5倍", "状态4→5"),
                Scenario("场景C(小概率)", "小概率",
                         "放量跌破前低, 收盘未收复",
                         "减至1/3仓防守", "状态4→3'"),
            ]
        elif state == 3:
            scenarios = [
                Scenario("场景A(大概率)", "大概率",
                         "回调不破前低, 继续整理",
                         "维持试探仓, 等待确认", "状态3→3"),
                Scenario("场景B(中概率)", "中概率",
                         "放量再创新高, 结构完整",
                         "加至标准仓(100%)", "状态3→4"),
                Scenario("场景C(小概率)", "小概率",
                         "放量跌破前低, 假突破确认",
                         "全部清仓止损", "状态3→1"),
            ]
        elif state == 5:
            scenarios = [
                Scenario("场景A(大概率)", "大概率",
                         "缩量企稳反弹, 不破前低",
                         "加仓至1.2~1.5倍", "状态5→4"),
                Scenario("场景B(中概率)", "中概率",
                         "继续整理, 方向不明",
                         "持仓不动, 继续观察", "状态5→5"),
                Scenario("场景C(小概率)", "小概率",
                         "放量跌破前低",
                         "减至1/3仓防守", "状态5→3'"),
            ]
        elif state == "3'":
            scenarios = [
                Scenario("场景A(大概率)", "大概率",
                         "假跌破确认, 快速收复前低",
                         "回补至标准仓", "状态3'→4"),
                Scenario("场景B(中概率)", "中概率",
                         "继续在低点附近缩量整理",
                         "维持1/3仓, 继续观察", "状态3'→3'"),
                Scenario("场景C(小概率)", "小概率",
                         "继续下跌, 再破新低",
                         "全部清仓", "状态3'→1"),
            ]
        elif state == 2:
            scenarios = [
                Scenario("场景A(大概率)", "大概率",
                         "继续反弹, 逐步靠近前高",
                         "不动, 紧盯前高", "状态2→2"),
                Scenario("场景B(中概率)", "中概率",
                         "放量突破前高",
                         "1/6试探建仓", "状态2→3"),
                Scenario("场景C(小概率)", "小概率",
                         "反弹结束, 回落破前低",
                         "继续空仓, 放弃跟踪", "状态2→1"),
            ]
        elif state == 1:
            scenarios = [
                Scenario("场景A(大概率)", "大概率",
                         "继续沿MA20下方运行, 持续下跌",
                         "空仓, 不动", "状态1→1"),
                Scenario("场景B(小概率)", "小概率",
                         "出现连续上涨反弹信号",
                         "纳入观察, 盯前高", "状态1→2"),
            ]

        return scenarios
