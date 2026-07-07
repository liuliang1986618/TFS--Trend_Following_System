"""Legacy display compatibility boundary for TFS v2."""

from __future__ import annotations


class LegacyDisplayCompatibility:
    def render_with_legacy_tools(self, *args, **kwargs):
        raise NotImplementedError("Task 8 implements legacy compatibility hooks")
