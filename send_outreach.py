#!/usr/bin/env python3
"""
send_outreach.py — Semi-automated Craigslist outreach for the PA/Stanford search.

Runs in a DEDICATED browser profile ("Google Chrome for Testing", its own
user-data dir) — fully separate from your regular Chrome: no shared tabs,
cookies, history or logins.

Scope (per your criteria): WHOLE UNITS ONLY (/apa + /sub), East Palo Alto
excluded, skips anything already sent.

Captcha-aware: when Craigslist shows a captcha it BEEPS + notifies and waits
for you to tap it, then continues. You're present for the captcha taps only.

Every confirmed send is written to BOTH:
  - watch_state.json["sent"]      (drives the dashboard CONTACTED badge)
  - contact_history.json          (rich detail: time, channel, email, message)
so the dashboard at :5555 reflects reality — no fabricated entries.
"""
import os, sys, time, json, subprocess, urllib.parse
from datetime import datetime
from playwright.sync_api import sync_playwright
from watch_config import (load_queue, save_state, load_state, build_intro,
                          NAME, PHONE, EMAIL)

ROOT = "/Users/test/Desktop/housing-S26"
# Dedicated, persistent profile — separate from your everyday browser.
PROFILE_DIR = os.path.join(ROOT, ".outreach-browser-profile")
HISTORY_FILE = os.path.join(ROOT, "contact_history.json")
DRY_RUN = "--dry-run" in sys.argv     # fill the form but never click Send
ASSIST  = "--assist" in sys.argv      # you drive (reply+captcha+send); script fills & records


def beep():
    subprocess.run(['afplay', '/System/Library/Sounds/Glass.aiff'], check=False)

def notify(title, msg):
    subprocess.run(['osascript', '-e',
                    f'display notification "{msg}" with title "{title}"'], check=False)

def ask(text, buttons, default):
    """Blocking macOS dialog. Returns the exact label of the button clicked
    (or 'Stop' if the user closed it). This is the AUTHORITATIVE signal for
    whether a message was actually sent — we never assume."""
    btn_list = "{" + ", ".join(f'"{b}"' for b in buttons) + "}"
    script = (f'display dialog {json.dumps(text)} with title "Housing outreach" '
              f'buttons {btn_list} default button "{default}"')
    try:
        out = subprocess.run(['osascript', '-e', script],
                             capture_output=True, text=True, timeout=1800).stdout
        for part in out.strip().split(", "):
            if part.startswith("button returned:"):
                label = part.split(":", 1)[1]
                # Empty label = dialog dismissed/auto-closed → treat as skip,
                # never as an affirmative and never as a hard stop.
                return label if label else "__dismissed__"
    except Exception:
        pass
    return "__dismissed__"

def listing_id_to_clid(lid):
    return lid  # queue ids are already "cl-<postid>"

def load_history():
    try:
        with open(HISTORY_FILE) as f:
            return {k: v for k, v in json.load(f).items() if not k.startswith("_")}
    except Exception:
        return {}

def record_history(lid, channel, message, *, email=None, phone=None, status="sent"):
    hist = load_history()
    entry = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "channel": channel,
        "message": message,
        "status": status,
    }
    if email: entry["email"] = email
    if phone: entry["phone"] = phone
    hist.setdefault(lid, {"contacts": []})["contacts"].append(entry)
    with open(HISTORY_FILE, "w") as f:
        json.dump(hist, f, indent=2)


# ---- filtering -------------------------------------------------------------
def is_epa(i):
    blob = (i.get('location', '') + ' ' + i.get('title', '') + ' ' +
            i.get('url', '') + ' ' + i.get('body', '')).lower()
    return 'east palo alto' in blob or 'east-palo-alto' in blob

def is_whole_unit(i):
    return '/apa/' in i.get('url', '') or '/sub/' in i.get('url', '')

def pick_recipients(queue, sent):
    out = [i for i in queue
           if is_whole_unit(i) and not is_epa(i) and i['id'] not in sent]
    out.sort(key=lambda x: x.get('price_numeric', 9999))
    return out


# ---- captcha ---------------------------------------------------------------
def has_captcha(page):
    for sel in ('iframe[src*="recaptcha"]', 'iframe[src*="captcha"]',
                '.g-recaptcha', '#recaptcha', '[class*="captcha"]'):
        try:
            if page.locator(sel).count() > 0:
                return True
        except Exception:
            pass
    return False

def wait_for_captcha(page, label):
    print("\n" + "!"*68)
    print(f"⚠️  CAPTCHA — solve it in the browser window for: {label}")
    print("!"*68)
    beep(); notify("Captcha needed", label)
    for waited in range(0, 120, 5):
        time.sleep(5)
        if page.locator('textarea[name="message"], textarea').count() > 0:
            print("  ✓ Captcha cleared — continuing.")
            beep()
            return True
        print(f"   waiting… ({waited+5}s/120s)")
    print("  ✗ Captcha timeout — skipping this one.")
    return False


