"""No-cache static server for the existing dashboard directory."""

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


def serve(port: int = 8765) -> None:
    root = Path(__file__).resolve().parents[1] / "dashboard"
    handler = lambda *args, **kwargs: NoCacheHTTPRequestHandler(*args, directory=str(root), **kwargs)
    with http.server.ThreadingHTTPServer(("", port), handler) as server:
        print(f"Serving {root} at http://localhost:{port}/")
        server.serve_forever()


if __name__ == "__main__":
    serve()
