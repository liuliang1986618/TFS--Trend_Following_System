"""No-cache static server for TFS v2 display output."""

from __future__ import annotations

import http.server
from pathlib import Path


class NoCacheHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    """Static handler that prevents browser caching during dashboard review."""

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()


def _find_latest_bundle(display_runs: Path) -> Path | None:
    """Find the most recent run bundle with a valid index.html."""
    candidates = []
    for child in display_runs.iterdir():
        if child.is_dir() and (child / "index.html").exists():
            candidates.append(child)
    if not candidates:
        return None
    # Sort by directory name (timestamp-based run IDs sort chronologically)
    candidates.sort(key=lambda p: p.name, reverse=True)
    return candidates[0]


def serve(port: int = 8765, directory: str | None = None) -> None:
    if directory:
        root = Path(directory)
    else:
        # Try v2 display_runs first, then runs directory, fall back to v1 dashboard
        project_root = Path(__file__).resolve().parents[1]
        
        # 查找display_runs目录中的bundle
        display_runs = project_root / "v2" / "data" / "derived" / "display_runs"
        latest = _find_latest_bundle(display_runs)
        
        # 如果display_runs没有，查找runs目录
        if latest is None:
            runs_dir = project_root / "v2" / "data" / "derived" / "runs"
            latest = _find_latest_bundle(runs_dir)
        
        if latest:
            root = latest
        else:
            root = project_root / "dashboard"

    handler = lambda *args, **kwargs: NoCacheHTTPRequestHandler(
        *args, directory=str(root), **kwargs
    )
    with http.server.ThreadingHTTPServer(("", port), handler) as server:
        print(f"Serving {root} at http://localhost:{port}/")
        server.serve_forever()


if __name__ == "__main__":
    serve()
