#!/usr/bin/env python3
"""
auto_send.py — safe, semi-automated outreach for queued matches.

Reads send_queue.json (filled by watch_listings.py), opens each listing's
DETAIL page, and confirms it's worth contacting before sending:

  GATE 1  budget   — re-parse price on the detail page; must be <= MAX_BUDGET
  GATE 2  date     — body must not say July/Aug/mid-late-June (June-1 rule)
  GATE 3  scam     — body must not trip scam heuristics
  GATE 4  dedupe   — never message the same listing twice (state['sent'])
  GATE 5  cap      — at most MAX_SENDS_PER_RUN per run
  GATE 6  hours    — only send 8am–9pm local (no 3am bot-grams)

Then it composes a polite, truthful Craigslist reply.

SAFETY: runs in DRY_RUN mode by default — it shows exactly what it WOULD send
and which gates passed, but sends nothing. Flip --live (and you must have the
browser session ready) to actually send. This is intentional: it never fires
real messages under your name from untested code on first run.

Usage:
  python3 auto_send.py            # dry run, headless, safe
  python3 auto_send.py --live     # actually send (opens visible browser)
  python3 auto_send.py --limit 3  # cap this run at 3 sends
"""
import argparse
import sys
import time
import urllib.request
import urllib.error

import watch_config as c

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

MAX_SENDS_PER_RUN = 5   # politeness + anti-bot cap; override with --limit


