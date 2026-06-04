#!/usr/bin/env python3
"""
watch_status.py — real-time status of the housing monitor.

Three ways to view:
  python3 watch_status.py            # live terminal dashboard (refreshes in place)
  python3 watch_status.py --once     # print status once and exit (good for piping)
  python3 watch_status.py --serve    # tiny web view at http://localhost:3112/

It reports, for each component (watch_listings / auto_send / check_replies):
  - state: running / idle, how long ago it last ran, last result line
  - whether the launchd scheduler is loaded
  - queue depth, # sent, # replies seen, scam-flag count
  - the tail of watch.log

Pure reader: it never sends anything and never edits state/queue.
"""
import json
import os
import time

import watch_config as c

STATUS_PORT = 3112
STALE_AFTER = 45 * 60   # a heartbeat older than this (no run) is "stale"


def _ago(ts):
    if not ts:
        return "never"
    s = int(time.time() - ts)
    if s < 60:
        return f"{s}s ago"
    if s < 3600:
        return f"{s // 60}m {s % 60}s ago"
    return f"{s // 3600}h {(s % 3600) // 60}m ago"


def scheduler_loaded():
    """True if the launchd job is loaded. Best-effort; no error if launchctl absent."""
    try:
        import subprocess
        out = subprocess.run(["launchctl", "list"], capture_output=True, text=True, timeout=5)
        return "com.simon.housing-watch" in out.stdout
    except Exception:
        return False


