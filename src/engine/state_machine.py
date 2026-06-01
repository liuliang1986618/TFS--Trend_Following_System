"""6状态状态机 — 趋势状态判定和状态转换。

设计文档§2.1 状态定义：
  状态1: 下跌趋势   → 仓位0，空仓。"熊市不亏就是赚"
  状态2: 下跌反弹   → 仓位0，盯前高。"等待确认信号"
  状态3: 翻转确认中 → 仓位1/6~1/3，试探。"盈亏比最佳的位置"
  状态4: 上涨趋势   → 仓位100%，持股。"主升浪赚钱"
  状态5: 上涨回调   → 仓位100%，等加仓。"正常回调，珍惜筹码"
  状态3': 转跌确认中 → 仓位1/3，防守。"保住利润，等待方向"

设计文档§2.2 状态转换表（6个关键操作点）：
  2→3 放量突破前高 → 买点1
  3→1 假突破止损
  3→4 再创新高 → 买点2
  5→4 企稳反弹 → 最佳加仓
  5→3' 放量跌破前低 → 防守
  3'→1 再破新低 → 退场

为什么用状态机而不是连续评分？
→ 多赚钱+少亏钱：每个状态直接映射到仓位动作，消除决策模糊性。
  评分高≠能买（可能即将见顶），状态3评分低但值得试探（盈亏比最佳）。
  "模糊的正确胜过精确的错误"——状态机是模糊的正确。
"""
from dataclasses import dataclass, field
from typing import Optional, Dict, Union
import pandas as pd

from .conditions import TrendConditions
from .ma_filter import MAFilter
from .pivots import PivotDetector


StateValue = Union[int, str]


@dataclass
class TrendState:
    """趋势状态判定结果——包含全部决策所需信息。"""
    state: StateValue
    state_label: str
    position_ratio: float
    conditions: Dict[str, object]
    prev_high: Optional[Dict] = None
    prev_low: Optional[Dict] = None
    consecutive_drop: bool = False
    consecutive_rise: bool = False
    volume_surge: bool = False
    volume_shrink: bool = False
    above_ma20: bool = False
    broke_prev_high: bool = False  # 是否突破前高
    broke_prev_low: bool = False   # 是否跌破前低


