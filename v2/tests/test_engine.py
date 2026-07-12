from pathlib import Path

import numpy as np
import pandas as pd

from v2.data_layer import DataLayer
from v2.engine import TrendEngine
from v2.engine.indicators import calculate_indicators, rsi
from v2.engine.levels import PivotDetector, _is_limit_day
from v2.engine.analyzers import PullbackAnalyzer
from v2.engine.signal import StrategySignal
from tests.conftest import make_ohlcv


def _write_trending_symbol(data_dir: Path, dtype: str = "stock", code: str = "300308") -> None:
    target = data_dir / dtype
    target.mkdir(parents=True, exist_ok=True)
    rows = []
    for i in range(260):
        close = 10 + i * 0.08
        rows.append(
            {
                "date": pd.Timestamp("2026-01-01") + pd.Timedelta(days=i),
                "open": close - 0.08,
                "high": close + 0.18,
                "low": close - 0.20,
                "close": close,
                "volume": 1000 + i * 10,
            }
        )
    pd.DataFrame(rows).to_parquet(target / f"{code}.parquet")


def test_calculate_indicators_matches_core_legacy_fields():
    df = pd.DataFrame(
        {
            "date": pd.date_range("2026-01-01", periods=80),
            "open": [10 + i * 0.1 for i in range(80)],
            "high": [10.2 + i * 0.1 for i in range(80)],
            "low": [9.8 + i * 0.1 for i in range(80)],
            "close": [10 + i * 0.1 for i in range(80)],
            "volume": [1000 + i * 5 for i in range(80)],
        }
    )

    indicators = calculate_indicators(df)

    assert indicators["ma_bullish"] is True
    assert indicators["ma_mid_bullish"] is True
    assert indicators["macd"]["dif"] > indicators["macd"]["dea"]
    assert indicators["rsi"] > 50
    assert 0 <= indicators["bb"]["position"] <= 1.5


def test_trend_engine_analyze_symbol_returns_stable_strategy_signal(tmp_path):
    _write_trending_symbol(tmp_path)
    engine = TrendEngine(DataLayer(tmp_path))

    signal = engine.analyze_symbol("stock", "300308", name="三六零")

    assert isinstance(signal, StrategySignal)
    assert signal.code == "300308"
    assert signal.name == "三六零"
    assert signal.dtype == "stock"
    assert signal.market_date == "2026-09-17"
    assert signal.state in (3, 4, 5)
    assert signal.state_label
    assert 0 <= signal.score <= 100
    assert 0 <= signal.confidence <= 1
    assert signal.scenario_estimate["up"] >= signal.scenario_estimate["down"]
    assert signal.position_hint["pct"] <= 50.0
    assert signal.position_hint["cap_reason"] == "market_context_unknown"
    assert signal.indicators["ma_bullish"] is True
    assert "old_score_150" in signal.signals


def test_trend_engine_rejects_short_history(tmp_path):
    target = tmp_path / "stock"
    target.mkdir(parents=True)
    pd.DataFrame(
        {
            "date": pd.date_range("2026-01-01", periods=10),
            "open": [1.0] * 10,
            "high": [1.1] * 10,
            "low": [0.9] * 10,
            "close": [1.0] * 10,
            "volume": [1000] * 10,
        }
    ).to_parquet(target / "short.parquet")

    engine = TrendEngine(DataLayer(tmp_path))

    try:
        engine.analyze_symbol("stock", "short")
    except ValueError as exc:
        assert "insufficient history" in str(exc)
    else:
        raise AssertionError("short history should be rejected")


def test_trend_engine_run_universe_returns_ranked_candidates(tmp_path):
    _write_trending_symbol(tmp_path, code="300308")
    _write_trending_symbol(tmp_path, code="002230")
    target = tmp_path / "stock"
    pd.DataFrame(
        {
            "date": pd.date_range("2026-01-01", periods=10),
            "open": [1.0] * 10,
            "high": [1.1] * 10,
            "low": [0.9] * 10,
            "close": [1.0] * 10,
            "volume": [1000] * 10,
        }
    ).to_parquet(target / "short.parquet")

    engine = TrendEngine(DataLayer(tmp_path))

    signals = engine.run_universe("stock", max_candidates=1)

    assert len(signals) == 1
    assert isinstance(signals[0], StrategySignal)
    assert signals[0].dtype == "stock"
    assert signals[0].code in {"300308", "002230"}
    assert signals[0].score >= 0


def test_trend_engine_scan_stock_funnel_groups_candidates_by_relations(tmp_path):
    _write_trending_symbol(tmp_path, code="300308")
    relations_dir = tmp_path / "meta" / "relations"
    relations_dir.mkdir(parents=True)
    (relations_dir / "current.json").write_text(
        '{"version":"2026-W27","source":"eastmoney","sectors":[{"code":"BK1036","name":"半导体"}],"themes":[{"code":"BK0800","name":"人工智能"}],"sector_members":{"BK1036":["300308"]},"theme_members":{"BK0800":["300308"]},"stock_profiles":{"300308":{"name":"中际旭创","sectors":["BK1036"],"themes":["BK0800"]}}}',
        encoding="utf-8",
    )
    engine = TrendEngine(DataLayer(tmp_path))

    result = engine.scan_stock_funnel(max_candidates=5)

    assert result["relation_version"] == "2026-W27"
    assert result["stocks"][0].code == "300308"
    assert result["sectors"][0]["code"] == "BK1036"
    assert result["sectors"][0]["candidate_count"] == 1
    assert result["themes"][0]["code"] == "BK0800"
    assert result["themes"][0]["candidate_count"] == 1


