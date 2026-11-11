#!/bin/bash
# Installs the toilet watcher and the Flush Control page on a Raspberry Pi.
#   sudo bash install.sh          install or update (your flush counts are kept)
#   sudo bash install.sh reset    same, but start the flush counts over at zero
# Safe to run again any time.
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "Run it with sudo: sudo bash install.sh"; exit 1; }
cd "$(dirname "$0")"
PAGE_USER="${SUDO_USER:-root}"   # the page runs as you, not as root

echo "--- installing gpiozero"
apt-get update -qq
apt-get install -y -qq python3-gpiozero python3-lgpio

install -d /opt/toilet-monitor/live /var/lib/toilet-monitor
if [ "${1:-}" = reset ]; then
  systemctl stop toilet-watch 2>/dev/null || true   # it rewrites the file every 10 s
  rm -f /var/lib/toilet-monitor/state.json
  echo "--- flush counts reset"
fi

echo "--- installing the watcher"
install -m 0755 toilet_watch.py /opt/toilet-monitor/
install -m 0644 live/server.py live/index.html /opt/toilet-monitor/live/
# Your settings live in /etc/default/toilet-watch. Never overwritten after the first install.
[ -f /etc/default/toilet-watch ] || install -m 0644 toilet-watch.default /etc/default/toilet-watch
chmod 600 /etc/default/toilet-watch   # it may hold your Slack webhook
install -m 0644 toilet-watch.service /etc/systemd/system/toilet-watch.service

echo "--- installing the Flush Control page (runs as $PAGE_USER)"
# The page reads the switch with pinctrl, which needs the gpio group.
getent group gpio >/dev/null && usermod -aG gpio "$PAGE_USER" || true
cat > /etc/systemd/system/toilet-live.service <<EOF
[Unit]
Description=Flush Control live toilet page on port 8080
After=toilet-watch.service

[Service]
User=$PAGE_USER
Environment=TOILET_GPIO=$(grep -E '^TOILET_GPIO=' /etc/default/toilet-watch | cut -d= -f2 || echo 17)
ExecStart=/usr/bin/python3 /opt/toilet-monitor/live/server.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now toilet-watch toilet-live
systemctl restart toilet-watch toilet-live

# Optional: Checkmk. Drop your Checkmk site's agent .deb in this folder and it gets installed too.
deb=$(ls check-mk-agent_*.deb 2>/dev/null | head -1 || true)
if [ -n "$deb" ]; then
  echo "--- installing Checkmk agent $deb"
  dpkg -i "$deb"
  install -d /usr/lib/check_mk_agent/local
  install -m 0755 ../checkmk/toilet-localcheck /usr/lib/check_mk_agent/local/toilet
fi

sleep 3
echo
echo "watcher: $(systemctl is-active toilet-watch)    page: $(systemctl is-active toilet-live)"
echo "Open http://$(hostname -I | awk '{print $1}'):8080 in your browser."
