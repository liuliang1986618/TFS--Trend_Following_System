from pathlib import Path

import pandas as pd

from v2.data_layer import DataLayer
from v2.engine import TrendEngine
from v2.engine.indicators import calculate_indicators
from v2.engine.signal import StrategySignal


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
