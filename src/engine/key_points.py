"""关键操作点识别器 — 识别6个需要决策的操作点。

设计文档§2.2 加粗行 = 6个关键操作点：
  2→3: 放量突破前高 → 买点1，1/6试探建仓
  3→1: 假突破 → 止损，全清
  3→4: 再创新高 → 买点2，加至标准仓
  5→4: 企稳反弹 → 最佳加仓，1.2~1.5倍
  5→3': 放量跌破前低 → 防守，减至1/3
  3'→1: 再破新低 → 全部清仓退场

为什么只有6个关键点？
→ 少亏钱：大多数交易日不需要操作。频繁操作=手续费+判断失误概率增加。
  只在状态转换的关键位置操作，降低交易频率，提高每笔交易的确定性。
"""
from dataclasses import dataclass
from typing import Optional, List

from .state_machine import StateValue


@dataclass
class KeyPoint:
    """关键操作点。"""
    transition: str  # 如 "2→3"
    action: str  # "买点1", "止损", "买点2", "最佳加仓", "防守", "退场"
    position_action: str  # 仓位动作
    priority: str  # "🔴" | "🟠" | "🟢" | "🟡"
    description: str  # 详细说明


class KeyPointDetector:
    """关键操作点识别器。

    对比前一状态和当前状态，识别是否触发了6个关键操作点。
    """

    KEY_TRANSITIONS = {
        "2→3": KeyPoint("2→3", "买点1", "1/6试探建仓", "🟡",
                        "放量突破前高, 试探仓进场——盈亏比最佳的位置"),
        "3→1": KeyPoint("3→1", "止损", "全部清仓", "🔴",
                        "假突破确认, 跌破新低止损——保住本金是第一要务"),
        "3→4": KeyPoint("3→4", "买点2", "加至标准仓(100%)", "🟢",
                        "再创新高结构完整, 标准仓位——主升浪启动"),
        "5→4": KeyPoint("5→4", "最佳加仓", "加至1.2~1.5倍", "🟢",
                        "回调企稳反弹, 最佳加仓时机——千金难买牛回头"),
        "5→3'": KeyPoint("5→3'", "防守", "减至1/3仓", "🟠",
                        "放量跌破前低, 上涨结构被破坏——先防守再观察"),
        "3'→1": KeyPoint("3'→1", "退场", "全部清仓", "🔴",
                        "再破新低结构破坏, 趋势结束——不清仓就是放任亏损"),
    }

    @classmethod
    def detect(cls, prev_state: StateValue, current_state: StateValue) -> Optional[KeyPoint]:
        """检测状态转换是否触发了关键操作点。

        → 多赚钱：及时识别关键点=在最佳时机执行操作。
        → 少亏钱：止损信号不能错过=保命的关键。
        """
        if prev_state == current_state:
            return None
        transition_key = f"{prev_state}→{current_state}"
        return cls.KEY_TRANSITIONS.get(transition_key)

    @classmethod
    def detect_all(cls, prev_results: dict, current_results: dict) -> List[tuple]:
        """批量检测所有标的的关键操作点。

        → 多赚钱：一次扫描所有持仓，不漏掉任何操作信号。
        """
        points = []
        for sym, cur in current_results.items():
            if sym in prev_results:
                prev_state = prev_results[sym].state
                kp = cls.detect(prev_state, cur.state)
                if kp:
                    points.append((sym, kp))
        return points
