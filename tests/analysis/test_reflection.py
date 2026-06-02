"""反思引擎 + 规则发现 + 数据完整性校验 单元测试。

覆盖:
  - 反思引擎: 正确/错误推演的反思、模式提取、错误分类
  - 规则发现: 频率分析、模式挖掘、纠错规则
  - 数据完整性校验: 正常数据通过、残缺数据报警
  - 权重调整: 增量限制、归一化

所有测试使用合成数据，不读取任何生产文件。
"""
import pytest
import json
import os
import tempfile
from src.analysis.reflection import (
    ReflectionEngine, ReflectionEntry, LearnedPattern,
    validate_results_integrity,
)
from src.analysis.rule_discovery import (
    RuleDiscovery, DiscoveredRule, validate_history_cache,
)
from src.analysis.projection_weights import ProjectionWeights
from src.analysis.projection_backtest import ProjectionResult


def make_result(date, symbol, cur, pred, actual, scenario, correct, partial=False):
    """快速创建ProjectionResult的工厂函数。"""
    return ProjectionResult(
        date=date, symbol=symbol, current_state=cur,
        predicted_state=pred, actual_state=actual,
        scenario_label=scenario, is_correct=correct, is_partial=partial)


class TestReflectionEngine:
    """反思引擎测试。"""

    @pytest.fixture
    def sample_results(self):
        """创建模拟推演结果（合成数据，无生产依赖）。"""
        results = []
        for i in range(100):
            results.append(make_result(
                f"2026-05-{min(i+1,28):02d}", f"8811{i%10+1:02d}",
                "4", "4", "4", "场A(大概率)", True))
        for i in range(50):
            results.append(make_result(
                f"2026-05-{min(i+1,28):02d}", f"8811{i%10+1:02d}",
                "3", "4", "4", "场B(中概率)", True))
        for i in range(20):
            results.append(make_result(
                f"2026-05-{min(i+1,28):02d}", f"8811{i%10+1:02d}",
                "4", "3p", "4", "场C(小概率)", False))
        for i in range(15):
            results.append(make_result(
                f"2026-05-{min(i+1,28):02d}", f"8811{i%10+1:02d}",
                "1", "1", "2", "场A(大概率)", False))
        return results

    def test_reflect_basic(self, sample_results):
        engine = ReflectionEngine()
        entries, patterns = engine.reflect(sample_results)
        assert len(entries) == len(sample_results)
        correct = sum(1 for e in entries if e.is_correct)
        assert correct == 150

    def test_error_classification(self, sample_results):
        engine = ReflectionEngine()
        entries, _ = engine.reflect(sample_results)
        errors = [e for e in entries if not e.is_correct]
        assert len(errors) == 35
        for e in errors:
            assert e.category in ("可优化", "不可控")

    def test_missed_reversal_classified(self):
        engine = ReflectionEngine()
        cat, cause = engine._classify_error("1", "4", "1")
        assert cat == "可优化"

    def test_mean_reversion_uncontrollable(self):
        engine = ReflectionEngine()
        cat, cause = engine._classify_error("4", "3p", "4")
        assert cat == "不可控"

    def test_patterns_have_min_occurrences(self, sample_results):
        engine = ReflectionEngine()
        _, patterns = engine.reflect(sample_results)
        for p in patterns:
            assert p.occurrences >= 3
            assert p.pattern_id.startswith("PTN_")

    def test_empty_results_no_error(self):
        engine = ReflectionEngine()
        entries, patterns = engine.reflect([])
        assert entries == []
        assert patterns == []

    def test_save_report(self, sample_results):
        engine = ReflectionEngine()
        engine.reflect(sample_results)
        with tempfile.TemporaryDirectory() as d:
            path = engine.save_reflection_report(os.path.join(d, "report.json"))
            assert os.path.exists(path)
            data = json.load(open(path))
            assert data["meta"]["total_entries"] == len(sample_results)


