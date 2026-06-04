#!/usr/bin/env python3
"""启动Dashboard本地HTTP服务 (端口8765)。

解决file://协议下iframe跨域限制，同时支持正确的MIME类型。
"""
import http.server
import os
import sys
import socket
import webbrowser
from pathlib import Path

PORT = 8765
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DASHBOARD_DIR = os.path.join(PROJECT_ROOT, "dashboard")


class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    """自定义handler：设置正确的编码和缓存控制。"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DASHBOARD_DIR, **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    def log_message(self, format, *args):
        # 简洁日志: 只显示关键请求，忽略favicon和错误日志
        path = str(args[0]) if args else ""
        if any(k in path for k in ("trend_dashboard", "index.html", "GET / HTTP")):
            print(f"  📄 {path}" if len(path) < 80 else f"  📄 {path[:80]}...")


def find_free_port(start: int) -> int:
    """找可用端口，从start开始试。"""
    for port in range(start, start + 100):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("localhost", port)) != 0:
                return port
    return start


def main():
    port = find_free_port(PORT)
    if port != PORT:
        print(f"⚠️  端口 {PORT} 被占用，改用 {port}")

    server = http.server.HTTPServer(("0.0.0.0", port), DashboardHandler)

    url = f"http://localhost:{port}"
    print("=" * 60)
    print(f"🚀 趋势跟随 Dashboard 已启动")
    print(f"   地址: {url}")
    print(f"   目录: {DASHBOARD_DIR}")
    print(f"   按 Ctrl+C 停止")
    print("=" * 60)

    # 确保服务就绪后再打开浏览器
    import time
    time.sleep(0.3)
    try:
        webbrowser.open(url)
    except Exception:
        pass

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n⏹  服务已停止")
        server.server_close()


if __name__ == "__main__":
    main()
