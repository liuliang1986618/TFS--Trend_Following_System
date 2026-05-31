"""趋势阶段分类器 — 判断趋势处于前期/中期/后期。

设计文档§2.4：
  前期(状态3): 试探建仓, 胜率低但赔率高
  中期(状态4早期): 标准仓位, 主升浪持股
  后期(状态4晚期): 收紧止损, 等退场信号

为什么需要阶段分类？
→ 多赚钱+少亏钱：同样是状态4，"前期"应该加仓，"后期"应该警惕减仓。
  阶段分类告诉你同一状态下应该进攻还是防守。
"""
from dataclasses import dataclass
from typing import Optional
import pandas as pd
import numpy as np


@dataclass
class StageResult:
    stage: str  # "early", "mid", "late"
    label: str  # "前期", "中期", "后期"
    reasons: list  # 判定依据——Dashboard的"为什么"


class StageClassifier:
    """趋势阶段分类器。

    晚期信号（设计文档§2.4）：
      1. 斜率变陡：近5日涨幅远超20日均速 → 加速赶顶
      2. 放量滞涨：成交量放大但价格不涨 → 多空分歧加大
      3. 回调频繁：阴线增多 → 趋势松动
    出现2个以上 = 后期警告。
    """

    @staticmethod
    def classify(state: int, daily_df: pd.DataFrame, days_in_state: int = 1) -> StageResult:
        """根据当前状态和数据判断趋势阶段。

        → 多赚钱：中期=放心持股，前期=试探建仓，后期=警觉减仓。
        → 少亏钱：后期信号=提前预警，避免在高位加仓被套。
        """
        if state == 3:
            return StageResult(stage="early", label="前期",
                             reasons=["状态3翻转确认中，处于趋势初期——盈亏比最佳位置"])

        if state not in [4, 5]:
            return StageResult(stage="", label="", reasons=["非上涨趋势状态，不适用阶段分类"])

        if days_in_state < 10:
            return StageResult(stage="mid", label="中期",
                             reasons=["状态4确认不足10日，处于中期早期——放心持股"])

        late_signals = StageClassifier._check_late_signals(daily_df)

        if len(late_signals) >= 2:
            return StageResult(stage="late", label="后期", reasons=late_signals)

        return StageResult(stage="mid", label="中期",
                         reasons=["状态4持续运行中，无异常晚期信号——主升浪持股"])

    @staticmethod
    def _check_late_signals(daily_df: pd.DataFrame) -> list:
        """检测晚期信号。出现2个以上=后期警告。

        → 少亏钱：这三个信号是顶部区域的经典特征。早期识别=提前减仓=保住利润。
        """
        signals = []

        if len(daily_df) < 20:
            return signals

        closes = daily_df["close"]
        volumes = daily_df["volume"]

        # 信号1：斜率变陡——加速度赶顶
        ret_5d = (closes.iloc[-1] / closes.iloc[-6] - 1) if len(closes) >= 6 else 0
        ret_20d = (closes.iloc[-1] / closes.iloc[-21] - 1) if len(closes) >= 21 else 0
        avg_5d_rate = ret_5d / 5
        avg_20d_rate = ret_20d / 20
        if avg_20d_rate > 0 and avg_5d_rate > avg_20d_rate * 3 and avg_5d_rate > 0.005:
            signals.append(f"斜率加速: 近5日日均涨幅{avg_5d_rate*100:.1f}% vs 20日均速{avg_20d_rate*100:.1f}%")

        # 信号2：放量滞涨——多空分歧加大
        recent_5_vol = volumes.iloc[-5:].mean()
        ma20_vol = volumes.rolling(20).mean().iloc[-1]
        if not pd.isna(ma20_vol) and recent_5_vol > ma20_vol * 1.3 and ret_5d < 0.01:
            signals.append(f"放量滞涨: 量能{recent_5_vol/ma20_vol:.1f}x均量, 但5日涨幅仅{ret_5d*100:.1f}%")

        # 信号3：回调频繁——趋势松动
        recent_20 = daily_df.iloc[-20:]
        yin_count = int((recent_20["close"] < recent_20["open"]).sum())
        if yin_count >= 9:
            signals.append(f"回调频繁: 近20日{yin_count}日收阴——空头开始发力")

        return signals
