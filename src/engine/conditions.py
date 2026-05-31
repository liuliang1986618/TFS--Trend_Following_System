"""三条件判断器 — 趋势确认的核心判断逻辑。

设计文档§1.1 三个必要条件（缺一不可）：
  A. 结构：至少1对更高高+更高低（前期）/ 2对（中期确认）
  B. 量能：近20日上涨日平均成交量 > 下跌日平均成交量
  C. 持续性：近20日阳线>阴线，且出现过连续3根阳线

这三个条件从方向、力量、节奏三个独立维度验证趋势。

为什么三个条件缺一不可？
→ 少亏钱：任何一个缺失都意味着趋势不成立。
  - 只有结构无量能=无量空涨，随时崩塌
  - 只有量能无结构=短期脉冲，追高必套
  - 有量能有结构无持续性=可能是诱多陷阱
  三重验证确保每一笔资金都投入到真正可靠的趋势中。
"""
import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import Tuple

from .pivots import PivotDetector


@dataclass
class ConditionResult:
    """单个条件的判断结果。

    为什么用dataclass而不是dict？
    → 多赚钱：类型安全 = IDE自动补全 + 重构安全 = 减少拼写错误bug。
      Bug少=信号准确=赚钱概率高。
    """
    pass_: bool
    detail: str  # 人类可读的判断详情，用于Dashboard的"为什么"展示


