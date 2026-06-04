#!/usr/bin/env python3
"""Review server for SF housing search. Port 4089."""
import http.server
import socketserver
import os
import re
import json
import html
from urllib.parse import urlparse

ROOT = "/Users/test/Desktop/housing-S26"
PORT = 4089

CSS = """
*{box-sizing:border-box}
body{font-family:-apple-system,system-ui,sans-serif;max-width:1200px;margin:0 auto;padding:20px;color:#222;line-height:1.6}
nav{background:#1a1a2e;padding:14px 20px;border-radius:8px;margin-bottom:24px;display:flex;gap:18px;flex-wrap:wrap}
nav a{text-decoration:none;color:#fff;font-weight:500;font-size:15px}
nav a:hover{text-decoration:underline;color:#90caf9}
h1{margin-top:0;color:#1a1a2e}
h2{border-bottom:2px solid #1a1a2e;padding-bottom:6px;margin-top:32px}
h3{color:#333;margin-top:24px}
table{border-collapse:collapse;width:100%;margin:12px 0;font-size:13px}
th,td{border:1px solid #ddd;padding:8px 10px;text-align:left;vertical-align:top}
th{background:#1a1a2e;color:#fff;font-weight:500}
tr:nth-child(even){background:#f8f9fa}
tr.highlight{background:#e8f5e9 !important}
tr.zillow{background:#e3f2fd !important}
a{color:#0366d6}
a:hover{color:#0256b9}
code{background:#f0f0f0;padding:2px 6px;border-radius:3px;font-size:12px}
pre{background:#1a1a2e;color:#e0e0e0;padding:14px;border-radius:6px;overflow-x:auto;font-size:13px}
pre code{background:none;padding:0;color:inherit}
.badge{display:inline-block;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:600;margin-right:4px}
.badge-park{background:#c8e6c9;color:#2e7d32}
.badge-short{background:#fff3e0;color:#e65100}
.badge-avail{background:#e3f2fd;color:#1565c0}
.badge-zillow{background:#1277e1;color:#fff}
.badge-reddit{background:#ff4500;color:#fff}
.badge-spareroom{background:#6c3baa;color:#fff}
.badge-rentcom{background:#00897b;color:#fff}
.badge-hotel{background:#795548;color:#fff}
.contact-btn{display:inline-block;background:#1a1a2e;color:#fff;padding:4px 10px;border-radius:4px;text-decoration:none;font-size:12px;margin-top:4px}
.contact-btn:hover{background:#333;color:#fff}
.card{border:1px solid #e0e0e0;border-radius:8px;padding:16px;margin:12px 0}
.card-top{border-left:4px solid #4caf50}
.stats{display:flex;gap:20px;flex-wrap:wrap;margin:16px 0}
.stat{background:#f5f5f5;padding:12px 16px;border-radius:6px;text-align:center}
.stat-num{font-size:24px;font-weight:700;color:#1a1a2e}
.stat-label{font-size:12px;color:#666}
.log{background:#0d1117;color:#c9d1d9;padding:16px;border-radius:6px;font-family:Menlo,monospace;font-size:13px;white-space:pre-wrap;max-height:600px;overflow-y:auto}
.section-zillow{border:2px solid #1277e1;border-radius:8px;padding:16px;margin:20px 0;background:#f8fbff}
blockquote.callout{background:#fff8e1;border-left:4px solid #f9a825;padding:12px 16px;margin:16px 0;border-radius:4px}
"""

NAV = """
<nav>
<a href="/">All Properties</a>
<a href="/zillow">Zillow</a>
<a href="/status">Contact Status</a>
<a href="/schedule">Schedule</a>
<a href="/script">Outreach Script</a>
<a href="/log">Live Log</a>
</nav>
"""

