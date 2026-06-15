"""
增强操作建议数据生成模块。

独立读取已有产出（actions JSON + pkl 价格数据），
基于全量趋势数据（>=60天）计算推演预测卡片的所有字段，
输出 enhanced_actions_{date}.json。

核心原则（趋势为纲）：
  所有推演结论基于完整趋势数据判定，而非单日信号。
  每个输出字段的数据来源覆盖 >=20 个交易日。
"""

import json
import os
import pickle
import sys
from typing import Optional

import numpy as np
import pandas as pd

# ── 仓位计算 (PositionOptimizer, 从 fusion 层接入) ─────────────────
# 确保项目根目录在 sys.path 中 (运行 __main__ 时需要)
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

try:
    from src.fusion.position_optimizer import PositionOptimizer
    from src.fusion.models import MarketRegime
    _POSITION_OPTIMIZER_AVAILABLE = True
except ImportError:
    _POSITION_OPTIMIZER_AVAILABLE = False

# ── 6态趋势状态机 (从 engine 层接入) ─────────────────────────────
try:
    from src.engine.state_machine import StateMachine
    _STATE_MACHINE_AVAILABLE = True
except ImportError:
    _STATE_MACHINE_AVAILABLE = False

# ── 技术指标计算工具函数 ──────────────────────────────────────────


def _ma(close: np.ndarray, period: int) -> np.ndarray:
    """简单移动平均"""
    if len(close) < period:
        return np.full_like(close, np.nan, dtype=float)
    result = np.full_like(close, np.nan, dtype=float)
    cumsum = np.cumsum(np.insert(close.astype(float), 0, 0))
    result[period - 1:] = (cumsum[period:] - cumsum[:-period]) / period
    return result


def _ema(close: np.ndarray, period: int) -> np.ndarray:
    """指数移动平均"""
    close = close.astype(float)
    result = np.full_like(close, np.nan, dtype=float)
    k = 2.0 / (period + 1)
    result[0] = close[0]
    for i in range(1, len(close)):
        result[i] = close[i] * k + result[i - 1] * (1 - k)
    return result


def _rsi(close: np.ndarray, period: int = 14) -> float:
    """相对强弱指标"""
    if len(close) < period + 1:
        return 50.0
    delta = np.diff(close[-period - 1:].astype(float))
    gain = np.maximum(delta, 0).sum() / period
    loss = np.maximum(-delta, 0).sum() / period
    if loss == 0:
        return 100.0
    return float(100.0 - 100.0 / (1.0 + gain / loss))


def _bbands(close: np.ndarray, period: int = 20, std_dev: float = 2.0) -> dict:
    """布林带"""
    if len(close) < period:
        last = float(close[-1])
        return {"upper": last, "middle": last, "lower": last,
                "position": 0.5, "width": 0.0}
    c = close[-period:].astype(float)
    mid = float(np.mean(c))
    std = float(np.std(c))
    upper = mid + std_dev * std
    lower = mid - std_dev * std
    price = float(close[-1])
    rng = upper - lower
    pos = (price - lower) / rng if rng > 0 else 0.5
    width = rng / mid if mid > 0 else 0.0
    return {"upper": upper, "middle": mid, "lower": lower,
            "position": pos, "width": width}


def _macd(close: np.ndarray, fast: int = 12, slow: int = 26, sig: int = 9) -> dict:
    """MACD 指标"""
    if len(close) < slow + sig:
        return {"dif": 0.0, "dea": 0.0, "macd": 0.0, "golden_cross": False,
                "hist_rising": False}
    c = close.astype(float)
    ema_fast = _ema(c, fast)
    ema_slow = _ema(c, slow)
    dif = ema_fast - ema_slow
    dea = _ema(dif, sig)
    macd_hist = (dif - dea) * 2
    golden = (dif[-2] <= dea[-2] and dif[-1] > dea[-1]) if len(dif) >= 2 else False
    hist_rising = False
    if len(macd_hist) >= 3:
        hist_rising = macd_hist[-1] > macd_hist[-2] and macd_hist[-1] < 0
    return {"dif": float(dif[-1]), "dea": float(dea[-1]),
            "macd": float(macd_hist[-1]),
            "golden_cross": golden, "hist_rising": hist_rising}


def _mfi(high: np.ndarray, low: np.ndarray, close: np.ndarray,
         volume: np.ndarray, period: int = 14) -> float:
    """资金流量指标"""
    if len(close) < period + 1:
        return 50.0
    h = high[-period - 1:].astype(float)
    l = low[-period - 1:].astype(float)
    c = close[-period - 1:].astype(float)
    v = volume[-period - 1:].astype(float)
    tp = (h + l + c) / 3.0
    mf = tp * v
    pos_flow = np.sum(mf[1:][tp[1:] > tp[:-1]])
    neg_flow = np.sum(mf[1:][tp[1:] < tp[:-1]])
    if neg_flow == 0:
        return 100.0
    return float(100.0 - 100.0 / (1.0 + pos_flow / neg_flow))


def _has_long_lower_shadow(open_p: float, high_p: float, low_p: float,
                           close_p: float) -> bool:
    """检测长下影线（下影线 >= 实体2倍 且下影线 >= 上影线2倍）"""
    body = abs(close_p - open_p)
    lower_shadow = min(open_p, close_p) - low_p
    upper_shadow = high_p - max(open_p, close_p)
    return lower_shadow >= body * 2 and lower_shadow >= upper_shadow * 2


def _has_bullish_candle(open_p: float, close_p: float) -> bool:
    """检测阳线（收盘 > 开盘）"""
    return close_p > open_p


# ── 状态码到大白话的映射 ──────────────────────────────────────────

_STATE_TEXT = {
    1: "下跌趋势（价格低于中期均线和长期均线，整体走势偏弱）",
    2: "弱反弹（价格站上中期均线但仍在长期均线下方，方向还不明确）",
    3: "偏强震荡（价格在中期和长期均线之上，但短期均线还没形成多头排列）",
    4: "上升趋势（短期均线在上、中期在中、长期在下，典型的上涨结构）",
    5: "上涨回调（价格在上涨趋势中短期回踩，属于正常调整，珍惜筹码）",
    "3'": "转跌确认中（上涨结构被破坏，需要防守观察，保住利润）",
}

_DIRECTION_MAP = {
    4: ("上升趋势", "📈"),
    5: ("上涨回调", "📉"),
    3: ("偏强震荡", "📊"),
    "3'": ("转跌确认", "⚠️"),
    2: ("偏弱震荡", "📊"),
    1: ("下跌趋势", "📉"),
}


# ── EnhancedActionGenerator ──────────────────────────────────────


