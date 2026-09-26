"""September search view, using the existing dashboard's server and styles."""
import html
import json
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent


def load_listings():
    return json.loads((ROOT / "september_listings.json").read_text())


def render(css, contacted_ids):
    data = load_listings()
    esc = html.escape
    labels = {
        "monthly": "Month-to-month advertised",
        "confirm": "Confirm monthly flexibility",
        "later": "Later start · October 14",
        "unverified": "Incomplete listing · verify first",
    }
    cards = []
    for rank, item in enumerate(data["listings"]):
        contacted = item["id"] in contacted_ids
        extra = "+" if item["extra"] else ""
        daily = f'{item["rent"] / 30:.2f}'.rstrip("0").rstrip(".")
        furnishing = {"yes": "Furnished", "no": "Unfurnished", "unknown": "Furnishing unconfirmed"}[item["furnished"]]
        facts = [item["bath"], item["included"], item["neighborhood"]]
        fact_html = "".join(f"<li>{esc(fact)}</li>" for fact in facts)
        contact = item.get("contact", "Use the listing’s Reply button to ask the host. No message has been sent.")
        cards.append(f'''
<article class="card latest-card{' top' if rank == 0 else ''}{' contacted' if contacted else ''}"
 data-id="{esc(item['id'])}" data-rank="{rank}" data-price="{item['rent']}"
 data-group="{item['group']}" data-parking="{item['parking']}" data-furnished="{item['furnished']}"
 data-contacted="{int(contacted)}" data-text="{esc(' '.join(str(v) for v in item.values()).lower())}">
 <div class="card-content">
  <div class="card-head"><h2 class="card-title">{esc(item['title'])}</h2>
   <div class="price">${item['rent']:,}{extra}<small>/month · ${daily}{extra}/day</small></div></div>
  <p class="area">{esc(item['area'])}</p>
  <div class="tags"><span class="status {'go' if item['group'] == 'monthly' else 'check'}">{labels[item['group']]}</span>
   <span class="pill">{furnishing}</span><span class="pill">{esc(item['parking_label'])}</span></div>
  <ul class="facts">{fact_html}</ul>
  <p class="confirmation"><strong>Confirm:</strong> {esc(item['confirm'])}</p>
  <details class="listing-details"><summary>Dates, deposit and house rules</summary>
   <dl><dt>Advertised timing</dt><dd>{esc(item['availability'])}</dd>
   <dt>Lease</dt><dd>{esc(item['term'])}</dd><dt>Upfront cost</dt><dd>{esc(item['deposit'])}</dd>
   <dt>House rules</dt><dd>{esc(item['conditions'])}</dd></dl>
  </details>
 </div>
 <aside class="contact-box">
  <div class="contact-title">{'Start here' if rank == 0 else 'Next step'}</div>
  <a class="btn" href="{esc(item['url'])}" target="_blank" rel="noopener noreferrer">Open listing ↗</a>
  <a class="map-link" href="https://www.google.com/maps/search/?api=1&amp;query={quote(item['area'] + ', California')}" target="_blank" rel="noopener noreferrer">Explore approximate area ↗</a>
  <button class="copy-inquiry reach-toggle" type="button">Copy inquiry</button>
  <button class="mark-contact reach-toggle{' on' if contacted else ''}" type="button" aria-pressed="{str(contacted).lower()}">{'✓ Reached out' if contacted else 'Mark as reached out'}</button>
  <p class="contact-help">{esc(contact)}</p>
 </aside>
</article>''')
    script = (ROOT / "latest_dashboard.js").read_text()
    return f'''<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Bay Area Monthly Stays · September 29</title>
<style>{css}
body{{background:#fafbfc;max-width:1160px;padding:28px 24px 48px}}
.masthead{{display:flex;justify-content:space-between;gap:20px;align-items:flex-start;margin-bottom:20px}}
.eyebrow{{font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:#64748b;font-weight:700;margin-bottom:6px}}
h1{{font-size:30px;letter-spacing:-.7px}}.archive-link{{font-size:12px;white-space:nowrap;padding-top:8px}}
.search-summary{{font-size:15px;color:#475569;margin-top:6px;max-width:780px}}
.scope-note{{font-size:12px;color:#64748b;margin-top:8px}}
.status-panel{{margin:18px 0}}.stat-num{{font-size:26px}}.stat-lbl{{font-size:11px}}
.research-note{{background:#eff6ff;border:1px solid #dbeafe;border-radius:8px;padding:12px 16px;color:#334155;font-size:13px}}
.filterbar{{position:static;padding:14px;margin-top:20px}}.filter-controls{{display:flex;flex-wrap:wrap;gap:10px;margin-top:12px}}
.filter-controls label{{display:flex;flex-direction:column;gap:4px;color:#64748b;font-size:11px;font-weight:600;flex:1;min-width:135px}}
select{{width:100%;padding:8px;border:1px solid #cbd5e1;border-radius:6px;background:white;color:#1e293b;font:inherit;font-size:13px}}
.fb-search{{background-image:none;padding-left:12px}}.fb-preset{{padding:9px 12px}}
.list-heading{{display:flex;justify-content:space-between;gap:12px;align-items:center;margin:22px 0 12px}}
.list-heading h2{{border:0;padding:0;margin:0}}.list-heading p{{color:#64748b;font-size:12px}}
.latest-card{{grid-template-columns:minmax(0,1fr) 220px;height:auto;padding:20px;gap:24px;margin:14px 0}}
.latest-card .card-title{{margin:0;padding:0;border:0;font-size:18px;line-height:1.35}}
.latest-card .card-content{{overflow:visible}}.latest-card .price{{font-size:20px;text-align:right}}
.price small{{display:block;font-size:11px;font-weight:500;color:#64748b;margin-top:3px}}
.latest-card .area{{font-size:13px;margin:4px 0 10px}}
.tags{{display:flex;flex-wrap:wrap;align-items:center;gap:6px;margin-bottom:8px}}
.tags .status{{margin:0}}.pill{{font-size:11px;background:#f1f5f9;color:#475569;border-radius:4px;padding:3px 8px}}
.latest-card .facts{{max-height:none;font-size:13px;line-height:1.65}}
.confirmation{{margin-top:10px;color:#92400e;background:#fffbeb;padding:8px 10px;border-radius:5px;font-size:12px;line-height:1.5}}
.latest-card .contact-box{{height:auto;overflow:visible;align-self:start;padding:12px;gap:8px}}
.latest-card .btn{{flex:initial}}.map-link{{font-size:12px;text-align:center}}
.contact-help{{font-size:11px;line-height:1.5;color:#64748b;margin-top:2px}}
.listing-details{{font-size:12px;margin-top:12px}}.listing-details summary{{color:#2563eb;cursor:pointer;font-weight:600}}
dl{{display:grid;grid-template-columns:120px 1fr;gap:6px 12px;margin-top:10px}}dt{{color:#64748b}}dd{{margin:0;color:#334155}}
.footer-note{{font-size:12px;color:#64748b;line-height:1.7;margin-top:22px}}
#feedback{{position:fixed;bottom:20px;left:50%;transform:translateX(-50%);padding:10px 18px;background:#0f172a;color:white;border-radius:8px;z-index:100;font-size:13px;max-width:90vw}}
#feedback:empty{{display:none}}[hidden]{{display:none!important}}button:focus-visible,select:focus-visible,a:focus-visible,summary:focus-visible{{outline:2px solid #2563eb;outline-offset:3px}}
@media(max-width:720px){{body{{padding:18px 12px}}.masthead{{flex-direction:column;gap:6px}}h1{{font-size:25px}}.archive-link{{padding:0}}.latest-card{{grid-template-columns:1fr;padding:16px;gap:14px}}.latest-card .card-head{{align-items:flex-start}}.latest-card .price{{text-align:left}}.latest-card .contact-box{{width:100%}}.list-heading{{align-items:flex-start}}.stat-num{{font-size:24px}}dl{{grid-template-columns:100px 1fr}}}}
</style></head><body>
<header class="masthead"><div><p class="eyebrow">Your housing search · Fall 2026</p><h1>Bay Area monthly stays</h1>
<p class="search-summary">From <strong>{data['move_in']}</strong> · preferably below <strong>$50/day</strong> · private bathroom + parking</p>
<p class="scope-note">Residential areas near shops. Private rooms in shared homes included; whole-place preference still to confirm.</p></div>
<a class="archive-link" href="summer.html">Summer housing archive ↗</a></header>
<div class="status-panel"><div class="status-row">
<div class="stat"><div class="stat-num">12</div><div class="stat-lbl">Researched leads</div></div>
<div class="stat"><div class="stat-num ok">4</div><div class="stat-lbl">Start-date leads advertising<br>month-to-month</div></div>
<div class="stat"><div class="stat-num">$875</div><div class="stat-lbl">Lowest advertised monthly cost<br>lease and area need checking</div></div>
<div class="stat"><div class="stat-num warn">0</div><div class="stat-lbl">September 29 dates<br>confirmed by a host</div></div>
</div></div>
<p class="research-note"><strong>Start with Sunnyvale:</strong> $1,200 including utilities, furnished, private entrance and month-to-month terms. Confirm a driveway space and September 29. <strong>Research: {data['researched']}.</strong> These are advertised leads; availability has not been confirmed with hosts.</p>
<div class="filterbar"><div class="fb-row">
<input id="search" class="fb-search" type="search" aria-label="Search listings" placeholder="Search city, neighborhood or details…">
<button id="best" class="fb-preset" type="button">Monthly options</button><button id="reset" class="fb-reset" type="button">Reset</button>
<span class="fb-count" aria-live="polite"><b id="shown">10</b> of 12 showing</span></div>
<div class="filter-controls">
<label>Monthly cost<select id="budget"><option value="1500">Up to $1,500</option><option value="1300">Up to $1,300</option><option value="1200">Up to $1,200</option><option value="1000">Up to $1,000</option></select></label>
<label>Lease / timing<select id="term"><option value="start">September 29 leads</option><option value="monthly">Month-to-month advertised</option><option value="confirm">Lease needs confirmation</option><option value="all">All, including later / unverified</option></select></label>
<label>Parking<select id="parking"><option value="all">All parking types</option><option value="offstreet">Driveway / off-street advertised</option><option value="street">Street only</option></select></label>
<label>Furnishing<select id="furnished"><option value="all">Any</option><option value="yes">Furnished</option><option value="no">Unfurnished</option></select></label>
<label>Sort<select id="sort"><option value="recommended">Recommended order</option><option value="price">Lowest price first</option></select></label>
</div><p class="scope-note">Price filters use known monthly charges. “+” means utilities or parking may cost extra. Off-street availability and fees still need confirmation.</p></div>
<main><div class="list-heading"><h2>The latest shortlist</h2><p>All bathrooms advertised as private</p></div>
<div id="listings">{''.join(cards)}</div>
<p id="empty" class="banner" hidden>No listings match. Try a higher budget or reset the filters.</p>
<details class="disc"><summary>Inquiry to send to the host</summary><div class="disc-body"><p id="inquiry">Hi, I’m looking for housing starting September 29, 2026, initially for one month with the option to extend monthly. Is your room available for those dates, and would that arrangement work? I need a bathroom exclusively for my use and parking for one car. Could you confirm the total monthly cost including utilities, internet and parking, all upfront charges, whether the room is furnished, and the notice required to move out? Please also share the nearest cross streets and whether an in-person or video tour is available. Thank you.</p></div></details>
</main><footer class="footer-note">Daily equivalents use a 30-day month; refundable deposits are additional move-in cash. Neighborhood descriptions are from advertisers and are not independent safety assessments. Source pages may contain cached details. Reached-out marks are saved in this browser and do not send messages.</footer>
<div id="feedback" role="status" aria-live="polite"></div><script>{script}</script></body></html>'''