def page(title, body, auto_refresh=False):
    refresh = '<meta http-equiv="refresh" content="3">' if auto_refresh else ''
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">{refresh}
<title>{html.escape(title)} — Simon's SF Housing</title>
<style>{CSS}</style></head>
<body>{NAV}<h1>{html.escape(title)}</h1>{body}</body></html>"""

def render_all_properties():
    """Main page: All listings grouped by search date."""
    out = []

    # Load all data sources
    pac_data = []
    p = os.path.join(ROOT, "pac_heights_listings.json")
    if os.path.exists(p):
        with open(p) as f:
            pac_data = json.load(f)

    cl_data = []
    p = os.path.join(ROOT, "craigslist_listings.json")
    if os.path.exists(p):
        with open(p) as f:
            cl_data = json.load(f)

    fb_data = []
    p = os.path.join(ROOT, "fb_marina_listings.json")
    if os.path.exists(p):
        with open(p) as f:
            fb_data = json.load(f)

    total = len(pac_data) + len(cl_data) + len(fb_data)
    out.append(f'''<div class="stats">
<div class="stat"><div class="stat-num">{total}</div><div class="stat-label">Total Listings</div></div>
<div class="stat"><div class="stat-num">{len(pac_data)}</div><div class="stat-label">SpareRoom</div></div>
<div class="stat"><div class="stat-num">{len(cl_data)}</div><div class="stat-label">Craigslist</div></div>
<div class="stat"><div class="stat-num">{len(fb_data)}</div><div class="stat-label">FB Marketplace</div></div>
</div>
<p><strong>Focus:</strong> Within 1 mi of Pacific Heights (Cow Hollow, Presidio, Marina, Russian Hill, Nob Hill, Cathedral Hill) + Dogpatch, Mission Bay, Potrero Hill | Budget ≤$1,600/mo all-inclusive | No co-living | June 1 move-in</p>''')

    # ===== MAY 18 — FB MARKETPLACE (newest) =====
    out.append('<div class="section-zillow" style="border-color:#1877f2">')
    out.append('<h2><span class="badge" style="background:#1877f2;color:#fff">NEW</span> May 18 — Facebook Marketplace</h2>')
    if fb_data:
        out.append(f'<p>{len(fb_data)} listings from FB Marketplace — Marina, Presidio, Pac Heights, Cow Hollow. <strong>Login required to message.</strong></p>')
        out.append('<table><thead><tr><th>#</th><th>Price</th><th>Area</th><th>Title</th><th>Source</th><th>Contact</th></tr></thead><tbody>')
        for i, r in enumerate(fb_data, 1):
            out.append(f'<tr><td>{i}</td><td><strong>${r["price"]:,}</strong></td><td>{html.escape(r.get("area",""))}</td><td>{html.escape(r.get("title","")[:50])}</td><td><a href="{html.escape(r.get("url",""))}" target="_blank">FB Marketplace</a></td><td><a class="contact-btn" href="{html.escape(r.get("url",""))}" target="_blank">View (login)</a></td></tr>')
        out.append('</tbody></table>')
    out.append('</div>')

    # ===== MAY 17 — SPAREROOM + CRAIGSLIST =====
    out.append('<div class="section-zillow" style="border-color:#4caf50">')
    out.append('<h2><span class="badge badge-park">May 17</span> SpareRoom + Craigslist — Target Areas</h2>')

    # SpareRoom
    if pac_data:
        out.append(f'<h3><span class="badge badge-spareroom">SPAREROOM</span> {len(pac_data)} listings</h3>')
        out.append('<table><thead><tr><th>#</th><th>Price</th><th>Area</th><th>Title</th><th>Parking</th><th>Furnished</th><th>Available</th><th>Link</th></tr></thead><tbody>')
        for i, r in enumerate(pac_data, 1):
            park_badge = '<span class="badge badge-park">PARKING</span>' if 'parking' in r.get('title','').lower() or r.get('parking','') == 'Yes' else ''
            out.append(f'<tr class="highlight"><td>{i}</td><td><strong>{html.escape(r.get("price",""))}</strong></td><td>{html.escape(r.get("area",""))}</td><td>{html.escape(r.get("title","")[:50])}</td><td>{park_badge}{html.escape(r.get("parking",""))}</td><td>{html.escape(r.get("furnished",""))}</td><td>{html.escape(r.get("avail",""))}</td><td><a href="{html.escape(r.get("url",""))}" target="_blank" class="contact-btn">View & Contact</a></td></tr>')
        out.append('</tbody></table>')

    # Craigslist
    if cl_data:
        out.append(f'<h3><span class="badge" style="background:#e91e63;color:#fff">CRAIGSLIST</span> {len(cl_data)} listings</h3>')
        out.append('<table><thead><tr><th>#</th><th>Price</th><th>Area</th><th>Title</th><th>Source</th><th>Contact</th></tr></thead><tbody>')
        for i, r in enumerate(cl_data, 1):
            out.append(f'<tr><td>{i}</td><td><strong>${r["price"]:,}</strong></td><td>{html.escape(r.get("area",""))}</td><td>{html.escape(r.get("title","")[:50])}</td><td><a href="{html.escape(r.get("url",""))}" target="_blank">Craigslist</a></td><td><a class="contact-btn" href="{html.escape(r.get("url",""))}" target="_blank">Reply</a></td></tr>')
        out.append('</tbody></table>')
    out.append('</div>')

    # ===== MAY 14-16 — EARLIER RESULTS =====
    out.append('<div class="section-zillow" style="border-color:#9e9e9e">')
    out.append('<h2><span class="badge" style="background:#9e9e9e;color:#fff">May 14–16</span> Earlier Results — Reddit, Zillow, Hotels</h2>')

    # Reddit
    out.append('<h3><span class="badge badge-reddit">REDDIT</span> r/SFBayHousing</h3>')
    reddit_listings = [
        {"price":"$1,069–$1,077","area":"NoPa / Alamo Square","title":"McAllister House — 2 rooms, Jun 1, Victorian group house","url":"https://www.reddit.com/r/SFBayHousing/comments/1szl2qn/","contact":"DM post author on Reddit"},
        {"price":"$1,287","area":"NoPa","title":"13-person community house, Jun 1, private bedroom","url":"https://www.reddit.com/r/SFBayHousing/comments/1snbzy8/","contact":"DM post author on Reddit"},
        {"price":"$1,100","area":"Hayes Valley","title":"2BR/1BA furnished, flexible timing, short-term OK","url":"https://www.reddit.com/r/SFBayHousing/comments/1slxsx5/","contact":"DM post author on Reddit"},
        {"price":"—","area":"Russian Hill","title":"2BR/2BA condo, private bed + bath","url":"https://www.reddit.com/r/SFBayHousing/comments/1sxr70h/","contact":"DM post author on Reddit"},
    ]
    out.append('<table><thead><tr><th>#</th><th>Price</th><th>Area</th><th>Title</th><th>Source</th><th>Contact</th></tr></thead><tbody>')
    for i, r in enumerate(reddit_listings, 1):
        out.append(f'<tr><td>{i}</td><td><strong>{html.escape(r["price"])}</strong></td><td>{html.escape(r["area"])}</td><td>{html.escape(r["title"])}</td><td><a href="{html.escape(r["url"])}" target="_blank">Reddit</a></td><td><a class="contact-btn" href="{html.escape(r["url"])}" target="_blank">{html.escape(r["contact"])}</a></td></tr>')
    out.append('</tbody></table>')

    # Zillow links
    out.append('<h3><span class="badge badge-zillow">ZILLOW</span> Direct Search Links</h3>')
    out.append('<p>Browse Zillow directly (set price filter to $1,600 max in browser):</p>')
    out.append('<p><a href="https://www.zillow.com/pacific-heights-san-francisco-ca/rentals/" target="_blank">Pacific Heights</a> | <a href="https://www.zillow.com/cow-hollow-san-francisco-ca/rentals/" target="_blank">Cow Hollow</a> | <a href="https://www.zillow.com/presidio-heights-san-francisco-ca/rentals/" target="_blank">Presidio Heights</a> | <a href="https://www.zillow.com/marina-district-san-francisco-ca/rentals/" target="_blank">Marina</a> | <a href="https://www.zillow.com/dogpatch-san-francisco-ca/rentals/" target="_blank">Dogpatch</a> | <a href="https://www.zillow.com/mission-bay-san-francisco-ca/rentals/" target="_blank">Mission Bay</a> | <a href="https://www.zillow.com/potrero-hill-san-francisco-ca/rentals/" target="_blank">Potrero Hill</a></p>')

    # Hotels
    out.append('<h3><span class="badge badge-hotel">HOTELS</span> Residential Hotels / Monthly SROs</h3>')
    hotels = [
        {"name":"The Mosser","addr":"54 4th St, SoMa","price":"$1,000–$1,600/mo","phone":"(415) 986-4400","url":"https://www.themosser.com/","notes":"Long-stay private rooms."},
        {"name":"Hotel Essex","addr":"684 Ellis St, Tenderloin edge","price":"$1,000–$1,300/mo","phone":"(415) 474-4664","url":"https://hotelessexsf.com/","notes":"Monthly SRO, private room."},
        {"name":"Adelaide Hostel","addr":"5 Isadora Duncan Ln, Lower Nob Hill","price":"$1,200–$1,500/mo","phone":"(415) 359-1915","url":"https://adelaidehostel.com/","notes":"Monthly private rooms."},
    ]
    out.append('<table><thead><tr><th>Name</th><th>Address</th><th>Price</th><th>Notes</th><th>Contact</th></tr></thead><tbody>')
    for h in hotels:
        out.append(f'<tr><td><strong>{html.escape(h["name"])}</strong></td><td>{html.escape(h["addr"])}</td><td>{html.escape(h["price"])}</td><td>{html.escape(h["notes"])}</td><td><a class="contact-btn" href="{html.escape(h["url"])}" target="_blank">{html.escape(h["phone"])}</a></td></tr>')
    out.append('</tbody></table>')
    out.append('</div>')

    # OTHER SOURCES
    out.append('<h2>Search Links</h2>')
    out.append('''<table><thead><tr><th>Source</th><th>Link</th></tr></thead><tbody>
<tr><td>FB Marketplace — room presidio</td><td><a href="https://www.facebook.com/marketplace/sanfrancisco/search/?query=room%20presidio&maxPrice=1600" target="_blank">Open (login required)</a></td></tr>
<tr><td>FB Marketplace — room pacific heights</td><td><a href="https://www.facebook.com/marketplace/sanfrancisco/search/?query=room%20pacific%20heights&maxPrice=1600" target="_blank">Open (login required)</a></td></tr>
<tr><td>FB Marketplace — sublet marina</td><td><a href="https://www.facebook.com/marketplace/sanfrancisco/search/?query=sublet%20marina&maxPrice=1600" target="_blank">Open (login required)</a></td></tr>
<tr><td>Craigslist SF rooms ≤$1,600</td><td><a href="https://sfbay.craigslist.org/search/sfc/roo?max_price=1600&availabilityMode=0" target="_blank">Open</a></td></tr>
<tr><td>Craigslist SF sublets — Marina</td><td><a href="https://sfbay.craigslist.org/search/sfc/sub?max_price=1600&query=marina" target="_blank">Open</a></td></tr>
<tr><td>SpareRoom (short-term, $800–$1,600)</td><td><a href="https://www.spareroom.com/flatshare/san_francisco?max_rent=1600&min_rent=800&per=pcm&offered=Y&room_types=single,double,studio&short_lets_considered=Y" target="_blank">Open</a></td></tr>
<tr><td>Trulia SF rentals under $1,600</td><td><a href="https://www.trulia.com/for_rent/San_Francisco,CA/0-1600_price" target="_blank">Open</a></td></tr>
<tr><td>HotPads SF under $1,600</td><td><a href="https://hotpads.com/san-francisco-ca/apartments-for-rent?price=0-1600" target="_blank">Open</a></td></tr>
</tbody></table>''')

    return "\n".join(out)

def render_zillow_page():
    """Dedicated Zillow page."""
    out = []
    p = os.path.join(ROOT, "zillow_sf.json")
    if os.path.exists(p):
        with open(p) as f:
            data = json.load(f)
        out.append(f'<p>Last scraped: <strong>{html.escape(data.get("timestamp",""))}</strong> | Total units: {data.get("total_scraped", 0)} | In budget: {data.get("budget_count", 0)}</p>')
        out.append(f'<p><em>{html.escape(data.get("note", ""))}</em></p>')

        budget = [l for l in data.get("results", {}).get("budget_listings", []) if l.get("price_numeric", 99999) <= 1400]
        if budget:
            out.append('<h2>Within Budget (≤$1,400)</h2>')
            out.append('<table><thead><tr><th>#</th><th>Price</th><th>Beds</th><th>Address</th><th>Status</th><th>Link</th></tr></thead><tbody>')
            for i, l in enumerate(budget, 1):
                url = l.get('url','')
                if url and not url.startswith('http'):
                    url = 'https://www.zillow.com' + url
                out.append(f'<tr class="highlight"><td>{i}</td><td><strong>{html.escape(str(l.get("price","")))}</strong></td><td>{html.escape(str(l.get("beds","")))}</td><td>{html.escape(str(l.get("address","")))}</td><td>{html.escape(str(l.get("status","")))}</td><td><a href="{html.escape(url)}" target="_blank">View on Zillow</a></td></tr>')
            out.append('</tbody></table>')

        all_listings = data.get("all_unique", [])
        if all_listings:
            filtered = sorted([l for l in all_listings if l.get('price_numeric', 99999) <= 1400], key=lambda x: x.get('price_numeric', 99999))
            out.append(f'<h2>All Listings ≤$1,400 ({len(filtered)} of {len(all_listings)} total)</h2>')
            if not filtered:
                out.append('<p><em>No Zillow listings under $1,400 in SF. Zillow mostly lists whole apartments which start around $1,450+ here.</em></p>')
            else:
                out.append('<table><thead><tr><th>#</th><th>Price</th><th>Beds</th><th>Address</th><th>Status</th><th>Link</th></tr></thead><tbody>')
                for i, l in enumerate(filtered, 1):
                    url = l.get('url','')
                    if url and not url.startswith('http'):
                        url = 'https://www.zillow.com' + url
                    pn = l.get('price_numeric', 99999)
                    row_class = ' class="highlight"'
                    out.append(f'<tr{row_class}><td>{i}</td><td>{html.escape(str(l.get("price","")))}</td><td>{html.escape(str(l.get("beds","")))}</td><td>{html.escape(str(l.get("address","")))}</td><td>{html.escape(str(l.get("status","")))}</td><td><a href="{html.escape(url)}" target="_blank">View</a></td></tr>')
                out.append('</tbody></table>')
    else:
        out.append('''<div class="section-zillow">
<h2>How to populate Zillow data</h2>
<p>Zillow uses PerimeterX bot protection. Run the scraper with a real browser:</p>
<pre><code>cd /Users/test/Desktop/housing-S26 && python3 scrape_zillow.py</code></pre>
</div>''')

    out.append('<h2>Browse Zillow Directly</h2>')
    out.append('<p>Open Zillow in your browser and set the price filter manually (their URL params don\'t work reliably):</p>')
    out.append('<p><a href="https://www.zillow.com/san-francisco-ca/rentals/" target="_blank" style="font-size:18px;font-weight:bold">Zillow SF Rentals →</a></p>')
    out.append('<p>Tips: Click "Price" → set Max to $2,000. Click "More" → set Parking: 1+. Zoom map to your preferred area.</p>')
    return "\n".join(out)

def render_schedule():
    p = os.path.join(ROOT, "schedule_may13.md")
    if not os.path.exists(p):
        return "<p><em>No schedule file.</em></p>"
    with open(p) as f:
        return md_to_html(f.read())

def render_script():
    p = os.path.join(ROOT, "contact_landlords.py")
    with open(p) as f:
        content = f.read()
    return f'<h2>contact_landlords.py</h2><p>Run: <code>cd /Users/test/Desktop/housing-S26 && python3 contact_landlords.py</code></p><pre><code>{html.escape(content)}</code></pre>'

def render_contact_status():
    """Show outreach tracker from outreach_tracker.json."""
    out = []

    # Message template
    out.append('''<div class="card" style="border-left:4px solid #1a1a2e;margin-bottom:24px">
<h3 style="margin-top:0">Short Opener (copy-paste)</h3>
<p style="font-size:14px;background:#f9f9f9;padding:12px;border-radius:4px;line-height:1.7">
Hi! I'm Simon, Cornell grad working at a startup in SF. Looking for a place starting June 1. Non-smoker, no parties, very clean. Is this still available? Happy to chat or tour anytime — 415-426-8741.
</p>
</div>''')

    # Load tracker
    tracker_path = os.path.join(ROOT, "outreach_tracker.json")
    if not os.path.exists(tracker_path):
        out.append('<p><em>No tracker file yet.</em></p>')
        return "\n".join(out)

    with open(tracker_path) as f:
        tracker = json.load(f)

    # Stats
    contacted = [t for t in tracker if t["status"] == "contacted"]
    replied = [t for t in tracker if t["status"] == "replied"]
    declined = [t for t in tracker if t["status"] in ("declined", "closed")]
    pending = [t for t in tracker if t["status"] == "pending"]

    out.append(f'''<div class="stats">
<div class="stat"><div class="stat-num" style="color:#2e7d32">{len(contacted)}</div><div class="stat-label">Contacted</div></div>
<div class="stat"><div class="stat-num" style="color:#1565c0">{len(replied)}</div><div class="stat-label">Replied</div></div>
<div class="stat"><div class="stat-num" style="color:#e65100">{len(pending)}</div><div class="stat-label">Pending</div></div>
<div class="stat"><div class="stat-num" style="color:#999">{len(declined)}</div><div class="stat-label">Closed</div></div>
</div>''')

    # Status color map
    status_colors = {"contacted": "#2e7d32", "replied": "#1565c0", "pending": "#e65100", "declined": "#999", "closed": "#999", "touring": "#6a1b9a"}

    # Full table
    out.append('<h2>All Outreach</h2>')
    out.append('<table><thead><tr><th>#</th><th>Status</th><th>Name</th><th>Address</th><th>Date</th><th>Response</th><th>Notes</th></tr></thead><tbody>')
    for t in tracker:
        color = status_colors.get(t["status"], "#333")
        status_label = t["status"].upper()
        row_class = ' class="highlight"' if t["status"] == "replied" else ''
        resp = html.escape(t.get("response") or "—")
        notes = html.escape(t.get("notes") or "—")
        out.append(f'<tr{row_class}><td>{t["id"]}</td><td><span style="color:{color};font-weight:bold">{status_label}</span></td><td><strong>{html.escape(t["name"])}</strong></td><td>{html.escape(t["address"])}</td><td>{html.escape(t.get("date_contacted",""))}</td><td>{resp}</td><td>{notes}</td></tr>')
    out.append('</tbody></table>')

    # Action items
    if replied:
        out.append('<h2 style="color:#1565c0">Action Required — Replies</h2>')
        for t in replied:
            out.append(f'<div class="card" style="border-left:4px solid #1565c0"><strong>{html.escape(t["name"])}</strong> — {html.escape(t["address"])}<br><em>{html.escape(t.get("response",""))}</em><br><small>{html.escape(t.get("notes",""))}</small></div>')

    out.append('<hr><p style="font-size:12px;color:#666">Data: <code>outreach_tracker.json</code> — edit status to: contacted, replied, pending, touring, declined, closed</p>')
    return "\n".join(out)


def render_log():
    p = os.path.join(ROOT, "outreach_live.log")
    if not os.path.exists(p):
        return "<p><em>No log yet.</em></p>"
    with open(p) as f:
        content = f.read()
    if not content.strip():
        return "<p><em>Log empty — waiting for script output...</em></p>"
    return f'<div class="log">{html.escape(content)}</div>'

def md_to_html(text):
    out = []
    in_code = False
    in_list = False
    in_para = []
    def flush():
        if in_para:
            out.append("<p>" + " ".join(in_para) + "</p>")
            in_para.clear()
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("```"):
            flush()
            if not in_code: out.append("<pre><code>")
            else: out.append("</code></pre>")
            in_code = not in_code
            i += 1; continue
        if in_code:
            out.append(html.escape(line))
            i += 1; continue
        if line.startswith("|") and i+1 < len(lines) and re.match(r"^\|[\s\-:|]+\|\s*$", lines[i+1]):
            flush()
            if in_list: out.append("</ul>"); in_list = False
            out.append('<table>')
            hdr = [c.strip() for c in line.strip("|").split("|")]
            out.append("<thead><tr>"+"".join(f"<th>{_inline(h)}</th>" for h in hdr)+"</tr></thead><tbody>")
            i += 2
            while i < len(lines) and lines[i].startswith("|"):
                row = [c.strip() for c in lines[i].strip("|").split("|")]
                out.append("<tr>"+"".join(f"<td>{_inline(c)}</td>" for c in row)+"</tr>")
                i += 1
            out.append("</tbody></table>"); continue
        if line.startswith(">"):
            flush()
            if in_list: out.append("</ul>"); in_list = False
            quote_lines = []
            while i < len(lines) and lines[i].startswith(">"):
                quote_lines.append(re.sub(r"^>\s?", "", lines[i]))
                i += 1
            inner = " ".join(_inline(q) for q in quote_lines if q.strip())
            out.append(f'<blockquote class="callout">{inner}</blockquote>')
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            flush()
            if in_list: out.append("</ul>"); in_list = False
            out.append(f"<h{len(m.group(1))}>{_inline(m.group(2))}</h{len(m.group(1))}>")
            i += 1; continue
        if re.match(r"^\s*[-*]\s+", line):
            flush()
            if not in_list: out.append("<ul>"); in_list = True
            out.append(f"<li>{_inline(re.sub(r'^\\s*[-*]\\s+','',line))}</li>")
            i += 1; continue
        else:
            if in_list: out.append("</ul>"); in_list = False
        if re.match(r"^\s*---+\s*$", line):
            flush(); out.append("<hr>"); i += 1; continue
        if line.strip() == "": flush()
        else: in_para.append(_inline(line))
        i += 1
    flush()
    if in_list: out.append("</ul>")
    return "\n".join(out)

def _inline(text):
    text = html.escape(text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2" target="_blank">\1</a>', text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r'(?<![\"=>])(https?://[^\s<>\"]+)', r'<a href="\1" target="_blank">\1</a>', text)
    return text

class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a, **k): pass
    def do_GET(self):
        path = urlparse(self.path).path
        try:
            if path == "/":
                html_out = page("All Properties — SF Housing Search", render_all_properties())
            elif path == "/zillow":
                html_out = page("Zillow Listings", render_zillow_page())
            elif path == "/status":
                html_out = page("Contact Status — Outreach Tracker", render_contact_status())
            elif path == "/schedule":
                html_out = page("Schedule — May 13", render_schedule())
            elif path == "/script":
                html_out = page("Outreach Script", render_script())
            elif path == "/log":
                body = '<h2>Live Outreach Log <span style="float:right;font-size:13px;color:#666">auto-refresh 3s</span></h2>' + render_log()
                html_out = page("Live Log", body, auto_refresh=True)
            else:
                self.send_response(404); self.end_headers()
                self.wfile.write(b"Not found"); return
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html_out.encode("utf-8"))
        except Exception as e:
            self.send_response(500); self.end_headers()
            self.wfile.write(f"Error: {e}".encode())

if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else PORT
    # Optional 2nd arg: data directory (SF data was archived to archive_SF_2026-05/)
    if len(sys.argv) > 2:
        ROOT = sys.argv[2]
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("127.0.0.1", port), H) as httpd:
        print(f"Server running at http://localhost:{port}")
        httpd.serve_forever()


