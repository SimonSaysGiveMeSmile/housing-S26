#!/usr/bin/env python3
"""Smoke + regression tests for the housing dashboard (palo_alto_server.py).

Runs with plain `python3 test_dashboard.py` — no pytest needed — and exits
non-zero on any failure, so it can gate the GitHub Pages deploy in CI.

What it guards:
  1. The dashboard builds without raising (a throw => broken live site).
  2. All the critical page sections are present.
  3. Every filter-eligible listing card actually renders — catches the class
     of bug where a card silently vanishes (e.g. the short-phrase filter or a
     render-path regression) while progress/action-plan copy still shows.
  4. The lease-length + on-campus filters behave (pure-function regression
     guard for the `_SHORT_PHRASES` / `_lease_span_days` logic).
"""
import os, sys, html

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import palo_alto_server as d  # noqa: E402  (import applies the card filters)

_fail = []
def check(cond, msg):
    print(("  ok  : " if cond else "  FAIL: ") + msg)
    if not cond:
        _fail.append(msg)

# --- 1. Build cleanly ---------------------------------------------------------
out = d.render_summer_body()
check(isinstance(out, str) and len(out) > 80_000,
      f"summer archive builds a full page ({len(out):,} bytes, expect >80k)")

# --- 2. Critical sections present --------------------------------------------
for anchor in [
    "Stanford Summer 2026 Housing",   # masthead h1
    "settle-in",                      # current-state framing
    "Progress (latest first)",        # progress log
    "Copy-paste outreach",            # templates section
    "status-panel",                   # stats
    "Strategy",                       # strategy disclosure
]:
    check(anchor in out, f"section present: {anchor!r}")

# --- 3. Every eligible card renders (no silent drops) ------------------------
lists = d.NON_CL + d.SUBLETS + d.REGULAR_RENTALS + d.SHORT_TERM + d.SUPOST + d.FRESH_LEADS
n_expected = len(lists)
n_rendered = out.count('class="card-title"')
check(n_rendered == n_expected,
      f"all {n_expected} filter-eligible cards render (found {n_rendered} card-title blocks)")

missing = [L["title"] for L in lists if html.escape(L["title"]) not in out]
check(not missing, f"every eligible card title appears in the HTML (missing: {missing[:5]})")

# --- 4. Lease + campus filters (regression guard for the short-phrase bug) ---
full_summer = {"title": "Full summer room", "status": ("go", "June 15 – September 1"),
               "area": "On campus, Stanford (EVGR)", "facts": []}
short_stay  = {"title": "Room", "status": ("go", "short-term stopgap only"),
               "area": "On campus, Stanford", "facts": []}
check(d._lease_ok(full_summer) is True,  "_lease_ok keeps a full-summer (Jun 15–Sep 1) card")
check(d._lease_ok(short_stay) is False,  "_lease_ok drops an explicit short-term card")

check("~1 week" in d._SHORT_PHRASES and "short-term" in d._SHORT_PHRASES,
      "_SHORT_PHRASES guard list is intact (~1 week / short-term)")

span = d._lease_span_days("available june 15 to september 1 2026")
check(span is not None and 75 <= span <= 80,
      f"_lease_span_days(Jun 15 -> Sep 1) is ~78 days (got {span})")
check(d._lease_span_days("cozy furnished room, quiet street") is None,
      "_lease_span_days returns None when no date range is present")

check(d._campus_only({"area": "On campus, Stanford (EVGR)", "title": "", "facts": []}) is True,
      "_campus_only keeps an on-campus listing")
check(d._campus_only({"area": "Downtown San Jose", "title": "Loft", "facts": []}) is False,
      "_campus_only drops an off-campus listing with no on-campus building named")

# --- 5. No unrendered template leaks ----------------------------------------
for leak in ["{len(", "{render_todos", "{render_progress", '{"".join']:
    check(leak not in out, f"no unrendered f-string leak: {leak!r}")

