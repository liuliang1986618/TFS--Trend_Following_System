"""真实持仓管理器 — 100万初始资金, 7 ETF + 3 个股, 跨日追踪。

用法:
    pm = PortfolioManager()
    portfolio = pm.load('2026-06-15')  # 加载当日持仓(从前一日继承)
    orders = pm.decide(recommendations, portfolio)  # 生成交易指令
    portfolio = pm.execute(orders, prices)  # 执行指令
    pm.save(portfolio, '2026-06-15')  # 持久化
"""
import json, os
from typing import Optional
from dataclasses import dataclass, field, asdict


# ═══════════════════════════════════════════════════════════════════
# 数据模型
# ═══════════════════════════════════════════════════════════════════

@dataclass
class Holding:
    code: str
    name: str
    type: str           # "etf" | "stock"
    shares: int         # 持有份额(股)
    avg_cost: float     # 平均成本价
    current_price: float  # 当前市价
    entry_date: str     # 建仓日期
    current_state: object  # 当前趋势状态
    prev_state: object    # 前一日状态

    @property
    def market_value(self) -> float:
        return self.shares * self.current_price

    @property
    def cost_basis(self) -> float:
        return self.shares * self.avg_cost

    @property
    def pnl(self) -> float:
        return self.market_value - self.cost_basis

    @property
    def pnl_pct(self) -> float:
        return (self.pnl / self.cost_basis * 100) if self.cost_basis > 0 else 0.0

    def to_dict(self) -> dict:
        return {
            "code": self.code, "name": self.name, "type": self.type,
            "shares": self.shares, "avg_cost": round(self.avg_cost, 4),
            "current_price": round(self.current_price, 4),
            "market_value": round(self.market_value, 2),
            "cost_basis": round(self.cost_basis, 2),
            "pnl": round(self.pnl, 2), "pnl_pct": round(self.pnl_pct, 2),
            "entry_date": self.entry_date,
            "days_held": 0,  # computed by manager
            "current_state": self.current_state,
            "prev_state": self.prev_state,
        }


@dataclass
class Order:
    code: str
    name: str
    type: str           # "etf" | "stock"
    action: str         # "建仓" | "加仓" | "减仓" | "清仓" | "持有"
    amount: float       # 金额 (元)
    target_pct: float   # 目标仓位百分比
    reason: str

    def to_dict(self) -> dict:
        return asdict(self)


# ═══════════════════════════════════════════════════════════════════
# 仓位管理器
# ═══════════════════════════════════════════════════════════════════

