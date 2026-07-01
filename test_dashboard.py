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
out = d.render_body()
check(isinstance(out, str) and len(out) > 80_000,
      f"render_body() builds a full page ({len(out):,} bytes, expect >80k)")

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

# --- summary -----------------------------------------------------------------
print()
if _fail:
    print(f"FAILED — {len(_fail)} check(s):")
    for m in _fail:
        print("  -", m)
    sys.exit(1)
print("All dashboard checks passed.")
