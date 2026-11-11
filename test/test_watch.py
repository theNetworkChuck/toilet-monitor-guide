#!/usr/bin/env python3
"""Logic tests with a fake clock. Run: python3 test/test_watch.py"""

import json
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pi"))
import toilet_watch as tw  # noqa: E402
from toilet_watch import Tank, render_local_check  # noqa: E402

T0 = datetime(2026, 10, 16, 12, 0, 0).timestamp()
failures = []


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        failures.append(name)


def feed(tank, raw_full, start, seconds, step=0.1):
    t = start
    while t < start + seconds:
        tank.sample(raw_full, t)
        t += step
    return t


# C1: one real flush counts once
tank = Tank()
t = feed(tank, True, T0, 5)
t = feed(tank, False, t, 3)      # tank drains
t = feed(tank, True, t, 40)      # refills
check("C1 one flush counts exactly once", tank.flushes_total == 1 and tank.flushes_today == 1)

# C1: sloshing shorter than the debounce counts zero
tank = Tank()
t = feed(tank, True, T0, 5)
for _ in range(20):
    t = feed(tank, False, t, 0.4)
    t = feed(tank, True, t, 0.4)
check("C1 sloshing under 1s counts zero", tank.flushes_total == 0 and tank.full)

# C1: three flushes count three
tank = Tank()
t = feed(tank, True, T0, 2)
for _ in range(3):
    t = feed(tank, False, t, 3)
    t = feed(tank, True, t, 30)
check("C1 three flushes count three", tank.flushes_today == 3)

# C2: tank service thresholds
tank = Tank()
t = feed(tank, True, T0, 2)
t = feed(tank, False, t, 2)
low_start = tank.low_since
st = tank.to_state(t)
out = render_local_check(st, low_start + 30)
check("C2 low 30s is under WARN", "tank_low_seconds=30;120;600" in out)
out = render_local_check(dict(st, updated=low_start + 130), low_start + 130)
check("C2 low 130s reports 130 against 120;600", "tank_low_seconds=130;120;600" in out and "running" in out)
full = tank.to_state(t)
full.update(tank="full", low_since=None)
out = render_local_check(full, t)
check("C2 full reports 0", "tank_low_seconds=0;120;600 Tank full" in out)
check("C2 tank line is a P (metric-levels) check", out.startswith('P "Toilet Tank"'))

# C3: stale or missing state is CRIT
check("C3 missing state is CRIT", render_local_check(None, t).startswith('2 "Toilet Tank"'))
check("C3 stale state is CRIT", render_local_check(dict(full, updated=t - 120), t).startswith('2 "Toilet Tank"'))

# C4: midnight resets today, not total
tank = Tank()
t = feed(tank, True, T0, 2)
t = feed(tank, False, t, 3)
t = feed(tank, True, t, 3)
midnight = datetime(2026, 10, 17, 0, 0, 5).timestamp()
tank.sample(True, midnight)
check("C4 today resets at midnight", tank.flushes_today == 0 and tank.flushes_total == 1)
out = render_local_check(dict(tank.to_state(t), updated=midnight), midnight)
check("C4 stale-day state renders 0 today", "flushes_today=0|flushes_total=1" in out)

# Restart keeps counts
again = Tank(tank.to_state(midnight))
check("restart keeps the total", again.flushes_total == 1)

# Fresh start with the tank already low is not a flush
tank = Tank()
feed(tank, False, T0, 5)
check("fresh start low counts zero flushes", tank.flushes_total == 0 and tank.full is False)

# Slack: the message, the route, and a real HTTP post to a fake webhook
msg = tw.flush_message(3, 41, datetime(2026, 10, 19, 15, 7).timestamp())
check("slack message names the time, today's count and the total",
      "3:07 PM" in msg and "3rd flush today" in msg and "41 all time" in msg)
check("ordinals", [tw._ordinal(n) for n in (1, 2, 3, 4, 11, 12, 13, 21, 22, 111)] ==
      ["1st", "2nd", "3rd", "4th", "11th", "12th", "13th", "21st", "22nd", "111th"])