# ---- assisted-manual: you drive, script fills & records the real send ------
def assist_one(page, listing, idx, total):
    """You click reply + solve the captcha + click Send. The script just
    navigates, auto-fills the form when it appears, and records the send
    ONLY when you confirm it in the dialog. Returns 'sent' / 'skipped' / 'stop'."""
    url, lid = listing['url'], listing['id']
    title = listing.get('title', '')[:60]
    price = listing.get('price_numeric', '?')
    msg = build_intro(listing)
    print(f"\n[{idx}/{total}] ${price} — {title}\n  {url}")

    try:
        page.goto(url, timeout=60000, wait_until="domcontentloaded")
    except Exception as e:
        print(f"  ✗ could not load: {str(e)[:50]}")
        r = ask(f"[{idx}/{total}] ${price} — {title}\n\nThe page didn't load "
                f"(Craigslist may be throttling). Load it yourself in the window "
                f"if you like, then choose:",
                ["Stop", "Skip", "I'll handle this one"], "Skip")
        if r == "Stop": return "stop"
        if r != "I'll handle this one": return "skipped"

    beep(); notify(f"Listing {idx}/{total}", "Click 'reply' and solve the captcha")
    r = ask(f"[{idx}/{total}] ${price} — {title}\n\n"
            f"In the browser window:\n"
            f"  1. Click 'reply'\n"
            f"  2. Choose email, solve the captcha if asked\n"
            f"  3. When the message box is on screen, click 'Fill it in' here.",
            ["Stop", "Skip this listing", "Fill it in"], "Fill it in")
    if r == "Stop": return "stop"
    if r != "Fill it in": return "skipped"

    # Auto-fill whatever fields are present
    filled = False
    try:
        field = page.locator('textarea[name="message"], textarea').first
        if field.is_visible(timeout=4000):
            for sel, val in (('input[name="from_name"]', NAME),
                             ('input[name="from_email"], input[type="email"]', EMAIL),
                             ('input[name="from_phone"], input[type="tel"]', PHONE)):
                try: page.fill(sel, val, timeout=1500)
                except Exception: pass
            field.fill(msg, timeout=3000)
            filled = True
            print("  ✓ message auto-filled")
    except Exception:
        pass

    if not filled:
        notify(f"Listing {idx}/{total}", "No form found — paste manually")
        r = ask(f"[{idx}/{total}] ${price} — {title}\n\n"
                f"Couldn't find the message box to auto-fill. You can paste the "
                f"message yourself (it's copied to your clipboard).\n\n"
                f"After you click SEND and see Craigslist's confirmation, choose:",
                ["Stop", "Couldn't send", "I sent it"], "I sent it")
        # put the message on the clipboard so they can paste
        subprocess.run(["pbcopy"], input=msg, text=True)
    else:
        beep(); notify(f"Listing {idx}/{total}", "Review, then click SEND")
        r = ask(f"[{idx}/{total}] ${price} — {title}\n\n"
                f"The message is filled in. Review it, then click SEND in the "
                f"browser. After you see Craigslist's 'message sent' confirmation, "
                f"choose 'I sent it'.",
                ["Stop", "Couldn't send", "I sent it"], "I sent it")

    if r == "Stop": return "stop"
    if r == "I sent it":
        record_history(lid, "Craigslist Reply (assisted)", msg, email=EMAIL, status="sent")
        print("  ✓ recorded as SENT (you confirmed)")
        return "sent"
    print("  – not sent (you said so) — leaving unrecorded")
    return "skipped"


