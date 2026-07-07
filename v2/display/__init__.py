"""Display facade for TFS v2."""

from __future__ import annotations

from .builder import DisplayPayloadBuilder
from .nav import NavPayloadBuilder
from .schema import validate_display_payload, validate_nav_payload


class Display:
    """Minimal importable display facade."""

    def validate_payload(self, payload: dict) -> dict:
        return validate_display_payload(payload)

    def render_daily(self, payload_path: str, output_path: str) -> str:
        from .renderer import DisplayRenderer

        return DisplayRenderer().render_daily(payload_path, output_path)

    def render_index(self, dates_dir: str, output_path: str) -> str:
        from .renderer import DisplayRenderer

        return DisplayRenderer().render_index(dates_dir, output_path)


__all__ = [
    "Display",
    "DisplayPayloadBuilder",
    "NavPayloadBuilder",
    "validate_display_payload",
    "validate_nav_payload",
]
