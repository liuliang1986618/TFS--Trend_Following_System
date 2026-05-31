"""置信度计算 — 双路交叉验证。

设计文档§3.2:
  漏斗命中 + ETF命中 = 最高置信度(0.85-1.0), 标准仓位
  仅漏斗命中 = 标准置信度(0.60-0.85), 标准仓位
  仅ETF直筛命中 = 中置信度(0.40-0.60), 试探仓位

为什么需要置信度？
→ 少亏钱：低置信度信号应减小仓位。双路确认比单路更可靠。
  仓位=置信度×标准仓位，量化控制风险。
"""
from typing import Set


class ConfidenceCalculator:
    """置信度计算器。"""

    @staticmethod
    def calculate_stock(symbol: str, funnel_symbols: Set[str],
                        etf_symbols: Set[str]) -> float:
        """计算个股的置信度。ETF直筛不直接产生个股信号，但可以提升板块置信度。"""
        if symbol in funnel_symbols:
            return 0.80  # 漏斗路径
        return 0.50  # 默认

    @staticmethod
    def calculate_etf(symbol: str, funnel_etfs: Set[str],
                      direct_etfs: Set[str]) -> dict:
        """计算ETF的置信度和来源路径。

        Returns: {"confidence": float, "source": str, "position_multiplier": float}
        """
        in_funnel = symbol in funnel_etfs
        in_direct = symbol in direct_etfs

        if in_funnel and in_direct:
            return {"confidence": 0.92, "source": "双路确认(漏斗+直筛)", "position_multiplier": 1.0}
        elif in_funnel:
            return {"confidence": 0.75, "source": "漏斗路径", "position_multiplier": 1.0}
        elif in_direct:
            return {"confidence": 0.55, "source": "ETF直筛路径", "position_multiplier": 0.5}
        else:
            return {"confidence": 0.0, "source": "无信号", "position_multiplier": 0.0}

    @staticmethod
    def calculate_sector(sector_code: str, stocks_in_trend: int,
                         total_stocks: int) -> float:
        """板块置信度 = 趋势成分股占比 + 板块自身状态分。

        → 少亏钱：成分股趋势占比低的板块=板块指数涨但个股不跟=虚假繁荣。
        """
        if total_stocks == 0:
            return 0.0
        ratio = stocks_in_trend / total_stocks
        return min(0.95, ratio * 0.7 + 0.25)
