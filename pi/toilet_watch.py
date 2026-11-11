#!/usr/bin/env python3
"""Toilet tank watcher.

Reads a float switch on a Raspberry Pi GPIO pin, counts flushes, times how long
the tank stays low, and writes the result to a small JSON state file. The
Checkmk local check (`render_local_check`) reads that file and turns it into
two services: Toilet Tank and Toilet Flushes.

A flush = the tank goes from full to low and stays low for DEBOUNCE seconds.
"""

import json
import os
import sys
import threading
import time
import urllib.request
from datetime import datetime

STATE_FILE = os.environ.get("TOILET_STATE", "/var/lib/toilet-monitor/state.json")
GPIO_PIN = int(os.environ.get("TOILET_GPIO", "17"))
# This switch connects when the float drops, so a full tank leaves it open.
FULL_WHEN = os.environ.get("TOILET_FULL_WHEN", "open")
DEBOUNCE = float(os.environ.get("TOILET_DEBOUNCE", "1.0"))
POLL = 0.1
HEARTBEAT = 10

# Slack on every flush (optional). Either an incoming webhook (one channel, the
# safest), or a bot token plus a channel ID. Unset = no Slack.
SLACK_WEBHOOK_URL = os.environ.get("TOILET_SLACK_WEBHOOK_URL", "")
SLACK_BOT_TOKEN = os.environ.get("TOILET_SLACK_BOT_TOKEN", "")
SLACK_CHANNEL = os.environ.get("TOILET_SLACK_CHANNEL", "")

WARN_LOW_SECONDS = 120
CRIT_LOW_SECONDS = 600
STALE_SECONDS = 60


class Tank:
    """Pure flush/low-time logic. Feed it raw samples with timestamps."""

    def __init__(self, state=None):
        s = state or {}
        # No saved state: take the first reading as the truth, never a flush.
        self.full = (s["tank"] == "full") if "tank" in s else None
        self.low_since = s.get("low_since")
        self.flushes_total = s.get("flushes_total", 0)
        self.flushes_today = s.get("flushes_today", 0)
        self.day = s.get("day")
        self.last_flush = s.get("last_flush")
        self._pending = None  # (raw_full, first_seen) while a change settles

    def sample(self, raw_full, now):
        """Returns True when the stable state changed."""
        self._roll_day(now)
        if self.full is None:
            self.full = raw_full
            self.low_since = None if raw_full else now
            return True
        if raw_full == self.full:
            self._pending = None
            return False
        if self._pending is None or self._pending[0] != raw_full:
            self._pending = (raw_full, now)
            return False
        if now - self._pending[1] < DEBOUNCE:
            return False
        # The change held long enough. Date it from when it started.
        changed_at = self._pending[1]
        self._pending = None
        self.full = raw_full
        if raw_full:
            self.low_since = None
        else:
            self.low_since = changed_at
            self.flushes_total += 1
            self.flushes_today += 1
            self.last_flush = changed_at
        return True

    def _roll_day(self, now):
        today = datetime.fromtimestamp(now).strftime("%Y-%m-%d")
        if self.day != today:
            self.day = today
            self.flushes_today = 0

    def to_state(self, now):
        return {
            "tank": "low" if self.full is False else "full",
            "full_when": FULL_WHEN,
            "low_since": self.low_since,
            "flushes_total": self.flushes_total,
            "flushes_today": self.flushes_today,
            "day": self.day,
            "last_flush": self.last_flush,
            "updated": now,
        }


def render_local_check(state, now):
    """Checkmk local check output for a state dict (or None if unreadable)."""
    if state is None:
        return '2 "Toilet Tank" - Watcher has no state file. Is toilet-watch running?\n'
    age = now - state.get("updated", 0)
    if age > STALE_SECONDS:
        return '2 "Toilet Tank" - Watcher stopped updating %ds ago. Is toilet-watch running?\n' % age

    lines = []
    if state["tank"] == "full":
        low = 0
        text = "Tank full"
    else:
        low = int(now - state["low_since"])
        text = "Tank low for %s" % _human(low)
        if low >= WARN_LOW_SECONDS:
            text += " - toilet is running or the water is off"
    lines.append('P "Toilet Tank" tank_low_seconds=%d;%d;%d %s'
                 % (low, WARN_LOW_SECONDS, CRIT_LOW_SECONDS, text))

    today = state.get("flushes_today", 0)
    if state.get("day") != datetime.fromtimestamp(now).strftime("%Y-%m-%d"):
        today = 0
    last = state.get("last_flush")
    when = datetime.fromtimestamp(last).strftime("%H:%M") if last else "never"
    lines.append('0 "Toilet Flushes" flushes_today=%d|flushes_total=%d %d flushes today, last flush %s'
                 % (today, state.get("flushes_total", 0), today, when))
    return "\n".join(lines) + "\n"


