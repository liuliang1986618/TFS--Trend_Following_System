"""龙头识别 — 题材内按涨幅+成交额排名。

设计文档§9.5 龙头判定:
  题材内涨幅排名 + 成交额排名 → 综合得分最高 = 龙头

为什么需要龙头识别？
→ 多赚钱：题材内龙头股弹性远大于板块ETF和跟风股。
  涨幅第一=市场公认的领头羊，成交额大=大资金在参与。
  龙头=超额收益的最佳载体。
"""
from typing import Dict, List, Tuple
import pandas as pd


class LeaderIdentifier:
    """龙头识别器。"""

    @staticmethod
    def identify(theme_code: str, stock_states: Dict[str, object],
                 stock_daily: Dict[str, pd.DataFrame],
                 lookback: int = 20) -> List[Tuple[str, float]]:
        """识别题材内的龙头股。

        Args:
            theme_code: 题材代码(GN)
            stock_states: {symbol: TrendState} 题材成分股的趋势状态
            stock_daily: {symbol: DataFrame} 成分股的日K数据
            lookback: 涨幅计算窗口(交易日)

        Returns:
            [(symbol, leader_score), ...] 按龙头得分降序排列

        龙头得分 = 涨幅排名分(50%) + 成交额排名分(30%) + 趋势状态分(20%)
        """
        if not stock_states:
            return []

        scores = []
        symbols = list(stock_states.keys())

        # 计算每个成分股的近N日涨幅
        returns = {}
        volumes = {}
        for sym in symbols:
            if sym in stock_daily and len(stock_daily[sym]) >= lookback:
                df = stock_daily[sym]
                ret = (df["close"].iloc[-1] / df["close"].iloc[-lookback] - 1)
                avg_vol = df["volume"].iloc[-lookback:].mean()
                returns[sym] = ret
                volumes[sym] = avg_vol
            else:
                returns[sym] = 0.0
                volumes[sym] = 0.0

        n = len(symbols)
        if n == 0:
            return []

        # 涨幅排名（降序=涨幅大排前面）
        ret_ranked = sorted(returns.items(), key=lambda x: x[1], reverse=True)
        ret_rank = {sym: i + 1 for i, (sym, _) in enumerate(ret_ranked)}

        # 成交额排名（降序=成交额大排前面）
        vol_ranked = sorted(volumes.items(), key=lambda x: x[1], reverse=True)
        vol_rank = {sym: i + 1 for i, (sym, _) in enumerate(vol_ranked)}

        # 趋势状态分
        state_scores = {4: 100, 5: 70, 3: 50}

        for sym in symbols:
            ret_score = 1.0 - (ret_rank[sym] - 1) / n  # 排名越前分越高
            vol_score = 1.0 - (vol_rank[sym] - 1) / n
            state_score = state_scores.get(stock_states[sym].state, 0) / 100.0

            leader_score = ret_score * 0.5 + vol_score * 0.3 + state_score * 0.2
            scores.append((sym, round(leader_score, 4)))

        return sorted(scores, key=lambda x: x[1], reverse=True)
