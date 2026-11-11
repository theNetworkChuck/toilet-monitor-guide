#!/usr/bin/env python3
"""Live toilet view: http://<pi>:8080  (no sudo needed)."""
import json, os, subprocess, sys, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, "/opt/toilet-monitor")  # installed copy
sys.path.insert(1, str(Path(__file__).resolve().parent.parent))  # or straight from this repo
from toilet_watch import load_state, WARN_LOW_SECONDS, CRIT_LOW_SECONDS, STALE_SECONDS  # noqa: E402

PAGE = (Path(__file__).parent / "index.html").read_bytes()


def pin_closed():
    try:
        out = subprocess.run(["pinctrl", "lev", os.environ.get("TOILET_GPIO", "17")], capture_output=True, text=True, timeout=1).stdout.strip()
        return (out == "0") if out in ("0", "1") else None  # pull-up: 0 = circuit closed
    except Exception:
        return None


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/state"):
            s = load_state() or {}
            now = time.time()
            s["now"] = now
            s["stale"] = (now - s.get("updated", 0)) > STALE_SECONDS
            s["switch_closed"] = pin_closed()
            closed = s["switch_closed"]
            s["float_up"] = None if closed is None else (closed if s.get("full_when") == "closed" else not closed)
            s["warn"], s["crit"] = WARN_LOW_SECONDS, CRIT_LOW_SECONDS
            body, ctype = json.dumps(s).encode(), "application/json"
        else:
            body, ctype = PAGE, "text/html; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


PORT = int(os.environ.get("TOILET_PORT", "8080"))
print("Flush Control: http://<this-pi>:%d" % PORT, flush=True)
ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()
