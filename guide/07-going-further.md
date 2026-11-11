# Going further

[◀ Slack alerts](06-slack-alerts.md) · [Back to the guide](../README.md)

## Catch a running toilet

The watcher also times how long the tank stays low. A flush refills in under a minute. If the tank is still low after **2 minutes**, the toilet is running or the water is off. After **10 minutes**, something is really wrong. The Flush Control page shows both thresholds on the low-water timer.

A leaky flapper shows up a different way: **phantom flushes**, refills that nobody asked for. If your count goes up at 3 AM and nobody was there, that's your flapper.

One thing a float can't see: a fill valve that's stuck open keeps the tank full and sends water down the overflow tube. The tank never drops, so nothing looks wrong.

## Put your toilet in Checkmk

If you run [Checkmk](https://checkmk.com) (I have [a whole video on it](https://www.youtube.com/watch?v=Bjifz55TTPI)), the toilet can be a host with two services:

| Service | What it shows |
|---|---|
| **Toilet Tank** | OK when full, WARN after 2 minutes low, CRIT after 10. Also CRIT if the watcher stops. |
| **Toilet Flushes** | Flushes today and all time, graphed |

1. In your Checkmk site, go to **Setup → Agents → Linux** and download the agent `.deb` for your Pi (`arm64` for 64-bit Pi OS, or the `all` package).
2. Copy it into the `~/toilet-monitor-guide/pi/` folder on the Pi.
3. Run `sudo bash ~/toilet-monitor-guide/pi/install.sh` again. It sees the `.deb`, installs the agent, and adds the toilet local check.
4. Add the Pi as a host in Checkmk, run service discovery, and activate changes.

Check it on the Pi:

```bash
/usr/lib/check_mk_agent/local/toilet
```

```
P "Toilet Tank" tank_low_seconds=0;120;600 Tank full
0 "Toilet Flushes" flushes_today=3|flushes_total=41 3 flushes today, last flush 15:07
```

## Run the tests

The flush logic has tests that run on any computer with Python 3, using a fake clock and a fake switch. No Pi needed:

```bash
python3 test/test_watch.py
python3 test/test_simple.py pi/toilet_simple.py
```

## Troubleshooting

| Problem | Fix |
|---|---|
| Page won't load at all | `systemctl status toilet-live`. Is the Pi's IP right, and can your computer reach port 8080? |
| Page says **Pi disconnected** | The page loaded but lost the Pi. Check the Pi is on the network: `systemctl status toilet-live`. |
| Page says the **watcher is down** | `journalctl -u toilet-watch -n 20`. Usually a typo in `/etc/default/toilet-watch`. |
| Counts go up when nobody flushed | A leaky flapper, or the float rubbing and sticking. Add a bigger spacer. |
| Never counts a flush | Float sits too low, so the water never drops below it. Move it up. Check with `python3 /opt/toilet-monitor/toilet_watch.py raw` (stop the service first with `sudo systemctl stop toilet-watch`). |
| Counts are backwards (counts the refill) | Flip `TOILET_FULL_WHEN` between `open` and `closed`. |
| Wrong times after a reboot | Most Pis have no clock battery, so the time is wrong until it syncs over the internet. Don't reboot it mid-flush. |
| Slack test says nothing is set | You edited the repo's `toilet-watch.default`, not `/etc/default/toilet-watch`. |

## Update

```bash
cd ~/toilet-monitor-guide && git pull && sudo bash pi/install.sh
```

Your flush counts and settings are kept.
