#!/bin/bash
# Sends one test flush message to Slack using the settings in /etc/default/toilet-watch.
#   sudo bash slack-test.sh
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "Run it with sudo: sudo bash slack-test.sh"; exit 1; }
set -a
. /etc/default/toilet-watch
set +a
python3 /opt/toilet-monitor/toilet_watch.py slack-test && echo "Sent. Check your Slack channel."
