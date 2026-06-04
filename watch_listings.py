#!/usr/bin/env python3
"""
watch_listings.py — one monitoring cycle.

Scans Craigslist Peninsula apartments + sublets (dedicated units only), parses
each listing's price + dates, and surfaces NEW listings that are:
  - below budget (<= MAX_BUDGET, with a real price)
  - in a preferred area (Palo Alto first)
  - available by June 1 (not July/Aug/mid-late-June)
  - not tripping scam heuristics

New clean matches are notified (macOS banner) and appended to send_queue.json.
Scam-flagged or over-budget ones are surfaced in the log/notification but NOT
queued for auto-send — you review those by hand.

SpareRoom / Zillow / Reddit need a logged-in browser to read reliably; this
cycle does a best-effort public scan and logs what it can. Stanford R&DE / SUpost
block automated fetch, so we emit a reminder to check them manually.

Run once per invocation (the launchd job / run_watch.sh calls it every 30 min).
"""
import sys
import urllib.request
import urllib.error

import watch_config as c

CRAIGSLIST_SEARCHES = [
    # Peninsula apartments/sublets, <= $2000, Palo Alto query first
    # /apa = apartments (whole units), /sub = sublets/temporary (whole units)
    "https://sfbay.craigslist.org/search/pen/apa?max_price=2000&query=palo+alto#search=1~list~0~0",
    "https://sfbay.craigslist.org/search/pen/apa?max_price=2000#search=1~list~0~0",
    "https://sfbay.craigslist.org/search/pen/sub?max_price=2000&query=palo+alto#search=1~list~0~0",
    "https://sfbay.craigslist.org/search/pen/sub?max_price=2000#search=1~list~0~0",
]

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

MANUAL_SOURCES = [
    ("Stanford R&DE summer housing", "https://rde.stanford.edu/conferences/summer-intern-housing"),
    ("SUpost (Stanford marketplace)", "https://supost.com"),
    ("Stanford Housing/Sublets FB group", "https://www.facebook.com/groups/304588736883828/"),
]


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read().decode("utf-8", "replace")
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
        c.log(f"  fetch failed for {url[:60]}…: {e}")
        return ""


def parse_craigslist(html_text):
    """Extract listings from Craigslist search HTML.

    Craigslist's no-JS markup renders each result as a self-contained
    <li class="cl-static-search-result" title="..."> block holding its own
    title, detail <a href>, <div class="price">, and <div class="location">.
    We parse per-<li> so every listing keeps ITS OWN price — critical, since
    the whole point is verifying each room is actually below budget.
    """
    import re
    out = []
    seen_local = set()

    li_pat = re.compile(
        r'<li class="cl-static-search-result"[^>]*\btitle="(?P<title>[^"]*)"[^>]*>(?P<inner>.*?)</li>',
        re.S,
    )
    href_pat = re.compile(r'href="(https://sfbay\.craigslist\.org/[a-z]{3}/(apa|sub)/d/[a-z0-9\-]+/(\d+)\.html)"')
    price_pat = re.compile(r'<div class="price">\s*(\$[\d,]+)\s*</div>')
    loc_pat = re.compile(r'<div class="location">\s*(.*?)\s*</div>', re.S)

    for m in li_pat.finditer(html_text):
        inner = m.group("inner")
        hm = href_pat.search(inner)
        if not hm:
            continue
        url, lid = hm.group(1), hm.group(3)
        if lid in seen_local:
            continue
        seen_local.add(lid)

        title = m.group("title").strip()
        pm = price_pat.search(inner)
        price = pm.group(1) if pm else ""
        lm = loc_pat.search(inner)
        location = re.sub(r"\s+", " ", lm.group(1)).strip() if lm else ""

        out.append({
            "id": f"cl-{lid}",
            "url": url,
            "title": title,
            # title is the real listing title; location is the posted area.
            # We do NOT have the full body from search results, so date/scam
            # checks here run on title+location only (the detail-page scan in
            # auto_send confirms before sending).
            "body": f"{title} {location}",
            "price": price,
            "price_numeric": c.parse_price(price),
            "source": "craigslist",
            "location": location,
        })
    return out