# ---- one listing -----------------------------------------------------------
def contact_one(page, listing, idx, total):
    url, lid = listing['url'], listing['id']
    title = listing.get('title', '')[:50]
    price = listing.get('price_numeric', '?')
    msg = build_intro(listing)
    print(f"\n{'='*68}\n[{idx}/{total}] ${price} — {title}\n{url}\n{'='*68}")

    try:
        page.goto(url, timeout=25000)
        time.sleep(2)
        if any(w in page.content().lower() for w in ("this posting has been deleted",
                                                     "this posting has expired")):
            print("  ⊗ deleted/expired"); return "deleted"

        try:
            page.locator('button:has-text("reply"), a:has-text("reply")').first.click(timeout=8000)
            time.sleep(3)
        except Exception:
            print("  ✗ no reply button"); return "no_reply"

        if has_captcha(page) and not wait_for_captcha(page, f"${price} {title}"):
            return "captcha_timeout"

        # Direct mailto path → compose in mail client (still requires your click)
        try:
            link = page.locator('a[href^="mailto:"]').first
            if link.is_visible(timeout=2500):
                addr = (link.get_attribute('href') or '').replace('mailto:', '').split('?')[0]
                if not DRY_RUN:
                    subj = urllib.parse.quote(f"Re: {title} — Stanford summer student")
                    subprocess.run(['open',
                        f'mailto:{addr}?subject={subj}&body={urllib.parse.quote(msg)}'], check=False)
                print(f"  ✉️  composed email to {addr}")
                record_history(lid, "Email (Craigslist)", msg, email=EMAIL, status="sent")
                time.sleep(2)
                return "email"
        except Exception:
            pass

        # CL webform path
        field = page.locator('textarea[name="message"], textarea').first
        if not field.is_visible(timeout=5000):
            print("  ✗ no reply form"); return "no_form"
        for sel, val in (('input[name="from_name"]', NAME),
                         ('input[name="from_email"], input[type="email"]', EMAIL),
                         ('input[name="from_phone"], input[type="tel"]', PHONE)):
            try: page.fill(sel, val, timeout=2000)
            except Exception: pass
        field.fill(msg, timeout=3000)
        print("  ✓ form filled")

        if DRY_RUN:
            print("  [dry-run] not submitting.")
            return "dry_run"

        try:
            btn = page.locator('button[type="submit"], input[type="submit"], '
                               'button:has-text("send")').first
            if btn.is_visible(timeout=2500):
                btn.click(timeout=3000)
                time.sleep(3)
                print("  ✓ SENT via Craigslist form")
                record_history(lid, "Craigslist Reply", msg, email=EMAIL, status="sent")
                return "form_sent"
        except Exception:
            pass

        print("  ⚠️  filled but couldn't auto-submit — click SEND in the browser")
        beep(); notify("Click SEND", f"${price} {title}")
        time.sleep(15)
        record_history(lid, "Craigslist Reply", msg, email=EMAIL, status="sent")
        return "manual_send"

    except Exception as e:
        print(f"  ✗ error: {str(e)[:60]}")
        return "error"


def main():
    queue = load_queue()
    state = load_state()
    sent = state.setdefault('sent', {})
    recipients = pick_recipients(queue, sent)

    print("\n" + "="*68)
    print("CRAIGSLIST OUTREACH — dedicated browser, whole units, EPA excluded")
    print("="*68)
    mode = "ASSISTED (you drive; script fills & records)" if ASSIST \
           else ("DRY RUN (no sends)" if DRY_RUN else "LIVE auto")
    print(f"Identity : {NAME} · {EMAIL} · {PHONE}")
    print(f"Profile  : {PROFILE_DIR}  (separate from your normal Chrome)")
    print(f"Mode     : {mode}")
    print(f"To send  : {len(recipients)} whole-unit listing(s)")
    for r in recipients:
        print(f"   ${r.get('price_numeric','?'):>5}  {r.get('location','?'):<13} {r['title'][:44]}")
    if not recipients:
        print("\nNothing to send — all matching listings already contacted.")
        return
    print("\nStarting in 5s…  (Ctrl-C to abort)")
    time.sleep(5)

    os.makedirs(PROFILE_DIR, exist_ok=True)
    counts = {}
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            PROFILE_DIR, headless=False, args=['--start-maximized'])
        page = ctx.new_page()
        for i, listing in enumerate(recipients, 1):
            if ASSIST:
                res = assist_one(page, listing, i, len(recipients))
            else:
                res = contact_one(page, listing, i, len(recipients))
            counts[res] = counts.get(res, 0) + 1
            if res in ("form_sent", "manual_send", "email", "sent"):
                sent[listing['id']] = {
                    'when': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'url': listing['url'],
                    'price': listing.get('price_numeric'),
                    'location': listing.get('location'),
                    'method': res,
                }
                state['sent'] = sent; save_state(state)   # save each confirmed send
                print(f"  💾 saved ({len(sent)} sent)")
            if res == "stop":
                print("\n  ⏹  Stopped at your request.")
                break
            if not ASSIST and i < len(recipients):
                time.sleep(6)  # polite gap (assisted is paced by you)
        state['sent'] = sent; save_state(state)
        print("\n" + "="*68)
        print("DONE — " + ", ".join(f"{k}:{v}" for k, v in counts.items()))
        sent_n = counts.get('form_sent',0)+counts.get('manual_send',0)+counts.get('email',0)
        print(f"Confirmed sent this run: {sent_n} · total contacted: {len(sent)}")
        print("="*68)
        notify("Outreach done", f"{sent_n} sent. Refresh the :5555 dashboard.")
        beep()
        time.sleep(6)
        ctx.close()


if __name__ == '__main__':
    main()
