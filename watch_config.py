#!/usr/bin/env python3
"""
Shared config + helpers for the Palo Alto housing monitor.

Imported by watch_listings.py, auto_send.py, check_replies.py.
Holds: contact info, budget rule, search criteria, scam heuristics,
the (truthful) outreach message, JSON state load/save, and macOS notify.

Nothing here sends anything or touches the network. Safe to import.
"""
import json
import os
import re
import subprocess
import time

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE = "/Users/test/Desktop/housing-S26"
STATE_FILE = os.path.join(BASE, "watch_state.json")   # seen listings + send/reply log
QUEUE_FILE = os.path.join(BASE, "send_queue.json")    # matches awaiting send
SECRETS_FILE = os.path.join(BASE, "secrets.json")     # IMAP creds — you create this, gitignore it
WATCH_LOG = os.path.join(BASE, "watch.log")
RUN_STATUS_FILE = os.path.join(BASE, "run_status.json")  # live heartbeat per component

# ---------------------------------------------------------------------------
# Who is asking — TRUE profile for the Palo Alto / Stanford summer search.
# (The old SF scripts said "Cornell grad at a startup" — that was the archived
#  SF search. For PA we use the accurate Stanford-summer-student framing.)
# ---------------------------------------------------------------------------
NAME = "Simon"
PHONE = "415-426-8741"  # Business number
EMAIL = "tianjiahe11@gmail.com"

# Hard budget. A room must be at or under this to be messaged. (Your rule:
# under $2,000/mo, will stretch for own space — so $2,000 is the ceiling.)
MAX_BUDGET = 2000

# Move-in rule: must be available by this date. Anything starting later is out.
MOVE_IN_BY = "2026-06-01"

# ---------------------------------------------------------------------------
# Outreach message — respectful, honest, no pressure. Used by auto_send.py.
# ---------------------------------------------------------------------------
def build_intro(listing=None):
    """A polite, truthful intro. `listing` may tune the opener but never lies."""
    price = ""
    if listing and listing.get("price_numeric"):
        price = f" (I saw it listed at ${listing['price_numeric']:,}/mo, which works for me.)"
    return (
        f"Hi! I'm {NAME}, an incoming Stanford summer student starting on campus "
        f"June 1, 2026. I'm looking for a room for the summer and yours looks like "
        f"a great fit.{price} I'm a non-smoker, no parties, quiet and clean. "
        f"Is it still available, and would a short summer stay work for you? "
        f"Happy to arrange an in-person or video tour at your convenience. "
        f"Thanks so much for considering — {NAME}, {PHONE}."
    )

# ---------------------------------------------------------------------------
# Search criteria — used to decide if a NEW listing is worth surfacing/sending.
# ---------------------------------------------------------------------------
# Areas we care about, best first. Palo Alto strongly preferred.
PREFERRED_AREAS = ["palo alto", "stanford", "menlo park", "atherton", "mountain view", "los altos"]