def classify(listing):
    """Return ('match' | 'scam' | 'overbudget' | 'late' | 'area' , reasons)."""
    flags = c.scam_flags(listing)
    if flags:
        return "scam", flags
    if not c.within_budget(listing):
        p = listing.get("price_numeric")
        return "overbudget", [f"price {p if p else 'unknown'} > ${c.MAX_BUDGET} or missing"]
    if not c.in_preferred_area(listing):
        return "area", ["outside preferred areas"]
    if c.looks_too_late(listing):
        return "late", ["start date looks July/Aug/mid-late June"]
    return "match", []


def main():
    c.log("=" * 64)
    c.log("WATCH CYCLE START")
    hb = c.heartbeat_start("watch_listings", "scanning Craigslist")
    state = c.load_state()
    seen = set(state.get("seen_ids", []))
    queue = c.load_queue()
    queued_ids = {q["id"] for q in queue}

    all_listings = []
    for url in CRAIGSLIST_SEARCHES:
        html_text = fetch(url)
        if html_text:
            found = parse_craigslist(html_text)
            c.log(f"  craigslist: {len(found)} listings from {url[:50]}…")
            all_listings.extend(found)

    # Dedupe by id across both searches
    uniq = {}
    for l in all_listings:
        uniq.setdefault(l["id"], l)
    listings = list(uniq.values())
    c.log(f"  {len(listings)} unique listings this cycle")

    new_matches, new_scam, skipped = [], [], 0
    for l in listings:
        if l["id"] in seen:
            skipped += 1
            continue
        seen.add(l["id"])
        verdict, reasons = classify(l)
        l["verdict"] = verdict
        l["reasons"] = reasons
        if verdict == "match":
            new_matches.append(l)
        elif verdict == "scam":
            new_scam.append(l)
        # overbudget/late/area: recorded as seen, not surfaced (reduces noise)

    # Queue clean matches for sending (auto_send.py consumes this)
    for l in new_matches:
        if l["id"] not in queued_ids:
            queue.append(l)
            queued_ids.add(l["id"])

    state["seen_ids"] = list(seen)
    c.save_state(state)
    c.save_queue(queue)

    # ---- Notifications ----
    if new_matches:
        top = new_matches[0]
        c.notify(
            f"{len(new_matches)} new unit(s) ≤ ${c.MAX_BUDGET}",
            f"${top.get('price_numeric','?')} — {top['title'][:50]}",
        )
        for l in new_matches:
            c.log(f"  ✅ MATCH ${l.get('price_numeric')}: {l['title'][:60]} — {l['url']}")
    if new_scam:
        c.notify(
            f"{len(new_scam)} listing(s) flagged — review by hand",
            "Possible scam / too cheap. Not auto-messaged.",
        )
        for l in new_scam:
            c.log(f"  ⚠️  SCAM-FLAG {l['title'][:50]}: {l['reasons']} — {l['url']}")

    if not new_matches and not new_scam:
        c.log(f"  no new listings (skipped {skipped} already-seen)")

    # Manual-source reminder (these block automation)
    c.log("  Reminder — check by hand (block automated fetch):")
    for name, url in MANUAL_SOURCES:
        c.log(f"    • {name}: {url}")
    c.log("  Also check your PHONE for texts/calls — those can't be auto-tracked.")

    c.log(f"WATCH CYCLE DONE — {len(new_matches)} new match, {len(new_scam)} flagged, "
          f"{len(queue)} in send queue")
    c.heartbeat_done(
        "watch_listings",
        f"{len(new_matches)} new match, {len(new_scam)} flagged, {len(queue)} queued",
        ok=True, started=hb,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