# --- Current search: stale summer criteria must not hide September leads ------
from latest_dashboard import load_listings
latest = d.render_body()
leads = load_listings()["listings"]
check("September 29, 2026" in latest and "Bay Area monthly stays" in latest,
      "home page shows the current September search")
check("settle-in mode" not in latest and "June-start" not in latest,
      "home page does not show obsolete summer criteria")
check(latest.count('data-rank=') == len(leads), "every new lead renders regardless of the old campus filter")
check(all(html.escape(item["url"]) in latest for item in leads), "every lead retains its source link")
check('href="summer.html"' not in latest, "withdrawn summer inventory is not linked")
check("craigslist" not in latest.lower(), "current page contains no excluded platform listings, links or controls")
check(all(item['source'] in ('zillow', 'supost', 'furnishedfinder') for item in leads),
      "inventory contains only the selected housing platforms")
check("availability has not been confirmed with hosts" in latest,
      "advertised leads are not represented as host-confirmed availability")
check(next(item for item in leads if item['id'] == 'ff-848526_1')['rent'] == 1400 + 100,
      "Fairfield comparison price includes the listed utility charge")

# A lead whose page stops being a rental offer must leave the inventory, not linger.
check(not any(item['id'] == 'zillow-15658964' for item in leads),
      "the withdrawn Vallejo listing (page now resolves to a sold house) is out of inventory")

# Lease terms longer than the requested one-month start are never counted as monthly.
check(next(item for item in leads if item['id'] == 'ff-415061_1')['group'] == 'confirm',
      "the two-month-minimum Hayward room is not counted as monthly terms")
check(all(item['group'] != 'one_month' for item in leads if '2 month' in item['term'].lower()
          or 'two-month' in item['term'].lower() or '12 month' in item['term'].lower()),
      "no longer-than-monthly minimum is filed under the one-month group")

# Older-calendar leads stay in the verify-first bucket, hidden by the default filter.
for stale in ('ff-933277_1', 'ff-933335_1', 'ff-915271_1', 'ff-306547_1'):
    item = next(i for i in leads if i['id'] == stale)
    check(item['group'] == 'unverified', f"older-calendar lead {stale} is marked verify-first")

# Every city needs a distance entry, or rendering a new lead raises KeyError.
import json as _json
with open(os.path.join(d.ROOT, 'distance_estimates.json')) as _f:
    _dist = _json.load(_f)['cities']
missing_city = sorted({item['city'] for item in leads} - set(_dist))
check(not missing_city, f"every lead's city has a measured SF distance (missing: {missing_city})")

# No lead may claim a host has confirmed the requested date.
check(all('no message has been sent' in item['contact'].lower() for item in leads),
      "every card still states that no message has been sent")
photos = [photo for item in leads for photo in item.get("photos", [])]
check(all(os.path.isfile(os.path.join(d.ROOT, "maps", photo["file"])) for photo in photos),
      "all listing photos exist for the static site build")
check(all('maps/' + html.escape(photo["file"]) in latest for photo in photos),
      "all downloaded listing photos appear in the galleries")

from pathlib import Path
from tempfile import TemporaryDirectory
from build_site import build
with TemporaryDirectory() as temporary:
    exported = Path(temporary) / 'site'
    build(exported)
    check((exported / 'index.html').read_text() == latest, "static export matches the reviewed page")
    archive = (exported / 'summer.html').read_text()
    check('url=index.html' in archive and 'craigslist' not in archive.lower() and 'card-title' not in archive,
          "old archive URL redirects without exposing withdrawn listings")
    check({p.name for p in (exported / 'maps').iterdir()} == {photo['file'] for photo in photos},
          "static site publishes only photos referenced by retained listings")

# --- summary -----------------------------------------------------------------
print()
if _fail:
    print(f"FAILED — {len(_fail)} check(s):")
    for m in _fail:
        print("  -", m)
    sys.exit(1)
print("All dashboard checks passed.")