class TrendConditions:
    """三条件判断器 — 提供结构A、量能B、持续性C的独立判断。

    每个条件返回ConditionResult，包含pass_和detail。
    detail用于Dashboard的"为什么"展示（设计文档§9.5）。
    """

    LOOKBACK = 20  # 量能和持续性的回看窗口
    MIN_CONSECUTIVE_YANG = 3  # 持续性中最小连阳天数

    @staticmethod
    def check_structure(daily_df: pd.DataFrame) -> ConditionResult:
        """条件A：结构判断 — 价格是否在建立更高的高点和低点。

        使用前高/前低检测结果：
          - 前期（状态3）：至少1对更高高+更高低
          - 中期确认（状态4）：至少2对更高高+更高低

        为什么关注更高低而不仅是更高高？
        → 少亏钱：更高高确认上涨意愿，更高低确认回调深度收窄。
          如果只涨不调(无更高低)=可能是庄股拉高出货，回调就会崩。
          如果回调破前低(无更高低)=上涨结构被破坏。
          两者同时满足才叫真正的上涨结构。
        """
        if daily_df is None or len(daily_df) < 20:
            return ConditionResult(False, "数据不足，至少需要20个交易日")

        highs = PivotDetector.get_last_n_highs(daily_df, n=2)
        lows = PivotDetector.get_last_n_lows(daily_df, n=2)

        higher_highs = 0
        higher_lows = 0

        if len(highs) >= 2:
            for i in range(1, len(highs)):
                if highs[i]["price"] > highs[i - 1]["price"]:
                    higher_highs += 1

        if len(lows) >= 2:
            for i in range(1, len(lows)):
                if lows[i]["price"] > lows[i - 1]["price"]:
                    higher_lows += 1

        pairs = min(higher_highs, higher_lows)

        if pairs >= 2:
            return ConditionResult(True,
                f"2更高高+2更高低 (前高: {highs[-1]['price']:.2f}, 前低: {lows[-1]['price']:.2f})")
        elif pairs >= 1:
            return ConditionResult(True,
                f"1更高高+1更高低 (初步结构, 前高={highs[-1]['price']:.2f})")
        else:
            if len(highs) >= 2 and highs[-1]["price"] < highs[-2]["price"]:
                return ConditionResult(False,
                    f"高点持续降低(下跌结构): {highs[-2]['price']:.2f}→{highs[-1]['price']:.2f}")
            return ConditionResult(False, "无明确的上涨结构(无足够更高高/更高低)")

    @staticmethod
    def check_volume(daily_df: pd.DataFrame) -> ConditionResult:
        """条件B：量能判断 — 上涨日的平均成交量是否大于下跌日。

        设计文档§1.1 B条件:
          近20日：上涨日平均成交量 > 下跌日平均成交量

        为什么上涨日必须放量？
        → 少亏钱：无量上涨=庄股拉高出货或散户跟风。这样的"趋势"一旦逆转
          往往连续跌停，根本跑不掉。真金白银推动的上涨才有持续性。
          量能确认=确认上涨是由大资金推动的=确认跟随的安全性。
        """
        if daily_df is None or len(daily_df) < TrendConditions.LOOKBACK:
            return ConditionResult(False, f"数据不足，至少需要{TrendConditions.LOOKBACK}个交易日")

        recent = daily_df.iloc[-TrendConditions.LOOKBACK:]
        up_days = recent[recent["close"] > recent["open"]]
        down_days = recent[recent["close"] < recent["open"]]

        if len(up_days) == 0:
            return ConditionResult(False, "近20日无阳线, 空头完全主导")

        if len(down_days) == 0:
            return ConditionResult(True, "近20日无阴线, 极强多头(涨均量远超跌均量)")

        up_avg_vol = float(up_days["volume"].mean())
        down_avg_vol = float(down_days["volume"].mean())

        if up_avg_vol > down_avg_vol:
            ratio = up_avg_vol / down_avg_vol
            return ConditionResult(True,
                f"上涨均量>下跌均量 {ratio:.1f}x (涨{up_avg_vol/1e8:.1f}亿 vs 跌{down_avg_vol/1e8:.1f}亿)")
        else:
            ratio = down_avg_vol / up_avg_vol if up_avg_vol > 0 else float("inf")
            return ConditionResult(False,
                f"上涨缩量, 下跌均量是上涨的{ratio:.1f}x")

    @staticmethod
    def check_persistence(daily_df: pd.DataFrame) -> ConditionResult:
        """条件C：持续性判断 — 多头是否持续占主导。

        设计文档§1.1 C条件:
          近20日：阳线 > 阴线，且出现过连续3根阳线

        为什么需要连续阳线而不只看总比例？
        → 多赚钱：连续阳线意味着多头有持续进攻能力，不是打一枪就跑。
          孤立的阳线在下跌市中也常见(单日反弹)，但连续阳线才代表
          真正的趋势力量。3连阳=多方已经连续3天压制空方=趋势形成。
        """
        if daily_df is None or len(daily_df) < TrendConditions.LOOKBACK:
            return ConditionResult(False, f"数据不足，至少需要{TrendConditions.LOOKBACK}个交易日")

        recent = daily_df.iloc[-TrendConditions.LOOKBACK:]

        yang_count = int((recent["close"] > recent["open"]).sum())
        yin_count = int((recent["close"] < recent["open"]).sum())

        # 检测最长连阳天数
        is_yang = recent["close"] > recent["open"]
        max_consecutive = 0
        current = 0
        for v in is_yang:
            if bool(v):
                current += 1
                max_consecutive = max(max_consecutive, current)
            else:
                current = 0

        has_consecutive = max_consecutive >= TrendConditions.MIN_CONSECUTIVE_YANG

        if yang_count > yin_count and has_consecutive:
            return ConditionResult(True,
                f"近20日阳{yang_count}/{yin_count}阴, 最大连阳{max_consecutive}天")
        elif yang_count > yin_count:
            return ConditionResult(False,
                f"阳多于阴(阳{yang_count}/阴{yin_count}), 但无连续{TrendConditions.MIN_CONSECUTIVE_YANG}阳, 持续性不足")
        else:
            return ConditionResult(False,
                f"阴盛阳衰(阳{yang_count}/阴{yin_count}), 空头主导")

    @classmethod
    def check_all(cls, daily_df: pd.DataFrame) -> dict:
        """一次执行全部三个条件检查。

        → 多赚钱：一次调用完成三维验证，减少重复的数据遍历。
          三个独立维度 = 三种不同的赚钱理由。全都通过 = 三重保险。

        Returns:
            {"structure": ConditionResult, "volume": ConditionResult, "persistence": ConditionResult}
        """
        return {
            "structure": cls.check_structure(daily_df),
            "volume": cls.check_volume(daily_df),
            "persistence": cls.check_persistence(daily_df),
        }
