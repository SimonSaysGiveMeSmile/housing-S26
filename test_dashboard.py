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
check(all(item['source'] in ('zillow', 'supost', 'furnishedfinder', 'spareroom', 'apartments') for item in leads),
      "inventory contains only the selected housing platforms")

# The lease rule is hard: month-by-month or sublet only. Nothing with a long
# minimum may sit in a group the default view presents as a ready option.
_long = [i['id'] for i in leads if i['group'] in ('monthly', 'one_month')
         and any(k in i['term'].lower() for k in ('12-month', 'twelve month', 'two-month', '60-day',
                                                  'three-month', '90-day', 'six month', 'year'))]
check(not _long, f"no long-minimum lease is presented as a monthly option (offenders: {_long})")
check("availability has not been confirmed with hosts" in latest,
      "advertised leads are not represented as host-confirmed availability")
# Solano came back on September 28 with the wider geography; every restored lead must say so,
# so nothing silently reappears without an explanation of why the rule changed.
_restored = [i['id'] for i in leads if i['city'] in ('Fairfield', 'Vacaville')]
check(all('wider' in next(x for x in leads if x['id'] == r)['outreach_note'].lower()
          or 'widened' in next(x for x in leads if x['id'] == r)['outreach_note'].lower()
          for r in _restored),
      f"each restored Solano lead records why it came back (restored: {len(_restored)})")

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
for stale in ('ff-933277_1', 'ff-933335_1', 'ff-306547_1'):
    item = next(i for i in leads if i['id'] == stale)
    check(item['group'] == 'unverified', f"older-calendar lead {stale} is marked verify-first")

# Every city needs a distance entry, or rendering a new lead raises KeyError.
import json as _json
with open(os.path.join(d.ROOT, 'distance_estimates.json')) as _f:
    _dist = _json.load(_f)['cities']
missing_city = sorted({item['city'] for item in leads} - set(_dist))
check(not missing_city, f"every lead's city has a measured SF distance (missing: {missing_city})")

# Both anchors must be measured for every city, or the card render raises KeyError.
_missing_anchor = sorted(c for c in {item['city'] for item in leads}
                         if not {'driving_miles', 'stanford_miles', 'balanced_miles'} <= set(_dist.get(c, {})))
check(not _missing_anchor, f"every city has SF + Stanford + balanced distances (missing: {_missing_anchor})")
check(all(_dist[c]['balanced_miles'] == max(_dist[c]['driving_miles'], _dist[c]['stanford_miles'])
          for c in {item['city'] for item in leads}),
      "balanced distance is the worse of the two drives, never an average")
check('Closest to Stanford' in latest and 'Balanced' in latest,
      "the board offers sorting by Stanford and by the balanced figure")

# The ceiling widened on September 28: the search is for a job-hunting base near the Bay Area,
# not a daily commute, so the limit is 2.5 hours on the worse anchor rather than 1.5.
CEILING_MINUTES = 150
_far = sorted({f"{item['city']} ({max(_dist[item['city']]['model_minutes'], _dist[item['city']]['stanford_minutes'])} min)"
               for item in leads
               if max(_dist[item['city']]['model_minutes'], _dist[item['city']]['stanford_minutes']) > CEILING_MINUTES})
check(not _far, f"no lead is more than 2.5 hours from both SF and Stanford (offenders: {_far})")

# Any bathroom that is not fully private must say so in the card title, not just the fine print,
# because the list heading now promises exactly that.
def _bath_compromised(item):
    b = item['bath'].lower()
    return any(k in b for k in ('shared bath', 'share a bath', 'sharing the bath', 'shares a bath',
                                'shared use of the bath', 'shared full bath', 'communal bath',
                                'shower is shared', 'shower is in the full bathroom and is shared',
                                'is shared', 'partial:'))
_undisclosed = [i['id'] for i in leads if _bath_compromised(i)
                and not any(w in i['title'].lower() for w in ('shared', 'partial'))]
check(not _undisclosed,
      f"any lead without a fully private bathroom says so in its title (undisclosed: {_undisclosed})")
check('Every bathroom is private unless the card says otherwise' in latest,
      "the list heading states the bathroom rule the cards are checked against")

# No lead may claim a host has confirmed the requested date.
# Outreach is outward-facing: a card may only claim a message was sent if it is logged as sent.
_sent_ids = set(_json.load(open(os.path.join(d.ROOT, 'manual_contacts.json'))))
_claims_sent = [i['id'] for i in leads if 'no message has been sent' not in i['contact'].lower()]
check(all(i in _sent_ids for i in _claims_sent),
      f"only logged-as-sent cards claim an outreach message (unlogged claims: "
      f"{[i for i in _claims_sent if i not in _sent_ids]})")
check(all('no message has been sent' in i['contact'].lower()
          for i in leads if i['id'] not in _sent_ids),
      "every card that has not been contacted still states that no message has been sent")

# Every contactable lead carries a draft; the two that cannot be contacted carry none.
_no_draft = [i['id'] for i in leads if i['group'] != 'waitlist' and not i.get('inquiry')]
check(not _no_draft, f"every contactable lead has a drafted message (missing: {_no_draft})")
_bad_draft = [i['id'] for i in leads if i['group'] == 'waitlist' and i.get('inquiry')]
check(not _bad_draft,
      f"no draft is offered for a lead whose advertiser is not accepting applications "
      f"(offenders: {_bad_draft})")
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