tw.SLACK_WEBHOOK_URL = tw.SLACK_BOT_TOKEN = tw.SLACK_CHANNEL = ""
check("slack off when nothing is set", tw.slack_request("x") is None)
tw.SLACK_BOT_TOKEN, tw.SLACK_CHANNEL = "xoxb-test", "C123"
r = tw.slack_request("hi")
check("bot route posts to chat.postMessage with the channel",
      r.full_url.endswith("chat.postMessage") and b'"C123"' in r.data and r.get_header("Authorization") == "Bearer xoxb-test")

import http.server, threading as _th  # noqa: E401,E402
got = []
class _Hook(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        got.append(self.rfile.read(int(self.headers["Content-Length"])))
        self.send_response(200); self.end_headers(); self.wfile.write(b"ok")
    def log_message(self, *a): pass
srv = http.server.HTTPServer(("127.0.0.1", 0), _Hook)
_th.Thread(target=srv.serve_forever, daemon=True).start()
tw.SLACK_WEBHOOK_URL = "http://127.0.0.1:%d/hook" % srv.server_port
tw.post_slack("flush!")
check("webhook route delivers the text", got and json.loads(got[0]) == {"text": "flush!"})
srv.shutdown()
tw.SLACK_WEBHOOK_URL = "http://127.0.0.1:9/nothing-listens-here"
try:
    tw.post_slack("flush!")
    ok = True
except Exception:
    ok = False
check("a dead Slack never raises (counting keeps going)", ok)
tw.SLACK_WEBHOOK_URL = tw.SLACK_BOT_TOKEN = tw.SLACK_CHANNEL = ""

# main(): exactly one Slack notice per counted flush, none for sloshing or the first reading
import types  # noqa: E402
check("default is full when open", tw.FULL_WHEN == "open")
clock = [T0]
# (start, end, float_up): pin reads 1 when up, 0 when down
plan = [(0, 5, True), (5, 5.4, False), (5.4, 10, True), (10, 15, False), (15, 30, True), (30, 33, False), (33, 45, True)]
class _Stop(Exception): pass
class _Btn:
    def __init__(self, *a, **k): pass
    @property
    def is_pressed(self):
        dt = clock[0] - T0
        return not next(u for a, b, u in plan if a <= dt < b)
def _sleep(s):
    clock[0] += s
    if clock[0] - T0 >= 44: raise _Stop
sys.modules["gpiozero"] = types.SimpleNamespace(Button=_Btn)
notices = []
states = []
saved = (tw.time.time, tw.time.sleep, tw.notify_flush, tw.STATE_FILE, tw.load_state, tw.save_state)
import tempfile  # noqa: E402
tw.time.time, tw.time.sleep = (lambda: clock[0]), _sleep
tw.notify_flush = lambda tank: notices.append(tank.flushes_total)
tw.STATE_FILE = os.path.join(tempfile.mkdtemp(), "state.json")
tw.load_state = lambda path=None: None
tw.save_state = lambda state, path=None: states.append(state)
try:
    import contextlib, io  # noqa: E401,E402
    with contextlib.redirect_stdout(io.StringIO()):
        tw.main()
except _Stop:
    pass
tw.time.time, tw.time.sleep, tw.notify_flush, tw.STATE_FILE, tw.load_state, tw.save_state = saved
check("main sends one Slack notice per flush (2 flushes, 1 slosh)", notices == [1, 2])
check("pin 1 starts full without a flush", states[0]["tank"] == "full" and states[0]["flushes_total"] == 0)
low = next(s for s in states if s["tank"] == "low")
check("pin 0 counts only after 1s low", low["flushes_total"] == 1 and
      low["updated"] - low["low_since"] >= tw.DEBOUNCE and abs(low["low_since"] - (T0 + 10)) < 0.2)
check("refill to pin 1 keeps both flushes", states[-1]["tank"] == "full" and states[-1]["flushes_total"] == 2)
check("state reports the polarity in force", all(s["full_when"] == "open" for s in states))

print()
print("%d failed" % len(failures) if failures else "all passed")
sys.exit(1 if failures else 0)
