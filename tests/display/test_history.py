"""HistoryTracker 单元测试。

覆盖: 快照加载、状态查询、轨迹方向、颜色映射、缓存序列化。
"""
import pytest
import json
import os
import tempfile
from src.display.history import HistoryTracker, StateRecord


class TestStateRecord:
    def test_create_and_fields(self):
        r = StateRecord(date="2026-05-31", state=4, state_label="上涨趋势",
                        score=85, position_ratio=1.0,
                        conditions={"structure": True, "volume": True, "persistence": True})
        assert r.date == "2026-05-31"
        assert r.state == 4
        assert r.score == 85
        assert r.conditions["structure"] is True

    def test_state_3p(self):
        r = StateRecord(date="2026-05-31", state="3p", state_label="转跌确认中",
                        score=40, position_ratio=0.333,
                        conditions={"structure": False, "volume": True, "persistence": False})
        assert r.state == "3p"
        assert r.position_ratio == 0.333


class TestHistoryTracker:
    @pytest.fixture
    def snapshots_dir(self):
        with tempfile.TemporaryDirectory() as d:
            d1 = {"sectors": [
                {"symbol": "881101", "state": 3, "state_label": "翻转确认中", "score": 70,
                 "position_ratio": 0.166,
                 "conditions": {"structure": {"pass": True}, "volume": {"pass": True},
                                "persistence": {"pass": False}}},
                {"symbol": "881102", "state": 4, "state_label": "上涨趋势", "score": 90,
                 "position_ratio": 1.0,
                 "conditions": {"structure": {"pass": True}, "volume": {"pass": True},
                                "persistence": {"pass": True}}},
            ]}
            d2 = {"sectors": [
                {"symbol": "881101", "state": 4, "state_label": "上涨趋势", "score": 85,
                 "position_ratio": 1.0,
                 "conditions": {"structure": {"pass": True}, "volume": {"pass": True},
                                "persistence": {"pass": True}}},
                {"symbol": "881102", "state": 5, "state_label": "上涨中的回调", "score": 75,
                 "position_ratio": 1.0,
                 "conditions": {"structure": {"pass": True}, "volume": {"pass": False},
                                "persistence": {"pass": True}}},
            ]}
            with open(os.path.join(d, "trend_snapshot_2026-05-30.json"), "w") as f:
                json.dump(d1, f)
            with open(os.path.join(d, "trend_snapshot_2026-05-31.json"), "w") as f:
                json.dump(d2, f)
            yield d

    def test_load_all(self, snapshots_dir):
        t = HistoryTracker(data_dir=snapshots_dir)
        r = t.load_from_snapshots()
        assert len(r["881101"]) == 2
        assert len(r["881102"]) == 2
        assert r["881101"][0].date == "2026-05-30"
        assert r["881101"][1].date == "2026-05-31"

    def test_load_filtered(self, snapshots_dir):
        t = HistoryTracker(data_dir=snapshots_dir)
        r = t.load_from_snapshots(symbol_list=["881101"])
        assert "881101" in r
        assert "881102" not in r

    def test_recent_states(self, snapshots_dir):
        t = HistoryTracker(data_dir=snapshots_dir)
        t.load_from_snapshots()
        recent = t.get_recent_states("881101", days=1)
        assert len(recent) == 1
        assert recent[0].state == 4

    def test_trajectory(self, snapshots_dir):
        t = HistoryTracker(data_dir=snapshots_dir)
        t.load_from_snapshots()
        assert t.get_state_trajectory("881101", days=2) == [3, 4]

    def test_score_history(self, snapshots_dir):
        t = HistoryTracker(data_dir=snapshots_dir)
        t.load_from_snapshots()
        assert t.get_score_history("881101", days=2) == [70, 85]

    def test_conditions_history(self, snapshots_dir):
        t = HistoryTracker(data_dir=snapshots_dir)
        t.load_from_snapshots()
        conds = t.get_conditions_history("881101", days=1)
        assert conds[0]["persistence"] is True

    def test_empty_dir(self):
        with tempfile.TemporaryDirectory() as d:
            t = HistoryTracker(data_dir=d)
            assert t.load_from_snapshots() == {}

    def test_unknown_symbol(self, snapshots_dir):
        t = HistoryTracker(data_dir=snapshots_dir)
        t.load_from_snapshots()
        assert t.get_recent_states("999999") == []

    def test_normalize_3p(self, snapshots_dir):
        t = HistoryTracker(data_dir=snapshots_dir)
        assert t._normalize_state("3'") == "3p"
        assert t._normalize_state(4) == 4


class TestStateColor:
    def test_six_states(self):
        for s in [1, 2, 3, 4, 5, "3p"]:
            c = HistoryTracker.state_to_color(s)
            assert c.startswith("#") and len(c) == 7

    def test_unknown(self):
        assert HistoryTracker.state_to_color(99) == "#6e7681"


class TestTrajectoryDirection:
    def test_up(self):
        assert HistoryTracker.trajectory_direction([3, 4]) == "up"

    def test_down(self):
        assert HistoryTracker.trajectory_direction([4, 1]) == "down"

    def test_stable(self):
        assert HistoryTracker.trajectory_direction([4, 4]) == "stable"

    def test_single(self):
        assert HistoryTracker.trajectory_direction([4]) == "stable"

    def test_empty(self):
        assert HistoryTracker.trajectory_direction([]) == "stable"

    def test_mixed(self):
        assert HistoryTracker.trajectory_direction([3, 4, 1, 4]) == "mixed"

    def test_3p_to_4(self):
        assert HistoryTracker.trajectory_direction(["3p", 4]) == "up"

    def test_5_to_4(self):
        assert HistoryTracker.trajectory_direction([5, 4]) == "up"


class TestCacheSerialization:
    @pytest.fixture
    def tracker(self):
        with tempfile.TemporaryDirectory() as d:
            s = {"sectors": [{"symbol": "881101", "state": 4,
                              "state_label": "上涨趋势", "score": 85,
                              "position_ratio": 1.0,
                              "conditions": {"structure": {"pass": True},
                                             "volume": {"pass": True},
                                             "persistence": {"pass": True}}}]}
            with open(os.path.join(d, "trend_snapshot_2026-05-31.json"), "w") as f:
                json.dump(s, f)
            t = HistoryTracker(data_dir=d)
            t.load_from_snapshots()
            yield t

    def test_to_dict(self, tracker):
        d = tracker.to_dict()
        assert "881101" in d
        assert d["881101"][0]["state"] == 4
        assert "conditions" in d["881101"][0]

    def test_save_cache(self, tracker):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "history_states.json")
            assert tracker.save_cache(p) == p
            assert os.path.exists(p)
            data = json.load(open(p))
            assert data["meta"]["total_symbols"] == 1
