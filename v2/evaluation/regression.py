"""Regression comparison boundary for TFS v2."""

from __future__ import annotations


class RegressionComparator:
    def compare_symbol(self, old_record: dict, new_signal) -> dict:
        old_state = self._state_key(old_record.get("state"))
        new_state = self._state_key(getattr(new_signal, "state", None))
        old_score = old_record.get("score")
        new_score = getattr(new_signal, "score", None)
        return {
            "code": old_record.get("code", getattr(new_signal, "code", "")),
            "state_match": old_state == new_state,
            "old_state": old_state,
            "new_state": new_state,
            "score_delta": None if old_score is None or new_score is None else new_score - old_score,
        }

    @staticmethod
    def _state_key(state) -> str:
        return str(state).replace("'", "p")
