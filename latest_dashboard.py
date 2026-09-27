"""September search view, using the existing dashboard's server and styles."""
import html
import json
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
    sources = {"zillow": "Zillow", "supost": "SUpost", "furnishedfinder": "Furnished Finder", "spareroom": "SpareRoom"}
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
        contacted = item["id"] in contacted_ids
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
  <ul class="facts">{fact_html}</ul>
  <p class="confirmation"><strong>Confirm:</strong> {esc(item['confirm'])}</p>
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
  <button class="copy-inquiry reach-toggle" type="button">Copy inquiry</button>
  <button class="mark-contact reach-toggle{' on' if contacted else ''}" type="button" aria-pressed="{str(contacted).lower()}">{'✓ Reached out' if contacted else 'Mark as reached out'}</button>
  <p class="contact-help">{esc(contact)}</p>
 </aside>
</article>''')
    script = (ROOT / "latest_dashboard.js").read_text()
    count = len(data["listings"])
    start_count = sum(item["group"] in ("monthly", "one_month", "confirm") for item in data["listings"])
    monthly_count = sum(item["group"] in ("monthly", "one_month") for item in data["listings"])
    lowest = min(item["rent"] for item in data["listings"] if item["group"] in ("monthly", "one_month", "confirm"))
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
.listing-details{{font-size:12px;margin-top:12px}}.listing-details summary{{color:#2563eb;cursor:pointer;font-weight:600}}
dl{{display:grid;grid-template-columns:120px 1fr;gap:6px 12px;margin-top:10px}}dt{{color:#64748b}}dd{{margin:0;color:#334155}}
.footer-note{{font-size:12px;color:#64748b;line-height:1.7;margin-top:22px}}
#feedback{{position:fixed;bottom:20px;left:50%;transform:translateX(-50%);padding:10px 18px;background:#0f172a;color:white;border-radius:8px;z-index:100;font-size:13px;max-width:90vw}}
#feedback:empty{{display:none}}[hidden]{{display:none!important}}button:focus-visible,select:focus-visible,a:focus-visible,summary:focus-visible{{outline:2px solid #2563eb;outline-offset:3px}}
@media(min-width:721px) and (max-width:1000px){{.latest-card{{grid-template-columns:180px minmax(0,1fr)}}.latest-card .contact-box{{grid-column:2}}}}
@media(max-width:720px){{body{{padding:18px 12px}}.channels{{grid-template-columns:1fr}}.masthead{{flex-direction:column;gap:6px}}h1{{font-size:25px}}.archive-link{{padding:0}}.latest-card{{grid-template-columns:1fr;padding:16px;gap:14px}}.latest-card .card-head{{align-items:flex-start}}.latest-card .price{{text-align:left}}.latest-card .contact-box{{width:100%}}.list-heading{{align-items:flex-start}}.stat-num{{font-size:24px}}dl{{grid-template-columns:100px 1fr}}.photo-main img{{height:230px}}.photo-thumb img{{height:55px}}.no-photos{{display:flex;align-items:center;gap:10px}}.no-photos img{{width:90px;height:81px;margin:0}}}}
</style></head><body>
<header class="masthead"><div><p class="eyebrow">Your housing search · Fall 2026</p><h1>Bay Area monthly stays</h1>
<p class="search-summary">From <strong>{data['move_in']}</strong> · preferably below <strong>$50/day</strong> · private bathroom + parking</p>
<p class="scope-note">Residential areas near shops. Private rooms in shared homes included. Ranked to work for <strong>both</strong> San Francisco and Stanford — the headline figure is the worse of the two one-way drives.</p></div>
</header>
<div class="status-panel"><div class="status-row">
<div class="stat"><div class="stat-num">{count}</div><div class="stat-lbl">Researched leads</div></div>
<div class="stat"><div class="stat-num ok">{monthly_count}</div><div class="stat-lbl">Leads advertising monthly terms<br>or a one-month minimum</div></div>
<div class="stat"><div class="stat-num">${lowest:,}</div><div class="stat-lbl">Lowest advertised monthly cost<br>lease and area need checking</div></div>
<div class="stat"><div class="stat-num warn">0</div><div class="stat-lbl">September 29 dates<br>confirmed by a host</div></div>
</div></div>
<p class="research-note"><strong>September 27 — the month-to-month rule changed the answer.</strong> Searching SpareRoom, which was not covered before, found what the other platforms did not: a <strong>Millbrae room at $1,500 including utilities with a private bathroom, parking and explicit month-to-month terms, available now</strong> — no minimum and no maximum term. Millbrae is {distances['cities']['Millbrae']['balanced_miles']:.0f} miles worst-case and the one stop served by both BART and Caltrain. It is unfurnished, which is the trade for a short stay. A <strong>San Mateo townhouse master suite at $1,600</strong> has no minimum term either, plus a garage and furniture. Both beat every Solano card on location by 50 miles and on lease terms outright. <em>Earlier framing, still true:</em> <strong>El Sobrante at $1,475</strong> is still the only lead meeting every requirement — en-suite bathroom, parking on site, one-month minimum, calendar updated September 10, 2026, replies within the hour — but at {distances['cities']['El Sobrante']['stanford_miles']:.0f} miles from campus it is a San Francisco answer, not a balanced one. The best-placed card is now <strong>Hayward at $1,250</strong>: {distances['cities']['Hayward']['driving_miles']:.0f} miles to SF and {distances['cities']['Hayward']['stanford_miles']:.0f} to Stanford, the only lead under 30 miles from both — its one obstacle is a 60-day minimum. <strong>The Solano rooms are gone.</strong> A 1.5-hour ceiling now applies to the worse of the two drives, and Fairfield ({distances['cities']['Fairfield']['stanford_minutes']} min to campus) and Vacaville ({distances['cities']['Vacaville']['stanford_minutes']} min) both break it, so all four cards were withdrawn. <strong>South San Francisco, searched on September 27, is where the cheap band actually lives</strong> — and it is almost entirely taken. A Sunshine Gardens room at <strong>$1,050</strong> has a private bathroom, parking, furniture, utilities included, a $500 deposit and no minimum or maximum term, and a Daly City suite at <strong>$1,100</strong> has a private bathroom and an assigned parking space; both are lease-pending and their advertisers are not accepting applications. They are on the board as watch items because rooms in this band turn over fast. <strong>Research: {data['researched']}.</strong> These are advertised leads; availability has not been confirmed with hosts.</p>
<section class="geography" id="north-bay"><h2>Two anchors: San Francisco and Stanford</h2>
<p>Every card now carries both drives, and the default ranking uses the <strong>worse</strong> of the two, so a low number means somewhere that is not bad to either. Nothing is genuinely close to both: the two anchors are about {distances['cities']['Palo Alto']['driving_miles']:.0f} miles apart, so a place near campus is far from the city and the reverse. The September 27 pass measured the whole Peninsula, and it takes the top of the table: <strong>Burlingame is the best-balanced town in the region at {distances['cities']['Burlingame']['balanced_miles']:.0f} miles worst-case</strong> ({distances['cities']['Burlingame']['driving_miles']:.0f} to SF, {distances['cities']['Burlingame']['stanford_miles']:.0f} to campus), then San Mateo at {distances['cities']['San Mateo']['balanced_miles']:.0f} and Millbrae at {distances['cities']['Millbrae']['balanced_miles']:.0f} — Millbrae being the one stop served by both BART and Caltrain. Nine of the ten best-balanced towns are south of SF. <strong>Anything whose worse drive exceeds 1.5 hours is now excluded outright</strong>, which removed the four Solano cards and leaves Novato the furthest thing still standing at {distances['cities']['Novato']['stanford_minutes']} minutes to campus — inside the ceiling on an open road, but the first card to fail it in traffic. Among the current cards <strong>Hayward is the only one under 30 miles from both</strong> ({distances['cities']['Hayward']['driving_miles']:.0f} to SF, {distances['cities']['Hayward']['stanford_miles']:.0f} to campus). The two Palo Alto rooms sit {distances['cities']['Palo Alto']['stanford_miles']:.1f} miles from campus but {distances['cities']['Palo Alto']['driving_miles']:.0f} from SF.</p>
<p>North of SF: the Novato $1,200 Furnished Finder room advertises a one-month minimum, private bathroom and onsite parking. Its December 2025 calendar is old, so it is hidden by default. No current complete match in Marin or Sonoma was verified in this search.</p>
<button id="north" class="fb-preset" type="button">North of SF + unverified backups</button>
<p class="scope-note">Distances use city centers → SF Ferry Building, not exact property addresses. They are approximate road distances, not live commute times. “Drive to SF” opens a route to check traffic. <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">© OpenStreetMap contributors</a> · <a href="https://project-osrm.org/" target="_blank" rel="noopener noreferrer">OSRM routing</a>.</p></section>
<section class="channels" aria-label="Search coverage">
<div class="channel"><h2>Zillow</h2><p>No current Zillow lead. The Vallejo room carried here on September 25 was withdrawn the same day: its listing page now resolves to a <strong>sold single-family house</strong>, not a room for rent, so it is not a rental offer.</p></div>
<div class="channel"><h2>SUpost</h2><p>Two private-bathroom backups at $1,430+ and $1,500. Both start after September 29; parking and monthly flexibility need confirmation.</p><button type="button" data-source-preset="supost">Show SUpost + later starts →</button></div>
<div class="channel"><h2>SpareRoom</h2><p>The best-performing source in this search. Three contactable Peninsula rooms with private baths, two with <strong>no minimum term at all</strong> — Millbrae at $1,500 all-in, the other two at $1,600. The September 27 South San Francisco sweep added the two cheapest private-bath rooms found anywhere, at <strong>$1,050 and $1,100</strong>, both lease-pending and held as watch items.</p><button type="button" data-source-preset="spareroom">Show SpareRoom leads →</button></div>
<div class="channel"><h2>Furnished Finder</h2><p>{ff_monthly} leads with a one-month minimum, plus {ff_older} older-calendar backups hidden by default. Check cleaning fees and whether monthly extensions are possible.</p><button type="button" data-source-preset="furnishedfinder">Show Furnished Finder leads →</button></div>
</section>
<div class="filterbar"><div class="fb-row">
<input id="search" class="fb-search" type="search" aria-label="Search listings" placeholder="Search city, neighborhood or details…">
<button id="best" class="fb-preset" type="button">One-month options</button><button id="reset" class="fb-reset" type="button">Reset</button>
<span class="fb-count" aria-live="polite"><b id="shown">{start_count}</b> of {count} showing</span></div>
<div class="filter-controls">
<label>Region<select id="region"><option value="all">Entire Bay Area</option>{region_options}</select></label>
<label>Distance to SF<select id="maxdistance"><option value="all">Any distance</option><option value="25">Within 25 driving miles</option><option value="35">Within 35 driving miles</option><option value="50">Within 50 driving miles</option></select></label>
<label>Monthly cost<select id="budget"><option value="1500">Up to $1,500</option><option value="1300">Up to $1,300</option><option value="1200">Up to $1,200</option><option value="1000">Up to $1,000</option></select></label>
<label>Source<select id="source"><option value="all">All sources</option>{source_options}</select></label>
<label>Lease / timing<select id="term"><option value="start">September 29 leads · confirm dates</option><option value="monthly">One-month / monthly advertised</option><option value="confirm">Lease needs confirmation</option><option value="active">Shortlist + later-start backups</option><option value="later">Later-start backups</option><option value="waitlist">Lease pending · cheapest band, watch these</option><option value="review">Include older-calendar backups</option></select></label>
<label>Parking<select id="parking"><option value="all">All parking types</option><option value="offstreet">Driveway / off-street advertised</option><option value="street">Street only</option></select></label>
<label>Furnishing<select id="furnished"><option value="all">Any</option><option value="yes">Furnished</option><option value="no">Unfurnished</option></select></label>
<label>Sort<select id="sort"><option value="balanced">Balanced · best for both</option><option value="distance">Closest to San Francisco</option><option value="stanford">Closest to Stanford</option><option value="recommended">Recommended order</option><option value="price">Lowest price first</option></select></label>
</div><p class="scope-note">Price filters use known recurring monthly charges. “+” means extra charges are unconfirmed. One-time fees and deposits appear under each listing’s details. A one-month minimum does not guarantee month-to-month renewal.</p></div>
<main><div class="list-heading"><h2>The latest shortlist</h2><p>All bathrooms advertised as private</p></div>
<div id="listings">{''.join(cards)}</div>
<p id="empty" class="banner" hidden>No leads match these filters. Try a wider distance or include later starts and older-calendar backups.</p>
<details class="disc"><summary>Inquiry to send to the host</summary><div class="disc-body"><p id="inquiry">Hi, I’m looking for housing starting September 29, 2026, initially for one month with the option to extend monthly. Is your room available for those dates, and would that arrangement work? I need a bathroom exclusively for my use and parking for one car. Could you confirm the total monthly cost including utilities, internet and parking, all upfront charges, whether the room is furnished, and the notice required to move out? Please also share the nearest cross streets and whether an in-person or video tour is available. Thank you.</p></div></details>
<details class="disc"><summary>Other sources checked and why some offers were excluded</summary><div class="disc-body">
<p><strong>Zillow / HotPads:</strong> <a href="https://www.zillow.com/homedetails/444-Stratford-Park-Ct-San-Jose-CA-95136/19704661_zpid/" target="_blank" rel="noopener noreferrer">San Jose’s $1,500 monthly room</a> and <a href="https://hotpads.com/dublin-ca-94568-1m804k4/7709/pad-for-sublet" target="_blank" rel="noopener noreferrer">Dublin’s $1,500 room</a> are off-market. The <a href="https://www.zillow.com/homedetails/300-Shasta-St-Vallejo-CA-94590/15658964_zpid/" target="_blank" rel="noopener noreferrer">Vallejo lead added earlier on September 25</a> was removed the same day: reopening it resolves to 300 Shasta Street, a closed sale of a three-bedroom house, so the $1,250 room it appeared to advertise is not an available rental. Search snippets can still show old rental offers; none of these is included as an available lead.</p>
<p><strong>Your SUpost feed:</strong> <a href="https://supost.com/post/furnished-room-long-term-in-menlow-park-willow-130109514" target="_blank" rel="noopener noreferrer">Menlo Park Willow</a> is $1,350 + $150 utilities and shares a bathroom. The other lower-price Palo Alto offer also has a shared bathroom. Housing-wanted posts are requests from renters, so they are excluded from the shortlist.</p>
<p><strong>Peninsula sweep, September 27 — nothing at budget south of SF.</strong> Every private-bathroom option found between Daly City and Menlo Park sits well above $1,500: <a href="https://supost.com/post/2-347-2br-1282ft2-private-bed-private-bathroom-available-for-130109607" target="_blank" rel="noopener noreferrer">Foster City waterfront townhouse</a> at $2,367 + utilities (private bed and bath, available exactly September 29 — the best date match seen anywhere, but 58% over budget and parking is not mentioned), <a href="https://supost.com/post/private-bed-bath-in-redwood-city-2b-2b-move-in-asap-130109275" target="_blank" rel="noopener noreferrer">Redwood City 2B/2B</a> at $1,847.50 + utilities (private bath, parking and laundry included, move-in ASAP — but a 12-month lease with a screening application), and <a href="https://supost.com/post/newly-renovated-studio-in-city-of-south-francisco-9-15-130104846" target="_blank" rel="noopener noreferrer">a renovated South San Francisco studio</a> at $1,950 + $100 utilities, rising to $2,050 for a short lease. The options that do meet the budget share a bathroom: <a href="https://supost.com/post/looking-for-a-female-roommate-foster-city-family-house-130106068" target="_blank" rel="noopener noreferrer">Foster City at $1,390</a> shares with one roommate and runs to September 2027, and <a href="https://supost.com/post/room-in-2b1b-furnished-place-in-redwood-city-long-term-130105668" target="_blank" rel="noopener noreferrer">Redwood City at $1,500</a> is a two-bedroom with one bathroom. One lead is still unresolved: <a href="https://supost.com/post/bright-garden-cottage-1bed-in-quiet-burlingame-neighborhood-130089573" target="_blank" rel="noopener noreferrer">a Burlingame garden cottage</a> — a whole two-level home with two full bathrooms, walking distance to Broadway Caltrain and five minutes from the Millbrae transit hub, in the best-balanced town on the board. Its price lives on a Furnished Finder page that is rate-limiting this search, so it has not been priced.</p>
<p><strong>East Bay sweep, September 25:</strong> searching Furnished Finder for a September 29 start across Oakland, Berkeley, Alameda, Richmond, Hayward, San Leandro and San Francisco surfaced four cards added here and ruled out the rest: <a href="https://www.furnishedfinder.com/property/1026292_1" target="_blank" rel="noopener noreferrer">San Leandro at $1,500</a> needs a 12-month minimum, <a href="https://www.furnishedfinder.com/property/452245_1" target="_blank" rel="noopener noreferrer">San Leandro at $1,600</a> and <a href="https://www.furnishedfinder.com/property/245533_1" target="_blank" rel="noopener noreferrer">Oakland at $1,600</a> are over budget, and <a href="https://www.furnishedfinder.com/property/917797_1" target="_blank" rel="noopener noreferrer">San Francisco at $1,800</a> is well over it. Cheaper East Bay rooms in the same results share a bathroom.</p>
<p><strong>Your SUpost rooms feed, September 25:</strong> the lower-priced Palo Alto rooms all share a bathroom — <a href="https://supost.com/post/furnished-bedroom-for-rent-in-palo-alto-available-september-130109079" target="_blank" rel="noopener noreferrer">Loma Verde at $1,400 + $100</a> (two baths between four bedrooms), <a href="https://supost.com/post/sunny-furnished-bedroom-in-clean-quiet-attractive-palo-alto-130108681" target="_blank" rel="noopener noreferrer">South Palo Alto at $1,400</a> (hall bath shared with two renters, six months preferred) and <a href="https://supost.com/post/cozy-furnished-room-in-college-terrace-2-blocks-from-stanfor-130087527" target="_blank" rel="noopener noreferrer">College Terrace at $850 + $50</a> (shared bath, windowless room, October 1). <a href="https://supost.com/post/beautiful-master-bedroom-in-the-heart-of-stanford-130109325" target="_blank" rel="noopener noreferrer">A room in the heart of campus</a> is $2,100–$2,500 with a semi-shared bath, and the <a href="https://supost.com/post/clean-updated-furnished-hardwood-floors-studio-redwood-city-130107850" target="_blank" rel="noopener noreferrer">Redwood City studio</a> starts November 1. One post worth a message has no price at all: a <a href="https://supost.com/post/1-1-1-1-130107029" target="_blank" rel="noopener noreferrer">furnished one-bedroom one-bath unit a 5–8 minute walk from Stanford hospital</a>, Stanford affiliates only, rent described as negotiable by move-in date — it is not on the board because no price is published.</p>
<p><strong>SpareRoom / Roomies:</strong> the reviewed Pacifica and San Rafael SpareRoom ads are not accepting applications. Roomies terms could not be verified. <strong>Rednote / 小红书:</strong> public search attempted; no housing posts verified.</p>
<p><strong>Freshness:</strong> SUpost research used public listing pages. Furnished Finder cards show calendar update dates; older 2025 calendars are hidden by default. Select “Include older-calendar backups” to review them.</p></div></details>
</main><footer class="footer-note">Daily equivalents use a 30-day month; refundable deposits are additional move-in cash. Neighborhood descriptions are from advertisers and are not independent safety assessments. Source pages may contain cached details. Reached-out marks are saved in this browser and do not send messages.</footer>
<dialog id="photo-dialog" class="photo-dialog" aria-labelledby="photo-title"><header><h2 id="photo-title">Listing photos</h2><button id="close-photo" type="button" aria-label="Close photos">Close ✕</button></header><img id="large-photo" alt=""><div class="photo-navigation"><button id="previous-photo" type="button" aria-label="Previous photo">← Previous</button><span id="photo-position" aria-live="polite"></span><button id="next-photo" type="button" aria-label="Next photo">Next →</button></div><p class="scope-note">Advertiser-supplied photos. Open the original listing for the complete photo set.</p></dialog>
<div id="feedback" role="status" aria-live="polite"></div><script>{script}</script></body></html>'''
