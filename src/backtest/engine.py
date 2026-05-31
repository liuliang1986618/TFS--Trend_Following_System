"""回测引擎 — 基于状态机的历史回测。

为什么需要回测？
→ 多赚钱：验证策略在历史上的表现，找到最优参数组合。
→ 少亏钱：回测发现策略弱点（如震荡市频繁止损），提前规避。

核心设计：
  每日用 classify() 获取独立信号 → 喂给 transition() 做时序跟踪 →
  检测状态转换 → 触发关键操作点 → 执行交易。
  为什么不用 classify() 直接比较每日状态？
  → 少亏钱：classify() 是独立分类器，可能从状态1跳到状态4，
    跳过中间的关键操作点（如买点1/买点2）。transition() 保证状态演变
    按设计文档§2.2的转换表逐步推进，不会漏掉关键操作点。
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from src.engine.state_machine import StateMachine, TrendState, StateValue
from src.engine.key_points import KeyPointDetector


class BacktestEngine:
    """回测引擎 — 模拟状态机驱动的交易策略。"""

    def __init__(self, initial_capital: float = 100000.0):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.shares = 0.0
        self.trades = []
        self.equity_curve = []

    def run(self, daily_df: pd.DataFrame, min_window: int = 60) -> dict:
        """在历史数据上运行回测。

        从第60天开始，每天运行状态机:
          1. classify() 获取当日信号（独立快照判定）
          2. 构建事件字典（从前一个TrendState提取信号）
          3. transition() 获取时序状态（保证逐步演变）
          4. 检测状态转换 → 触发关键操作点 → 执行交易
        """
        self._reset()

        if len(daily_df) < min_window:
            return {"error": f"数据不足({len(daily_df)}行)，需要至少{min_window}个交易日"}

        dates = daily_df.index[min_window:]
        prev_state = None  # 时序跟踪的状态值

        for i, date in enumerate(dates):
            idx = daily_df.index.get_loc(date)
            start_idx = max(0, idx - 120)
            window = daily_df.iloc[start_idx:idx + 1]
            price = window["close"].iloc[-1]

            try:
                ts = StateMachine.classify(window)
            except Exception:
                prev_state = None
                self._record_equity(date, price, "?")
                continue

            # 构建事件字典（从TrendState提取信号）
            event = self._build_event(ts)

            if prev_state is None:
                # 首次：直接用 classify 结果作为初始状态
                current_state = ts.state
            else:
                # 后续：用 transition() 保证逐步演变
                current_state = StateMachine.transition(prev_state, event)

            # 检测状态转换 → 触发关键操作点
            if prev_state is not None and current_state != prev_state:
                kp = KeyPointDetector.detect(prev_state, current_state)
                if kp:
                    self._execute_trade(kp, price, date, current_state)

            prev_state = current_state
            self._record_equity(date, price, str(current_state))

        return self._calculate_metrics()

    @staticmethod
    def _build_event(ts: TrendState) -> dict:
        """从TrendState提取事件字典，供 transition() 使用。"""
        return {
            "consecutive_rise": ts.consecutive_rise,
            "consecutive_drop": ts.consecutive_drop,
            "broke_prev_high": ts.broke_prev_high,
            "broke_prev_low": ts.broke_prev_low,
            "volume_surge": ts.volume_surge,
            "volume_shrink": ts.volume_shrink,
        }

    def _execute_trade(self, kp, price, date, current_state):
        """执行交易 — 在关键操作点按当日收盘价调整仓位。

        P&L = (卖出价 - 买入价) * 股数。每次买卖都实际计算盈亏。
        """
        target_ratio = StateMachine.position_suggestion(current_state)
        total_equity = self.cash + self.shares * price
        action_type = kp.action

        if action_type in ("止损", "退场"):
            if self.shares > 0:
                self.cash += self.shares * price
                self.shares = 0.0

        elif action_type in ("买点1", "买点2", "最佳加仓"):
            target_shares = (total_equity * target_ratio) / price
            share_delta = target_shares - self.shares
            if share_delta > 0 and self.cash >= share_delta * price:
                self.cash -= share_delta * price
                self.shares += share_delta
            elif share_delta < 0:
                self.cash += abs(share_delta) * price
                self.shares -= abs(share_delta)

        elif action_type == "防守":
            target_shares = (total_equity * target_ratio) / price
            if self.shares > target_shares:
                excess = self.shares - target_shares
                self.cash += excess * price
                self.shares -= excess

        self.trades.append({
            "date": date,
            "action": kp.action,
            "transition": kp.transition,
            "price": round(float(price), 4),
            "shares": round(self.shares, 2),
            "cash": round(self.cash, 2),
            "equity": round(self.cash + self.shares * price, 2),
        })

    def _record_equity(self, date, price, state_label):
        """记录每日权益（按收盘价盯市）。"""
        pv = self.shares * price
        self.equity_curve.append({
            "date": date, "state": state_label, "price": price,
            "cash": self.cash, "position_value": pv,
            "equity": self.cash + pv,
        })

    def _calculate_metrics(self) -> dict:
        """计算回测指标。"""
        if not self.equity_curve:
            return {"error": "无回测数据"}

        equity = pd.DataFrame(self.equity_curve)
        equity["returns"] = equity["equity"].pct_change()

        total_return = equity["equity"].iloc[-1] / self.initial_capital - 1

        years = max(len(equity) / 252, 0.01)
        if total_return > -1:
            annual_return = (1 + total_return) ** (1 / years) - 1
        else:
            annual_return = -1.0

        cummax = equity["equity"].cummax()
        drawdown = (equity["equity"] - cummax) / cummax
        max_drawdown = drawdown.min()
        max_dd_date = equity.loc[drawdown.idxmin(), "date"] if drawdown.min() < 0 else None

        trade_rounds = self._extract_trade_rounds()
        win_count = sum(1 for e, x in trade_rounds if x["equity"] > e["equity"])
        win_rate = (win_count / max(len(trade_rounds), 1)) * 100 if trade_rounds else 0

        risk_free = 0.03
        rets = equity["returns"].dropna()
        if rets.std() > 0 and len(rets) > 1:
            sharpe = float((rets.mean() - risk_free / 252) / rets.std() * np.sqrt(252))
        else:
            sharpe = 0.0

        return {
            "total_return": round(total_return * 100, 2),
            "annual_return": round(annual_return * 100, 2),
            "max_drawdown": round(max_drawdown * 100, 2),
            "max_drawdown_date": str(max_dd_date) if max_dd_date else None,
            "sharpe_ratio": round(sharpe, 2),
            "num_trades": len(self.trades),
            "num_rounds": len(trade_rounds),
            "win_rate": round(win_rate, 1),
            "final_equity": round(
                self.cash + self.shares * float(self.equity_curve[-1]["price"])
                if self.equity_curve else 0, 2),
            "trade_log": self.trades,
        }

    def _extract_trade_rounds(self) -> list:
        """提取完整的交易轮次（买入→卖出配对）。"""
        rounds = []
        entry = None
        for t in self.trades:
            if t["action"] in ("买点1", "买点2", "最佳加仓"):
                if entry is None:
                    entry = t
            elif t["action"] in ("止损", "退场", "防守"):
                if entry is not None:
                    rounds.append((entry, t))
                    entry = None
        if entry is not None and self.equity_curve:
            last = self.equity_curve[-1]
            rounds.append((entry, {"equity": last["equity"], "date": last["date"],
                                    "action": "持仓中"}))
        return rounds

    def _reset(self):
        self.cash = self.initial_capital
        self.shares = 0.0
        self.trades = []
        self.equity_curve = []