class StateMachine:
    """6状态趋势判定状态机。

    核心流程:
      1. 计算三条件结果
      2. 检测关键信号（连续涨跌、放量缩量、突破/跌破）
      3. 根据当前状态和事件 → 确定下一状态
    """

    ALL_STATES = {1, 2, 3, 4, 5, "3'"}
    STATE_LABELS = {
        1: "下跌趋势", 2: "下跌中的反弹", 3: "翻转确认中",
        4: "上涨趋势", 5: "上涨中的回调", "3'": "转跌确认中",
    }
    POSITIONS = {
        1: 0.0, 2: 0.0, 3: 0.166, 4: 1.0, 5: 1.0, "3'": 0.333,
    }

    @classmethod
    def classify(cls, daily_df: pd.DataFrame) -> TrendState:
        """对日K数据运行状态机，独立判定当前状态。

        为什么可以独立判断（不依赖前一日状态）？
        → 多赚钱：首次运行时没有前一状态。独立分类从数据结构推断最可能的状态，
          够准确。后续每日运行时会对比前一日状态做精确的状态转换。
        """
        conds = TrendConditions.check_all(daily_df)

        recent = daily_df.iloc[-5:]
        closes = daily_df["close"]
        volumes = daily_df["volume"]

        # 关键信号检测
        consecutive_drop = cls._detect_consecutive_drop(daily_df)
        consecutive_rise = cls._detect_consecutive_rise(daily_df)

        # 放量/缩量
        ma20_vol = volumes.rolling(20).mean().iloc[-1]
        today_vol = volumes.iloc[-1]
        volume_surge = bool(today_vol > ma20_vol * 1.2) if not pd.isna(ma20_vol) else False
        volume_shrink = bool(today_vol < ma20_vol * 0.8) if not pd.isna(ma20_vol) else False

        above_ma20 = MAFilter.check(daily_df)

        prev_high = PivotDetector.recent_high(daily_df)
        prev_low = PivotDetector.recent_low(daily_df)

        struct_ok = conds["structure"].pass_
        volume_ok = conds["volume"].pass_
        persist_ok = conds["persistence"].pass_

        # 突破/跌破检测
        broke_prev_high = False
        if prev_high and len(daily_df) >= 2:
            broke_prev_high = closes.iloc[-1] > prev_high["price"]

        broke_prev_low = False
        if prev_low and len(daily_df) >= 2:
            broke_prev_low = closes.iloc[-1] < prev_low["price"]

        # 独立状态判定
        # 设计文档§2.1: 三条件缺一不可，但结构+持续性双满足=趋势已形成的强信号
        if struct_ok and volume_ok and persist_ok:
            if consecutive_drop and not broke_prev_low and volume_shrink:
                state = 5  # 上涨中的正常回调
            else:
                state = 4  # 健康上涨
        elif struct_ok and persist_ok and not volume_ok:
            # 结构+持续性双满足，仅量能不足 → 大概率是上涨趋势中的短暂缩量
            # 半导体案例: +17.5%, 14/6阳/阴, 连阳8天，仅因2天极端放量暴跌拉低量比
            # → 少亏钱: 不应判为状态2(观望)而错失趋势，应判为状态3(试探)或状态4(确认)
            if above_ma20:
                state = 4 if broke_prev_high else 3  # 站上均线=至少翻转确认
            else:
                state = 3  # 即使均线下方，结构+持续性也值得试探
        elif struct_ok and not volume_ok and not persist_ok:
            if broke_prev_high:
                state = 3  # 突破前高但尚未完全确认
            else:
                state = 2  # 反弹未突破
        elif struct_ok and volume_ok and not persist_ok:
            # 结构+量能OK，持续性不足 → 可能是趋势启动初期
            if broke_prev_high and above_ma20:
                state = 3
            else:
                state = 2
        elif struct_ok:
            if broke_prev_high and above_ma20:
                state = 3
            else:
                state = 2
        elif not struct_ok and above_ma20 and consecutive_rise:
            state = 2
        elif consecutive_drop and broke_prev_low and volume_surge:
            state = "3'"  # 放量跌破，转跌警告
        elif consecutive_rise and not broke_prev_high:
            state = 2
        else:
            state = 1  # 默认空头

        return TrendState(
            state=state,
            state_label=cls.STATE_LABELS.get(state, "未知"),
            position_ratio=cls.position_suggestion(state),
            conditions=conds,
            prev_high=prev_high,
            prev_low=prev_low,
            consecutive_drop=consecutive_drop,
            consecutive_rise=consecutive_rise,
            volume_surge=volume_surge,
            volume_shrink=volume_shrink,
            above_ma20=above_ma20,
            broke_prev_high=broke_prev_high,
            broke_prev_low=broke_prev_low,
        )

    @classmethod
    def transition(cls, prev_state: StateValue, event: dict) -> StateValue:
        """基于前一日状态和当日事件，判定状态转换。

        设计文档§2.2 完整状态转换表。

        为什么在classify之外还需要transition？
        → 少亏钱：classify是快照判断(只看当前数据)，transition是时序判断(对比前后)。
          例如状态3持续回调不破前低→仍是状态3但应该加仓。
          仅靠classify会漏掉状态内部的仓位变化。
        """
        if prev_state == 1:
            if event.get("consecutive_rise") and not event.get("broke_prev_high"):
                if event.get("volume_shrink", True):
                    return 2  # 1→2: 反弹，盯前高
            return 1

        elif prev_state == 2:
            if event.get("broke_prev_low"):
                return 1  # 2→1: 反弹失败
            if event.get("broke_prev_high") and event.get("volume_surge"):
                return 3  # 2→3: 买点1！
            return 2

        elif prev_state == 3:
            if event.get("broke_prev_low") and event.get("volume_surge"):
                return 1  # 3→1: 假突破止损！
            if event.get("broke_prev_high") and event.get("volume_surge"):
                return 4  # 3→4: 买点2！
            return 3

        elif prev_state == 4:
            if event.get("consecutive_drop"):
                if event.get("broke_prev_low") and event.get("volume_surge"):
                    return "3'"  # 4→5→3': 防守！
                if not event.get("broke_prev_low"):
                    return 5  # 4→5: 正常回调
            return 4

        elif prev_state == 5:
            if event.get("broke_prev_low") and event.get("volume_surge"):
                return "3'"  # 5→3': 防守！
            if event.get("consecutive_rise") and not event.get("broke_prev_low"):
                return 4  # 5→4: 最佳加仓！
            return 5

        elif prev_state == "3'":
            if event.get("broke_new_low"):
                return 1  # 3'→1: 退场！
            if event.get("consecutive_rise") and event.get("volume_surge"):
                return 4  # 3'→4: 假跌破修复
            return "3'"

        return prev_state

    @classmethod
    def position_suggestion(cls, state: StateValue) -> float:
        """返回指定状态的建议仓位比例。

        → 多赚钱+少亏钱：仓位直接由状态决定，消除情绪干扰。
          状态1空仓=熊市不亏就是赚。状态4满仓=充分享受主升浪。
        """
        return cls.POSITIONS.get(state, 0.0)

    @staticmethod
    def _detect_consecutive_drop(daily_df: pd.DataFrame, min_days: int = 2, min_pct: float = -0.015) -> bool:
        """检测连续下跌（设计文档§2.3）：至少2日连阴，累计跌幅>1.5%。

        → 少亏钱：及时检测到连续下跌=尽早发现回调或趋势转弱。
        """
        if len(daily_df) < min_days:
            return False
        recent = daily_df.iloc[-min_days:]
        all_yin = all(bool(recent["close"].values[i] < recent["open"].values[i]) for i in range(len(recent)))
        if not all_yin:
            return False
        cum_ret = (recent["close"].iloc[-1] / recent["close"].iloc[0] - 1)
        return cum_ret < min_pct

    @staticmethod
    def _detect_consecutive_rise(daily_df: pd.DataFrame, min_days: int = 2, min_pct: float = 0.02) -> bool:
        """检测连续上涨（设计文档§2.3）：至少2日连阳，累计涨幅>2%。

        → 多赚钱：尽早发现连续上涨=尽早发现翻转信号=抢先入场。
        """
        if len(daily_df) < min_days:
            return False
        recent = daily_df.iloc[-min_days:]
        all_yang = all(bool(recent["close"].values[i] > recent["open"].values[i]) for i in range(len(recent)))
        if not all_yang:
            return False
        cum_ret = (recent["close"].iloc[-1] / recent["close"].iloc[0] - 1)
        return cum_ret > min_pct