def _human(seconds):
    if seconds < 60:
        return "%ds" % seconds
    return "%dm %02ds" % (seconds // 60, seconds % 60)


def flush_message(flushes_today, flushes_total, when):
    """The Slack text for one flush."""
    at = datetime.fromtimestamp(when).strftime("%-I:%M %p")
    return (":toilet: *FLUSH!* The toilet just flushed at %s.\n"
            "That's the %s flush today (%d all time)." % (at, _ordinal(flushes_today), flushes_total))


def _ordinal(n):
    if n % 100 in (11, 12, 13):
        return "%dth" % n
    return "%d%s" % (n, {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th"))


def slack_request(text):
    """The HTTP request for the configured Slack route, or None if Slack is off."""
    if SLACK_WEBHOOK_URL:
        return urllib.request.Request(SLACK_WEBHOOK_URL, data=json.dumps({"text": text}).encode(),
                                      headers={"Content-Type": "application/json"})
    if SLACK_BOT_TOKEN and SLACK_CHANNEL:
        return urllib.request.Request("https://slack.com/api/chat.postMessage",
                                      data=json.dumps({"channel": SLACK_CHANNEL, "text": text}).encode(),
                                      headers={"Content-Type": "application/json; charset=utf-8",
                                               "Authorization": "Bearer " + SLACK_BOT_TOKEN})
    return None


def post_slack(text):
    """Send it; never raise. Runs on its own thread so a slow Slack can't stall the float readings."""
    req = slack_request(text)
    if req is None:
        return False
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            body = r.read().decode("utf-8", "replace")
        if body.startswith("{") and not json.loads(body).get("ok", True):
            print("slack: refused: %s" % body[:200], flush=True)
            return False
        return True
    except Exception as e:  # network down, bad token: log it and keep counting
        print("slack: failed: %s" % e, flush=True)
        return False


def notify_flush(tank):
    text = flush_message(tank.flushes_today, tank.flushes_total, tank.last_flush)
    threading.Thread(target=post_slack, args=(text,), daemon=True).start()


def load_state(path=STATE_FILE):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def save_state(state, path=STATE_FILE):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f)
    os.replace(tmp, path)


def main():
    from gpiozero import Button  # only on the Pi

    switch = Button(GPIO_PIN, pull_up=True, bounce_time=None)
    tank = Tank(load_state())
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    last_write = 0
    slack = "webhook" if SLACK_WEBHOOK_URL else ("bot to %s" % SLACK_CHANNEL if SLACK_BOT_TOKEN and SLACK_CHANNEL else "off")
    print("toilet-watch: GPIO%d, full when %s, slack %s" % (GPIO_PIN, FULL_WHEN, slack), flush=True)
    while True:
        now = time.time()
        closed = switch.is_pressed
        raw_full = closed if FULL_WHEN == "closed" else not closed
        before = tank.flushes_total
        if tank.sample(raw_full, now):
            print("tank %s, flushes today %d" % ("full" if tank.full else "LOW", tank.flushes_today), flush=True)
            if tank.flushes_total > before:
                notify_flush(tank)
            save_state(tank.to_state(now))
            last_write = now
        elif now - last_write >= HEARTBEAT:
            save_state(tank.to_state(now))
            last_write = now
        time.sleep(POLL)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "check":
        sys.stdout.write(render_local_check(load_state(), time.time()))
    elif len(sys.argv) > 1 and sys.argv[1] == "slack-test":
        # Sends one sample flush message through whatever Slack route is configured.
        if slack_request("x") is None:
            sys.exit("Slack is off: set TOILET_SLACK_WEBHOOK_URL, or TOILET_SLACK_BOT_TOKEN + TOILET_SLACK_CHANNEL")
        if not post_slack(flush_message(1, 1, time.time()) + "\n_(test message)_"):
            sys.exit(1)
    elif len(sys.argv) > 1 and sys.argv[1] == "raw":
        # Live readout for wiring and calibration: lift the float, watch it change.
        from gpiozero import Button
        b = Button(GPIO_PIN, pull_up=True, bounce_time=None)
        while True:
            print("switch CLOSED" if b.is_pressed else "switch open  ", flush=True)
            time.sleep(0.5)
    else:
        main()