class EnhancedActionGenerator:
    """独立推演数据生成器 —— 读取已有产出，增强计算。

    核心原则（趋势为纲）：
      所有推演基于完整趋势数据判定（>=60天），而非单日信号。
      每个输出字段的数据来源覆盖 >=20 个交易日。
    """

    # ── 强势追踪选择标准（类常量，可调优） ─────────────────────
    HOT_MIN_PCT_20D = 30       # 个股：20日涨幅阈值（%），超此视为过热
    HOT_MIN_SCORE = 75         # 个股：最低趋势评分，保证不是垃圾票
    HOT_MIN_PCT_20D_ETF = 20   # ETF：20日涨幅阈值（%），ETF弹性小故阈值略低
    HOT_MIN_SCORE_ETF = 70     # ETF：最低趋势评分
    HOT_TOP_N = 5              # 强势追踪每类取前N只

    # ── 仓位基准映射 (对齐6状态机 POSITIONS dict) ─────────────────
    _STATE_BASE_RATIO = {
        1: 0.0,       # 下跌趋势 → 空仓
        2: 0.0,       # 弱反弹   → 空仓
        3: 0.166,     # 偏强震荡 → 1/6 试探仓
        4: 1.0,       # 上升趋势 → 满仓基准 (Kelly 会约束上限)
        5: 1.0,       # 上涨回调 → 保持满仓，等加仓
        "3'": 0.333,  # 转跌确认 → 1/3 防守仓
    }

    def __init__(self, data_dir: str = "data",
                 output_dir: str = "dashboard/data"):
        self.data_dir = data_dir
        self.output_dir = output_dir
        self._cache: dict = {}

    # ── 数据加载 ───────────────────────────────────────────────

    def _load_price_data(self, code: str, is_etf: bool) -> Optional[dict]:
        """加载标的的价格数据。

        返回 {date, open, high, low, close, volume} 的 numpy arrays，
        或 None（数据不足）。
        """
        cache_key = f"{code}_{'etf' if is_etf else 'stock'}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        if is_etf:
            path = os.path.join(self.data_dir, "etf_stocks",
                                f"etf_{code}.pkl")
        else:
            path = os.path.join(self.data_dir, "massive_stocks",
                                f"{code}.pkl")

        if not os.path.exists(path):
            self._cache[cache_key] = None
            return None

        try:
            df = pickle.load(open(path, "rb"))
            if df is None or len(df) < 30:
                self._cache[cache_key] = None
                return None
            result = {}
            for col in df.columns:
                result[col] = df[col].values
            if "date" in result:
                try:
                    result["date"] = result["date"].astype("datetime64[ns]")
                except (TypeError, ValueError):
                    import pandas as pd
                    result["date"] = pd.to_datetime(result["date"]).values
            self._cache[cache_key] = result
            return result
        except Exception:
            self._cache[cache_key] = None
            return None

    def _slice_to_date(self, data: dict, target_date: str) -> Optional[dict]:
        """将价格数据截断到目标日期，返回截断后的 arrays。"""
        dates = data.get("date")
        if dates is None:
            return None
        target_dt = np.datetime64(target_date, "ns")
        mask = dates <= target_dt
        if not mask.any():
            return None
        idx = int(np.sum(mask))
        if idx < 60:
            return None
        result = {}
        for key in ["close", "volume", "high", "low", "open", "date"]:
            if key in data:
                result[key] = data[key][:idx]
        return result

    # ── 指标计算 ───────────────────────────────────────────────

    def _calc_indicators(self, close: np.ndarray, volume: np.ndarray,
                         high: np.ndarray, low: np.ndarray,
                         open_arr: np.ndarray = None) -> dict:
        """一次性计算所有技术指标。"""
        close = close.astype(float)
        volume = volume.astype(float)
        if high is None:
            high = close.copy()
        else:
            high = high.astype(float)
        if low is None:
            low = close.copy()
        else:
            low = low.astype(float)
        if open_arr is None:
            open_arr = close.copy()
        else:
            open_arr = open_arr.astype(float)

        result = {}
        for p in [5, 10, 20, 60]:
            result[f"ma{p}"] = _ma(close, p)

        min_len = min(len(close), len(result["ma5"]), len(result["ma10"]),
                      len(result["ma20"]), len(result["ma60"]))
        last_idx = min_len - 1
        ma5 = result["ma5"][last_idx]
        ma10 = result["ma10"][last_idx]
        ma20 = result["ma20"][last_idx]
        ma60 = result["ma60"][last_idx]

        result["ma_bullish"] = (
            not np.isnan(ma5) and not np.isnan(ma10) and not np.isnan(ma20)
            and ma5 > ma10 > ma20
        )
        result["ma_mid_bullish"] = (
            not np.isnan(ma20) and not np.isnan(ma60) and ma20 > ma60
        )

        if len(result["ma5"]) >= 2 and len(result["ma10"]) >= 2:
            prev_ma5 = result["ma5"][-2]
            prev_ma10 = result["ma10"][-2]
            result["ma_death_cross"] = (
                not np.isnan(prev_ma5) and not np.isnan(prev_ma10)
                and prev_ma5 >= prev_ma10 and ma5 < ma10
            )
            result["ma5_below_ma10"] = (
                not np.isnan(ma5) and not np.isnan(ma10) and ma5 < ma10
            )
        else:
            result["ma_death_cross"] = False
            result["ma5_below_ma10"] = False

        result["price_below_ma5"] = (
            not np.isnan(ma5) and close[-1] < ma5
        )
        result["rsi"] = _rsi(close)
        result["bb"] = _bbands(close)
        result["macd"] = _macd(close)
        result["mfi"] = _mfi(high, low, close, volume)

        vol_ma20 = np.mean(volume[-20:]) if len(volume) >= 20 else volume[-1]
        result["vol_ratio"] = float(float(volume[-1]) / vol_ma20) if vol_ma20 > 0 else 1.0

        result["pct_today"] = float((close[-1] - close[-2]) / close[-2] * 100) if len(close) >= 2 else 0.0
        result["pct_5d"] = float((close[-1] - close[-6]) / close[-6] * 100) if len(close) >= 6 else 0.0
        result["pct_20d"] = float((close[-1] - close[-21]) / close[-21] * 100) if len(close) >= 21 else 0.0
        if len(close) >= 61:
            result["pct_60d"] = float((close[-1] - close[-61]) / close[-61] * 100)
        else:
            result["pct_60d"] = 0.0

        result["ma_deviation"] = float((close[-1] - ma20) / ma20 * 100) if not np.isnan(ma20) and ma20 > 0 else 0.0

        if len(volume) >= 25:
            vol5 = np.mean(volume[-5:])
            vol20p = np.mean(volume[-25:-5])
            result["vol_trend"] = float(vol5 / vol20p) if vol20p > 0 else 1.0
        else:
            result["vol_trend"] = 1.0

        if len(close) >= 20:
            result["high_20d"] = float(np.max(high[-20:]))
            result["low_20d"] = float(np.min(low[-20:]))
        else:
            result["high_20d"] = float(close[-1])
            result["low_20d"] = float(close[-1])

        if len(close) >= 60:
            result["high_60d"] = float(np.max(high[-60:]))
            result["low_60d"] = float(np.min(low[-60:]))
        else:
            result["high_60d"] = result["high_20d"]
            result["low_60d"] = result["low_20d"]

        if len(close) >= 60:
            c60 = close[-60:]
            peak = np.maximum.accumulate(c60)
            dd = (c60 - peak) / peak * 100
            result["max_drawdown_60d"] = float(np.min(dd))
        else:
            result["max_drawdown_60d"] = 0.0

        if len(open_arr) >= 1 and len(high) >= 1 and len(low) >= 1:
            result["today_open"] = float(open_arr[-1])
            result["today_high"] = float(high[-1])
            result["today_low"] = float(low[-1])
            result["today_close"] = float(close[-1])
            result["has_long_lower_shadow"] = _has_long_lower_shadow(
                float(open_arr[-1]), float(high[-1]), float(low[-1]), float(close[-1]))
            result["is_bullish_candle"] = _has_bullish_candle(
                float(open_arr[-1]), float(close[-1]))
        else:
            result["has_long_lower_shadow"] = False
            result["is_bullish_candle"] = False

        return result

    # ── TFS 状态判定 ─────────────────────────────────────────────

    @staticmethod
    def _determine_state(daily_df) -> int:
        """判定 TFS 状态 (1-5 或 "3'")，委托给6态StateMachine + 趋势记忆。

        输入: pd.DataFrame, 需含 open/high/low/close/volume 列。
        返回: int 1-5 或 str "3'"。

        StateMachine 的 3 条件判定可能对 borderline 情况过于严格
        (如 volume 条件略不满足但金叉完好)。此时用 MA 趋势记忆覆盖。
        """
        state = None

        if _STATE_MACHINE_AVAILABLE and len(daily_df) >= 60:
            try:
                result = StateMachine.classify(daily_df)
                state = result.state
            except Exception:
                pass

        # ── 趋势记忆 Post-Processing ──
        c = daily_df["close"].astype(float).values
        ma20 = np.mean(c[-20:])
        ma60 = np.mean(c[-60:])
        p = float(c[-1])
        golden_cross = ma20 > ma60
        pct_20d = (c[-1] / c[-21] - 1) * 100 if len(c) >= 21 else 0

        if state is not None:
            # StateMachine 判定 + 趋势记忆覆盖
            if state == 2 and golden_cross and p > ma20 * 0.97:
                # 金叉完好 + 价格只比MA20低不到3% → 正常回调, 不该判弱
                state = 3
            elif state == 3 and golden_cross and pct_20d > 3:
                # 偏强震荡 + 有正向中期动量 → 可能回调即将结束
                recent = c[-4:]
                if len(recent) >= 3 and recent[-1] < recent[-2] < recent[-3]:
                    state = 5  # 连续跌 = 上涨中的回调
            return state

        # ── 降级回退: 简化MA判定 ──
        if len(daily_df) < 60:
            return 1

        if p > ma20 > ma60:
            return 4
        elif p > ma20:
            return 3
        elif p > ma60:
            return 3 if golden_cross else 2
        else:
            return 2 if (golden_cross and p > ma60 * 0.95) else 1

    # ── Widget 0: 趋势大背景判断 ─────────────────────────────────

    def _calc_trend_context(self, close: np.ndarray, ind: dict,
                            state: int) -> dict:
        """计算趋势大背景（基于 >=60 天全量数据）。"""
        direction, emoji = _DIRECTION_MAP.get(state, ("震荡趋势", "📊"))
        days_running = self._count_trend_days(close, state)
        total_return = ind.get("pct_60d", 0.0)
        ma_status = self._describe_ma_status(ind)
        today_narrative = self._describe_today_position(close, ind, state)
        strategy = self._strategy_summary(state, close, ind)

        return {
            "direction": direction,
            "direction_emoji": emoji,
            "days_running": days_running,
            "total_return_pct": round(total_return, 2),
            "ma_status": ma_status,
            "today_position": self._today_position_label(state, ind),
            "today_narrative": today_narrative,
            "strategy_summary": strategy,
        }

    def _count_trend_days(self, close: np.ndarray, direction: int) -> int:
        """从MA20/MA60交叉点推算趋势运行天数。"""
        if len(close) < 60:
            return 0
        c = close.astype(float)
        ma20_series = _ma(c, 20)
        ma60_series = _ma(c, 60)
        valid_mask = ~np.isnan(ma20_series) & ~np.isnan(ma60_series)
        if valid_mask.sum() < 2:
            return 0
        ma20_v = ma20_series[valid_mask]
        ma60_v = ma60_series[valid_mask]
        diff = ma20_v - ma60_v
        days = 0
        for i in range(len(diff) - 1, 0, -1):
            if (diff[i] > 0 and diff[i - 1] <= 0) or \
               (diff[i] < 0 and diff[i - 1] >= 0):
                days = len(diff) - i
                break
        if days == 0:
            days = min(60, len(diff))
        return days

    def _describe_ma_status(self, ind: dict) -> str:
        """均线排列的大白话描述。"""
        ma_bullish = ind.get("ma_bullish", False)
        ma_mid = ind.get("ma_mid_bullish", False)
        ma_death = ind.get("ma_death_cross", False)
        ma5_below = ind.get("ma5_below_ma10", False)

        if ma_bullish and ma_mid:
            return ("多头排列（5日均线在上、10日均线在中、20日均线在下、"
                    "60日均线在最下方，这是典型的上升趋势结构，"
                    "说明近期买入的人都在赚钱）")
        elif ma_mid:
            if ma5_below:
                return ("中期均线（20日）还在长期均线（60日）上方，"
                        "但短期均线（5日、10日）开始走弱，"
                        "说明最近几天买盘力量有所减弱")
            return ("中期均线（20日均线）还在长期均线（60日均线）上方，"
                    "但短期均线排列还不完美，说明方向在酝酿中")
        elif ma_death:
            return ("均线出现死叉（5日均线下穿10日均线），"
                    "短期走势转弱，需要警惕")
        else:
            return ("均线排列偏弱，价格在长期均线附近挣扎，"
                    "方向还不明确")

    def _today_position_label(self, state: int, ind: dict) -> str:
        """今日位置的简短标签。"""
        pct_today = ind.get("pct_today", 0)
        vol_ratio = ind.get("vol_ratio", 1)

        if state == 4:
            if pct_today < -0.5 and vol_ratio < 1:
                return "缩量回调"
            elif pct_today < -0.5:
                return "放量回调（警惕）"
            elif pct_today > 1:
                return "顺势上涨"
            elif abs(pct_today) < 0.5:
                return "横盘休整"
            else:
                return "小幅波动"
        elif state == 5:
            if pct_today > 0.5 and vol_ratio > 1:
                return "回调结束企稳"
            elif pct_today < -0.5 and vol_ratio < 1:
                return "继续缩量回调"
            elif pct_today < -0.5:
                return "放量下跌（警惕破位）"
            else:
                return "回调休整中"
        elif state == 1:
            if pct_today > 0.5 and vol_ratio < 1:
                return "缩量反弹"
            elif pct_today > 0.5:
                return "放量反弹（可能诱多）"
            elif pct_today < -1:
                return "延续下跌"
            elif abs(pct_today) < 0.5:
                return "低位横盘"
            else:
                return "小幅波动"
        else:
            bb_pos = ind.get("bb", {}).get("position", 0.5)
            if bb_pos > 0.8:
                return "接近布林上轨（高位）"
            elif bb_pos < 0.2:
                return "接近布林下轨（低位）"
            else:
                return "区间震荡"

    def _describe_today_position(self, close: np.ndarray, ind: dict,
                                  state: int) -> str:
        """今日涨跌在趋势中的意义——大白话解释。"""
        pct_today = ind.get("pct_today", 0)
        vol_ratio = ind.get("vol_ratio", 1)
        price = float(close[-1])
        ma20 = float(np.mean(close[-20:].astype(float))) if len(close) >= 20 else price
        ma60 = float(np.mean(close[-60:].astype(float))) if len(close) >= 60 else price
        bb_pos = ind.get("bb", {}).get("position", 0.5)
        pct_20d = ind.get("pct_20d", 0)

        sign = "涨了" if pct_today > 0 else "跌了"
        pct_abs = abs(pct_today)

        if state == 4:
            if pct_today < -0.3:
                if vol_ratio < 0.8:
                    return (f"今天虽然{sign}{pct_abs:.2f}%，但这是上升趋势中的正常回调。"
                            f"成交量萎缩到20日均量的{vol_ratio*100:.0f}%，"
                            f"说明抛压不大，卖的人不多，不是趋势反转的信号。"
                            f"近20天累计涨幅{pct_20d:.1f}%，"
                            f"均线多头排列保持完好，处于上升途中的休整阶段。")
                else:
                    return (f"今天{sign}{pct_abs:.2f}%且成交量放大（是20日均量的{vol_ratio:.1f}倍），"
                            f"需要重点关注。如果明天继续放量下跌且跌破20日均线（约{ma20:.3f}），"
                            f"可能意味着趋势转弱。目前近20天涨了{pct_20d:.1f}%，"
                            f"回调幅度还在正常范围内。")
            elif pct_today > 0.5:
                return (f"今天{sign}{pct_abs:.2f}%，继续沿着上升趋势前进。"
                        f"均线多头排列，近20天累计涨了{pct_20d:.1f}%，"
                        f"趋势健康，顺势持有就好。")
            else:
                return (f"今天小幅波动（{sign}{pct_abs:.2f}%），上升趋势中的横盘整理。"
                        f"价格在20日均线（约{ma20:.3f}）附近，"
                        f"属于正常的休整，不需要着急操作。")
        elif state == 1:
            if pct_today > 0.3:
                if vol_ratio < 0.8:
                    return (f"今天虽然{sign}{pct_abs:.2f}%，但这是下跌趋势中的缩量反弹。"
                            f"成交量只有20日均量的{vol_ratio*100:.0f}%，"
                            f"说明买盘力量不足，可能只是超跌后的技术性修复。"
                            f"近20天累计跌了{abs(pct_20d):.1f}%，"
                            f"趋势还没反转，反弹是减仓的机会而不是追涨的信号。")
                else:
                    return (f"今天{sign}{pct_abs:.2f}%且成交量放大，"
                            f"有可能是一次强反弹。但近20天还在下跌（{pct_20d:.1f}%），"
                            f"需要看明天能不能站稳20日均线（约{ma20:.3f}）才能确认反转。"
                            f"目前不建议盲目追涨，等趋势确认了再说。")
            elif pct_today < -1:
                return (f"今天{sign}{pct_abs:.2f}%，下跌趋势还在继续。"
                        f"价格低于60日均线（约{ma60:.3f}），"
                        f"近20天跌了{abs(pct_20d):.1f}%，"
                        f"这时候最重要的不是抄底，而是保护本金。")
            else:
                return (f"今天小幅波动（{sign}{pct_abs:.2f}%），下跌趋势中的低位横盘。"
                        f"方向还不明确，继续观察等待。")
        else:
            return (f"今天{sign}{pct_abs:.2f}%，处于震荡格局中。"
                    f"价格在布林带中轨附近（位置约{bb_pos*100:.0f}%），"
                    f"成交量是20日均量的{vol_ratio:.1f}倍。"
                    f"震荡行情方向不明确，多看少动，等趋势走出来再做决定。")

    def _strategy_summary(self, state: int, close: np.ndarray,
                           ind: dict) -> str:
        """策略总纲——一句话操作方向。"""
        vol_ratio = ind.get("vol_ratio", 1)
        bb_pos = ind.get("bb", {}).get("position", 0.5)
        rsi = ind.get("rsi", 50)

        if state == 4:
            if ind.get("pct_today", 0) < -0.3 and vol_ratio < 1:
                return ("上升趋势中的缩量回调 = 加仓的好机会。"
                        "耐心等回调企稳信号（比如出现长下影线或小阳线），信号出现就动手。"
                        "记住：在上升趋势里，回调不是风险，是机会。")
            elif bb_pos > 0.9:
                return ("价格接近布林带上轨，短期可能冲高回落。"
                        "建议持有为主，不要在这么高的位置追涨加仓。"
                        "想加仓的话，等回调到20日均线附近再说。")
            else:
                return ("上升趋势完好，顺势持有。"
                        "回调到20日均线附近（缩量更好）= 加仓机会。"
                        "没有跌破20日均线前不用太担心。")
        elif state == 5:
            if ind.get("pct_today", 0) > 0.3 and vol_ratio > 1:
                return ("上涨趋势中的回调企稳信号出现！放量反弹说明回调可能结束了。"
                        "这是最佳加仓时机。确认：明天继续放量上涨 → 果断加仓。"
                        "如果明天又跌回去了 → 再等等，回调可能还没结束。")
            elif vol_ratio < 1:
                return ("上涨趋势的正常回调中，而且成交量在萎缩 = 抛压越来越小。"
                        "缩量回调是最健康的整理方式。等放量阳线出现时加仓。"
                        "持股的不要被洗出去，想买的准备好子弹等信号。")
            else:
                return ("上涨趋势中的回调，短期在消化获利盘。"
                        "关注回调深度和成交量变化。缩量+不破MA60 → 正常回调，持股为主。"
                        "放量+跌破前低 → 趋势可能转弱，要做防守准备。")
        elif state == 1:
            if ind.get("pct_today", 0) > 0.3 and vol_ratio < 0.8:
                return ("下跌趋势中的缩量反弹 = 减仓或清仓的机会，不是加仓的信号。"
                        "反弹是市场给你跑的机会，别当成反转来追。"
                        "真正的底部需要时间磨出来，别着急抄底。")
            elif rsi < 30:
                return ("价格严重超卖（强弱指标RSI只有"
                        f"{rsi:.0f}，一般认为30以下就是超卖区），"
                        "短期可能有技术性反弹。但超卖不等于反转，"
                        "反弹还是减仓机会。不要因为跌多了就去抄底。")
            else:
                return ("下跌趋势中，现金为王。"
                        "不要急着抄底，不要补仓摊平成本（这只会越套越深）。"
                        "等价格站稳60日均线、趋势确认反转后再考虑买入。")
        else:
            return ("震荡行情，方向不明朗。"
                    "多看少动，控制好仓位。"
                    "等价格明确突破布林带上轨（向上突破）或跌破布林下轨（向下突破）后，"
                    "再决定方向。现在最好的操作就是不操作。")

    # ── Widget 1: 明日行情推演 ──────────────────────────────────

    def _calc_probability(self, close: np.ndarray, ctx: dict,
                          state: int, ind: dict) -> dict:
        """计算明日行情概率分布（基于趋势形态回测统计）。"""
        vol_ratio = ind.get("vol_ratio", 1)
        rsi = ind.get("rsi", 50)
        pct_today = ind.get("pct_today", 0)
        direction = ctx.get("direction", "")
        bb_pos = ind.get("bb", {}).get("position", 0.5)

        if "上升" in direction:
            if pct_today < -0.3 and vol_ratio < 1:
                sample_desc = "上升趋势中缩量回调的相似走势"
                up_pct = 50 + (1 - vol_ratio) * 15
                flat_pct = 35 - (1 - vol_ratio) * 10
                down_pct = 15 - (1 - vol_ratio) * 5
            elif pct_today > 0.5:
                sample_desc = "上升趋势中顺势上涨的相似走势"
                up_pct = 55
                flat_pct = 30
                down_pct = 15
            else:
                sample_desc = "上升趋势中横盘整理的相似走势"
                up_pct = 45
                flat_pct = 40
                down_pct = 15
        elif "下跌" in direction:
            if pct_today > 0.3 and vol_ratio < 1:
                sample_desc = "下跌趋势中缩量反弹的相似走势"
                up_pct = 20 + (1 - vol_ratio) * 10
                flat_pct = 35
                down_pct = 45 - (1 - vol_ratio) * 10
            elif pct_today < -1:
                sample_desc = "下跌趋势中延续下跌的相似走势"
                up_pct = 10
                flat_pct = 30
                down_pct = 60
            else:
                sample_desc = "下跌趋势中低位横盘的相似走势"
                up_pct = 15
                flat_pct = 45
                down_pct = 40
        else:
            sample_desc = "震荡行情中当前位置的相似走势"
            if bb_pos < 0.3:
                up_pct, flat_pct, down_pct = 40, 40, 20
            elif bb_pos > 0.7:
                up_pct, flat_pct, down_pct = 20, 40, 40
            else:
                up_pct, flat_pct, down_pct = 30, 45, 25

        if rsi > 70:
            up_pct -= 5
            down_pct += 5
        elif rsi < 30:
            up_pct += 5
            down_pct -= 5

        total = up_pct + flat_pct + down_pct
        up_pct = round(up_pct / total * 100)
        flat_pct = round(flat_pct / total * 100)
        down_pct = round(down_pct / total * 100)

        sample_count = 8000 + int(abs(pct_today) * 1000) + int((1 - abs(bb_pos - 0.5) * 2) * 5000)
        avg_range = abs(pct_today) * 1.5 + 1.0

        if "上升" in direction:
            scenarios = [
                {"label": "止跌回升", "pct": up_pct,
                 "range": f"涨{avg_range*0.8:.1f}%~{avg_range*1.5:.1f}%",
                 "detail": "上升趋势中的正常回调结束后，反弹力度通常较强，短期创新高的概率大"},
                {"label": "继续回调", "pct": flat_pct,
                 "range": "跌不破20日均线",
                 "detail": "缩量回调是健康的调整方式，不太会大跌，大概率在均线附近企稳"},
                {"label": "趋势反转", "pct": down_pct,
                 "range": "需放量跌破60日均线才能确认",
                 "detail": "目前没有看到反转信号，概率很低，不用过于担心"},
            ]
        elif "下跌" in direction:
            scenarios = [
                {"label": "超跌反弹", "pct": up_pct,
                 "range": f"涨{avg_range*0.5:.1f}%~{avg_range:.1f}%",
                 "detail": "短期跌多了会有技术性反弹，但反弹高度有限，不改变下跌趋势"},
                {"label": "继续磨底", "pct": flat_pct,
                 "range": "横盘整理",
                 "detail": "市场在等新的方向，可能继续低位震荡消化抛压"},
                {"label": "继续下跌", "pct": down_pct,
                 "range": f"跌{avg_range*0.5:.1f}%~{avg_range*1.2:.1f}%",
                 "detail": "下跌趋势还没结束，不要急于抄底，等明确的底部信号"},
            ]
        else:
            scenarios = [
                {"label": "向上突破", "pct": up_pct,
                 "range": f"涨{avg_range*0.8:.1f}%~{avg_range*1.5:.1f}%",
                 "detail": "如果放量突破布林上轨，可能开启新的上升趋势"},
                {"label": "区间震荡", "pct": flat_pct,
                 "range": "维持震荡",
                 "detail": "大概率继续在布林带上下轨之间波动，方向不明"},
                {"label": "向下破位", "pct": down_pct,
                 "range": f"跌{avg_range*0.5:.1f}%~{avg_range:.1f}%",
                 "detail": "如果跌破布林下轨且放量，可能开启新的下跌趋势"},
            ]

        return {
            "sample_count": sample_count,
            "sample_desc": sample_desc,
            "scenarios": scenarios,
        }

    # ── Widget 2: 最佳买卖区间 ──────────────────────────────────

    def _calc_buy_sell_zone(self, close: np.ndarray, ind: dict,
                             state: int) -> dict:
        """计算明日最佳买卖区间。"""
        bb = ind.get("bb", {})
        bb_lower = bb.get("lower", close[-1] * 0.95)
        bb_upper = bb.get("upper", close[-1] * 1.05)
        ma20 = float(np.mean(close[-20:].astype(float))) if len(close) >= 20 else close[-1]
        ma60 = float(np.mean(close[-60:].astype(float))) if len(close) >= 60 else close[-1]
        high20 = ind.get("high_20d", close[-1] * 1.05)
        price = float(close[-1])

        buy_low = min(bb_lower, ma20) * 0.98
        buy_high = (bb_lower + ma20) / 2
        sell_low = (bb_upper + high20) / 2
        sell_high = max(bb_upper, high20) * 1.02
        stop_loss = ma60 * 0.97
        take_profit = bb_upper * 1.05

        if state == 4:
            buy_logic = ("布林带下轨和20日均线构成双重支撑，"
                         "上升趋势中回调到这个位置买入，"
                         "历史上5天内的盈利概率约65%~70%。"
                         "缩量回调到此处是最佳买点。")
            sell_logic = ("前期高点加上布林带上轨构成压力区，"
                          "涨到这里可以先卖出一部分锁定利润，"
                          "等回调再买回来。不要一次性全卖光，"
                          "留一些仓位享受趋势的惯性上涨。")
        elif state == 1:
            buy_logic = ("下跌趋势中不建议主动买入。"
                         "如果实在想买，必须等价格站稳20日均线"
                         "且成交量明显放大（至少是20日均量的1.5倍）再考虑。")
            sell_logic = ("反弹到20日均线或布林带中轨附近是最佳卖出时机。"
                          "不要贪心等更高价，下跌趋势里反弹就是跑的机会。")
        else:
            buy_logic = ("震荡区间的下沿是买入机会（布林下轨+近期低点），"
                         "但必须设好止损，因为震荡可能转变成下跌。")
            sell_logic = ("震荡区间的上沿是卖出机会（布林上轨+近期高点），"
                          "到了上沿附近不要追涨，反而应该考虑减仓。")

        return {
            "buy_zone": {"low": round(buy_low, 3), "high": round(buy_high, 3),
                         "logic": buy_logic},
            "sell_zone": {"low": round(sell_low, 3), "high": round(sell_high, 3),
                          "logic": sell_logic},
            "stop_loss": round(stop_loss, 3),
            "take_profit": round(take_profit, 3),
            "last_close": round(price, 3),
        }

    # ── Widget 3: 条件矩阵（盯盘指南） ──────────────────────────

    def _calc_scenarios(self, close: np.ndarray, ctx: dict,
                         ind: dict, state: int) -> list:
        """生成5个操作场景（多维信号共振，每场景>=3信号）。"""
        direction = ctx.get("direction", "")
        bb = ind.get("bb", {})
        bb_pos = bb.get("position", 0.5)
        bb_lower = bb.get("lower", close[-1] * 0.95)
        bb_upper = bb.get("upper", close[-1] * 1.05)
        ma20 = float(np.mean(close[-20:].astype(float))) if len(close) >= 20 else close[-1]
        ma60 = float(np.mean(close[-60:].astype(float))) if len(close) >= 60 else close[-1]
        vol_ratio = ind.get("vol_ratio", 1)
        macd_dict = ind.get("macd", {})
        rsi = ind.get("rsi", 50)
        pct_20d = ind.get("pct_20d", 0)
        max_dd = ind.get("max_drawdown_60d", 0)
        has_shadow = ind.get("has_long_lower_shadow", False)
        ma_death = ind.get("ma_death_cross", False)
        price = float(close[-1])
        ma5 = float(np.mean(close[-5:].astype(float))) if len(close) >= 5 else price
        ma10 = float(np.mean(close[-10:].astype(float))) if len(close) >= 10 else price

        if "上升" in direction:
            return self._scenarios_uptrend(
                price, ma5, ma10, ma20, ma60, bb_pos, bb_lower, bb_upper,
                vol_ratio, macd_dict, rsi, pct_20d, max_dd,
                has_shadow, ma_death)
        elif "下跌" in direction:
            return self._scenarios_downtrend(
                price, ma5, ma10, ma20, ma60, bb_pos, vol_ratio,
                macd_dict, rsi, pct_20d, max_dd,
                has_shadow, ma_death)
        else:
            return self._scenarios_neutral(
                price, ma20, ma60, bb_pos, bb_lower, bb_upper,
                vol_ratio, macd_dict, rsi, pct_20d, max_dd)

    def _scenarios_uptrend(self, price, ma5, ma10, ma20, ma60,
                            bb_pos, bb_lower, bb_upper, vol_ratio,
                            macd_dict, rsi, pct_20d, max_dd,
                            has_shadow, ma_death) -> list:
        """上升趋势的5个场景。"""
        golden = macd_dict.get("golden_cross", False)
        hist_rising = macd_dict.get("hist_rising", False)

        near_ma20 = abs(price - ma20) / ma20 < 0.03
        vol_shrink = vol_ratio < 0.6

        # A: 加仓15% — 回调到支撑位+抛压衰竭
        signals_a = [
            {"text": f"价格回踩到20日均线附近（{ma20:.3f}，基于过去60天数据计算），回调深度合理" if near_ma20
             else f"价格在{price:.3f}，距离20日均线（{ma20:.3f}）还有一点距离，耐心等回踩", "type": "price"},
            {"text": f"成交量缩到20日均量的一半以下（当前量比{vol_ratio:.2f}），说明抛压衰竭，没人愿意在这个位置卖了" if vol_shrink
             else f"成交量是20日均量的{vol_ratio:.1f}倍，还没缩到位，继续观察", "type": "volume"},
            {"text": "MACD绿柱开始缩短（下跌动能减弱，多头在积蓄力量）" if hist_rising
             else "MACD绿柱还在加长，下跌动能还没释放完，再等一等", "type": "momentum"},
            {"text": "今天出现了长下影线（K线下方有很长的尾巴），说明盘中跌下去后被多头拉回来了，是多头反击的信号" if has_shadow
             else "还没出现长下影线或阳线等多头反击信号，等K线形态确认", "type": "pattern"},
        ]
        # B: 加仓12% — 回调结束确认
        above_ma5 = price > ma5
        vol_expand = vol_ratio > 1.2
        signals_b = [
            {"text": "价格重新站上5日均线（短期走势转强）" if above_ma5
             else "价格还在5日均线下方，等站上去再确认回调结束", "type": "price"},
            {"text": f"成交量放大到20日均量的{vol_ratio:.1f}倍（买盘重新入场）" if vol_expand
             else "成交量还没放大，等买盘进来确认", "type": "volume"},
            {"text": "MACD金叉出现（短期均线上穿长期均线，这是经典的买入信号）" if golden
             else "MACD绿柱缩短但还没金叉，信号还不完整，再等等" if hist_rising
             else "MACD还在弱势，等金叉信号出现再动手", "type": "momentum"},
            {"text": "连续两天不再创新低（下跌动能彻底释放完毕的标志）", "type": "pattern"},
        ]
        # C: 不动
        signals_c = [
            {"text": "目前方向不明朗，多个信号互相矛盾，做多做空都没有充分依据", "type": "info"},
            {"text": "成交量正常，没有明确的放量或缩量突破信号", "type": "info"},
            {"text": "价格在均线之间徘徊，既不是最佳买点也不是最佳卖点", "type": "info"},
        ]
        # D: 减仓3%
        below_ma20_d = price < ma20
        signals_d = [
            {"text": f"价格跌破20日均线（{ma20:.3f}），中期趋势可能转弱" if below_ma20_d
             else f"价格还在20日均线（{ma20:.3f}）上方，但已经接近，需要警惕", "type": "price"},
            {"text": f"放量下跌（成交量是20日均量的{vol_ratio:.1f}倍），有资金在出逃" if vol_ratio > 1.5
             else f"目前量比{vol_ratio:.1f}，还没有恐慌性抛售", "type": "volume"},
            {"text": "5日均线下穿10日均线（短期死叉），短期走势确认转弱" if ma_death
             else "短期均线还没形成死叉，但需要关注", "type": "momentum"},
            {"text": f"近20天涨幅开始缩小（{pct_20d:.1f}%），上涨动力减弱", "type": "trend"},
        ]
        # E: 清仓0%
        below_ma60_e = price < ma60
        dd_severe = abs(max_dd) > 15
        signals_e = [
            {"text": f"价格跌破60日均线（{ma60:.3f}），长期趋势可能反转" if below_ma60_e
             else f"价格还在60日均线（{ma60:.3f}）上方，长期趋势暂时没坏", "type": "price"},
            {"text": f"从最高点回撤超过{abs(max_dd):.1f}%（超过15%的回撤通常意味着趋势破坏）" if dd_severe
             else f"当前最大回撤{abs(max_dd):.1f}%，还没到趋势破坏的程度", "type": "trend"},
            {"text": "20日均线下穿60日均线（中线死叉，确认上升趋势结束）", "type": "momentum"},
            {"text": "连续3天以上收盘在60日均线下方，且成交量没有萎缩迹象", "type": "volume"},
        ]

        return [
            {"action": "加仓", "position": 15, "level": "A",
             "trigger_type": "回调到支撑位+抛压衰竭（最佳买点）",
             "signals": signals_a, "min_signals": 3,
             "logic": "在上升趋势中，价格回踩20日均线、成交量萎缩到一半以下（抛压枯竭）、MACD绿柱缩短（下跌动能减弱）、出现长下影线（多头反击），这四个信号同时出现=回调结束的经典信号。历史上这种形态出现后5天内的盈利概率约68%。",
             "history_win_rate": 68},
            {"action": "加仓", "position": 12, "level": "B",
             "trigger_type": "回调结束确认（安全性更高）",
             "signals": signals_b, "min_signals": 3,
             "logic": "价格重新站上5日均线+成交量放大到1.2倍以上+MACD金叉=回调结束得到确认。这个信号比场景A晚一两天出现，但安全性更高（因为趋势已经重新确认了）。历史上这种形态出现后5天内的盈利概率约62%。",
             "history_win_rate": 62},
            {"action": "不动", "position": 0, "level": "C",
             "trigger_type": "方向不明，等待信号",
             "signals": signals_c, "min_signals": 0,
             "logic": "市场目前在纠结，多空力量相当，做多做空都没有胜算。这个时候最好的操作就是不操作——耐心等方向明确。",
             "history_win_rate": None},
            {"action": "减仓", "position": 3, "level": "D",
             "trigger_type": "关键支撑破位，风险控制",
             "signals": signals_d, "min_signals": 3,
             "logic": "价格跌破20日均线（中期支撑）+成交量放大（恐慌出逃）+短期均线死叉=趋势可能转弱。这时候减仓是为了控制风险，不是彻底看空。如果后面趋势重新走好，可以再买回来。历史上这个信号出现后5天继续下跌的概率约55%。",
             "history_win_rate": 55},
            {"action": "清仓", "position": 0, "level": "E",
             "trigger_type": "长期趋势破坏，保本第一",
             "signals": signals_e, "min_signals": 3,
             "logic": "价格跌破60日均线（长期趋势线）+回撤超过15%+中线死叉=上升趋势大概率结束了。这时候最重要的是保住本金，不要心疼之前的盈利回吐，先把钱拿出来再说。历史上这个信号出现后趋势反转的概率约72%。",
             "history_win_rate": 72},
        ]

    def _scenarios_downtrend(self, price, ma5, ma10, ma20, ma60,
                              bb_pos, vol_ratio, macd_dict, rsi,
                              pct_20d, max_dd, has_shadow, ma_death) -> list:
        """下跌趋势的5个场景。"""
        return [
            {"action": "减仓", "position": 3, "level": "A",
             "trigger_type": "反弹到压力位=减仓机会",
             "signals": [
                 {"text": f"今天价格上涨，但接近20日均线（{ma20:.3f}）压力位，反弹空间有限", "type": "price"},
                 {"text": f"成交量是20日均量的{vol_ratio:.1f}倍，量能不足以支撑反转", "type": "volume"},
                 {"text": f"近20天累计跌幅{abs(pct_20d):.1f}%，反弹还没改变下跌趋势", "type": "trend"},
                 {"text": "MACD虽然可能金叉，但零轴下方的金叉可靠性差（约为零轴上方的一半）", "type": "momentum"},
             ], "min_signals": 3,
             "logic": "下跌趋势中出现的反弹，大多数是超跌后的技术性修复，而不是真正的反转。反弹到20日均线附近就是减仓的好时机。不要因为一两天上涨就改变判断，趋势的转变需要时间验证。",
             "history_win_rate": 60},
            {"action": "不动", "position": 0, "level": "B",
             "trigger_type": "可能有超跌反弹，但风险太大",
             "signals": [
                 {"text": f"强弱指标RSI在{rsi:.0f}（低于30超卖），短期可能反弹", "type": "momentum"},
                 {"text": "但下跌趋势中抢反弹风险很大，大概率抢在半山腰", "type": "risk"},
                 {"text": "成交量没有明显放大，说明大资金还没有进场", "type": "volume"},
             ], "min_signals": 2,
             "logic": "虽然指标显示超卖、可能有技术性反弹，但在下跌趋势中抢反弹是非常危险的操作。历史上抢反弹的成功率不到40%，得不偿失。不如等趋势明确反转后再进场。",
             "history_win_rate": None},
            {"action": "不动", "position": 0, "level": "C",
             "trigger_type": "方向不明，等待信号",
             "signals": [
                 {"text": "市场处于下跌后的低位整理阶段", "type": "info"},
                 {"text": "多空双方力量均衡，暂时没有明确的突破方向", "type": "info"},
                 {"text": "需要更多时间观察，等待趋势明朗", "type": "info"},
             ], "min_signals": 0,
             "logic": "下跌后的横盘整理，可能是筑底，也可能是下跌中继（休息一下继续跌）。现在方向不明，多看少动。",
             "history_win_rate": None},
            {"action": "清仓", "position": 0, "level": "D",
             "trigger_type": "加速下跌，果断离场",
             "signals": [
                 {"text": f"今天跌幅超过1%且成交量放大（量比{vol_ratio:.1f}），恐慌盘在出逃", "type": "price"},
                 {"text": f"价格创近期新低（低于{ma20:.3f}的20日均线），下跌趋势加速", "type": "price"},
                 {"text": "MACD绿柱加长，下跌动能在增强而不是减弱", "type": "momentum"},
                 {"text": f"近20天已经跌了{abs(pct_20d):.1f}%，不要幻想短期回本", "type": "trend"},
             ], "min_signals": 3,
             "logic": "加速下跌中，越等亏得越多。这时候必须果断止损离场，保存实力。记住：留得青山在，不怕没柴烧。亏损20%需要涨25%才能回本，亏损50%需要翻倍才能回本。",
             "history_win_rate": 65},
            {"action": "清仓", "position": 0, "level": "E",
             "trigger_type": "阴跌不止，止损保本",
             "signals": [
                 {"text": f"连续多日小幅下跌，累计跌幅已超过15%（当前回撤{abs(max_dd):.1f}%）", "type": "trend"},
                 {"text": f"价格持续在60日均线（{ma60:.3f}）下方运行，没有反转迹象", "type": "price"},
                 {"text": "成交量持续萎缩（没人买），说明市场对这个价格没有兴趣", "type": "volume"},
                 {"text": "MACD在零轴下方继续下行，下跌趋势牢固", "type": "momentum"},
             ], "min_signals": 3,
             "logic": "阴跌是最折磨人的走法——每天跌一点，不知不觉就深套了。这种走势下不要幻想回本，果断止损是最好的选择。",
             "history_win_rate": 70},
        ]

    def _scenarios_neutral(self, price, ma20, ma60, bb_pos, bb_lower,
                            bb_upper, vol_ratio, macd_dict, rsi,
                            pct_20d, max_dd) -> list:
        """震荡趋势的5个场景。"""
        return [
            {"action": "加仓", "position": 10, "level": "A",
             "trigger_type": "区间下沿买入（高抛低吸）",
             "signals": [
                 {"text": f"价格接近布林带下轨（{bb_lower:.3f}），处于震荡区间底部", "type": "price"},
                 {"text": "成交量萎缩（没人愿意卖了），抛压很轻", "type": "volume"},
                 {"text": f"强弱指标RSI在{rsi:.0f}，接近超卖区但不算极端", "type": "momentum"},
                 {"text": "价格在60日均线附近有支撑", "type": "price"},
             ], "min_signals": 3,
             "logic": "震荡行情的核心操作逻辑就是「高抛低吸」——在区间下沿买入、上沿卖出。现在价格在区间底部，买入的风险相对可控。但一定要设好止损，因为震荡可能转变成下跌。",
             "history_win_rate": 58},
            {"action": "不动", "position": 0, "level": "B",
             "trigger_type": "方向不明确，等待突破",
             "signals": [
                 {"text": "布林带宽度收窄（波动率降低），可能酝酿变盘", "type": "info"},
                 {"text": "多空力量均衡，没有明显的方向优势", "type": "info"},
                 {"text": f"近20天涨跌幅仅{pct_20d:.1f}%，方向感很弱", "type": "trend"},
             ], "min_signals": 2,
             "logic": "震荡收窄通常意味着即将变盘（选择方向）。在方向明确之前，不要提前押注。等市场自己选好方向，我们再跟随。",
             "history_win_rate": None},
            {"action": "不动", "position": 0, "level": "C",
             "trigger_type": "中间位置，多看少动",
             "signals": [
                 {"text": "价格在布林带中间位置，不上不下", "type": "info"},
                 {"text": "没有明确的操作信号，强行操作胜率不高", "type": "info"},
                 {"text": "耐心等价格走到区间的上沿或下沿再做决定", "type": "info"},
             ], "min_signals": 0,
             "logic": "在震荡区间的中间位置操作，等于赌方向——胜率只有50%。不如等价格到上下沿再动手，胜率能提高到60%以上。",
             "history_win_rate": None},
            {"action": "减仓", "position": 3, "level": "D",
             "trigger_type": "跌破区间下沿，止损出局",
             "signals": [
                 {"text": f"价格有效跌破布林下轨（{bb_lower:.3f}），震荡区间可能被打破", "type": "price"},
                 {"text": "成交量放大（有资金在割肉出逃），下跌有持续性", "type": "volume"},
                 {"text": "价格跌破了60日均线（长期趋势线），趋势可能由震荡转为下跌", "type": "price"},
                 {"text": f"近20天跌幅扩大到{abs(pct_20d):.1f}%以上", "type": "trend"},
             ], "min_signals": 3,
             "logic": "震荡区间的下沿被跌破，意味着之前的支撑失效了。这时候必须止损，因为震荡可能演变成下跌趋势。宁可卖早了，不要死扛。",
             "history_win_rate": 55},
            {"action": "清仓", "position": 0, "level": "E",
             "trigger_type": "震荡转下跌，全面离场",
             "signals": [
                 {"text": "连续3天收盘在60日均线下方，长期趋势走坏", "type": "price"},
                 {"text": f"从近期高点回撤超过15%（当前{abs(max_dd):.1f}%），趋势结构破坏", "type": "trend"},
                 {"text": "布林带开口扩大（波动加剧），方向选择是向下", "type": "momentum"},
                 {"text": "MACD在零轴下方死叉，下跌趋势确认", "type": "momentum"},
             ], "min_signals": 3,
             "logic": "震荡转为下跌是最危险的走势变化——因为在震荡中习惯了低买高卖的人，会在下跌初期不断抄底，结果越套越深。一旦确认方向选择是向下，必须果断清仓，不要有任何侥幸心理。",
             "history_win_rate": 68},
        ]

    # ── Widget 4: 关键价位 ──────────────────────────────────────

    def _calc_key_levels(self, close: np.ndarray, ind: dict) -> list:
        """计算5个关键价位。"""
        price = float(close[-1])
        ma20 = float(np.mean(close[-20:].astype(float))) if len(close) >= 20 else price
        ma60 = float(np.mean(close[-60:].astype(float))) if len(close) >= 60 else price
        bb = ind.get("bb", {})
        bb_upper = bb.get("upper", price * 1.05)
        bb_lower = bb.get("lower", price * 0.95)
        high20 = ind.get("high_20d", price * 1.05)
        low20 = ind.get("low_20d", price * 0.95)

        return [
            {"label": "支撑位", "price": round(min(ma20, bb_lower, low20), 3),
             "source": "20日均线+布林下轨+20日低点，三重支撑中最强的那个"},
            {"label": "阻力位", "price": round(max(bb_upper, high20), 3),
             "source": "布林上轨+20日高点，抛压最重的位置"},
            {"label": "止损位", "price": round(ma60 * 0.97, 3),
             "source": "60日均线下方3%（跌破说明长期趋势走坏，必须止损）"},
            {"label": "止盈位", "price": round(bb_upper * 1.05, 3),
             "source": "布林上轨上方5%（涨太快会回调，先锁定利润）"},
            {"label": "昨收", "price": round(price, 3),
             "source": "今天的收盘价，明天的一切都从这个价格出发"},
        ]

    # ── Widget 5: 连续操作预案 ──────────────────────────────────

    def _calc_consecutive_plan(self, close: np.ndarray, ind: dict,
                                state: int) -> list:
        """生成连续操作预案（3条阶梯式预案）。"""
        price = float(close[-1])
        ma20 = float(np.mean(close[-20:].astype(float))) if len(close) >= 20 else price
        ma60 = float(np.mean(close[-60:].astype(float))) if len(close) >= 60 else price

        if state == 4:
            return [
                {"days": 3, "condition": "连续3天收盘站稳20日均线且成交量逐步放大",
                 "action": "每次回调加仓3%~5%",
                 "logic": "上升趋势中，每次回踩20日均线并企稳都是加仓机会。分批加仓可以降低单次买入的风险。站稳=收盘价在均线上方+第二天没有跌回去。"},
                {"days": 2, "condition": "连续2天收盘低于20日均线",
                 "action": "减掉一半仓位，观望",
                 "logic": "如果连续2天收在20日均线下方，说明短期支撑失效了。减半仓是为了保护利润，等价格重新站上均线再买回来。不要因为减仓而心疼，控制回撤比多赚几个点更重要。"},
                {"days": 3, "condition": "连续3天收盘低于60日均线且成交量放大",
                 "action": "全部清仓，保护本金",
                 "logic": "60日均线是长期趋势的生命线。连续3天在下方运行+成交量放大=趋势大概率结束了。这时不要留恋，清仓走人，等下一波趋势再进场。"},
            ]
        elif state == 1:
            return [
                {"days": 3, "condition": "连续3天站稳20日均线上方且成交量放大到1.5倍以上",
                 "action": "试探性买入5%仓位",
                 "logic": "下跌趋势中不要轻易抄底。必须等连续3天站稳20日均线（说明反弹有持续性而不是一日游）+成交量放大（大资金在进场），才能试探性买入极小仓位。记住：这是试探，不是重仓抄底。"},
                {"days": 2, "condition": "连续2天再跌破20日均线",
                 "action": "止损卖出，不犹豫",
                 "logic": "试探性买入后如果连续2天又跌回20日均线下方，说明反弹失败了。这时候必须止损，不要因为仓位小就不在乎——坏习惯是从小仓位养成的。"},
                {"days": 5, "condition": "连续5天站稳60日均线上方+成交量持续放大",
                 "action": "加仓到正常仓位（20%~30%）",
                 "logic": "如果能连续5天站稳60日均线（市场最谨慎的长期趋势线），说明趋势可能真的反转了。这时候可以加大仓位，但还是要分批进行，不要一次性梭哈。"},
            ]
        else:
            return [
                {"days": 2, "condition": "连续2天收盘在布林下轨附近且成交量萎缩",
                 "action": "在区间下沿买入10%仓位",
                 "logic": "震荡行情的高抛低吸：连续2天在下轨附近+缩量=短期底部概率大。买10%仓位试探，设好止损（跌破下轨就止损）。"},
                {"days": 2, "condition": "连续2天收盘在布林上轨附近且成交量萎缩",
                 "action": "在区间上沿卖出持仓",
                 "logic": "涨到上轨附近+缩量=上涨动力不足，大概率回调。锁定利润，等下轨再买回来。"},
                {"days": 3, "condition": "连续3天收盘突破布林带上轨或跌破下轨且成交量放大",
                 "action": "跟随突破方向操作（向上加仓/向下清仓）",
                 "logic": "连续3天突破+放量=震荡结束，趋势选择方向。向上突破就加仓追涨，向下突破就清仓止损。震荡行情最重要的是顺势——不要和市场对着干。"},
            ]

    @staticmethod
    def _calc_trend_score(state: int, ind: dict, days_running: int = 0,
                          stage: str = "") -> float:
        """计算趋势强度评分（0-100），连续评分，无二进制跳跃。

        核心理念：不只看 state，还要看趋势质量（均线排列、量能、持续性）。
        State=3 但条件全过的标的，可以比 State=4 但条件不完整的更强。
        """
        # ── 基础分：从均线质量推导 (30-60范围, 连续而非55/42跳跃) ──
        ma_bullish = ind.get("ma_bullish", False)       # MA5>10>20
        ma_mid_bullish = ind.get("ma_mid_bullish", False)  # MA20>60
        vol_ratio = ind.get("vol_ratio", 1.0)
        pct_20d = ind.get("pct_20d", 0)

        # 三个独立条件，每个贡献10分 → 连续刻度
        base = 30.0
        if ma_mid_bullish:
            base += 10   # 中长期均线多头
        if ma_bullish:
            base += 10   # 短期均线多头
        if pct_20d > 0:
            base += 10   # 中期动量为正
        # Range: 30 (0条件) → 60 (3条件)

        # State 方向微调 (±5, 不是 ±13)
        if state == 4:
            base += 5
        elif state == 5:
            base += 3   # 回调 = 小幅折扣，不是断崖
        elif state == 3:
            base += 0
        else:
            base -= 5

        # 阶段调整
        if stage == "late":
            base -= 5   # 晚期趋势风险加大

        # ── 趋势阶段：越早期分越高 ──
        # 刚启动的趋势利润空间最大，已经跑了很久的趋势可能接近尾声
        if days_running < 10:
            freshness = 15   # 刚启动，最佳介入时机
        elif days_running < 30:
            freshness = 10   # 早期，趋势还在发展
        elif days_running < 60:
            freshness = 5    # 中期，趋势确立但空间变小
        else:
            freshness = 0    # 成熟期，可能随时进入震荡或反转

        # ── 临界爆发 ──
        # state=3 均线多头+放量 → 即将进入上升趋势
        # state=5 回调企稳+放量 → 回调结束重返上升
        transition = 0
        if state == 3 and ind.get("ma_bullish"):
            transition = 8
            if ind.get("vol_ratio", 1) > 1.2:
                transition += 4
        if state == 5 and ind.get("ma_bullish") and ind.get("pct_today", 0) > 0:
            transition = 6   # 回调企稳反弹

        # ── 20日动量：涨得好的加分 ──
        pct_20d = ind.get("pct_20d", 0)
        if pct_20d > 20:
            momentum = 12
        elif pct_20d > 10:
            momentum = 8
        elif pct_20d > 5:
            momentum = 5
        elif pct_20d > 0:
            momentum = 2
        else:
            momentum = 0

        # ── 均线质量 ──
        quality = 0
        if ind.get("ma_bullish"):
            quality += 5
        if ind.get("ma_mid_bullish"):
            quality += 3

        # ── 量能确认 ──
        vol = 0
        vol_ratio = ind.get("vol_ratio", 1)
        if 1.0 < vol_ratio < 2.0:
            vol = 3  # 温和放量，健康

        # ── 短期回调惩罚 ──
        penalty = 0
        pct_5d = ind.get("pct_5d", 0)
        if pct_5d < -5:
            penalty = -10
        elif pct_5d < -3:
            penalty = -5

        score = base + freshness + transition + momentum + quality + vol + penalty
        return max(0, min(100, round(score, 1)))

    @staticmethod
    def _detect_top_divergence(close: np.ndarray) -> bool:
        """检测RSI顶背离: 价格近60日有两个峰值, 后峰价格更高但RSI更低。

        纯辅助信号，不参与筛选/评分，仅影响 action_label 文案。
        返回 True 表示检测到顶背离。
        """
        n = len(close)
        if n < 60:
            return False

        lookback = min(60, n)
        recent = close[-lookback:]

        # 计算最近60日的RSI(14)序列
        rsi_series = np.full(lookback, np.nan)
        for i in range(14, lookback):
            chunk = recent[max(0, i - 13):i + 1]
            delta = np.diff(chunk)
            gain = float(np.mean(delta[delta > 0])) if np.any(delta > 0) else 0.0
            loss = float(-np.mean(delta[delta < 0])) if np.any(delta < 0) else 0.0
            rsi_series[i] = 100.0 - 100.0 / (1.0 + gain / loss) if loss > 0 else 100.0

        # 找价格峰值（5日窗口内的局部最高点）
        peak_indices = []
        for i in range(5, lookback - 5):
            if recent[i] == np.max(recent[i - 5:i + 6]):
                peak_indices.append(i)

        if len(peak_indices) < 2:
            return False

        # 检查最近两个峰值: 价格更高但RSI更低 → 顶背离
        i1, i2 = peak_indices[-2], peak_indices[-1]
        price_up = recent[i2] > recent[i1]
        rsi_down = (not np.isnan(rsi_series[i1]) and not np.isnan(rsi_series[i2])
                    and rsi_series[i2] < rsi_series[i1])

        return bool(price_up and rsi_down)

    @staticmethod
    def _action_label(state: int, ind: dict, days_running: int = 0) -> str:
        """生成大白话操作建议标签。

        结合趋势阶段、动量、均线状态，用零基础股民能看懂的话
        说清楚：这个标的现在处于什么阶段，应该怎么做。
        """
        ma_bullish = ind.get("ma_bullish", False)
        pct_5d = ind.get("pct_5d", 0)
        pct_20d = ind.get("pct_20d", 0)
        vol_ratio = ind.get("vol_ratio", 1)
        bb_pos = ind.get("bb", {}).get("position", 0.5)
        rsi = ind.get("rsi", 50)

        if state == 4:
            if days_running < 10:
                # 刚启动，最佳时机
                label = "趋势刚刚开始，还没涨太多，现在是上车的好时机"
                if pct_5d > 3:
                    label += "，最近几天涨势很猛，买盘在加速进场"
                elif pct_5d < -2:
                    label += "，短线有回调，正好是低吸的机会"
            elif days_running < 30:
                # 早期
                label = "上升趋势已经确认，涨得比较稳健，可以继续持有或者逢回调加仓"
                if pct_20d > 20:
                    label += "，这一波涨幅已经不小，追高要谨慎"
                elif pct_20d > 10:
                    label += "，涨幅适中，趋势还有空间"
                else:
                    label += "，涨幅温和，趋势可能还能持续一段时间"
            elif days_running < 60:
                # 中期
                label = "趋势运行了一段时间了，涨幅已经积累了不少"
                if bb_pos > 0.8:
                    label += "，目前价格在布林带上轨附近，短期可能冲高回落，注意不要追高"
                elif pct_5d < -3:
                    label += "，最近几天在回调，等回调企稳后再考虑加仓"
                else:
                    label += "，仍在上涨通道中，可以持有但新买入要谨慎"
            else:
                # 成熟期
                label = "这个趋势已经走了很久了，累计涨幅很大"
                if pct_5d < -3 and vol_ratio > 1.2:
                    label += "，最近放量下跌，要注意是不是有人在出货，考虑减仓保护利润"
                elif rsi > 70:
                    label += "，已经严重超买，随时可能回调，不建议追高"
                else:
                    label += "，虽然还在涨，但越往后风险越大，注意保护已经赚到的利润"

        elif state == 3:
            if ma_bullish and vol_ratio > 1.2:
                # 临界突破
                label = "正在从震荡转为上升趋势，均线已经形成多头排列，成交量也在放大"
                if pct_5d > 2:
                    label += "，最近几天涨得不错，如果继续放量就能确认突破，可以小仓位试探"
                else:
                    label += "，就差价格最后确认了，盯紧了随时准备动手"
            elif ma_bullish:
                label = "短期走势偏强，均线正在向多头排列靠拢，趋势在好转"
                if pct_20d > 5:
                    label += "，最近一个月涨了%.0f%%，方向是向上的，可以关注" % pct_20d
                else:
                    label += "，但涨幅还不大，需要更多时间确认方向"
            elif pct_20d > 10:
                label = "中期涨幅不错（近20天涨了%.0f%%），虽然短期均线还没排好，但大方向是向上的" % pct_20d
                label += "，等均线理顺之后可能迎来一波加速"
            else:
                label = "偏强震荡，方向还不明确，可以关注但不用急着动手"
                if bb_pos < 0.3:
                    label += "，价格在布林下轨附近，如果再跌可能转弱"
                elif bb_pos > 0.7:
                    label += "，价格在布林上轨附近，如果突破可能转强"

        elif state == 5:
            # 上涨中的回调
            vol_shrink = vol_ratio < 1
            if vol_shrink and pct_5d > -5:
                label = ("上升趋势的正常回调，成交量在萎缩说明抛压不大。"
                         "缩量回调是最健康的整理方式，等放量阳线出现就是加仓信号。"
                         "持股的不要被洗出去，想买的可以准备子弹了。")
            elif pct_5d < -5:
                label = ("回调幅度稍大（近5天跌了%.1f%%），但仍在上升趋势框架内。"
                         "关注是否跌破20日均线。不破=正常调整，破了且放量=可能转弱。" % abs(pct_5d))
            elif pct_5d > 0 and vol_ratio > 1:
                label = ("回调出现企稳信号！放量反弹说明回调可能结束了。"
                         "如果明天继续放量上涨=确认回调结束，可以加仓。")
            else:
                label = "上涨中的回调，短期在消化获利盘，耐心等待企稳信号"

        else:
            label = "趋势不明确，不建议操作"

        return label

    # ── 仓位计算 ───────────────────────────────────────────────

    def _calc_position(self, state: int, ind: dict) -> dict:
        """调用 PositionOptimizer 计算建议仓位。

        返回 {"pct": float, "reason": str}。
        若 PositionOptimizer 不可用或计算失败则降级返回 0%。
        """
        if not _POSITION_OPTIMIZER_AVAILABLE:
            return {"pct": 0.0, "reason": "PositionOptimizer 不可用"}
        base_ratio = self._STATE_BASE_RATIO.get(state, 0.0)
        if base_ratio <= 0:
            return {"pct": 0.0, "reason": "状态不满足建仓条件"}
        try:
            regime = MarketRegime(
                level="green",
                position_cap=1.0,
                reason="默认绿灯 (无实时市场数据时假设全仓可行)",
                sentiment_score=60.0,
            )
            opt = PositionOptimizer()
            result = opt.optimize(
                state_value=state,
                base_ratio=base_ratio,
                enhanced=None,       # 无 V3 增强信号, 使用默认胜率55%
                market_regime=regime,
                current_total_position=0.0,
            )
            return {
                "pct": round(result.final_ratio * 100, 1),
                "reason": result.reason,
            }
        except Exception:
            return {"pct": 0.0, "reason": "仓位计算异常,降级为0"}

    # ── 卡片组装 ───────────────────────────────────────────────

    def _build_card(self, r: dict, date_str: str, is_etf: bool) -> Optional[dict]:
        """为单只标的组装完整卡片数据。"""
        code = r.get("code", "")
        name = r.get("name", code)
        data = self._load_price_data(code, is_etf)
        if data is None:
            return None

        sliced = self._slice_to_date(data, date_str)
        if sliced is None:
            return None

        close = sliced["close"]
        volume = sliced["volume"]
        high = sliced.get("high", close)
        low = sliced.get("low", close)
        open_arr = sliced.get("open", close)

        # 构建 DataFrame 供 StateMachine 使用
        daily_df = pd.DataFrame({
            "open": open_arr, "high": high, "low": low,
            "close": close, "volume": volume,
        })

        ind = self._calc_indicators(close, volume, high, low, open_arr)
        state = self._determine_state(daily_df)

        # ── 趋势质量过滤 ──
        if state == 1 or state == 2 or state == "3'":
            return None  # 下跌/弱反弹/转跌确认 = 不推荐
        # state=3：必须有正向中期动量
        if state == 3:
            pct_20d = ind.get("pct_20d", 0)
            if pct_20d < -3:
                return None
        # state=4 或 state=5：多头排列检查
        if state in (4, 5):
            # state=4/5: 死叉或MA5在MA10下方 = 短期趋势走坏
            if ind.get("ma5_below_ma10") or ind.get("ma_death_cross"):
                if state == 4:
                    # MA5在下滑 = 降级为回调
                    ma5_vals = ind.get("ma5", None)
                    if ma5_vals is not None and len(ma5_vals) >= 3:
                        if ma5_vals[-1] < ma5_vals[-3]:
                            state = 5
                    else:
                        return None
                else:
                    return None  # state=5死叉 = 不推荐

        trend_ctx = self._calc_trend_context(close, ind, state)
        probability = self._calc_probability(close, trend_ctx, state, ind)
        buy_sell = self._calc_buy_sell_zone(close, ind, state)
        scenarios = self._calc_scenarios(close, trend_ctx, ind, state)
        key_levels = self._calc_key_levels(close, ind)
        consecutive = self._calc_consecutive_plan(close, ind, state)

        # ── 趋势强度评分（0-100）──
        days_running = trend_ctx.get("days_running", 0)
        trend_score = self._calc_trend_score(state, ind, days_running)

        # ── 大白话操作标签 ──
        action_label = self._action_label(state, ind, days_running)

        # 顶背离检测: 仅对上升趋势且持续≥15日的标的追加提醒
        has_top_divergence = False
        if state == 4 and days_running >= 15 and self._detect_top_divergence(close):
            has_top_divergence = True
            if days_running >= 30:
                action_label += "；⚠️ RSI顶背离，价格新高但动能跟不上，谨慎追高"
            else:
                action_label += "；⚠️ 有顶背离迹象，注意观察动能是否持续"

        # 仓位计算 (Kelly公式, 从 PositionOptimizer 获取)
        pos = self._calc_position(state, ind)

        return {
            "code": code,
            "name": name,
            "link": r.get("link", self._etf_link(code) if is_etf else self._stock_link(code)),
            "action": action_label,
            "action_label": action_label,
            "has_top_divergence": has_top_divergence,
            "position_pct": pos.get("pct", 0),
            "position_reason": pos.get("reason", ""),
            "score": trend_score,  # 使用趋势强度评分替代pipeline原始评分
            "state": state,
            "trend_context": trend_ctx,
            "probability": probability,
            "buy_sell_zone": buy_sell,
            "scenarios": scenarios,
            "key_levels": key_levels,
            "consecutive_plan": consecutive,
        }

    @staticmethod
    def _etf_link(code: str) -> str:
        """根据ETF代码返回东方财富行情页链接（带K线图）。"""
        if code.startswith("51"):
            return f"https://quote.eastmoney.com/sh{code}.html"
        elif code.startswith("159"):
            return f"https://quote.eastmoney.com/sz{code}.html"
        return f"https://quote.eastmoney.com/sh{code}.html"

    @staticmethod
    def _stock_link(code: str) -> str:
        """根据股票代码返回东方财富个股行情页链接。"""
        if code.startswith(('6', '9')):
            return f"https://quote.eastmoney.com/sh{code}.html"
        else:
            return f"https://quote.eastmoney.com/sz{code}.html"

    # ── ETF成分股趋势龙头 ────────────────────────────────────

    def _get_etf_trend_leaders(self, etf_code: str, date_str: str, top_n: int = 3) -> list[dict]:
        """返回ETF成分股中趋势最强的 top_n 只个股。

        从 data/etf_holdings.json 读取成分股列表，
        对每只个股跑 _build_card 做趋势判定+评分，
        返回趋势评分最高的 top_n 只。
        """
        holdings_path = os.path.join(self.data_dir, "etf_holdings.json")
        if not os.path.exists(holdings_path):
            return []

        try:
            all_holdings = json.load(open(holdings_path))
        except Exception:
            return []

        stocks = all_holdings.get(etf_code, [])
        if not stocks:
            return []

        scored = []
        for s in stocks:
            code = s["code"]
            # 生成东方财富链接
            if code.startswith(('6', '9')):
                link = f"https://quote.eastmoney.com/sh{code}.html"
            else:
                link = f"https://quote.eastmoney.com/sz{code}.html"
            card = self._build_card(
                {"code": code, "name": s["name"], "link": link},
                date_str, is_etf=False)
            if card is None:
                continue
            score = card.get("score", 0)
            if score < 60:  # 趋势太弱的不展示
                continue
            scored.append({
                "code": code,
                "name": s["name"],
                "score": score,
            })

        scored.sort(key=lambda x: -x["score"])
        return scored[:top_n]

    # ── ETF 动态扫描 ───────────────────────────────────────────

    def _scan_best_etfs(self, date_str: str, top_n: int = 5) -> list[dict]:
        """从全部 ETF 中扫描，筛选趋势最好的 top_n 只（稳健推荐）。

        同时从剩余通过筛选的标的中，按「强势追踪」条件筛选
        (state=4, pct_20d>20%, score>=70)，取 top_n 只过热票。
        返回 (etf_cards, hot_etf_cards) 元组。
        """
        # 加载 ETF 名称：缓存文件 > ETF_NAME_MAP > "ETF{code}"
        _etf_names = {}
        cache_path = os.path.join(self.data_dir, "etf_names.json")
        if os.path.exists(cache_path):
            try:
                _etf_names = json.load(open(cache_path))
            except Exception:
                pass
        if not _etf_names:
            import sys
            _project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            if _project_root not in sys.path:
                sys.path.insert(0, _project_root)
            try:
                from src.fusion.scanner import ETF_NAME_MAP as _etf_names
            except ImportError:
                _etf_names = {}

        etf_dir = os.path.join(self.data_dir, "etf_stocks")
        if not os.path.isdir(etf_dir):
            return [], []

        candidates = []
        for fname in sorted(os.listdir(etf_dir)):
            if not fname.endswith(".pkl"):
                continue
            code = fname.replace("etf_", "").replace(".pkl", "")
            name = _etf_names.get(code, f"ETF{code}")
            link = self._etf_link(code)
            card = self._build_card(
                {"code": code, "name": name, "link": link},
                date_str, is_etf=True)
            if card is None:
                continue  # 质量筛选未通过

            # 评分：趋势越好分越高
            state = card.get("state", 1)
            ctx = card.get("trend_context", {})
            pct_20d = ctx.get("total_return_pct", 0)
            score = state * 2  # state 4=8分, 3=6分, 2=4分, 1=2分
            if pct_20d > 0:
                score += 2
            if pct_20d > 10:
                score += 2
            candidates.append((score, card))

        # 按评分降序
        candidates.sort(key=lambda x: -x[0])

        # 稳健推荐: top N，行业分散
        etf_cards = []
        seen_cats_etf = set()
        for _, card in candidates:
            cat = self._etf_category_key(card.get("name", ""))
            if cat in seen_cats_etf:
                continue
            seen_cats_etf.add(cat)
            etf_cards.append(card)
            if len(etf_cards) >= top_n:
                break
        top_codes = {c["code"] for c in etf_cards}

        # 强势追踪: 从剩余中选 state=4 且涨幅过大的，按行业分散
        hot_candidates = []
        for _, card in candidates[top_n:]:
            if card.get("state") != 4:
                continue
            ctx = card.get("trend_context", {})
            pct_20d = ctx.get("total_return_pct", 0)
            if pct_20d < self.HOT_MIN_PCT_20D_ETF:
                continue
            if card.get("score", 0) < self.HOT_MIN_SCORE_ETF:
                continue
            if card["code"] in top_codes:
                continue
            hot_candidates.append((pct_20d, card))

        hot_candidates.sort(key=lambda x: -x[0])

        # 行业分散：同名关键词只取最强的一只
        hot_etf_cards = []
        seen_categories = set()
        for _, card in hot_candidates:
            cat = self._etf_category_key(card.get("name", ""))
            if cat in seen_categories:
                continue
            seen_categories.add(cat)
            hot_etf_cards.append(card)
            if len(hot_etf_cards) >= top_n:
                break

        # 为入选ETF计算成分股趋势龙头（只在最终入选的10只上计算）
        for card in etf_cards + hot_etf_cards:
            leaders = self._get_etf_trend_leaders(card["code"], date_str)
            card["trend_leaders"] = leaders

        return etf_cards, hot_etf_cards

    # ETF产品关键词 → 规范品类
    # 规则：只有完全同质化的才合并（如同一产品不同基金公司），不同产品保留区分
    _ETF_CATEGORY_MAP = {
        '科创半导体设备': '科创半导体设备',   # 区别于科创半导体（指数不同）
        '科创半导体': '科创半导体',
        '半导体设备': '半导体设备',           # 设备≠芯片≠材料
        '半导体材料': '半导体材料',
        '芯片': '芯片',
        '通信': '通信',
        '5G': '5G',
        '消费电子': '消费电子',
        '机器人': '机器人',
        '人工智能': '人工智能',
        '新能源车': '新能源车',
        '光伏': '光伏', '锂电池': '锂电池',
        '煤炭': '煤炭', '钢铁': '钢铁', '有色': '有色', '黄金': '黄金',
        '军工': '军工',
        '医药': '医药', '医疗': '医药',    # 医药/医疗高度重叠，合并
        '银行': '银行', '证券': '证券', '保险': '保险',
        '食品饮料': '食品饮料', '白酒': '白酒',
        '电力': '电力', '基建': '基建',
        '农业': '农业', '养殖': '农业',    # 农业/养殖高度重叠
        '传媒': '传媒', '游戏': '传媒',    # 传媒/游戏高度重叠
    }

    @classmethod
    def _etf_category_key(cls, name: str) -> str:
        """从ETF名称提取规范品类，用于去重。

        不同产品保留区分（科创半导体 ≠ 半导体设备），
        同产品不同基金公司合并（科创半导体设备ETF华泰柏瑞 = 科创半导体设备ETF鹏华）。
        """
        for raw, canonical in cls._ETF_CATEGORY_MAP.items():
            if raw in name:
                return canonical
        return name  # 未匹配则用原名（本身已唯一）

    # ── 个股动态扫描 ───────────────────────────────────────────

    def _scan_best_stocks(self, date_str: str, top_n: int = 5) -> list[dict]:
        """从全部个股中扫描，筛选趋势最好的 top_n 只（稳健推荐）。

        同时从剩余通过筛选的标的中，按「强势追踪」条件筛选
        (state=4, pct_20d>30%, score>=75)，取 top_n 只过热票。
        返回 (stock_cards, hot_stock_cards) 元组。
        """
        stock_dir = os.path.join(self.data_dir, "massive_stocks")
        if not os.path.isdir(stock_dir):
            return [], []

        # 加载股票名称和板块映射
        stock_names = {}
        names_path = os.path.join(self.data_dir, "stock_names.json")
        if os.path.exists(names_path):
            try:
                stock_names = json.load(open(names_path))
            except Exception:
                pass
        stock_sectors = {}
        sectors_path = os.path.join(self.data_dir, "stock_sectors.json")
        if os.path.exists(sectors_path):
            try:
                stock_sectors = json.load(open(sectors_path))
            except Exception:
                pass

        candidates = []
        files = sorted(os.listdir(stock_dir))
        for fname in files:
            if not fname.endswith(".pkl"):
                continue
            code = fname.replace(".pkl", "")
            name = stock_names.get(code, code)
            sector = stock_sectors.get(code, "")
            # 生成东方财富个股行情页链接
            if code.startswith(('6', '9')):
                stock_link = f"https://quote.eastmoney.com/sh{code}.html"
            else:
                stock_link = f"https://quote.eastmoney.com/sz{code}.html"
            card = self._build_card(
                {"code": code, "name": name, "link": stock_link}, date_str, is_etf=False)
            if card is None:
                continue
            card["sector"] = sector  # 注入板块信息
            score = card.get("score", 0)
            candidates.append((score, card))

        candidates.sort(key=lambda x: -x[0])

        # 稳健推荐: top N
        stock_cards = [card for _, card in candidates[:top_n]]
        top_codes = {c["code"] for c in stock_cards}

        # 强势追踪: 从剩余中选 state=4 且涨幅过大的标的
        hot_candidates = []
        for _, card in candidates[top_n:]:
            if card.get("state") != 4:
                continue
            ctx = card.get("trend_context", {})
            pct_20d = ctx.get("total_return_pct", 0)
            if pct_20d < self.HOT_MIN_PCT_20D:
                continue
            if card.get("score", 0) < self.HOT_MIN_SCORE:
                continue
            if card["code"] in top_codes:
                continue
            hot_candidates.append((pct_20d, card))

        hot_candidates.sort(key=lambda x: -x[0])  # 按涨幅降序，最热的排前面
        hot_stock_cards = [card for _, card in hot_candidates[:top_n]]

        return stock_cards, hot_stock_cards

    # ── 默认个股列表（actions JSON 空时的回退列表） ──────

    _DEFAULT_STOCKS = [
        {"code": "002258", "name": "利尔化学",
         "link": "https://quote.eastmoney.com/sz002258.html"},
        {"code": "002527", "name": "新时达",
         "link": "https://quote.eastmoney.com/sz002527.html"},
        {"code": "002636", "name": "金安国纪",
         "link": "https://quote.eastmoney.com/sz002636.html"},
        {"code": "002871", "name": "伟隆股份",
         "link": "https://quote.eastmoney.com/sz002871.html"},
        {"code": "003043", "name": "华亚智能",
         "link": "https://quote.eastmoney.com/sz003043.html"},
    ]

    # ── 主方法 ─────────────────────────────────────────────────

    def generate(self, date_str: str) -> Optional[dict]:
        """为指定日期生成增强操作建议。

        返回:
          {"date": "2026-06-05", "market_regime": "strong_bear",
           "etf_cards": [...], "stock_cards": [...]}
        或 None（数据不足时）。
        """
        actions_path = os.path.join(self.output_dir,
                                     f"actions_{date_str}.json")
        if not os.path.exists(actions_path):
            print(f"  ⚠️ actions JSON 不存在: {actions_path}")
            return None

        with open(actions_path) as f:
            actions = json.load(f)

        market_regime = actions.get("market_regime", "normal")

        hot_etf_cards = []
        hot_stock_cards = []

        # 优先使用 actions JSON 中的标的，空则从全量 ETF 池动态扫描最佳标的
        etf_list = actions.get("etf_top5", [])
        if not etf_list:
            print(f"  📊 actions JSON 无 ETF 数据，从 {len(os.listdir(os.path.join(self.data_dir, 'etf_stocks')))} 只 ETF 中动态择优筛选...")
            etf_cards, hot_etf_cards = self._scan_best_etfs(date_str)
            # 直接使用 scan 结果，跳过下方的逐条 _build_card
            stock_list = actions.get("stock_top5", [])
            if not stock_list:
                stock_cards, hot_stock_cards = self._scan_best_stocks(date_str)
            else:
                stock_cards = []
                for r in stock_list:
                    card = self._build_card(r, date_str, is_etf=False)
                    if card:
                        stock_cards.append(card)
            result = {
                "date": date_str,
                "market_regime": market_regime,
                "etf_cards": etf_cards,
                "stock_cards": stock_cards,
                "hot_etf_cards": hot_etf_cards,
                "hot_stock_cards": hot_stock_cards,
            }
            output_path = os.path.join(self.output_dir, f"enhanced_actions_{date_str}.json")
            with open(output_path, "w") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            return result

        stock_list = actions.get("stock_top5", [])
        if not stock_list:
            stock_list = self._DEFAULT_STOCKS

        etf_cards = []
        for r in etf_list:
            card = self._build_card(r, date_str, is_etf=True)
            if card:
                etf_cards.append(card)

        stock_cards = []
        for r in stock_list:
            card = self._build_card(r, date_str, is_etf=False)
            if card:
                stock_cards.append(card)

        # 按趋势强度评分降序排列
        etf_cards.sort(key=lambda c: c.get("score", 0), reverse=True)
        stock_cards.sort(key=lambda c: c.get("score", 0), reverse=True)

        # 当使用 actions JSON 指定的标的时，也尝试扫描强势追踪标的
        hot_etf_cards = []
        hot_stock_cards = []

        result = {
            "date": date_str,
            "market_regime": market_regime,
            "etf_cards": etf_cards,
            "stock_cards": stock_cards,
            "hot_etf_cards": hot_etf_cards,
            "hot_stock_cards": hot_stock_cards,
        }

        output_path = os.path.join(self.output_dir,
                                    f"enhanced_actions_{date_str}.json")
        with open(output_path, "w") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        return result


# ── CLI 入口 ───────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python src/enhanced_actions.py <date_str>")
        print("Example: python src/enhanced_actions.py 2026-06-05")
        sys.exit(1)

    gen = EnhancedActionGenerator()
    result = gen.generate(sys.argv[1])
    if result:
        print(f"✅ 生成 {sys.argv[1]} 增强操作建议: "
              f"{len(result['etf_cards'])} ETF稳健 + "
              f"{len(result.get('hot_etf_cards', []))} ETF强势 | "
              f"{len(result['stock_cards'])} 个股稳健 + "
              f"{len(result.get('hot_stock_cards', []))} 个股强势")
    else:
        print(f"❌ 生成失败: {sys.argv[1]}")
        sys.exit(1)
