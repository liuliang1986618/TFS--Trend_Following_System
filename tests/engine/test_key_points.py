"""测试关键操作点识别器。"""
import pytest
from src.engine.key_points import KeyPointDetector


class TestKeyPointDetector:
    def test_transition_2_to_3_is_buy1(self):
        kp = KeyPointDetector.detect(2, 3)
        assert kp is not None
        assert kp.action == "买点1"

    def test_transition_3_to_1_is_stop_loss(self):
        kp = KeyPointDetector.detect(3, 1)
        assert kp is not None
        assert kp.action == "止损"

    def test_transition_5_to_3prime_is_defense(self):
        kp = KeyPointDetector.detect(5, "3'")
        assert kp is not None
        assert kp.action == "防守"

    def test_same_state_no_keypoint(self):
        assert KeyPointDetector.detect(4, 4) is None

    def test_all_six_key_points_defined(self):
        transitions = ["2→3", "3→1", "3→4", "5→4", "5→3'", "3'→1"]
        for t in transitions:
            assert t in KeyPointDetector.KEY_TRANSITIONS