def gather():
    """Collect everything the views need into one dict."""
    status = c.load_run_status()
    state = c.load_state()
    queue = c.load_queue()

    comps = []
    for key, label in [("watch_listings", "Listing monitor"),
                       ("auto_send", "Auto-sender"),
                       ("check_replies", "Reply tracker")]:
        rec = status.get(key, {})
        running = rec.get("state") == "running"
        ref_ts = rec.get("started_at") if running else rec.get("finished_at")
        stale = (not running) and ref_ts and (time.time() - ref_ts > STALE_AFTER)
        comps.append({
            "key": key,
            "label": label,
            "state": rec.get("state", "never run"),
            "running": running,
            "stale": bool(stale),
            "detail": rec.get("detail", ""),
            "result": rec.get("result", ""),
            "ago": _ago(ref_ts),
            "duration": rec.get("duration"),
            "runs": rec.get("runs", 0),
            "last_ok": rec.get("last_ok"),
            "ok": rec.get("ok", True),
        })

    return {
        "components": comps,
        "queue_depth": len(queue),
        "sent_count": len(state.get("sent", {})),
        "replies_count": len(state.get("replies_seen", [])),
        "seen_count": len(state.get("seen_ids", [])),
        "scheduler": scheduler_loaded(),
        "now": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


def log_tail(n=12):
    if not os.path.exists(c.WATCH_LOG):
        return []
    try:
        with open(c.WATCH_LOG) as f:
            lines = f.readlines()
        return [l.rstrip("\n") for l in lines[-n:]]
    except OSError:
        return []


# ---------------------------------------------------------------------------
# Terminal rendering (ANSI). Live mode clears + redraws so it updates in place.
# ---------------------------------------------------------------------------
RESET = "\033[0m"; BOLD = "\033[1m"; DIM = "\033[2m"
GREEN = "\033[32m"; YELLOW = "\033[33m"; RED = "\033[31m"; CYAN = "\033[36m"; GREY = "\033[90m"


def _dot(comp):
    if comp["running"]:
        return f"{CYAN}● running{RESET}"
    if comp["stale"]:
        return f"{YELLOW}● stale{RESET}"
    if not comp["ok"]:
        return f"{RED}● error{RESET}"
    if comp["state"] == "never run":
        return f"{GREY}○ never run{RESET}"
    return f"{GREEN}● idle{RESET}"


def render_terminal(data):
    L = []
    sch = f"{GREEN}loaded{RESET}" if data["scheduler"] else f"{YELLOW}not loaded{RESET}"
    L.append(f"{BOLD}Housing Monitor — live status{RESET}   {DIM}{data['now']}{RESET}")
    L.append(f"scheduler (every 30m): {sch}    "
             f"queue {BOLD}{data['queue_depth']}{RESET}  "
             f"sent {BOLD}{data['sent_count']}{RESET}  "
             f"replies {BOLD}{data['replies_count']}{RESET}  "
             f"seen {data['seen_count']}")
    L.append("─" * 64)
    for comp in data["components"]:
        L.append(f"{_dot(comp)}  {BOLD}{comp['label']:<16}{RESET} "
                 f"{DIM}{comp['ago']:<12}{RESET} runs:{comp['runs']}")
        if comp["result"]:
            L.append(f"     {GREY}└ {comp['result']}{RESET}")
        elif comp["running"] and comp["detail"]:
            L.append(f"     {GREY}└ {comp['detail']}…{RESET}")
    L.append("─" * 64)
    L.append(f"{DIM}recent log:{RESET}")
    for line in log_tail(8):
        short = line if len(line) <= 76 else line[:73] + "…"
        L.append(f"{GREY}  {short}{RESET}")
    return "\n".join(L)


def live_loop(interval=3):
    """Clear-and-redraw terminal dashboard. Ctrl-C to exit."""
    try:
        while True:
            os.system("clear")
            print(render_terminal(gather()))
            print(f"\n{DIM}refreshing every {interval}s — Ctrl-C to exit{RESET}")
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nbye")


# ---------------------------------------------------------------------------
# Web rendering — self-refreshing HTML. Reused by palo_alto_server's /status
# route (import render_html) and by --serve below.
# ---------------------------------------------------------------------------
def render_html(refresh=5):
    import html as _h
    d = gather()

    def badge(comp):
        if comp["running"]:
            return '<span class="b run">running</span>'
        if comp["stale"]:
            return '<span class="b stale">stale</span>'
        if not comp["ok"]:
            return '<span class="b err">error</span>'
        if comp["state"] == "never run":
            return '<span class="b none">never run</span>'
        return '<span class="b idle">idle</span>'

    rows = []
    for comp in d["components"]:
        line = comp["result"] or (comp["detail"] + "…" if comp["running"] and comp["detail"] else "")
        rows.append(
            f'<div class="comp">{badge(comp)}'
            f'<div class="cinfo"><b>{_h.escape(comp["label"])}</b>'
            f'<span class="meta">{comp["ago"]} · {comp["runs"]} runs'
            f'{" · " + str(comp["duration"]) + "s" if comp.get("duration") else ""}</span>'
            f'<span class="res">{_h.escape(line)}</span></div></div>'
        )

    sch = ('<span class="b idle">loaded</span>' if d["scheduler"]
           else '<span class="b stale">not loaded</span>')
    logs = "".join(f"<div>{_h.escape(l)}</div>" for l in log_tail(12))

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<meta http-equiv="refresh" content="{refresh}">
<title>Housing Monitor — status</title><style>
body{{font-family:-apple-system,system-ui,sans-serif;max-width:720px;margin:0 auto;padding:22px;background:#0f1117;color:#e6e6e6}}
h1{{font-size:19px;margin:0 0 4px}}
.sub{{color:#8a8f98;font-size:12px;margin-bottom:16px}}
.stat{{display:flex;gap:18px;flex-wrap:wrap;background:#181b24;border-radius:9px;padding:12px 15px;font-size:13px;margin-bottom:14px}}
.stat b{{font-size:17px;display:block}}
.comp{{display:flex;align-items:center;gap:12px;background:#181b24;border-radius:9px;padding:12px 15px;margin:9px 0}}
.cinfo{{display:flex;flex-direction:column}}
.cinfo b{{font-size:14px}}
.meta{{color:#8a8f98;font-size:11px;margin-top:1px}}
.res{{color:#b8c0cc;font-size:12px;margin-top:3px}}
.b{{font-size:11px;font-weight:700;padding:3px 9px;border-radius:11px;white-space:nowrap}}
.b.run{{background:#0d3b66;color:#5bc0ff}}.b.idle{{background:#13402a;color:#5ad18a}}
.b.stale{{background:#4a3b0d;color:#ffd24d}}.b.err{{background:#4a1414;color:#ff7a7a}}
.b.none{{background:#2a2e38;color:#8a8f98}}
.log{{background:#0a0c11;border-radius:9px;padding:12px 15px;font-family:ui-monospace,Menlo,monospace;font-size:11px;color:#8a8f98;line-height:1.55;margin-top:14px;overflow-x:auto;white-space:nowrap}}
</style></head><body>
<h1>Housing Monitor — live status</h1>
<div class="sub">auto-refresh {refresh}s · {d['now']} · scheduler (every 30m): {sch}</div>
<div class="stat">
<div>queue<b>{d['queue_depth']}</b></div><div>sent<b>{d['sent_count']}</b></div>
<div>replies<b>{d['replies_count']}</b></div><div>seen<b>{d['seen_count']}</b></div></div>
{''.join(rows)}
<div class="log">{logs}</div>
</body></html>"""


def serve(port=STATUS_PORT):
    import http.server, socketserver
    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a, **k): pass
        def do_GET(self):
            out = render_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers(); self.wfile.write(out)
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("127.0.0.1", port), H) as s:
        print(f"Status dashboard at http://localhost:{port}  (Ctrl-C to stop)")
        try:
            s.serve_forever()
        except KeyboardInterrupt:
            print("\nbye")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true", help="print once and exit")
    ap.add_argument("--serve", action="store_true", help="run web dashboard")
    ap.add_argument("--interval", type=int, default=3, help="terminal refresh seconds")
    a = ap.parse_args()
    if a.serve:
        serve()
    elif a.once:
        print(render_terminal(gather()))
    else:
        live_loop(a.interval)