class TestDataIntegrity:
    """数据完整性校验测试。"""

    def test_empty_results_fails(self):
        passed, warnings, stats = validate_results_integrity([])
        assert not passed

    def test_insufficient_dates_warns(self):
        results = [make_result("2026-05-01", "881101", "4", "4", "4", "场A", True)
                   for _ in range(10)]
        passed, warnings, _ = validate_results_integrity(results)
        assert any("700" in w for w in warnings)

    def test_missing_states_warns(self):
        results = [make_result("2026-05-01", f"8811{i%90+1:02d}",
                               "4", "4", "4", "场A", True) for i in range(1000)]
        passed, warnings, _ = validate_results_integrity(results)
        assert any("缺失状态" in w for w in warnings)

    def test_cache_validation_passes(self):
        cache = {"sectors": {}}
        for j in range(90):
            cache["sectors"][f"8811{j+1:02d}"] = [
                {"date": f"2023-01-{min(i+3,28):02d}", "state": 4}
                for i in range(800)]
        passed, _, stats = validate_history_cache(cache)
        assert passed
        assert stats["total_sectors"] == 90

    def test_cache_insufficient_sectors(self):
        cache = {"sectors": {f"8811{i:02d}": [] for i in range(10)}}
        passed, warnings, _ = validate_history_cache(cache)
        assert not passed or any("板块数" in w for w in warnings)


class TestRuleDiscovery:
    """规则发现引擎测试。"""

    @pytest.fixture
    def history_cache(self):
        cache = {"sectors": {}}
        for j in range(90):
            records = []
            for i in range(800):
                states = [4, 4, 5, 4, 4, 3, 3, 4, 4, 4]
                records.append({
                    "date": f"2023-01-{min(i+3,28):02d}",
                    "state": states[i % len(states)],
                })
            cache["sectors"][f"8811{j+1:02d}"] = records
        return cache

    @pytest.fixture
    def backtest_results(self):
        results = []
        for i in range(200):
            results.append(make_result("2026-05-01", f"8811{i%10+1:02d}",
                                       "4", "4", "4", "场A", True))
        for i in range(30):
            results.append(make_result("2026-05-01", f"8811{i%10+1:02d}",
                                       "4", "3p", "4", "场C", False))
        return results

    def test_frequency_analysis_produces_rules(self, history_cache):
        discovery = RuleDiscovery()
        rules = discovery._frequency_analysis(history_cache)
        assert len(rules) > 0
        for r in rules:
            assert r.source == "frequency_analysis"
            assert r.support > 0

    def test_discover_full(self, history_cache, backtest_results):
        engine = ReflectionEngine()
        entries, _ = engine.reflect(backtest_results)
        discovery = RuleDiscovery()
        rules = discovery.discover(history_cache, backtest_results, entries)
        assert len(rules) > 0

    def test_priority_sorting(self, history_cache, backtest_results):
        engine = ReflectionEngine()
        entries, _ = engine.reflect(backtest_results)
        discovery = RuleDiscovery()
        rules = discovery.discover(history_cache, backtest_results, entries)
        for i in range(len(rules) - 1):
            assert rules[i].priority <= rules[i+1].priority

    def test_transition_matrix(self, history_cache):
        discovery = RuleDiscovery()
        discovery._frequency_analysis(history_cache)
        summary = discovery.get_transition_summary()
        assert "4" in summary

    def test_save_rules(self, history_cache, backtest_results):
        engine = ReflectionEngine()
        entries, _ = engine.reflect(backtest_results)
        discovery = RuleDiscovery()
        discovery.discover(history_cache, backtest_results, entries)
        with tempfile.TemporaryDirectory() as d:
            path = discovery.save_rules(os.path.join(d, "rules.json"))
            assert os.path.exists(path)


class TestProjectionWeights:
    """权重管理器完整性测试。"""

    def test_default_weights_sum_to_one(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "weights.json")
            pw = ProjectionWeights(config_path=p)
            for state in ["1", "2", "3", "4", "5", "3p"]:
                w = pw.get_weights(state)
                assert abs(sum(w.values()) - 1.0) < 0.01

    def test_adjust_clamped(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "weights.json")
            pw = ProjectionWeights(config_path=p)
            pw.adjust("4", "A", 5.0, reason="超大调整")
            w = pw.get_weights(4)
            assert w["A"] <= 0.95

    def test_save_reload_preserves(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "weights.json")
            pw = ProjectionWeights(config_path=p)
            pw.adjust("4", "A", 0.05, reason="测试")
            pw.save()
            pw2 = ProjectionWeights(config_path=p)
            assert pw2.get_weights(4)["A"] > 0.60

    def test_normalize_after_multiple_adjusts(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "weights.json")
            pw = ProjectionWeights(config_path=p)
            for _ in range(10):
                pw.adjust("4", "A", 0.03, reason="迭代")
            w = pw.get_weights(4)
            assert abs(sum(w.values()) - 1.0) < 0.01
