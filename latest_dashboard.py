"""September search view, using the existing dashboard's server and styles."""
import html
import json
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent


def load_listings():
    return json.loads((ROOT / "september_listings.json").read_text())


def render(css, contacted_ids, placeholder_svg):
    data = load_listings()
    distances = json.loads((ROOT / 'distance_estimates.json').read_text())
    esc = html.escape
    labels = {
        "monthly": "Month-to-month advertised",
        "one_month": "One-month minimum · renewal unconfirmed",
        "confirm": "Confirm monthly flexibility",
        "later": "Later start · check dates",
        "unverified": "Incomplete listing · verify first",
        "waitlist": "Lease pending · watch for it to reopen",
        "unavailable": "Listing page no longer available",
    }
    sources = {"zillow": "Zillow", "supost": "SUpost", "furnishedfinder": "Furnished Finder", "spareroom": "SpareRoom", "apartments": "Apartments.com", "craigslist": "Craigslist"}
    present_sources = {item['source'] for item in data['listings']}
    source_options = ''.join(f'<option value="{key}">{value}</option>'
                             for key, value in sources.items() if key in present_sources)
    regions = {"north": "North of SF · Marin / Sonoma", "solano": "Solano · northeast Bay", "east": "East Bay", "peninsula": "Peninsula", "south": "South Bay"}
    present_regions = {item['region'] for item in data['listings']}
    region_options = ''.join(f'<option value="{key}">{value}</option>'
                             for key, value in regions.items() if key in present_regions)
    ff_monthly = sum(item['source'] == 'furnishedfinder' and item['group'] == 'one_month' for item in data['listings'])
    ff_older = sum(item['source'] == 'furnishedfinder' and item['group'] == 'unverified' for item in data['listings'])
    cards = []
    for rank, item in enumerate(data["listings"]):
        contacted = bool(item.get("verified_contact"))
        status = item.get('outreach_status', 'blocked')
        rating = item.get('visual_review', {})
        score = lambda key: 'Unrated' if rating.get(key) is None else f"{rating[key]:g} / 5"
        verified = contacted
        tour = item.get('tour_status', 'No tour arranged.')
        priority = 0 if tour.startswith('Confirmed') else 1 if 'Replied' in item.get('timing_label', '') else 2 if contacted else 3
        show_draft = bool(item.get('inquiry')) and not contacted
        status_labels = {'sent': 'Sent · verified', 'previously_sent': 'Sent earlier · verified', 'queued': 'Accepted · delivery queued', 'blocked': 'Blocked · not sent', 'closed': 'Closed · not sent', 'submission_unconfirmed': 'Submission unconfirmed'}
        fit_labels = {'candidate': 'Advertised fit · confirm details', 'conditional': 'Terms or timing need agreement', 'mismatch': 'Requirement mismatch · backup only', 'closed': 'Closed listing'}
        distance = distances['cities'][item['city']]
        miles = distance['driving_miles']
        campus_miles = distance['stanford_miles']
        balanced_miles = distance['balanced_miles']
        route_url = f"https://www.google.com/maps/dir/?api=1&origin={distance['lat']},{distance['lon']}&destination={distances['destination']['lat']},{distances['destination']['lon']}&travelmode=driving"
        campus_route_url = f"https://www.google.com/maps/dir/?api=1&origin={distance['lat']},{distance['lon']}&destination={distances['destination_stanford']['lat']},{distances['destination_stanford']['lon']}&travelmode=driving"
        extra = "+" if item["extra"] else ""
        daily = f'{item["rent"] / 30:.2f}'.rstrip("0").rstrip(".")
        furnishing = {"yes": "Furnished", "no": "Unfurnished", "unknown": "Furnishing unconfirmed"}[item["furnished"]]
        facts = [item["bath"], item["included"], item["neighborhood"]]
        fact_html = "".join(f"<li>{esc(fact)}</li>" for fact in facts)
        contact = item.get("contact", "Use the listing’s Reply button to ask the host. No message has been sent.")
        photos = item.get("photos", [])
        if photos:
            photo_data = esc(json.dumps(["maps/" + photo["file"] for photo in photos]))
            thumbs = "".join(
                f'<button class="photo-thumb" type="button" data-photo-index="{index}" aria-label="Open photo {index + 1} of {esc(item["area"])}">'
                f'<img src="maps/{esc(photo["file"])}" alt="Listing photo {index + 1}" loading="lazy" width="60" height="45"></button>'
                for index, photo in enumerate(photos) if index > 0)
            gallery = f'''<figure class="listing-gallery" data-photos="{photo_data}" data-location="{esc(item['area'])}">
 <button class="photo-main" type="button" data-photo-index="0" aria-label="View photos of {esc(item['area'])}">
 <img src="maps/{esc(photos[0]['file'])}" alt="Advertiser’s listing photo for {esc(item['area'])}" loading="lazy" width="600" height="450">
 <span class="photo-count">{len(photos)} photos · enlarge</span></button>
 <div class="photo-thumbs">{thumbs}</div><figcaption>Photos from the advertiser’s listing</figcaption></figure>'''
        else:
            gallery = f'''<figure class="listing-gallery no-photos"><img src="{placeholder_svg(item['area'], '')}" alt="Area illustration for {esc(item['area'])}; property photos unavailable" width="180" height="162"><figcaption>Area illustration · no listing photos available</figcaption></figure>'''
        cards.append(f'''
<article id="{esc(item['id'])}" class="card latest-card{' contacted' if contacted else ''}"
 data-id="{esc(item['id'])}" data-rank="{rank}" data-price="{item['rent']}"
 data-distance="{miles}" data-stanford="{campus_miles}" data-balanced="{balanced_miles}" data-region="{item['region']}"
 data-group="{item['group']}" data-source="{item['source']}" data-parking="{item['parking']}" data-furnished="{item['furnished']}"
 data-verified="{int(verified)}" data-outreach="{status}" data-fit="{item.get('fit_status', 'conditional')}" data-priority="{priority}"
 data-clean="{rating.get('cleanliness') or 0}" data-modern="{rating.get('modernity') or 0}" data-value="{rating.get('value') or 0}"
 data-contacted="{int(contacted)}" data-text="{esc(' '.join(str(v) for v in item.values()).lower())}">
 {gallery}
 <div class="card-content">
  <div class="card-head"><h2 class="card-title">{esc(item['title'])}</h2>
   <div class="price">${item['rent']:,}{extra}<small>/month · ${daily}{extra}/day</small></div></div>
  <p class="area">{esc(item['area'])}</p>
  <p class="distance-line"><strong>≈ {miles:.0f} mi to SF</strong> · <strong>≈ {campus_miles:.0f} mi to Stanford</strong> · {regions[item['region']]}
   <small>Worst-case one-way drive: <b>{balanced_miles:.0f} miles</b>. From {esc(item['city'])} city center to the Ferry Building and to campus.</small></p>
  <div class="tags"><span class="pill source-label">{sources[item['source']]}</span><span class="status {'go' if item['group'] in ('monthly', 'one_month') else 'check'}">{esc(item.get('timing_label', labels[item['group']]))}</span>
   <span class="pill">{furnishing}</span><span class="pill">{esc(item['parking_label'])}</span></div>
  <div class="outreach-status {status}"><strong>{esc(status_labels[status])}</strong><p>{esc(item.get('outreach_note', ''))}</p><p><strong>Tour:</strong> {esc(tour)}</p></div>
  <p class="fit-note {item.get('fit_status', 'conditional')}">{esc(fit_labels[item.get('fit_status', 'conditional')])}</p>
  <ul class="facts">{fact_html}</ul>
  <div class="rating-row"><span>Apparent cleanliness <b>{score('cleanliness')}</b></span><span>Modernity <b>{score('modernity')}</b></span><span>Value for your needs <b>{score('value')}</b></span></div>
  <details class="rating-details"><summary>Photo review · {esc(rating.get('scope', 'No usable photos'))}</summary><p>{esc(rating.get('note', ''))}</p></details>
  <p class="confirmation"><strong>Confirm:</strong> {esc(item['confirm'])}</p>
  {f'''<details class="draft"><summary>Short unsent draft &middot; <em>{esc(item["inquiry_note"])}</em></summary><p class="draft-text">{esc(item["inquiry"])}</p></details>''' if show_draft else ''}
  <details class="listing-details"><summary>Dates, deposit and house rules</summary>
   <dl><dt>Advertised timing</dt><dd>{esc(item['availability'])}</dd>
   <dt>Lease</dt><dd>{esc(item['term'])}</dd><dt>Upfront cost</dt><dd>{esc(item['deposit'])}</dd>
   <dt>House rules</dt><dd>{esc(item['conditions'])}</dd></dl>
  </details>
 </div>
 <aside class="contact-box">
  <div class="contact-title">Next step</div>
  <a class="btn" href="{esc(item['url'])}" target="_blank" rel="noopener noreferrer">Open listing ↗</a>
  <a class="map-link" href="https://www.google.com/maps/search/?api=1&amp;query={quote(item['area'] + ', California')}" target="_blank" rel="noopener noreferrer">Explore approximate area ↗</a>
  <a class="map-link" href="{esc(route_url)}" target="_blank" rel="noopener noreferrer">Drive to SF · check traffic ↗</a>
  <a class="map-link" href="{esc(campus_route_url)}" target="_blank" rel="noopener noreferrer">Drive to Stanford · check traffic ↗</a>
  {'<button class="copy-inquiry reach-toggle" type="button">Copy short inquiry</button>' if show_draft else ''}
  <button class="mark-contact reach-toggle{' on' if contacted else ''}" type="button" aria-pressed="{str(contacted).lower()}" {'disabled' if verified else ''}>{'✓ Verified in message log' if contacted else 'Mark as contacted manually'}</button>
  <p class="contact-help">{esc(contact)}</p>
 </aside>
</article>''')
    script = (ROOT / "latest_dashboard.js").read_text()
    count = len(data["listings"])
    stats = data.get('outreach_summary', {})
    photo_count = sum(x.get('visual_review', {}).get('cleanliness') is not None for x in data['listings'])
    tour_cards = []
    for tour_item in sorted(data.get('tours_public', []), key=lambda t: (t['status'] == 'postponed_by_host', t.get('when') or '')):
        lead = next(x for x in data['listings'] if x['id'] == tour_item['listing_id'])
        when = datetime.fromisoformat(tour_item['when']).strftime('%B %-d, %-I:%M %p') if tour_item.get('when') else 'Time requested'
        label = {'confirmed': 'Confirmed', 'awaiting_confirmation': 'Proposed · awaiting confirmation', 'postponed_by_host': 'Postponed by host · no longer booked', 'canceled_unavailable': 'Canceled · room taken', 'past_outcome_unknown': 'Past viewing · outcome unknown', 'agreed_time_undecided': 'Tour agreed · time still to be set'}.get(tour_item['status'], tour_item['status'])
        tour_cards.append(f'<p><strong>{esc(label)} · {esc(when)} Pacific:</strong> {esc(lead["city"])} · {esc(tour_item["area"])}. {esc(tour_item.get("note", ""))}</p>')
    monitoring = data.get('monitoring_public', {})
    monitor_html = ''
    monitor_html = '<p class="research-note"><strong>Messages and monitoring:</strong> <a href="http://localhost:5555/inbox">Open your private housing inbox →</a> Incoming and outgoing messages, tour updates, and live channel status are together there. Available on this computer.</p>'
    start_count = sum(item["group"] in ("monthly", "one_month", "confirm") for item in data["listings"])
    monthly_count = sum(item["group"] in ("monthly", "one_month") for item in data["listings"])
    lowest = min(item["rent"] for item in data["listings"] if item["group"] in ("monthly", "one_month", "confirm"))
    return f'''<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Bay Area Monthly Stays · September 29</title>
<style>{css}
.outreach-status{{padding:10px 12px;background:#ecfdf5;border-left:3px solid #059669;border-radius:5px;font-size:12px;line-height:1.55;margin:12px 0}}.outreach-status p{{margin:5px 0 0}}.outreach-status.blocked,.outreach-status.submission_unconfirmed,.outreach-status.queued{{background:#fffbeb;border-color:#d97706}}.outreach-status.closed{{background:#f1f5f9;border-color:#94a3b8}}
.fit-note{{font-size:11px;font-weight:600;color:#475569;margin:8px 0}}.fit-note.mismatch{{color:#9a3412}}.rating-row{{display:flex;flex-wrap:wrap;gap:14px;margin:12px 0}}.rating-row span{{font-size:10px;color:#64748b}}.rating-row b{{display:block;font-size:16px;color:#334155}}.rating-details{{font-size:12px;color:#475569}}.rating-details summary{{cursor:pointer;color:#2563eb}}.rating-details p{{margin:8px 0;line-height:1.6}}.tour-panel{{border:1px solid #a7d4ca;background:#effbf5;padding:16px;border-radius:8px;margin:16px 0;color:#164e3d;font-size:13px;line-height:1.65}}.tour-panel h2{{font-size:18px;margin:0 0 8px;border:0;padding:0}}.tour-panel p{{margin:6px 0}}.mark-contact:disabled{{cursor:default;opacity:1}}.status-panel .stat-lbl{{line-height:1.4}}
body{{background:#fafbfc;max-width:1160px;padding:28px 24px 48px}}
.masthead{{display:flex;justify-content:space-between;gap:20px;align-items:flex-start;margin-bottom:20px}}
.eyebrow{{font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:#64748b;font-weight:700;margin-bottom:6px}}
h1{{font-size:30px;letter-spacing:-.7px}}.archive-link{{font-size:12px;white-space:nowrap;padding-top:8px}}
.search-summary{{font-size:15px;color:#475569;margin-top:6px;max-width:780px}}
.scope-note{{font-size:12px;color:#64748b;margin-top:8px}}
.status-panel{{margin:18px 0}}.stat-num{{font-size:26px}}.stat-lbl{{font-size:11px}}
.research-note{{background:#eff6ff;border:1px solid #dbeafe;border-radius:8px;padding:12px 16px;color:#334155;font-size:13px}}
.geography{{margin:16px 0;padding:16px;border:1px solid #a7d4ca;background:#f0f9f6;border-radius:8px;font-size:13px;color:#334155;line-height:1.6}}
.geography h2{{border:0;margin:0 0 6px;padding:0;font-size:17px;color:#0f513d}}.geography .fb-preset{{margin-top:10px}}
.distance-line{{margin:0 0 12px;font-size:12px;color:#0f766e;line-height:1.6}}.distance-line small{{display:block;color:#64748b;font-size:11px}}
.channels{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-top:16px}}
.channel{{border:1px solid #e2e8f0;border-radius:8px;background:white;padding:14px;font-size:12px;color:#475569;line-height:1.55}}
.channel h2{{font-size:15px;margin:0 0 6px;border:0;padding:0;color:#0f172a}}.channel p{{margin-bottom:8px}}
.channel button{{border:0;padding:0;background:none;font:inherit;color:#2563eb;text-align:left;cursor:pointer;font-weight:600}}
.source-label{{background:#e0e7ff!important;color:#3730a3!important;font-weight:600}}
.filterbar{{position:static;padding:14px;margin-top:20px}}.filter-controls{{display:flex;flex-wrap:wrap;gap:10px;margin-top:12px}}
.filter-controls label{{display:flex;flex-direction:column;gap:4px;color:#64748b;font-size:11px;font-weight:600;flex:1;min-width:135px}}
select{{width:100%;padding:8px;border:1px solid #cbd5e1;border-radius:6px;background:white;color:#1e293b;font:inherit;font-size:13px}}
.fb-search{{background-image:none;padding-left:12px}}.fb-preset{{padding:9px 12px}}
.list-heading{{display:flex;justify-content:space-between;gap:12px;align-items:center;margin:22px 0 12px}}
.list-heading h2{{border:0;padding:0;margin:0}}.list-heading p{{color:#64748b;font-size:12px}}
.latest-card{{grid-template-columns:200px minmax(0,1fr) 180px;height:auto;padding:18px;gap:18px;margin:14px 0}}
.listing-gallery{{margin:0;min-width:0;align-self:start}}.listing-gallery img{{display:block;max-width:100%}}
.photo-main{{position:relative;display:block;width:100%;padding:0;border:0;border-radius:6px;overflow:hidden;background:#f1f5f9;cursor:zoom-in}}
.photo-main img{{width:100%;height:160px;object-fit:contain}}.photo-count{{position:absolute;bottom:6px;right:6px;background:rgba(15,23,42,.85);color:white;border-radius:4px;padding:3px 6px;font-size:10px}}
.photo-thumbs{{display:grid;grid-template-columns:repeat(4,1fr);gap:4px;margin-top:5px}}.photo-thumb{{border:1px solid #e2e8f0;border-radius:4px;padding:0;overflow:hidden;background:#f8fafc;cursor:zoom-in}}
.photo-thumb img{{width:100%;height:42px;object-fit:cover}}figcaption{{font-size:10px;color:#64748b;line-height:1.4;margin-top:7px}}
.no-photos{{border:1px solid #e2e8f0;border-radius:6px;padding:10px;background:#f3f4f6;text-align:center}}.no-photos img{{margin:auto;width:180px;height:162px}}
.photo-dialog{{border:1px solid #cbd5e1;border-radius:12px;width:min(900px,94vw);max-height:94vh;padding:16px;margin:auto;background:#fff;color:#0f172a}}
.photo-dialog::backdrop{{background:rgba(15,23,42,.8)}}.photo-dialog header{{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:12px}}
.photo-dialog h2{{margin:0;border:0;padding:0;font-size:17px}}.photo-dialog button{{cursor:pointer;padding:8px 14px;border:1px solid #cbd5e1;border-radius:5px;background:white;color:#1e293b;font:inherit}}
#large-photo{{display:block;width:100%;height:min(65vh,620px);object-fit:contain;background:#f1f5f9;border-radius:6px}}.photo-navigation{{display:flex;justify-content:space-between;align-items:center;margin-top:12px;gap:10px}}#photo-position{{font-size:12px;color:#64748b}}
.latest-card .card-title{{margin:0;padding:0;border:0;font-size:18px;line-height:1.35}}
.latest-card .card-head{{flex-wrap:wrap}}
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
.draft{{margin-top:12px;border:1px solid #c7d2fe;background:#eef2ff;border-radius:8px;padding:10px 12px;font-size:12px}}
.draft summary{{color:#3730a3;cursor:pointer;font-weight:700}}.draft summary em{{font-weight:500;font-style:normal;color:#4f46e5}}
.draft-text{{margin:8px 0 0;color:#1e1b4b;font-size:13px;line-height:1.55;white-space:pre-wrap}}
.listing-details{{font-size:12px;margin-top:12px}}.listing-details summary{{color:#2563eb;cursor:pointer;font-weight:600}}
dl{{display:grid;grid-template-columns:120px 1fr;gap:6px 12px;margin-top:10px}}dt{{color:#64748b}}dd{{margin:0;color:#334155}}
.footer-note{{font-size:12px;color:#64748b;line-height:1.7;margin-top:22px}}
#feedback{{position:fixed;bottom:20px;left:50%;transform:translateX(-50%);padding:10px 18px;background:#0f172a;color:white;border-radius:8px;z-index:100;font-size:13px;max-width:90vw}}
#feedback:empty{{display:none}}[hidden]{{display:none!important}}button:focus-visible,select:focus-visible,a:focus-visible,summary:focus-visible{{outline:2px solid #2563eb;outline-offset:3px}}
@media(min-width:721px) and (max-width:1000px){{.latest-card{{grid-template-columns:180px minmax(0,1fr)}}.latest-card .contact-box{{grid-column:2}}}}
@media(max-width:720px){{body{{padding:18px 12px}}.channels{{grid-template-columns:1fr}}.masthead{{flex-direction:column;gap:6px}}h1{{font-size:25px}}.archive-link{{padding:0}}.latest-card{{grid-template-columns:1fr;padding:16px;gap:14px}}.latest-card .card-head{{align-items:flex-start}}.latest-card .price{{text-align:left}}.latest-card .contact-box{{width:100%}}.list-heading{{align-items:flex-start}}.stat-num{{font-size:24px}}dl{{grid-template-columns:100px 1fr}}.photo-main img{{height:230px}}.photo-thumb img{{height:55px}}.no-photos{{display:flex;align-items:center;gap:10px}}.no-photos img{{width:90px;height:81px;margin:0}}}}
</style></head><body>
<header class="masthead"><div><p class="eyebrow">Your housing search · Fall 2026</p><h1>Bay Area monthly stays</h1>
<p class="search-summary">From <strong>September 29–30, 2026</strong> · one month initially · <strong>$1,500 all in</strong> · private full bathroom + parking</p>
<p class="scope-note">Sublet or month-to-month. Furnished apartment or condo preferred; shared homes included. Updated {esc(data['researched'])} · {esc(data['updated_at'][11:16])} Pacific.</p></div></header>
<div class="status-panel"><div class="status-row">
<div class="stat"><div class="stat-num">{count}</div><div class="stat-lbl">Tracked leads</div></div>
<div class="stat"><div class="stat-num ok">{stats.get('total_hosts_contacted', 0)}</div><div class="stat-lbl">Hosts contacted</div></div>
<div class="stat"><div class="stat-num">{stats.get('total_verified_outgoing_messages', 0)}</div><div class="stat-lbl">Outgoing messages verified<br>includes {stats.get('accepted_queued_messages', 0)} accepted / queued</div></div>
<div class="stat"><div class="stat-num ok">{stats.get('confirmed_tours', 0)}</div><div class="stat-lbl">Confirmed in-person tours</div></div>
</div></div>
<section class="tour-panel"><h2>Tour schedule</h2>
{''.join(tour_cards)}<p>{esc(data.get('travel_plan', ''))}</p></section>
{monitor_html}
<p class="research-note"><strong>September 29 update.</strong> {count} leads now include Craigslist and Zillow, with verified outreach, tour status and photo reviews. {photo_count} have enough interior photos for provisional scores. Furnished Finder access is restored. Both SUpost inquiries were accepted after email verification. The downtown poster replied; Grant Avenue is still queued. Both Zillow inquiries are verified sent. Foster City free contact now works; a one-month discount was requested. <strong>Rental availability has not been confirmed with hosts for a complete match to the brief.</strong> A tour confirmation is not a rental commitment.</p>
<section class="geography" id="north-bay"><h2>Location and fit</h2>
<p>The current ceiling is <strong>2.5 hours</strong> to the worse of San Francisco and Stanford, so Fairfield, Vacaville and Sacramento remain backups. Balanced sorting uses the greater of the two road distances. City-center routes are approximate, without live traffic; check each property's exact drive before a tour.</p>
<p>Known shared bathrooms, later dates, over-budget offers and closed ads remain visible for the outreach history, with their conflicts marked. “Show all tracked” includes every record.</p>
<button class="fb-preset" id="north" type="button">North of SF + backups</button>
<p class="scope-note">© OpenStreetMap contributors · Nominatim / OSRM. Photo scores describe visible tidiness and finishes, not an inspection. Value includes price, location and fit for this one-month stay.</p></section>
<section class="channels" aria-label="Source status">
<div class="channel"><h2>SpareRoom</h2><p>All reachable tracked advertisers contacted, including Tim in Foster City after free contact became available. Four ads remain closed or unavailable. No paid upgrade.</p><button type="button" data-source-preset="spareroom">Show SpareRoom →</button></div>
<div class="channel"><h2>Furnished Finder</h2><p>All ten inquiries verified. Anna confirmed September 30 at 9 AM. Leticia's room was taken; her proposed tour is canceled. Mona will send a new time. Don's tenant leaves next week. Berkeley and Vacaville were declined after bathroom conflicts were confirmed.</p><button type="button" data-source-preset="furnishedfinder">Show Furnished Finder →</button></div>
<div class="channel"><h2>Craigslist</h2><p>Twelve email inquiries verified. Foster City's phone-only ad has no message sent and also conflicts on date and bathroom.</p><button type="button" data-source-preset="craigslist">Show Craigslist →</button></div>
<div class="channel"><h2>SUpost</h2><p>Both Palo Alto inquiries accepted. The downtown poster replied by email and supplied the landlord's phone; the Grant Avenue inquiry is still queued.</p><button type="button" data-source-preset="supost">Show SUpost →</button></div>
<div class="channel"><h2>Zillow</h2><p>Both inquiries verified sent. San Jose advertises $1,600, so a discount is needed. Suisun City supplied a message confirmation and email receipt; its private-bathroom claim still conflicts with the description.</p><button type="button" data-source-preset="zillow">Show Zillow →</button></div>
<div class="channel"><h2>SF House + Rednote</h2><p>SF House's private-bath tier starts at $1,750 before extras; a compliant exception was requested. Rednote still requires login; no messages sent there.</p><button type="button" data-source-preset="apartments">Show SF House →</button></div>
</section>
<div class="filterbar"><div class="fb-row">
<input id="search" class="fb-search" type="search" aria-label="Search listings" placeholder="Search city, neighborhood or details…">
<button id="best" class="fb-preset" type="button">One-month options</button><button class="fb-preset" id="all-tracked" type="button">Show all tracked</button><button id="reset" class="fb-reset" type="button">Reset</button>
<span class="fb-count" aria-live="polite"><b id="shown">{start_count}</b> of {count} showing</span></div>
<div class="filter-controls">
<label>Region<select id="region"><option value="all">Entire Bay Area</option>{region_options}</select></label>
<label>Distance to SF<select id="maxdistance"><option value="all">Any distance</option><option value="25">Within 25 driving miles</option><option value="35">Within 35 driving miles</option><option value="50">Within 50 driving miles</option></select></label>
<label>Monthly cost<select id="budget"><option value="1500">Up to $1,500</option><option value="1300">Up to $1,300</option><option value="1200">Up to $1,200</option><option value="1000">Up to $1,000</option><option value="999999">Any price · review exceptions</option></select></label>
<label>Source<select id="source"><option value="all">All sources</option>{source_options}</select></label>
<label>Lease / timing<select id="term"><option value="start">Current candidates · confirm dates</option><option value="monthly">One-month / monthly advertised</option><option value="confirm">Lease needs confirmation</option><option value="active">Shortlist + later-start backups</option><option value="later">Later-start backups</option><option value="waitlist">Lease pending · cheapest band, watch these</option><option value="review">All timing, including closed</option></select></label>
<label>Parking<select id="parking"><option value="all">All parking types</option><option value="offstreet">Driveway / off-street advertised</option><option value="street">Street only</option></select></label>
<label>Furnishing<select id="furnished"><option value="all">Any</option><option value="yes">Furnished</option><option value="no">Unfurnished</option></select></label>
<label>Fit<select id="fit"><option value="viable">Candidates + conditional leads</option><option value="all">All fits, including mismatches</option><option value="mismatch">Known requirement mismatches</option><option value="closed">Closed ads</option></select></label>
<label>Outreach<select id="outreach"><option value="all">All outreach statuses</option><option value="sent">Sent / accepted</option><option value="blocked">Blocked · not sent</option><option value="submission_unconfirmed">Submission unconfirmed</option><option value="closed">Closed · not sent</option></select></label>
<label>Sort<select id="sort"><option value="balanced">Balanced · best for both</option><option value="distance">Closest to San Francisco</option><option value="stanford">Closest to Stanford</option><option value="recommended">Recommended order</option><option value="price">Lowest price first</option><option value="priority">Tours and replies first</option><option value="value">Highest value for this stay</option><option value="clean">Cleanest appearance</option><option value="modern">Most modern finishes</option></select></label>
</div><p class="scope-note">Price filters use known recurring monthly charges. “+” means extra charges are unconfirmed. One-time fees and deposits appear under each listing’s details. A one-month minimum does not guarantee month-to-month renewal.</p></div>
<main><div class="list-heading"><h2>The latest shortlist</h2><p>Every bathroom is private unless the card says otherwise</p></div>
<div id="listings">{''.join(cards)}</div>
<p id="empty" class="banner" hidden>No leads match these filters. Try a wider distance or include later starts and older-calendar backups.</p>
<details class="disc"><summary>Short outreach template</summary><div class="disc-body"><p id="inquiry">Hi, I'm Simon, a Stanford graduate. Is your room available for a one-month stay from September 30? When could I tour it in person? Thanks!</p></div></details>
<details class="disc"><summary>How to read the status and ratings</summary><div class="disc-body"><p>Sent means a platform confirmation or matching outgoing conversation was observed. The Grant Avenue SUpost message still shows queued delivery; the downtown poster has replied. An unconfirmed submission is not counted as sent. Exact message text, timestamps and evidence are retained in the private outreach log.</p><p>{esc(data.get('rating_scale', ''))}</p><p>The former Vallejo Zillow lead was removed because its page resolves to a sold house. Closed ads are retained only to avoid duplicate inquiries. No upgrades or application fees have been paid.</p></div></details>
</main><footer class="footer-note">Daily equivalents use a 30-day month; refundable deposits are additional move-in cash. Neighborhood descriptions are from advertisers and are not independent safety assessments. Source pages may contain cached details. Verified message statuses come from the outreach log. Manual contact marks are browser notes and do not send messages or change verified counts.</footer>
<dialog id="photo-dialog" class="photo-dialog" aria-labelledby="photo-title"><header><h2 id="photo-title">Listing photos</h2><button id="close-photo" type="button" aria-label="Close photos">Close ✕</button></header><img id="large-photo" alt=""><div class="photo-navigation"><button id="previous-photo" type="button" aria-label="Previous photo">← Previous</button><span id="photo-position" aria-live="polite"></span><button id="next-photo" type="button" aria-label="Next photo">Next →</button></div><p class="scope-note">Advertiser-supplied photos. Open the original listing for the complete photo set.</p></dialog>
<div id="feedback" role="status" aria-live="polite"></div><script>{script}</script></body></html>'''
