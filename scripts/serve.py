#!/usr/bin/env python3
"""Dashboard 服务 + Watchlist API"""
import http.server, os, sys, json, socket, webbrowser, time, subprocess, glob

PORT = 8765
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DASHBOARD_DIR = os.path.join(PROJECT_ROOT, "dashboard")

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DASHBOARD_DIR, **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    def do_POST(self):
        import urllib.parse as _up
        os.chdir(PROJECT_ROOT)
        sys.path.insert(0, PROJECT_ROOT)

        if not self.path.startswith("/api/watchlist"):
            self.send_response(404); self.end_headers(); return

        # Parse params from query + body
        qs = _up.parse_qs(self.path.split("?")[1] if "?" in self.path else "")
        body = {}
        if "x-www-form-urlencoded" in self.headers.get("Content-Type", ""):
            cl = int(self.headers.get("Content-Length", 0))
            if cl > 0:
                body = _up.parse_qs(self.rfile.read(cl).decode())
        for k, v in body.items():
            qs[k] = v

        query = (qs.get("code", [""])[0] or "").strip()
        method = (qs.get("_method", ["POST"])[0] or "POST").upper()

        if method == "DELETE" and query:
            self._do_delete(query, is_ajax=(qs.get("ajax", [""])[0] == "1"))
            return

        if not query:
            self._json({"ok": False, "error": "请输入代码或名称"})
            return

        is_ajax = (qs.get("ajax", [""])[0] == "1")

        # Lookup code (silent for AJAX to avoid double response)
        code = self._lookup_code(query, silent=is_ajax)
        if not code:
            if is_ajax:
                self._json({"ok": False, "error": f"未找到包含「{query}」的股票"})
            return

        # Add to watchlist
        wl_path = os.path.join(PROJECT_ROOT, "watchlist.json")
        wl = json.load(open(wl_path)) if os.path.exists(wl_path) else {"stocks": [], "notes": {}}
        if code not in wl["stocks"]:
            wl["stocks"].append(code)
            wl["notes"][code] = ""
            json.dump(wl, open(wl_path, "w"), ensure_ascii=False, indent=2)

        self._rebuild_and_redirect(is_ajax=is_ajax)

    def do_DELETE(self):
        import urllib.parse as _up
        os.chdir(PROJECT_ROOT)
        sys.path.insert(0, PROJECT_ROOT)
        params = _up.parse_qs(self.path.split("?")[1] if "?" in self.path else "")
        code = (params.get("code", [""])[0] or "").strip().zfill(6)
        is_ajax = (params.get("ajax", [""])[0] == "1")
        if code:
            self._do_delete(code, is_ajax=is_ajax)

    def do_GET(self):
        if self.path.startswith("/api/analyze"):
            self._handle_analyze()
        else:
            super().do_GET()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST,GET,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    # ---- helpers ----

    def _json(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())

    def _lookup_code(self, query, silent=False):
        with open(os.path.join(PROJECT_ROOT, "data", "stock_names.json")) as f:
            names = json.load(f)
        if query.isdigit():
            code = query.zfill(6)
            name = names.get(code, code)
            if not silent:
                self._json({"ok": True, "code": code, "name": name})
            return code
        matches = [(c, n) for c, n in names.items() if query.lower() in n.lower()]
        if len(matches) == 0:
            if not silent:
                self._json({"ok": False, "error": f"未找到包含「{query}」的股票"})
            return None
        if len(matches) == 1:
            code, name = matches[0]
            if not silent:
                self._json({"ok": True, "code": code, "name": name})
            return code
        candidates = [{"code": c, "name": n} for c, n in matches[:20]]
        if not silent:
            self._json({"ok": False, "multiple": True, "candidates": candidates,
                         "hint": f"找到{len(matches)}个，请选择"})
        return None

    def _do_delete(self, code, is_ajax=False):
        wl_path = os.path.join(PROJECT_ROOT, "watchlist.json")
        if os.path.exists(wl_path):
            wl = json.load(open(wl_path))
            if code in wl["stocks"]:
                wl["stocks"].remove(code)
                wl["notes"].pop(code, None)
                json.dump(wl, open(wl_path, "w"), ensure_ascii=False, indent=2)
        if is_ajax:
            # AJAX删除：立即返回，异步重建页面
            self._json({"ok": True, "code": code})
            import threading
            threading.Thread(target=self._rebuild_silent, daemon=True).start()
        else:
            self._rebuild_and_redirect()

    def _rebuild_silent(self):
        """静默重建（AJAX删除后异步调用，不发HTTP响应）。"""
        try:
            self._rebuild_and_redirect(is_ajax=True)
        except Exception:
            pass

    def _rebuild_and_redirect(self, is_ajax=False):
        """重建 actions + build_final，然后重定向。"""
        # 更新 actions JSON 中的 watchlist
        dash_data = os.path.join(PROJECT_ROOT, "dashboard", "data")
        afiles = sorted(glob.glob(os.path.join(dash_data, "actions_*.json")))
        if afiles:
            try:
                with open(afiles[-1]) as f:
                    adata = json.load(f)
                from src.fusion.scanner import MarketScanner
                scanner = MarketScanner()
                with open(os.path.join(PROJECT_ROOT, "data", "stock_names.json")) as nf:
                    nmap = json.load(nf)
                wl = json.load(open(os.path.join(PROJECT_ROOT, "watchlist.json")))
                new_wl = []
                import pickle, pandas as pd, numpy as np
                for wcode in wl.get("stocks", []):
                    rpath = os.path.join(PROJECT_ROOT, "data", "massive_stocks", f"{wcode}.pkl")
                    if not os.path.exists(rpath): continue
                    df = pickle.load(open(rpath, "rb"))
                    df["date"] = pd.to_datetime(df["date"])
                    md = df["date"] <= pd.Timestamp(adata["date"])
                    if md.sum() < 30: continue
                    idx = int(md.sum() - 1)
                    close = df["close"].values[:idx+1].astype(float)
                    volume = df["volume"].values[:idx+1].astype(float)
                    hcol = "high" if "high" in df.columns else "close"
                    lcol = "low" if "low" in df.columns else "close"
                    high = df[hcol].values[:idx+1].astype(float)
                    low = df[lcol].values[:idx+1].astype(float)
                    ind = scanner._calc_indicators(close, volume, high, low)
                    score = scanner._score_stock(ind)
                    name = nmap.get(wcode, wcode)
                    note = wl.get("notes", {}).get(wcode, "")
                    mkt = "sh" if str(wcode).startswith("6") else "sz"
                    link = f"https://quote.eastmoney.com/{mkt}{wcode}.html"
                    if score is None:
                        new_wl.append({"code": wcode, "name": name, "score": 0, "action": "回避", "position_pct": 0,
                                       "reason": f"趋势过滤未通过 | {note}" if note else "趋势过滤未通过",
                                       "link": link, "state": scanner._determine_tfs_state(close),
                                       "ma_deviation": ind.get("ma_deviation", 0), "ret_20d": ind.get("pct_20d", 0)})
                    else:
                        res = scanner._result_from_row(wcode, name, score, ind, is_etf=False)
                        if note: res.reason += f" | {note}"
                        res.state = scanner._determine_tfs_state(close)
                        new_wl.append({"code": res.code, "name": res.name, "score": res.score,
                                       "action": res.action, "position_pct": res.position_pct,
                                       "reason": res.reason, "link": res.link, "state": res.state,
                                       "ma_deviation": res.ma_deviation, "ret_20d": res.ret_20d})
                adata["watchlist"] = new_wl
                json.dump(adata, open(afiles[-1], "w"), ensure_ascii=False, indent=2)
            except Exception:
                pass
        # 重建页面
        subprocess.run([sys.executable, os.path.join(PROJECT_ROOT, "scripts", "build_final.py")],
                       cwd=PROJECT_ROOT, timeout=30, capture_output=True)
        subprocess.run([sys.executable, os.path.join(PROJECT_ROOT, "scripts", "build_nav_index.py")],
                       cwd=PROJECT_ROOT, timeout=30, capture_output=True)
        # AJAX 请求返回 JSON，不重定向
        if is_ajax:
            self._json({"ok": True})
            return
        # 重定向（传统表单提交）
        self.send_response(303)
        self.send_header("Location", self.headers.get("Referer", "/"))
        self.end_headers()

    def _handle_analyze(self):
        import urllib.parse as _up
        os.chdir(PROJECT_ROOT)
        sys.path.insert(0, PROJECT_ROOT)
        params = _up.parse_qs(self.path.split("?")[1] if "?" in self.path else "")
        code = (params.get("code", [""])[0] or "").strip().zfill(6)
        if not code:
            self._json({"ok": False, "error": "missing code"}); return
        try:
            from src.fusion.scanner import MarketScanner
            from src.engine.state_machine import StateMachine
            import pickle, pandas as pd, numpy as np
            path = os.path.join(PROJECT_ROOT, "data", "massive_stocks", f"{code}.pkl")
            df = pickle.load(open(path, "rb"))
            df["date"] = pd.to_datetime(df["date"])
            ts = StateMachine.classify(df)
            scanner = MarketScanner()
            c_arr = df["close"].values.astype(float)
            v_arr = df["volume"].values.astype(float)
            h_arr = df["high"].values.astype(float) if "high" in df.columns else c_arr
            l_arr = df["low"].values.astype(float) if "low" in df.columns else c_arr
            ind = scanner._calc_indicators(c_arr, v_arr, h_arr, l_arr)
            score = scanner._score_stock(ind)
            with open(os.path.join(PROJECT_ROOT, "data", "stock_names.json")) as f:
                names = json.load(f)
            name = names.get(code, code)
            states = {1: "持续下跌 · 别碰", 2: "跌多了弹一下 · 再等等",
                      3: "趋势转好，突破买入 · 可以买了", 4: "持续上涨 · 拿着别动",
                      5: "涨多了歇一下 · 准备加仓", "3p": "趋势转差，破位减仓 · 赶紧卖"}
            conds = ts.conditions
            self._json({"ok": True, "code": code, "name": name,
                        "score": score if score is not None else 0,
                        "state": ts.state, "state_label": states.get(ts.state, str(ts.state)),
                        "close": float(c_arr[-1]), "pct_today": round(ind["pct_today"], 1),
                        "pct_5d": round(ind["pct_5d"], 1), "pct_20d": round(ind["pct_20d"], 1),
                        "ma_deviation": round(ind["ma_deviation"], 1),
                        "rsi": round(ind["rsi"], 0), "mfi": round(ind["mfi"], 0),
                        "vol_ratio": round(ind["vol_ratio"], 2),
                        "ma_bullish": bool(ind["ma_bullish"]), "ma_mid_bullish": bool(ind["ma_mid_bullish"]),
                        "macd_golden": bool(ind["macd"]["golden_cross"]),
                        "bb_position": round(ind["bb"]["position"], 2),
                        "bb_breakout": bool(ind["bb"]["breakout_upper"]),
                        "structure": bool(conds["structure"].pass_),
                        "volume_ok": bool(conds["volume"].pass_),
                        "persistence": bool(conds["persistence"].pass_),
                        "position_pct": round(ts.position_ratio * 100, 0)})
        except Exception as e:
            self._json({"ok": False, "error": str(e)})

    def log_message(self, format, *args):
        path = str(args[0]) if args else ""
        if any(k in path for k in ("dashboard", "index", "api", "GET / HTTP")) and len(path) < 120:
            print(f"  {path}")

def main():
    server = http.server.ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    url = f"http://localhost:{PORT}"
    print(f"🚀 {url}")
    time.sleep(0.3)
    try: webbrowser.open(url)
    except: pass
    try: server.serve_forever()
    except KeyboardInterrupt:
        print("\n⏹ 停止"); server.server_close()

if __name__ == "__main__":
    main()