def test_trend_engine_scan_etf_direct_uses_etf_universe(tmp_path):
    _write_trending_symbol(tmp_path, dtype="etf", code="512760")
    engine = TrendEngine(DataLayer(tmp_path))

    signals = engine.scan_etf_direct(max_candidates=3)

    assert len(signals) == 1
    assert signals[0].dtype == "etf"
    assert signals[0].code == "512760"


def test_rsi_matches_wilder_standard():
    """验证RSI符合Wilder标准算法。"""
    # 使用Wikipedia上的RSI示例数据
    close = np.array([44, 44.34, 44.09, 43.61, 44.33, 44.83, 45.10, 45.42, 45.84, 46.08,
                      45.89, 46.03, 45.61, 46.28, 46.28, 46.00, 46.03, 46.41, 46.22, 45.64])
    rsi_val = rsi(close, period=14)
    # 手动计算Wilder RSI（初始avg_gain=0.0871, avg_loss=0.0586）
    # 期望RSI ≈ 59.88
    assert 55 < rsi_val < 65


def test_rsi_short_data_returns_50():
    """验证数据不足时RSI返回50。"""
    close = np.array([44, 44.34, 44.09])
    rsi_val = rsi(close, period=14)
    assert rsi_val == 50.0


def test_pivot_detector_skips_limit_days():
    """验证枢轴点检测跳过涨跌停日。"""
    # 构造包含涨跌停日的数据
    dates = pd.date_range("2026-01-01", periods=20, freq="B")
    # 第10日涨10%（涨停）
    closes = [10 + i * 0.1 for i in range(10)] + [20] + [20 - i * 0.1 for i in range(9)]
    opens = [10 + i * 0.1 for i in range(10)] + [18] + [20 - i * 0.1 for i in range(9)]
    
    df = make_ohlcv(dates, closes, [1000000] * 20, opens)
    highs = PivotDetector.find_highs(df, window=3)
    
    # 涨停日（第10日）不应成为枢轴点
    limit_day_idx = df.index[10]
    assert limit_day_idx not in highs.index


def test_is_limit_day_detection():
    """验证涨跌停日检测函数。"""
    # 构造包含涨跌停日的数据
    dates = pd.date_range("2026-01-01", periods=5, freq="B")
    # 第2日涨10%（涨停）
    closes = [10, 11, 10.5, 10.2, 10.1]
    opens = [10, 10, 10.5, 10.2, 10.1]
    
    df = make_ohlcv(dates, closes, [1000000] * 5, opens)
    
    # 非涨跌停日
    assert _is_limit_day(df, 0) == False
    # 涨停日
    assert _is_limit_day(df, 1) == True
    # 非涨跌停日
    assert _is_limit_day(df, 2) == False


def test_pullback_analyzer_healthy():
    """验证回调分析器健康回调识别。"""
    # 构造健康回调数据（缩量、未破位、浅回调）
    n = 80
    dates = pd.date_range("2026-01-01", periods=n, freq="B")
    # 先涨后小幅回调
    closes = [10 + i * 0.1 for i in range(60)] + [16 - i * 0.05 for i in range(20)]
    opens = closes.copy()
    # 回调时大幅缩量（确保vol_ratio < 0.8）
    volumes = [1000000] * 60 + [100000] * 20
    
    df = make_ohlcv(dates, closes, volumes, opens)
    
    profile = PullbackAnalyzer.analyze(df, peak_price=16.0)
    
    assert profile is not None
    assert profile.is_healthy == True
    assert profile.volume_pattern == "shrinking"
    assert profile.broke_prev_low == False


def test_pullback_analyzer_unknown_pivot():
    """验证PivotDetector失败时回调标记为不健康。"""
    # 构造数据不足的场景（<60日）
    dates = pd.date_range("2026-01-01", periods=30, freq="B")
    closes = [10 + i * 0.1 for i in range(30)]
    df = make_ohlcv(dates, closes, [1000000] * 30)
    
    profile = PullbackAnalyzer.analyze(df)
    
    # 数据不足返回None，不会产生错误
    assert profile is None


def test_trend_filters_limit_day():
    """验证涨跌停日被趋势过滤。"""
    from v2.engine.filters import apply_trend_filters
    
    # 构造涨跌停日数据（最后一天是涨跌停日）
    dates = pd.date_range("2026-01-01", periods=5, freq="B")
    closes = [10, 10.1, 10.2, 10.3, 11]  # 最后一天涨10%（涨停）
    opens = [10, 10.1, 10.2, 10.3, 10]   # 开盘10，收盘11
    
    df = make_ohlcv(dates, closes, [1000000] * 5, opens)
    
    # 涨跌停日应该被过滤
    passed, reasons = apply_trend_filters(4, {}, df)
    assert passed == False
    assert "limit_up_down_day" in reasons
    
    # 非涨跌停日不应该被过滤
    passed, reasons = apply_trend_filters(4, {}, df.iloc[:4])
    assert passed == True
    assert "limit_up_down_day" not in reasons
