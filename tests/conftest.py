"""共享测试fixtures：生成模拟日K线数据。"""
import pytest
import pandas as pd
import numpy as np


def make_ohlcv(dates, prices, volumes, opens=None):
    """根据收盘价序列生成完整OHLCV DataFrame。

    dates: list of str 'YYYY-MM-DD'
    prices: list of float 收盘价序列
    volumes: list of int 成交量序列
    opens: list of float 开盘价序列（可选，默认与收盘价相等）
    """
    n = len(prices)
    if opens is None:
        opens = [prices[i] for i in range(n)]
    data = {
        "date": pd.to_datetime(dates),
        "open": opens,
        "high": [max(opens[i], prices[i]) * 1.02 for i in range(n)],
        "low": [min(opens[i], prices[i]) * 0.98 for i in range(n)],
        "close": prices,
        "volume": volumes,
    }
    df = pd.DataFrame(data)
    df.set_index("date", inplace=True)
    for i in range(n):
        df.iloc[i, df.columns.get_loc("high")] = max(df.iloc[i]["open"], df.iloc[i]["close"]) * 1.01
        df.iloc[i, df.columns.get_loc("low")] = min(df.iloc[i]["open"], df.iloc[i]["close"]) * 0.99
    return df


@pytest.fixture
def uptrend_daily():
    """构造一个标准上涨趋势的40日日K序列。

    叠加正弦波制造清晰的局部高点和低点，确保前高/前低检测正常工作。
    每个周期的高点依次抬高、低点依次抬高，形成上涨结构。
    """
    np.random.seed(42)
    n = 40
    dates = pd.date_range("2026-03-01", periods=n, freq="B")
    trend = np.linspace(10, 15, n)
    # 叠加正弦波制造3个完整周期，每个周期有一个清晰高点和低点
    wave = np.sin(np.linspace(0, 3 * 2 * np.pi, n)) * 0.7
    noise = np.random.randn(n) * 0.06
    closes = trend + wave + noise
    closes = np.maximum(closes, 1.0)
    # 阳线为主(约80%): close > open
    opens = closes - np.abs(np.random.randn(n) * 0.10) - 0.02
    base_vol = 1_000_000
    volumes = []
    for i in range(n):
        if closes[i] > opens[i]:
            vols = int(base_vol * (1.3 + np.random.random() * 0.5))
        else:
            vols = int(base_vol * (0.6 + np.random.random() * 0.4))
        volumes.append(vols)
    return make_ohlcv(dates, closes.tolist(), volumes, opens.tolist())


@pytest.fixture
def downtrend_daily():
    """构造一个标准下跌趋势的40日日K序列。

    叠加正弦波制造清晰的局部高点和低点，前高/前低依次降低。
    """
    np.random.seed(99)
    n = 40
    dates = pd.date_range("2026-03-01", periods=n, freq="B")
    trend = np.linspace(20, 13, n)
    # 叠加正弦波制造清晰的高点和低点
    wave = np.sin(np.linspace(0, 3 * 2 * np.pi, n)) * 0.7
    noise = np.random.randn(n) * 0.06
    closes = trend + wave + noise
    closes = np.maximum(closes, 1.0)
    # 阴线为主(约80%): close < open
    opens = closes + np.abs(np.random.randn(n) * 0.10) + 0.02
    base_vol = 1_000_000
    volumes = []
    for i in range(n):
        if closes[i] < opens[i]:
            vols = int(base_vol * (1.3 + np.random.random() * 0.5))
        else:
            vols = int(base_vol * (0.6 + np.random.random() * 0.4))
        volumes.append(vols)
    return make_ohlcv(dates, closes.tolist(), volumes, opens.tolist())


@pytest.fixture
def sideways_daily():
    """构造一个横盘震荡的40日日K序列。"""
    np.random.seed(55)
    n = 40
    dates = pd.date_range("2026-03-01", periods=n, freq="B")
    closes = 10 + np.random.randn(n) * 0.3
    closes = np.maximum(closes, 1.0)
    volumes = [int(1_000_000 * (1.0 + np.random.random())) for _ in range(n)]
    return make_ohlcv(dates, closes.tolist(), volumes)


@pytest.fixture
def position_data():
    """示例持仓数据。"""
    return {
        "total_asset": 330700,
        "available_cash": 43200,
        "holdings": [
            {
                "symbol": "300308", "name": "中际旭创", "type": "stock",
                "cost": 152.30, "shares": 400, "current_weight": 0.25,
            },
            {
                "symbol": "512480", "name": "半导体ETF", "type": "etf",
                "cost": 0.842, "shares": 100000, "current_weight": 0.25,
            },
            {
                "symbol": "159819", "name": "AI智能ETF", "type": "etf",
                "cost": 1.052, "shares": 50000, "current_weight": 0.15,
            },
        ],
    }
