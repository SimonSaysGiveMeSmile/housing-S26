#!/bin/bash
# run_watch.sh — one full monitoring cycle (scan listings + check replies).
# Called by launchd every 30 min, or run by hand anytime.
#
# By default the SENDER runs in DRY-RUN (sends nothing). To let the scheduler
# actually send, set AUTO_SEND_LIVE=1 in the launchd plist's environment —
# only do that once you've watched a few dry runs and logged into Craigslist.

cd "$(dirname "$0")" || exit 1
PY="$(command -v python3)"

echo "===== run_watch $(date '+%Y-%m-%d %H:%M:%S') ====="

# 1) scan for new below-budget June-1 listings -> queue + notify
"$PY" watch_listings.py

# 2) sender: dry-run unless AUTO_SEND_LIVE=1
if [ "$AUTO_SEND_LIVE" = "1" ]; then
    "$PY" auto_send.py --live --limit 5
else
    "$PY" auto_send.py --limit 5
fi

# 3) check email replies (platform inboxes need --browser, run manually)
"$PY" check_replies.py

echo "===== run_watch done ====="