def fetch_detail(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read().decode("utf-8", "replace")
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
        c.log(f"    detail fetch failed: {e}")
        return ""


def extract_detail(html_text):
    """Pull body text + the posting price from a Craigslist detail page."""
    import re
    body = ""
    bm = re.search(r'id="postingbody">(.*?)</section>', html_text, re.S)
    if bm:
        body = re.sub(r"<[^>]+>", " ", bm.group(1))
        body = re.sub(r"\s+", " ", body).strip()
    pm = re.search(r'class="price">\s*(\$[\d,]+)', html_text)
    price = pm.group(1) if pm else ""
    removed = ("This posting has been deleted" in html_text
               or "This posting has expired" in html_text)
    return {"body": body, "price": price, "removed": removed}


def gate_check(listing):
    """Run all pre-send gates against the DETAIL page. Returns (ok, reasons)."""
    detail = extract_detail(fetch_detail(listing["url"]))
    reasons = []

    if detail["removed"]:
        return False, ["listing deleted/expired"]

    # Merge detail body into the listing for richer checks.
    merged = dict(listing)
    if detail["body"]:
        merged["body"] = detail["body"]
    # Prefer the price shown on the detail page if present.
    if detail["price"]:
        merged["price"] = detail["price"]
        merged["price_numeric"] = c.parse_price(detail["price"])

    # GATE 1 — budget (the thing you explicitly asked to verify)
    if not c.within_budget(merged):
        reasons.append(f"over budget / no price (got {merged.get('price_numeric')})")
    # GATE 2 — date
    if c.looks_too_late(merged):
        reasons.append("start date looks July/Aug/mid-late June")
    # GATE 3 — scam
    sf = c.scam_flags(merged)
    if sf:
        reasons.extend(sf)

    return (len(reasons) == 0), reasons, merged


def send_craigslist_reply(page, url, message):
    """Open listing, click reply, surface the contact email via mailto.

    Mirrors contact_landlords.py: Craigslist hides the email behind the reply
    button and often shows a captcha, so we open the mail compose rather than
    blindly POSTing. You complete the send in your mail client — that keeps a
    human in the loop on the actual outbound message.
    """
    from playwright.sync_api import TimeoutError as PWTimeout
    page.goto(url, wait_until="domcontentloaded")
    time.sleep(2)
    try:
        page.locator('button.reply-button, button:has-text("reply")').first.click(timeout=8000)
        time.sleep(2)
        email_link = page.locator('a.mailapp, a[href^="mailto:"]').first
        if email_link.is_visible(timeout=4000):
            href = email_link.get_attribute("href") or ""
            email = href.replace("mailto:", "").split("?")[0]
            import subprocess, urllib.parse
            subject = urllib.parse.quote("Re: your room listing — Stanford summer student")
            body = urllib.parse.quote(message)
            subprocess.run(["open", f"mailto:{email}?subject={subject}&body={body}"], check=False)
            c.log(f"    ✓ composed email to {email}")
            return True
        c.log("    ⚠ no reply email found (captcha or login needed)")
        return False
    except PWTimeout:
        c.log("    ⚠ reply flow timed out (captcha?)")
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="actually send (default: dry run)")
    ap.add_argument("--limit", type=int, default=MAX_SENDS_PER_RUN)
    args = ap.parse_args()
    dry = not args.live

    c.log("=" * 64)
    c.log(f"AUTO_SEND START — mode={'DRY-RUN' if dry else 'LIVE'} limit={args.limit}")
    hb = c.heartbeat_start("auto_send", "DRY-RUN" if dry else "LIVE")

    # GATE 6 — send hours (skip in dry-run so you can preview anytime)
    if not dry and not c.within_send_hours():
        c.log(f"  outside send hours ({c.SEND_START_HOUR}:00–{c.SEND_END_HOUR}:00). "
              f"Exiting without sending.")
        c.heartbeat_done("auto_send", "skipped — outside send hours", ok=True, started=hb)
        return 0

    state = c.load_state()
    sent = state.setdefault("sent", {})
    queue = c.load_queue()
    if not queue:
        c.log("  send queue empty — nothing to do.")
        c.heartbeat_done("auto_send", "queue empty", ok=True, started=hb)
        return 0

    page = ctx = browser = pw = None
    if not dry:
        from playwright.sync_api import sync_playwright
        pw = sync_playwright().start()
        browser = pw.chromium.launch(headless=False,
                                     args=["--disable-blink-features=AutomationControlled"])
        ctx = browser.new_context(user_agent=UA, viewport={"width": 1400, "height": 900})
        page = ctx.new_page()
        c.log("  Browser open. Solve any captcha / login when prompted.")

    sends = 0
    remaining = []
    for listing in queue:
        lid = listing["id"]
        if lid in sent:                       # GATE 4 — dedupe
            c.log(f"  skip {lid}: already messaged {sent[lid].get('when')}")
            continue
        if sends >= args.limit:               # GATE 5 — cap
            remaining.append(listing)
            continue

        result = gate_check(listing)
        ok, reasons = result[0], result[1]
        merged = result[2] if len(result) > 2 else listing
        price = merged.get("price_numeric")
        label = f"${price} {listing['title'][:45]}"

        if not ok:
            c.log(f"  ✗ HOLD {label}: {'; '.join(reasons)}")
            # keep in queue only if it might become sendable (not deleted/scam)
            if not any("deleted" in r or "scam" in r for r in reasons):
                remaining.append(listing)
            continue

        msg = c.build_intro(merged)
        if dry:
            c.log(f"  [DRY] WOULD SEND → {label}")
            c.log(f"        {listing['url']}")
            c.log(f"        msg: {msg[:90]}…")
            remaining.append(listing)         # stays queued for the real run
            sends += 1
            continue

        c.log(f"  → sending {label}")
        if send_craigslist_reply(page, listing["url"], msg):
            sent[lid] = {"when": time.strftime("%Y-%m-%d %H:%M:%S"),
                         "url": listing["url"], "price": price}
            sends += 1
            time.sleep(8)                     # polite spacing
        else:
            remaining.append(listing)

    state["sent"] = sent
    c.save_state(state)
    c.save_queue(remaining)

    if not dry and browser:
        time.sleep(3)
        browser.close()
        pw.stop()

    verb = "would send" if dry else "sent"
    c.notify("Outreach run done", f"{sends} {verb}, {len(remaining)} left in queue")
    c.log(f"AUTO_SEND DONE — {sends} {verb}, {len(remaining)} remaining")
    c.heartbeat_done(
        "auto_send",
        f"{'[dry] ' if dry else ''}{sends} {verb}, {len(remaining)} queued",
        ok=True, started=hb,
    )
    if dry:
        c.log("  This was a DRY RUN. Re-run with --live to actually send.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
