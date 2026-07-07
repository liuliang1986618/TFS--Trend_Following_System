"""Evolution suggestion boundary for TFS v2."""

from __future__ import annotations


class EvolutionAdvisor:
    def suggest(self, report) -> list[dict]:
        raise NotImplementedError("Task 5 implements evolution suggestions")