# Phrases that mean "available now / June" (good) vs later (excluded).
LATER_MONTH_PAT = re.compile(
    r"\b(jul(y)?|aug(ust)?|sept(ember)?)\b|\bjune\s*(1[0-9]|2[0-9]|3[0-9])\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Scam / low-quality heuristics — "keep it legit." If a listing trips these we
# do NOT auto-message it; we surface it with a warning for manual review.
# ---------------------------------------------------------------------------
SCAM_KEYWORDS = [
    "wire transfer", "western union", "moneygram", "zelle only", "cash app only",
    "send deposit", "deposit before", "out of the country", "out of town",
    "overseas", "missionary", "god bless", "keys will be mailed", "shipping the keys",
    "no viewing", "cannot show", "can't show", "rent sight unseen",
    "gift card", "bitcoin", "crypto", "first to pay",
]

def scam_flags(listing):
    """Return a list of reasons this listing looks risky. Empty = clean."""
    flags = []
    text = " ".join(str(listing.get(k, "")) for k in ("title", "body", "status")).lower()
    price = listing.get("price_numeric")

    for kw in SCAM_KEYWORDS:
        if kw in text:
            flags.append(f"scam phrase: '{kw}'")

    # Absurdly cheap for the area (private PA room well under market).
    if isinstance(price, int) and 0 < price < 700:
        flags.append(f"price ${price} far below market — verify in person")

    return flags

# ---------------------------------------------------------------------------
# Budget + date helpers
# ---------------------------------------------------------------------------
def parse_price(raw):
    """'$1,290' / '1290' / '$1,290/mo' -> 1290 (int) or None."""
    if raw is None:
        return None
    nums = re.findall(r"[\d,]+", str(raw))
    if not nums:
        return None
    try:
        return int(nums[0].replace(",", ""))
    except ValueError:
        return None

def within_budget(listing):
    """True only if we have a price AND it is <= MAX_BUDGET."""
    p = listing.get("price_numeric")
    if p is None:
        p = parse_price(listing.get("price"))
        listing["price_numeric"] = p
    return isinstance(p, int) and 0 < p <= MAX_BUDGET

def looks_too_late(listing):
    """True if the text indicates a July/Aug/mid-to-late-June start."""
    text = " ".join(str(listing.get(k, "")) for k in ("title", "body", "status"))
    return bool(LATER_MONTH_PAT.search(text))

def in_preferred_area(listing):
    text = " ".join(str(listing.get(k, "")) for k in ("title", "body", "area", "url")).lower()
    return any(a in text for a in PREFERRED_AREAS)

# ---------------------------------------------------------------------------
# State (seen listings, send log, reply log) — plain JSON, atomic-ish write.
# ---------------------------------------------------------------------------
def _load(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default

def _save(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)

def load_state():
    return _load(STATE_FILE, {
        "seen_ids": [],        # listing ids we've already surfaced
        "sent": {},            # id -> {when, url, mode}
        "replies_seen": [],    # message fingerprints already notified
    })

def save_state(state):
    _save(STATE_FILE, state)

def load_queue():
    return _load(QUEUE_FILE, [])

def save_queue(q):
    _save(QUEUE_FILE, q)

def load_secrets():
    """Read local secrets.json (IMAP). Returns {} if absent. Never logged."""
    return _load(SECRETS_FILE, {})

# ---------------------------------------------------------------------------
# Live run status / heartbeat — each component records when it starts, when it
# finishes, and a one-line result. watch_status.py reads this to show real-time
# state without parsing logs. One record per component, overwritten each run.
# ---------------------------------------------------------------------------
def heartbeat_start(component, detail=""):
    """Mark a component as RUNNING now. Returns a monotonic-ish start stamp."""
    status = _load(RUN_STATUS_FILE, {})
    now = time.time()
    prev = status.get(component, {})
    status[component] = {
        "state": "running",
        "detail": detail,
        "started_at": now,
        "started_str": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now)),
        "finished_at": None,
        "result": "",
        "runs": prev.get("runs", 0) + 1,
        "last_ok": prev.get("last_ok"),
    }
    _save(RUN_STATUS_FILE, status)
    return now

def heartbeat_done(component, result="", ok=True, started=None):
    """Mark a component as IDLE (finished). result is a one-line summary."""
    status = _load(RUN_STATUS_FILE, {})
    now = time.time()
    rec = status.get(component, {})
    rec.update({
        "state": "idle",
        "finished_at": now,
        "finished_str": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now)),
        "result": result,
        "ok": ok,
        "duration": round(now - started, 1) if started else None,
    })
    if ok:
        rec["last_ok"] = rec["finished_str"]
    status[component] = rec
    _save(RUN_STATUS_FILE, status)

def load_run_status():
    return _load(RUN_STATUS_FILE, {})

# ---------------------------------------------------------------------------
# Logging + native macOS notification (osascript — no extra install needed)
# ---------------------------------------------------------------------------
def log(msg):
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with open(WATCH_LOG, "a") as f:
            f.write(line + "\n")
    except OSError:
        pass

def notify(title, message):
    """Best-effort macOS banner. Falls back silently if osascript missing."""
    safe_t = title.replace('"', "'")
    safe_m = message.replace('"', "'")
    try:
        subprocess.run(
            ["osascript", "-e",
             f'display notification "{safe_m}" with title "{safe_t}" sound name "Glass"'],
            check=False, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        pass
    log(f"NOTIFY: {title} — {message}")

# ---------------------------------------------------------------------------
# Quiet hours — don't message landlords in the middle of the night (looks like
# a bot, and it's just rude). Returns True if NOW is inside the send window.
# ---------------------------------------------------------------------------
SEND_START_HOUR = 8    # 8am
SEND_END_HOUR = 21     # 9pm

def within_send_hours(now_struct=None):
    h = (now_struct or time.localtime()).tm_hour
    return SEND_START_HOUR <= h < SEND_END_HOUR
