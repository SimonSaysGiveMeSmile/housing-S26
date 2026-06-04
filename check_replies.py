#!/usr/bin/env python3
"""
check_replies.py — scan for landlord replies, notify on anything new.

Two sources (per your setup):
  1. EMAIL inbox via IMAP — where Craigslist replies land. Credentials come
     from secrets.json (you create it; see secrets.example.json). We read only
     recent messages and match housing-related subjects/senders. We NEVER print
     the password and NEVER send anything.
  2. PLATFORM inboxes (SpareRoom / Reddit / Zillow) — these need a logged-in
     browser. This script can open them with --browser so you can eyeball
     threads; full auto-parsing of each platform's DOM is brittle, so we open
     the inbox pages and let you read, while still de-duping email replies.

PHONE texts/calls to your number CANNOT be tracked here — the script will remind
you to check your phone, but that part stays manual.

Usage:
  python3 check_replies.py             # email scan only (headless, safe)
  python3 check_replies.py --browser   # also open platform inboxes to review
"""
import argparse
import email
import imaplib
import sys
import time
from email.header import decode_header

import watch_config as c

# Subject/sender signals that a message is about housing outreach.
REPLY_SIGNALS = [
    "room", "rent", "listing", "apartment", "sublet", "available", "tour",
    "craigslist", "spareroom", "housing", "bedroom", "lease", "palo alto",
    "stanford", "menlo", "mountain view",
]

PLATFORM_INBOXES = [
    ("SpareRoom messages", "https://www.spareroom.com/myaccount/"),
    ("Reddit inbox", "https://www.reddit.com/message/inbox/"),
    ("Zillow messages", "https://www.zillow.com/messaging/"),
]


def _decode(s):
    if not s:
        return ""
    parts = decode_header(s)
    out = ""
    for text, enc in parts:
        if isinstance(text, bytes):
            out += text.decode(enc or "utf-8", "replace")
        else:
            out += text
    return out


def looks_like_reply(subject, sender):
    blob = f"{subject} {sender}".lower()
    return any(sig in blob for sig in REPLY_SIGNALS)


def scan_email(state):
    """Connect via IMAP, find recent housing replies, notify on new ones."""
    secrets = c.load_secrets()
    imap = secrets.get("imap", {})
    host = imap.get("host")
    user = imap.get("user")
    pw = imap.get("app_password")
    if not (host and user and pw):
        c.log("  email: no IMAP creds in secrets.json — skipping email scan.")
        c.log("         (copy secrets.example.json -> secrets.json and fill it in)")
        return 0

    seen = set(state.setdefault("replies_seen", []))
    new_count = 0
    try:
        M = imaplib.IMAP4_SSL(host)
        M.login(user, pw)              # password used only here, never logged
        M.select("INBOX")
        # Last 7 days, unseen-or-seen — we de-dupe by Message-ID ourselves.
        since = time.strftime("%d-%b-%Y", time.localtime(time.time() - 7 * 86400))
        typ, data = M.search(None, f'(SINCE {since})')
        ids = data[0].split() if data and data[0] else []
        for mid in ids[-100:]:         # cap work
            typ, msg_data = M.fetch(mid, "(RFC822.HEADER)")
            if typ != "OK" or not msg_data or not msg_data[0]:
                continue
            hdr = email.message_from_bytes(msg_data[0][1])
            msg_id = hdr.get("Message-ID", "") or f"{hdr.get('Date','')}-{hdr.get('From','')}"
            if msg_id in seen:
                continue
            subject = _decode(hdr.get("Subject", ""))
            sender = _decode(hdr.get("From", ""))
            if looks_like_reply(subject, sender):
                seen.add(msg_id)
                new_count += 1
                # Sender name only — avoid echoing full addresses to the log.
                who = sender.split("<")[0].strip() or sender
                c.notify("New housing reply", f"{who}: {subject[:60]}")
                c.log(f"  📩 REPLY from {who} — “{subject[:70]}”")
        M.logout()
    except (imaplib.IMAP4.error, OSError) as e:
        c.log(f"  email: IMAP error ({type(e).__name__}) — check host/creds.")
        return 0

    state["replies_seen"] = list(seen)
    return new_count


def open_platform_inboxes():
    """Open each platform inbox in a visible browser for manual review."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        c.log("  playwright not available — can't open platform inboxes.")
        return
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_context().new_page()
        for name, url in PLATFORM_INBOXES:
            c.log(f"  opening {name}: {url}")
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                time.sleep(4)
            except Exception as e:
                c.log(f"    couldn't open {name}: {e}")
        c.log("  Review the open tabs. Closing in 45s…")
        time.sleep(45)
        browser.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--browser", action="store_true",
                    help="also open platform inboxes for manual review")
    args = ap.parse_args()

    c.log("=" * 64)
    c.log("CHECK_REPLIES START")
    hb = c.heartbeat_start("check_replies", "scanning inbox")
    state = c.load_state()

    n = scan_email(state)
    c.save_state(state)
    if n:
        c.log(f"  {n} new email reply(ies).")
    else:
        c.log("  no new email replies.")

    if args.browser:
        open_platform_inboxes()
    else:
        c.log("  (platform inboxes not checked — re-run with --browser to review)")

    c.log("  Reminder: check your PHONE for texts/calls — not trackable here.")
    c.log("CHECK_REPLIES DONE")
    c.heartbeat_done("check_replies", f"{n} new repl{'y' if n == 1 else 'ies'}",
                     ok=True, started=hb)
    return 0


if __name__ == "__main__":
    sys.exit(main())
