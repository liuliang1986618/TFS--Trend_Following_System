"""板块β强度计算 — 板块相对大盘的弹性。

为什么需要β？
→ 多赚钱：β>1=弹性大于大盘，牛市=涨得比大盘多=超额收益。
→ 少亏钱：β<1=防御型板块，熊市=跌得比大盘少=控制回撤。
"""
import pandas as pd
import numpy as np


class BetaCalculator:
    """板块β强度计算器。"""

    @staticmethod
    def calculate(sector_daily: pd.DataFrame, benchmark_daily: pd.DataFrame,
                  lookback: int = 60) -> float:
        """计算板块相对基准(如上证指数)的β值。

        β = Cov(sector_returns, benchmark_returns) / Var(benchmark_returns)
        """
        if len(sector_daily) < lookback or len(benchmark_daily) < lookback:
            return 1.0

        sector_closes = sector_daily["close"].iloc[-lookback:]
        bench_closes = benchmark_daily["close"].iloc[-lookback:]

        # 对齐日期
        common_dates = sector_closes.index.intersection(bench_closes.index)
        if len(common_dates) < 20:
            return 1.0

        sector_ret = sector_closes.loc[common_dates].pct_change().dropna()
        bench_ret = bench_closes.loc[common_dates].pct_change().dropna()

        if len(sector_ret) < 20:
            return 1.0

        cov = np.cov(sector_ret, bench_ret)[0][1]
        var = np.var(bench_ret)

        return round(cov / var, 3) if var > 0 else 1.0

    @staticmethod
    def interpret(beta: float) -> str:
        """解读β值的交易含义。"""
        if beta > 1.5:
            return f"高弹性(β={beta}): 牛市领涨，熊市领跌——进攻型配置"
        elif beta > 1.0:
            return f"正常弹性(β={beta}): 跟随大盘——标准配置"
        elif beta > 0.5:
            return f"低弹性(β={beta}): 防御型——熊市抗跌"
        else:
            return f"极低弹性(β={beta}): 与大盘弱相关——独立行情"