class PortfolioManager:
    """真实交易持仓管理器。

    约束:
      - 初始资金: 100万
      - ETF 上限: 7只, 单只上限20万, 总上限70万
      - 个股上限: 3只, 单只上限10万, 总上限25万
      - 总仓位上限: 80万 (80%), 留20万现金
      - 止损: -8% 或 state=1
    """

    INITIAL_CAPITAL = 1_000_000
    MAX_ETF = 7
    MAX_STOCK = 3
    MAX_SINGLE_ETF = 200_000    # 单只ETF上限
    MAX_SINGLE_STOCK = 100_000  # 单只个股上限
    MAX_TOTAL_ETF = 700_000     # ETF总上限
    MAX_TOTAL_STOCK = 250_000   # 个股总上限
    MAX_TOTAL = 800_000         # 总仓位上限
    STOP_LOSS_PCT = -8          # 止损线

    # 分状态目标仓位 (%)
    TARGET_PCT = {
        # (type, state): pct
        ("etf", 3): 8,      ("stock", 3): 3,
        ("etf", 4): 15,     ("stock", 4): 8,
        ("etf", 5): 20,     ("stock", 5): 10,
        ("etf", "3'"): 5,   ("stock", "3'"): 3,
    }

    def __init__(self, output_dir: str = "dashboard/data"):
        self.output_dir = output_dir
        self._today_date: str = ""

    # ── 加载/保存 ─────────────────────────────────────────────

    def load(self, date_str: str) -> dict:
        """加载当日持仓。从最近的前一日期继承，首次为空仓。"""
        self._today_date = date_str
        # 找最近的前一日期文件
        prev = self._find_prev(date_str)
        if prev:
            path = os.path.join(self.output_dir, f"portfolio_{prev}.json")
            if os.path.exists(path):
                with open(path) as f:
                    return json.load(f)

        # 冷启动: 空仓
        return {
            "date": date_str,
            "initial_capital": self.INITIAL_CAPITAL,
            "cash": self.INITIAL_CAPITAL,
            "total_value": self.INITIAL_CAPITAL,
            "total_return_pct": 0.0,
            "holdings": [],
            "orders": [],
        }

    def save(self, portfolio: dict, date_str: str = None):
        """持久化持仓到 portfolio_{date}.json"""
        d = date_str or self._today_date
        path = os.path.join(self.output_dir, f"portfolio_{d}.json")
        portfolio["date"] = d
        with open(path, "w") as f:
            json.dump(portfolio, f, ensure_ascii=False, indent=2)

    def _find_prev(self, date_str: str) -> Optional[str]:
        """找到最近的前一交易日持仓文件."""
        from datetime import datetime, timedelta
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        for i in range(1, 10):  # 最多回退10天
            prev_dt = dt - timedelta(days=i)
            if prev_dt.weekday() >= 5:
                continue  # 跳过周末
            prev = prev_dt.strftime("%Y-%m-%d")
            path = os.path.join(self.output_dir, f"portfolio_{prev}.json")
            if os.path.exists(path):
                return prev
        return None

    # ── 决策引擎 ─────────────────────────────────────────────

    def decide(self, recommendations: list[dict],
               portfolio: dict) -> list[Order]:
        """根据今日推荐 + 当前持仓 → 生成交易指令。

        recommendations: enhanced_actions 的 etf_cards + stock_cards
        """
        orders = []
        holdings = {h["code"]: h for h in portfolio.get("holdings", [])}
        cash = portfolio["cash"]
        total_value = portfolio["total_value"]

        # 统计当前持仓数
        etf_count = sum(1 for h in holdings.values() if h["type"] == "etf")
        stock_count = sum(1 for h in holdings.values() if h["type"] == "stock")

        for rec in recommendations:
            code = rec["code"]
            name = rec["name"]
            rtype = "etf" if rec.get("is_etf", code.startswith("51") or code.startswith("159")) else "stock"
            state = rec.get("state", 1)
            score = rec.get("score", 0)
            price = rec.get("price", rec.get("trend_context", {}).get("price", 0))

            if code in holdings:
                # ── 已在持仓中 ──
                h = holdings[code]
                prev_state = h.get("current_state", state)
                pnl_pct = h.get("pnl_pct", 0)

                # 止损检查
                if pnl_pct <= self.STOP_LOSS_PCT:
                    orders.append(Order(code, name, rtype, "清仓",
                                        h["market_value"], 0,
                                        f"止损: 亏损{pnl_pct:.1f}%达到-8%线"))
                    continue

                # State 变化驱动的操作
                if state == 1 or state == 2:
                    orders.append(Order(code, name, rtype, "清仓",
                                        h["market_value"], 0,
                                        f"趋势转弱: state={state}"))
                elif state == 5 and prev_state == 4:
                    # 4→5: 回调 → 加仓机会
                    target_pct = self.TARGET_PCT.get((rtype, 5), 10)
                    target_amount = total_value * target_pct / 100
                    current_amount = h["market_value"]
                    add_amount = min(target_amount - current_amount,
                                     self.MAX_SINGLE_ETF if rtype == "etf" else self.MAX_SINGLE_STOCK,
                                     cash)
                    if add_amount > 5000:  # 最少加5000元
                        orders.append(Order(code, name, rtype, "加仓",
                                            add_amount, target_pct,
                                            "上升趋势正常回调,缩量企稳=加仓机会"))
                elif state == 4 and prev_state == 5:
                    orders.append(Order(code, name, rtype, "持有",
                                        h["market_value"],
                                        self.TARGET_PCT.get((rtype, 4), 15),
                                        "回调结束企稳,继续持有"))
                elif state == "3'":
                    # 减仓防守
                    target_pct = self.TARGET_PCT.get((rtype, "3'"), 5)
                    target_amount = total_value * target_pct / 100
                    reduce = h["market_value"] - target_amount
                    if reduce > 0:
                        orders.append(Order(code, name, rtype, "减仓",
                                            reduce, target_pct,
                                            "转跌确认,减仓防守保利润"))
                else:
                    target_pct = self.TARGET_PCT.get((rtype, state), 10)
                    orders.append(Order(code, name, rtype, "持有",
                                        h["market_value"], target_pct,
                                        f"继续持有 (state={state})"))

            else:
                # ── 不在持仓中 ──
                if state in (1, 2, "3'"):
                    continue  # 不推荐开仓

                # 检查 slots
                if rtype == "etf" and etf_count >= self.MAX_ETF:
                    continue
                if rtype == "stock" and stock_count >= self.MAX_STOCK:
                    continue

                # 开新仓
                target_pct = self.TARGET_PCT.get((rtype, state), 8 if rtype == "etf" else 3)
                target_amount = total_value * target_pct / 100
                single_max = self.MAX_SINGLE_ETF if rtype == "etf" else self.MAX_SINGLE_STOCK
                entry_amount = min(target_amount, single_max, cash * 0.5)

                if entry_amount >= 30000 if rtype == "etf" else entry_amount >= 10000:
                    orders.append(Order(code, name, rtype, "建仓",
                                        entry_amount, target_pct,
                                        f"趋势确认(state={state}, score={score}),试探建仓"))
                    if rtype == "etf":
                        etf_count += 1
                    else:
                        stock_count += 1

        return orders

    def execute(self, orders: list[Order], portfolio: dict,
                prices: dict = None) -> dict:
        """执行交易指令,更新持仓."""
        holdings = {h["code"]: h for h in portfolio.get("holdings", [])}
        cash = portfolio["cash"]
        total_value = portfolio["total_value"]

        for order in orders:
            price = (prices or {}).get(order.code, 0)
            if price == 0:
                # 从持仓信息取价格
                h = holdings.get(order.code)
                if h:
                    price = h.get("current_price", 0)

            if order.action == "清仓":
                h = holdings.pop(order.code, None)
                if h:
                    cash += h["market_value"]
            elif order.action == "建仓":
                if price > 0 and cash >= order.amount:
                    shares = int(order.amount / price / 100) * 100  # A股100股整数倍
                    if shares >= 100:
                        cost = shares * price
                        cash -= cost
                        holdings[order.code] = {
                            "code": order.code, "name": order.name,
                            "type": order.type,
                            "shares": shares,
                            "avg_cost": price,
                            "current_price": price,
                            "market_value": cost,
                            "cost_basis": cost,
                            "pnl": 0.0, "pnl_pct": 0.0,
                            "entry_date": self._today_date,
                            "days_held": 0,
                            "current_state": 0, "prev_state": 0,
                        }
            elif order.action == "加仓":
                h = holdings.get(order.code)
                if h and price > 0 and cash >= order.amount:
                    add_shares = int(order.amount / price / 100) * 100
                    if add_shares >= 100:
                        cost = add_shares * price
                        cash -= cost
                        total_shares = h["shares"] + add_shares
                        total_cost = h["cost_basis"] + cost
                        h["shares"] = total_shares
                        h["avg_cost"] = total_cost / total_shares
                        h["cost_basis"] = total_cost
                        h["current_price"] = price
                        h["market_value"] = total_shares * price
            elif order.action == "减仓":
                h = holdings.get(order.code)
                if h and price > 0:
                    reduce_shares = int(order.amount / price / 100) * 100
                    if reduce_shares > 0 and reduce_shares < h["shares"]:
                        cash += reduce_shares * price
                        h["shares"] -= reduce_shares
                        h["cost_basis"] = h["shares"] * h["avg_cost"]
                        h["current_price"] = price
                        h["market_value"] = h["shares"] * price

        # 重算总市值
        positions_value = sum(h.get("market_value", h.get("shares", 0) * h.get("current_price", 0))
                              for h in holdings.values())
        total_value = cash + positions_value
        total_return = (total_value - self.INITIAL_CAPITAL) / self.INITIAL_CAPITAL * 100

        # 更新 days_held
        for h in holdings.values():
            h["days_held"] = h.get("days_held", 0) + 1

        portfolio["cash"] = round(cash, 2)
        portfolio["total_value"] = round(total_value, 2)
        portfolio["total_return_pct"] = round(total_return, 2)
        portfolio["holdings"] = list(holdings.values())
        portfolio["orders"] = [o.to_dict() for o in orders]

        return portfolio

    def summary(self, portfolio: dict) -> str:
        """持仓摘要."""
        h = portfolio.get("holdings", [])
        etfs = [x for x in h if x["type"] == "etf"]
        stocks = [x for x in h if x["type"] == "stock"]
        orders = portfolio.get("orders", [])
        lines = [
            f"📊 持仓摘要 {portfolio['date']}",
            f"  总资产: {portfolio['total_value']:,.0f} ({portfolio['total_return_pct']:+.1f}%)",
            f"  现金: {portfolio['cash']:,.0f}",
            f"  ETF持仓: {len(etfs)}/7 市值{sum(x.get('market_value',0) for x in etfs):,.0f}",
            f"  个股持仓: {len(stocks)}/3 市值{sum(x.get('market_value',0) for x in stocks):,.0f}",
        ]
        if orders:
            lines.append(f"  今日指令: {len(orders)}条")
            for o in orders:
                lines.append(f"    {o['action']} {o['name']} {o['amount']:,.0f}元")
        return "\n".join(lines)
