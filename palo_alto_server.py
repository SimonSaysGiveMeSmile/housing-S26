#!/usr/bin/env python3
"""Palo Alto / Stanford summer housing dashboard. Default port 5555.
Card layout: each listing shows contact method + location map image.
Updated to exclude East Palo Alto, focus on good neighborhoods only."""
import http.server, socketserver, os, sys, html, mimetypes, json
from urllib.parse import urlparse, quote
from datetime import datetime

ROOT = "/Users/test/Desktop/housing-S26"
PORT = 5555
MY_EMAIL = "tianjiahe11@gmail.com"  # Email used for contacting landlords

# Load contact tracking data.
# IMPORTANT: "contacted" means a message was actually SENT — sourced from
# watch_state["sent"] and/or contact_history.json. It is NOT seen_ids
# (seen_ids only means the scraper saw the listing, not that we reached out).
try:
    with open(os.path.join(ROOT, "watch_state.json")) as f:
        watch_state = json.load(f)
        sent_log = watch_state.get("sent", {}) or {}
except:
    sent_log = {}

# Load contact history (real confirmed sends only)
try:
    with open(os.path.join(ROOT, "contact_history.json")) as f:
        contact_history = {k: v for k, v in json.load(f).items() if not k.startswith("_")}
except:
    contact_history = {}

# Manual "I reached out" marks set by you on the webpage (separate from auto
# sends, but equally real — you attest to them). Persisted here.
MANUAL_FILE = os.path.join(ROOT, "manual_contacts.json")

def load_manual():
    try:
        with open(MANUAL_FILE) as f:
            return set(json.load(f))
    except Exception:
        return set()

def save_manual(ids):
    with open(MANUAL_FILE, "w") as f:
        json.dump(sorted(ids), f, indent=2)

def toggle_manual(listing_id):
    """Flip a listing's manual-contacted mark; return True if now contacted."""
    ids = load_manual()
    if listing_id in ids:
        ids.discard(listing_id); now_on = False
    else:
        ids.add(listing_id); now_on = True
    save_manual(ids)
    return now_on

# A listing counts as contacted if it has a real send record OR you marked it.
# (Recomputed per request inside render_body so toggles show immediately.)
contacted_ids = set(sent_log.keys()) | set(contact_history.keys()) | load_manual()

# Load the pending outreach queue (matches awaiting send — NOT yet contacted).
try:
    with open(os.path.join(ROOT, "send_queue.json")) as f:
        queued_ids = {item["id"] for item in json.load(f) if "id" in item}
except:
    queued_ids = set()

def time_elapsed(timestamp_str):
    """Calculate time elapsed from timestamp"""
    try:
        contact_time = datetime.fromisoformat(timestamp_str)
        now = datetime.now()
        delta = now - contact_time

        if delta.days > 0:
            return f"{delta.days}d ago"
        hours = delta.seconds // 3600
        if hours > 0:
            return f"{hours}h ago"
        minutes = (delta.seconds % 3600) // 60
        return f"{minutes}m ago"
    except:
        return "recently"

CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:system-ui,-apple-system,sans-serif;max-width:1100px;margin:0 auto;padding:20px;color:#1a1a1a;line-height:1.45;background:#fff;font-size:14px}
a{color:#2563eb;text-decoration:none}
a:hover{text-decoration:underline}
.masthead{margin-bottom:14px}
.kicker{display:none}
h1{font-size:24px;font-weight:700;color:#111;margin-bottom:4px}
h1 em{font-style:normal;color:#111}
.sub{font-size:13px;color:#666;line-height:1.5}
.banner{background:#f7f7f8;border-left:3px solid #2563eb;padding:10px 14px;margin:12px 0;font-size:13px;line-height:1.5;color:#444;border-radius:4px}
.banner strong{color:#111}
.banner.cl{border-left-color:#d97706;background:#fffbeb}
h2{font-size:17px;font-weight:700;color:#111;margin:28px 0 8px;padding-bottom:6px;border-bottom:2px solid #111}
h3.cat{font-size:14px;font-weight:700;color:#333;margin:18px 0 8px;padding:5px 10px;background:#f3f4f6;border-radius:5px}
.status-panel{border:1px solid #e2e2e2;border-radius:8px;margin:14px 0;background:#fff}
.status-row{display:flex}
.stat{flex:1;text-align:center;padding:14px 8px;border-right:1px solid #eee}
.stat:last-child{border-right:none}
.stat-num{font-size:28px;font-weight:700;color:#111;line-height:1}
.stat-num.ok{color:#15803d}.stat-num.warn{color:#b45309}.stat-num.dead-num{color:#b91c1c}.stat-num.replied-num{color:#7c3aed}
.stat-lbl{font-size:10px;color:#888;margin-top:6px;line-height:1.3;text-transform:uppercase;letter-spacing:.03em}
.status-detail{font-size:12.5px;color:#555;line-height:1.6;padding:10px 14px;border-top:1px solid #eee}
.status-detail strong{color:#111}
.card{position:relative;display:grid;grid-template-columns:180px 1fr 240px;gap:14px;background:#fff;border:1px solid #e2e2e2;border-radius:8px;padding:14px;margin:10px 0;height:190px;overflow:hidden;transition:box-shadow .15s}
.card:hover{box-shadow:0 2px 8px rgba(0,0,0,.08)}
.card.noimg{grid-template-columns:1fr 240px}
.card.top{border-color:#15803d}
.card.contacted{border-left:4px solid #15803d}
.card.queued{border-left:4px solid #d97706}
.card.replied{border-left:4px solid #7c3aed}
.card.dead{opacity:.55}
.card.dead .card-title{text-decoration:line-through}
.card.dead .card-images{filter:grayscale(1)}
.card.offcriteria{border-style:dashed}
.card.expanded{height:auto;max-height:640px;overflow-y:auto}
.contact-badge{position:absolute;top:0;right:0;background:#15803d;color:#fff;padding:4px 10px;font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:.04em;border-bottom-left-radius:6px}
.contact-badge.queued{background:#d97706}
.contact-badge.dead{background:#b91c1c}
.contact-badge.replied{background:#7c3aed}
.card-images{width:180px;height:162px;display:flex;flex-direction:column;gap:3px;overflow:hidden}
.card-images img{width:100%;height:100%;object-fit:cover;border-radius:4px}
.card-images.multi{display:grid;grid-template-columns:1fr 1fr;grid-template-rows:1fr 1fr;gap:3px}
.card-images.multi img:first-child{grid-column:1/3;grid-row:1}
.card-content{display:flex;flex-direction:column;min-width:0;overflow:hidden}
.card-head{display:flex;justify-content:space-between;align-items:baseline;gap:10px;margin-bottom:4px}
.card-title{font-size:16px;font-weight:700;line-height:1.2;color:#111}
.price{font-size:16px;font-weight:700;color:#15803d;white-space:nowrap}
.area{font-size:12px;color:#777;margin-bottom:6px}
.status{display:inline-block;font-size:11px;font-weight:600;padding:2px 8px;border-radius:4px;margin-bottom:6px}
.status.go{background:#dcfce7;color:#15803d}.status.check{background:#fef3c7;color:#b45309}.status.warn{background:#fee2e2;color:#b91c1c}
ul.facts{list-style:disc;padding-left:18px;font-size:12.5px;color:#444;line-height:1.5;max-height:66px;overflow:hidden}
.card.expanded ul.facts{max-height:none}
ul.facts li{margin:2px 0}
.expand-toggle{background:none;border:none;color:#2563eb;font-size:12px;cursor:pointer;padding:6px 0 0;margin-top:auto;text-align:left}
.expand-toggle:hover{text-decoration:underline}
.reply-note{font-size:12.5px;color:#6d28d9;background:#f5f3ff;border-left:3px solid #7c3aed;padding:6px 9px;margin-bottom:6px;line-height:1.4;border-radius:3px}
.offcriteria-note{font-size:12px;color:#b45309;background:#fffbeb;border-left:3px solid #d97706;padding:6px 9px;margin-bottom:6px;line-height:1.4;border-radius:3px}
.contact-box{border:1px solid #e2e2e2;background:#fafafa;border-radius:6px;padding:10px;display:flex;flex-direction:column;gap:5px;height:162px;overflow:hidden}
.card.expanded .contact-box{height:auto;overflow:visible}
.contact-title{font-size:10px;font-weight:600;letter-spacing:.05em;text-transform:uppercase;color:#999;padding-bottom:4px;border-bottom:1px solid #eee}
.contact-item{font-size:12px;display:flex;align-items:center;gap:6px;padding:2px 0;color:#555}
.contact-item svg{width:13px;height:13px;flex-shrink:0;color:#999}
.contact-item a{word-break:break-all}
.contact-item.my-email{background:#eff6ff;border:1px solid #bfdbfe;border-radius:4px;padding:5px 8px;margin-top:2px;color:#1e40af}
.contact-note{display:none;font-size:11px;color:#888;margin-top:3px;line-height:1.4}
.card.expanded .contact-note{display:block}
.btn-group{display:flex;gap:6px;margin-top:4px}
.btn{display:inline-block;background:#2563eb;color:#fff!important;padding:8px 12px;border-radius:5px;font-weight:600;font-size:12px;text-align:center;flex:1}
.btn:hover{background:#1d4ed8;text-decoration:none}
.btn.secondary{background:#6b7280}
.reach-toggle{margin-top:4px;width:100%;padding:8px;border:1px solid #2563eb;background:#fff;color:#2563eb;border-radius:5px;font-size:12px;font-weight:600;cursor:pointer}
.reach-toggle:hover{background:#eff6ff}
.reach-toggle.on{background:#15803d;color:#fff;border-color:#15803d}
.reach-toggle:disabled{opacity:.5;cursor:wait}
.contact-history{margin-top:8px;padding-top:8px;border-top:1px solid #eee;display:none}
.card.expanded .contact-history{display:block}
.contact-history-title{font-size:10px;font-weight:600;letter-spacing:.04em;text-transform:uppercase;color:#999;margin-bottom:6px}
.contact-entry{background:#fafafa;border:1px solid #eee;border-radius:5px;padding:8px;margin-bottom:6px;font-size:12px}
.contact-entry-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:4px}
.contact-channel{font-size:11px;font-weight:600;color:#2563eb}
.contact-time{color:#999;font-size:10px}
.contact-via{color:#888;font-size:10px;margin-bottom:4px}
.contact-message{color:#444;line-height:1.5;font-style:italic;padding:6px 8px;background:#fff;border-left:2px solid #ddd;border-radius:3px}
table{border-collapse:collapse;width:100%;margin:10px 0;font-size:13px}
th,td{border:1px solid #e2e2e2;padding:7px 10px;text-align:left;vertical-align:top}
th{background:#f3f4f6;color:#111;font-weight:600;font-size:12px}
tr:nth-child(even) td{background:#fafafa}
@media (max-width:720px){body{padding:12px}.card,.card.noimg{grid-template-columns:1fr;height:auto}.card-images{width:100%;height:160px}.status-row{flex-wrap:wrap}.stat{flex:1 0 50%;border-bottom:1px solid #eee}}
@media print{.card{break-inside:avoid;height:auto!important}h2{break-after:avoid}}
"""

# ---- listing data ----------------------------------------------------------
NON_CL = [
 {"top":True,"title":"Stanford R&DE — Official Summer Housing","price":"varies","status":("go","Open — apply online"),
  "area":"On campus, Stanford","facts":["Most reliable June-1 option, right next to campus.",
          "Ask specifically for a studio / dedicated unit (not a shared room).","Apply online with your admit/role status."],
  "clabel":"Apply / info (R&DE Summer Housing)",
  "curl":"https://rde.stanford.edu/conferences/summer-intern-housing",
  "email":"summerhousing@stanford.edu",
  "cnote":"No phone listed — online application. Request a self-contained unit; email the housing office with your admit status.",
  "src":"Stanford R&DE"},
]

# SUBLEASE — avoids applications
SUBLETS = [
 {"top":True,"title":"One Bedroom Flat (whole unit) — SUBLEASE","price":"$1,890/mo","src":"Craigslist /sub · private party",
  "area":"Palo Alto (453 sqft)","status":("go","SUBLEASE · no application mentioned"),
  "imgs":["flat_1890_1.jpg","flat_1890_2.jpg","flat_1890_3.jpg","flat_1890_4.jpg"],
  "facts":["Self-contained 1BR: your OWN kitchen with full-sized appliances + your OWN tiled bath.",
           "No housemates — a complete private flat, not a room in a shared house.",
           "SUBLEASE from private individual — NO credit check or application process mentioned.",
           "Wood floors, high ceilings, exposed brick, off-street parking, laundry in building."],
  "clabel":"View listing",
  "curl":"https://sfbay.craigslist.org/pen/sub/d/palo-alto-one-bedroom-flat-for-rent/7936614381.html",
  "cnote":"THE sublease option to skip applications. Confirm: (1) June 1 OK, (2) utilities included, (3) lease length."},
]

# Regular rentals — likely require applications/credit checks
REGULAR_RENTALS = [
 {"top":False,"title":"Cottage, private corner of property","price":"$1,800/mo","src":"Craigslist /apa · likely needs application",
  "area":"Menlo Park (~10 min drive to Stanford)","status":("check","Regular rental · application likely"),
  "imgs":["cottage_1800.jpg"],
  "facts":["Cozy cottage in private corner of property — separate structure, not shared.",
           "Posted in /apa (not /sub) — likely a regular rental requiring application.",
           "No move-in date posted — confirm June 1 works."],
  "clabel":"View listing",
  "curl":"https://sfbay.craigslist.org/pen/apa/d/menlo-park-lovely-cozy-little-cottage/7936493194.html",
  "cnote":"Whole cottage in Menlo Park. Likely needs application — confirm if negotiable."},

 {"top":False,"title":"1BR unit in redwood forest with deck","price":"$1,750/mo","src":"Craigslist /apa · likely needs application",
  "area":"Woodside/Kings Mountain (~15 min to Stanford)","status":("check","Regular rental · 1-year lease required"),
  "offcriteria":"Outside your criteria: July 1 start (you need June 1) + one-year lease (not a summer option).",
  "facts":["Whole lower unit (540 sqft): 1BR/1BA, full kitchen, washer/dryer in unit.",
           "Private entrance, wood floors, large covered redwood deck with mountain views.",
           "In redwoods with hiking trails nearby, off-street parking, AC included.",
           "Utilities: $150/mo flat rate (gas, electric, water, garbage) + internet separate."],
  "clabel":"View listing",
  "curl":"https://sfbay.craigslist.org/pen/apa/d/redwood-city-kings-mountain-redwood/7937976892.html",
  "cnote":"Beautiful forest setting, but 1-year lease + July 1 start. Ask if shorter term possible."},

 {"top":False,"title":"In-law unit, 2BD/2BA lower level","price":"$1,700/mo","src":"Craigslist /apa · likely needs application",
  "area":"Redwood City/Atherton area (~15 min drive to Stanford)","status":("check","Regular rental · application likely"),
  "dead":True,
  "imgs":["inlaw_1700_1.jpg","inlaw_1700_2.jpg","inlaw_1700_3.jpg","inlaw_1700_4.jpg"],
  "facts":["Lower-level in-law unit: 2 bedrooms, 2 full baths — your own space.",
           "Posted in /apa (not /sub) — likely a regular rental requiring application.",
           "No move-in date posted — confirm June 1 works."],
  "clabel":"View listing",
  "curl":"https://sfbay.craigslist.org/pen/apa/d/redwood-city-bd-ba-lower-level-in-law/7938345199.html",
  "cnote":"2BD/2BA in-law unit in Redwood City. Likely needs application."},

 {"top":False,"title":"Studio with EV charging, roof deck","price":"$1,414/mo","src":"Craigslist /apa · likely management company",
  "area":"Redwood City, 855 Veterans Blvd (~15 min to Stanford)","status":("check","Regular rental · application required"),
  "facts":["Whole 674 sqft studio with private kitchen and bathroom.",
           "In-unit washer/dryer, dishwasher, stainless appliances, walk-in closet, central AC.",
           "Building: fitness center, roof deck, dog park, EV charging, bike storage, attached garage.",
           "Pets allowed: $500 deposit + $50/mo per pet."],
  "clabel":"View listing",
  "curl":"https://sfbay.craigslist.org/pen/apa/d/redwood-city-nest-thermostats-ev/7936533032.html",
  "cnote":"Modern amenities, good price for 674 sqft. Confirm utilities, security deposit, and June 1 availability."},

 {"top":False,"title":"Studio, 1207 Paloma Ave #1","price":"$1,895/mo","src":"Craigslist /apa · property management",
  "area":"Burlingame (~20 min to Stanford)","status":("check","Regular rental · application required"),
  "facts":["Whole studio (0BR/1BA) with private kitchen and full bath (shower over tub).",
           "First floor with lots of windows, black granite counters, full-size fridge.",
           "Covered parking (carport) + storage, laundry in building.",
           "Application fee: $40 per applicant 18+."],
  "clabel":"View listing",
  "curl":"https://sfbay.craigslist.org/pen/apa/d/burlingame-avr-realty-inc-presents-1207/7933895643.html",
  "cnote":"Clean studio near transit. Burlingame is 20 min from Stanford — confirm commute works for you."},

 {"top":False,"title":"Studio in-law unit, separate entrance","price":"$1,650/mo","src":"Craigslist /apa · private landlord",
  "area":"San Bruno (~25 min to Stanford)","status":("check","Regular rental · references required"),
  "dead":True,
  "offcriteria":"Outside your criteria: ~25 min from Stanford (over your 20-min limit).",
  "facts":["In-law studio unit with separate entrance (308 sqft).",
           "Updated floors, recessed lighting, walking distance to SFO shuttle.",
           "No smoking, street parking available, no on-site laundry.",
           "Landlord requires: occupation info, income, credit score, and personal bio."],
  "clabel":"View listing",
  "curl":"https://sfbay.craigslist.org/pen/apa/d/san-bruno-in-law-studio-unit-separate/7931983958.html",
  "cnote":"Affordable but farther from Stanford. ASK about kitchen before applying. Confirm June 1 availability."},

 {"top":False,"title":"Small backyard studio","price":"$1,495/mo","src":"Craigslist /apa · private landlord",
  "area":"San Mateo (~20 min to Stanford)","status":("check","Regular rental · restrictions apply"),
  "facts":["Newly remodeled studio — described as 'small backyard' unit.",
           "Laundry on site, off-street parking included.",
           "No smoking, no drugs, no pets, single occupancy only.",
           "Near El Camino Real, Hillsdale Shopping Center, and CalTrain."],
  "clabel":"View listing",
  "curl":"https://sfbay.craigslist.org/pen/apa/d/san-mateo-small-back-yard-studio-not/7935265977.html",
  "cnote":"Budget-friendly option. MUST verify it has private kitchen and bathroom before applying."},

 {"top":False,"title":"Newly remodeled studio","price":"$1,750/mo","src":"Craigslist /apa · private landlord",
  "area":"San Mateo (~20 min to Stanford)","status":("check","Regular rental · application likely"),
  "facts":["Described as 'newly remodeled studio' near CalTrain and shopping.",
           "Laundry on site, off-street parking included.",
           "No smoking, no drugs, no pets, single occupancy only."],
  "clabel":"View listing",
  "curl":"https://sfbay.craigslist.org/pen/apa/d/san-mateo-studio-in-san-mateo/7937147440.html",
  "cnote":"MUST verify private kitchen and bathroom before applying. Confirm June 1 availability."},

 {"top":False,"title":"Affordable studio, 605 Willow Rd","price":"$1,300/mo","src":"Craigslist /apa · formal application REQUIRED",
  "area":"Menlo Park (~10 min drive to Stanford)","status":("warn","Income-restricted · REQUIRES application"),
  "imgs":["studio_1300.jpg"],
  "facts":["Whole 450 sqft studio, partially furnished (bed, nightstand, table, chairs).",
           "INCOME-RESTRICTED (tax-credit): requires ~$38,982 MIN gross annual income + formal application.",
           "NOT a sublease — full application process, waitlist, $1,200 deposit required."],
  "clabel":"View listing",
  "curl":"https://sfbay.craigslist.org/pen/apa/d/menlo-park-open-house-605-willow-rd-am/7934591226.html",
  "cnote":"Cheapest, but mandatory formal application + income docs. Skip if avoiding applications. Phone shown on the listing page (click 'show contact info')."},
]

# Additional short-term sublets
SHORT_TERM = [
 {"top":False,"title":"1BR/1BA short-term (mid-June to mid-Aug)","price":"$1,800/mo","src":"Craigslist /sub · short-term",
  "area":"Portola Valley (~5 min to Stanford)","status":("check","Short-term · shared housing"),
  "offcriteria":"Outside your criteria: shared house with a housemate (you wanted dedicated units only); covers only mid-June to mid-Aug.",
  "facts":["~1000 sqft private room with private bathroom in shared house (one other person).",
           "Short-term only: mid-June to mid-August 2026, minimum 5-6 weeks.",
           "Access to patios, garden, on-site laundry, carport parking.",
           "This is NOT a whole unit — you share the house with one other person."],
  "clabel":"View listing",
  "curl":"https://sfbay.craigslist.org/pen/sub/d/portola-valley-short-term-br-with-1ba/7933971597.html",
  "cnote":"Great location but shared housing (has housemate). Only covers part of summer."},
]

# SUpost (Stanford-only marketplace) — extracted from the listing page on
# 2026-06-05. These are OFFERS only (the many "housing wanted" posts are
# omitted). SUpost is login-gated: I can't pull the poster's email, and there
# are no per-post links in the source, so "View listing" points to the SUpost
# housing page — search the title there while logged in with your @stanford.edu.
SUPOST = [
 # ---- NEWEST (Jun 8) — your latest outreach on top ----
 {"top":True,"title":"Room sublease — Kennedy (Jun 23–Sep 10)","mid":"su-kennedy-jun23-sep10","price":"$1,600/mo","src":"SUpost · Stanford-only",
  "area":"On campus, Stanford (Kennedy grad housing)","status":("go","CONTACTED Jun 8 · best date match"),
  "facts":["Room sublease in Kennedy graduate housing, June 23 – Sept 10 — covers nearly your whole summer.",
           "Under budget at $1,600, on campus.",
           "Best date coverage of this batch."],
  "clabel":"Find post →","curl":"https://supost.com/search/cat/3",
  "cnote":"You messaged this Jun 8 via SUpost (from ipo@stanford.edu). Sent: \"Hi! I'm Simon, coming from Cornell for the summer. Your place looks great and the location is good. Is it still available, and when would be a good time for a tour? I'm already in Palo Alto so it's flexible.\" Awaiting reply — best date match of the batch."},

 {"top":True,"title":"Summer sublet — Kennedy Commons grad housing","mid":"su-kennedy-commons-1570","price":"$1,570/mo","src":"SUpost · Stanford-only",
  "area":"On campus, Stanford (Kennedy Commons · 6 Comstock Circle, by EVGR)","status":("go","TEXTED Jun 8 · awaiting reply"),
  "offcriteria":"Stanford grad housing — poster says you must be a Stanford affiliate AND a graduate student or over 21. Confirm you qualify before counting on it.",
  "facts":["Room in a 2b/2b junior apartment — fully furnished, kitchen has all major appliances.",
           "Dates: June 15 – Aug 19. Under budget at $1,570.",
           "Poster: Bri — call/text 623-810-3457, or ba624@stanford.edu.",
           "Located next to EVGR on 6 Comstock Circle.",
           "Eligibility: must be Stanford affiliate + grad student or 21+ (Stanford sublicense rules)."],
  "clabel":"Find post →","curl":"https://supost.com/search/cat/3",
  "cnote":"You TEXTED Bri at 623-810-3457 on Jun 8 (also reachable at ba624@stanford.edu). $1,570, Jun 15–Aug 19, furnished room in a 2b/2b. Awaiting reply. Heads-up: grad-housing eligibility requires a Stanford affiliation + grad/21+ — confirm you qualify."},

 # ---- NEW Jun-start leads (Jun 8 paste) — you're in a hotel, June availability ----
 {"top":True,"title":"Stopgap: rooms in campus house (Jun 9–20)","mid":"su-campus-stopgap-jun9","price":"$1,200/mo","src":"SUpost · Stanford-only",
  "area":"Heart of Stanford campus","status":("go","IMMEDIATE bridge · get out of the hotel"),
  "offcriteria":"Only covers June 9–20 — a short bridge, not a full-summer place. Pair it with a July-start sublet.",
  "facts":["Rooms with bathroom in a house in the heart of campus, June 9 – 20.","$1,200. Available right now — fills your immediate hotel gap.","Bridge to a longer (July-start) sublet."],
  "clabel":"Find post →","curl":"https://supost.com/search/cat/3",
  "cnote":"IMMEDIATE bridge (Jun 9–20) to get you out of the hotel now. Pair with a July-start place. Not yet messaged."},

 {"top":True,"title":"Summer sublet — co-op close to campus","mid":"su-coop-summer","price":"$1,300/mo","src":"SUpost · Stanford-only",
  "area":"Near Stanford campus (co-op house)","status":("go","Cheap · summer · confirm June start"),
  "facts":["Room in a co-op house close to campus, summer sublet (has a photo on SUpost).","Under budget at $1,300 — one of the cheapest near campus.","Confirm the exact June start date and that it runs through your stay."],
  "clabel":"Find post →","curl":"https://supost.com/search/cat/3",
  "cnote":"NEW Jun 8 lead — cheap ($1,300) co-op room near campus, summer. Ask if it starts in June. Not yet messaged."},

 {"top":True,"title":"Room in creative community house (yard/pool/sauna)","mid":"su-community-house","price":"$1,100/mo","src":"SUpost · Stanford-only",
  "area":"Palo Alto area","status":("go","Cheapest · confirm June start"),
  "facts":["Room opening in a bright community house with a huge yard, pool, and sauna (photo on SUpost).","Cheapest option found at $1,100.","Dates not stated — confirm June availability."],
  "clabel":"Find post →","curl":"https://supost.com/search/cat/3",
  "cnote":"NEW Jun 8 lead — cheapest at $1,100, community house w/ pool+sauna. Ask if it starts in June. Not yet messaged."},

 {"top":False,"title":"Private room for rent — Mountain View ($1,425)","mid":"su-mv-room-1425","price":"$1,425/mo","src":"SUpost · Stanford-only",
  "area":"Mountain View (~15–20 min to Stanford)","status":("check","Private room · confirm June start"),
  "facts":["Private room for rent in Mountain View.","Under budget at $1,425.","Dates not stated — confirm June availability.","Farther out (~15–20 min to campus)."],
  "clabel":"Find post →","curl":"https://supost.com/search/cat/3",
  "cnote":"NEW Jun 8 lead — Mountain View private room, $1,425. Ask if it starts in June. Not yet messaged."},

 {"top":False,"title":"Private cottage + live-in assistant gig (Menlo Park)","mid":"su-menlo-livein-cottage","price":"$1,700/mo","src":"SUpost · Stanford-only",
  "area":"Menlo Park","status":("check","Whole cottage · comes with a 10-15 hr/wk job"),
  "offcriteria":"Comes with a commitment: live-in household assistant, 10-15 hrs/week (paid $25/hr). Only worth it if you want that on top of classes/research.",
  "facts":["Private cottage in Menlo Park for $1,700/mo — a WHOLE unit, under budget.","Tied to a live-in household-assistant role: 10-15 hrs/week at $25/hr (the pay roughly offsets the rent).","Sponsored post on SUpost. Confirm dates and exact duties.","Trade-off: extra time commitment alongside your summer work."],
  "clabel":"Find post →","curl":"https://supost.com/search/cat/3",
  "cnote":"NEW Jun 9 lead — whole private cottage $1,700 in Menlo Park, but you'd work 10-15 hrs/wk as a live-in assistant ($25/hr offsets rent). Good value if the hours fit your schedule."},

 # ---- WHOLE UNITS (studios / apartments) — best fit ----
 {"top":True,"title":"Fully Furnished EV Studio + Free Bike","mid":"su-ev-freebike","price":"$1,900/mo","src":"SUpost · Stanford-only",
  "area":"On campus, Stanford (Escondido Village)","status":("go","Whole studio · utilities incl · full summer"),
  "facts":["WHOLE studio on campus — your own unit, no housemates.",
           "Dates: June 9 – Sept 22 (covers the whole summer).",
           "Utilities INCLUDED; comes with a free bike.",
           "Under budget at $1,900. Contact via SUpost (Stanford login)."],
  "clabel":"Find post →","curl":"https://supost.com/search/cat/3",
  "cnote":"STRONG — whole studio, utilities incl, full summer, $1,900. Search 'Fully Furnished EV Studio Free Bike' on SUpost."},

 {"top":True,"title":"EVGR-B Private Studio sublet","mid":"su-evgrb-studio","price":"$1,600/mo","src":"SUpost · Stanford-only",
  "area":"On campus, Stanford (EVGR-B)","status":("go","Whole studio · on campus · under budget"),
  "facts":["WHOLE studio (your own unit, no housemates) on campus in EVGR-B.",
           "Dates: June 20 – Sept 15. Covers all summer.",
           "Cheapest full-summer whole studio in this batch.",
           "Contact via SUpost (Stanford login)."],
  "clabel":"Find post →","curl":"https://supost.com/search/cat/3",
  "cnote":"STRONG — whole on-campus studio, $1,600, full summer. Search 'EVGR B Private Studio' on SUpost."},

 {"top":True,"title":"EV low-rise apartment sublet","mid":"su-ev-lowrise-apt","price":"$1,414/mo","src":"SUpost · Stanford-only",
  "area":"On campus, Stanford (Escondido Village low-rise)","status":("go","Whole apartment · cheapest"),
  "facts":["Subletting a whole EV low-rise apartment on campus.",
           "Dates: ~June 15 – Sept 15.",
           "Cheapest whole unit found — $1,414, well under budget.",
           "Contact via SUpost (Stanford login)."],
  "clabel":"Find post →","curl":"https://supost.com/search/cat/3",
  "cnote":"Cheapest whole unit, on campus, full summer. Search 'subletting EV low-rise apartment' on SUpost."},

 {"top":False,"title":"EV Studio for rent (flexible dates)","mid":"su-ev-studio-jun8-sep12","price":"$2,000/mo","src":"SUpost · Stanford-only",
  "area":"On campus, Stanford (Escondido Village)","status":("check","Whole studio · at budget"),
  "facts":["Whole EV studio on campus, no housemates.",
           "Dates: June 8 – Sept 12 (flexible).",
           "At your $2,000 ceiling. Contact via SUpost (Stanford login)."],
  "clabel":"Find post →","curl":"https://supost.com/search/cat/3",
  "cnote":"Whole studio, full summer, flexible dates, $2,000. Search 'EV Studio For Rent June 8 Sept 12' on SUpost."},

 {"top":False,"title":"On-campus Stanford studio sublet (June–July)","price":"$2,000/mo","src":"SUpost · Stanford-only",
  "area":"On campus, Stanford","status":("check","Whole studio · partial summer"),
  "offcriteria":"Covers June–July only (not the full summer).",
  "facts":["Subletting a whole on-campus studio.",
           "Dates: June–July. At your $2,000 ceiling.",
           "Contact via SUpost (Stanford login)."],
  "clabel":"Find post →","curl":"https://supost.com/search/cat/3",
  "cnote":"Whole on-campus studio but June–July only. Search 'Subletting Stanford On-Campus Studio June July' on SUpost."},

 {"top":False,"title":"EVGR Summer sublease","mid":"su-evgr-summer","price":"$2,000/mo","src":"SUpost · Stanford-only",
  "area":"On campus, Stanford (EVGR)","status":("check","On campus · at budget"),
  "facts":["EVGR sublease for the summer (confirm whether whole studio or room).",
           "At your $2,000 ceiling. Contact via SUpost (Stanford login)."],
  "clabel":"Find post →","curl":"https://supost.com/search/cat/3",
  "cnote":"At budget, on campus. Confirm studio vs room. Search 'EVGR Sublease over Summer' on SUpost."},

 {"top":False,"title":"1 bedroom in 2BHK — no flatmate","mid":"su-1b-2bhk-noflatmate","price":"$1,684/mo","src":"SUpost · Stanford-only",
  "area":"Near Stanford","status":("check","Private 1BR · effectively whole"),
  "facts":["1 bedroom in a 2BHK sublet — listing says NO flatmate (you'd have it to yourself).",
           "Dates: June 15 – Sept 15. Under budget at $1,684.",
           "Confirm the no-flatmate detail. Contact via SUpost (Stanford login)."],
  "clabel":"Find post →","curl":"https://supost.com/search/cat/3",
  "cnote":"Effectively private (no flatmate), full summer, $1,684. Search 'Sublet Jun 15 Sept 15 1B 2BHK no flatmate' on SUpost."},

 # ---- PRIVATE SUITE / ROOM + PRIVATE BATH ----
 {"top":True,"title":"Private garden suite (bed + bath, own entrance)","price":"$2,000/mo","src":"SUpost · Stanford-only",
  "area":"Near Palo Alto High (~10 min to Stanford)","status":("go","Private suite · utilities included"),
  "facts":["Private garden suite: own bedroom + own bathroom + private entrance.",
           "Utilities, laundry, and internet INCLUDED in the $2,000/mo.",
           "Effectively self-contained near Palo Alto High. Contact via SUpost (Stanford login)."],
  "clabel":"Find post →","curl":"https://supost.com/search/cat/3",
  "cnote":"At budget but utilities incl + private entrance. Search 'Private garden suite Palo Alto High School' on SUpost."},

 {"top":False,"title":"Private bed + bath, 5-min walk to Stanford (2B2B)","price":"$1,600/mo","src":"SUpost · Stanford-only",
  "area":"5-min walk to Stanford","status":("check","Private room+bath · top location"),
  "offcriteria":"Private room in a 2B2B (one housemate), not a whole unit.",
  "facts":["Private bedroom + private bath + walk-in wardrobe in a 2B2B.",
           "5-minute WALK to Stanford — best location in this batch.",
           "Bright, quiet, park view. $1,600. Contact via SUpost (Stanford login)."],
  "clabel":"Find post →","curl":"https://supost.com/search/cat/3",
  "cnote":"Unbeatable location (5-min walk), private bed+bath, $1,600. Search '2B2B Private Bedroom Private Bath 5-min Walk to Stanford' on SUpost."},

 {"top":False,"title":"Furnished private room + bath, Palo Alto (available now)","price":"$1,450/mo","src":"SUpost · Stanford-only",
  "area":"Palo Alto","status":("check","Private room+bath · available now"),
  "offcriteria":"Private room (shared house), not a whole unit.",
  "facts":["Furnished private room + private bath in Palo Alto.",
           "Available NOW / June 1 — good for your immediate need.",
           "Under budget at $1,450. Contact via SUpost (Stanford login)."],
  "clabel":"Find post →","curl":"https://supost.com/search/cat/3",
  "cnote":"Available now, private bed+bath, $1,450, Palo Alto. Search 'Furnished private room private bath available now June 1st Palo Alto' on SUpost."},

 {"top":False,"title":"Small private room + private bath, Palo Alto","price":"$1,500/mo","src":"SUpost · Stanford-only",
  "area":"Palo Alto","status":("check","Private room+bath · under budget"),
  "offcriteria":"Private room (shared house), not a whole unit.",
  "facts":["A small private room with private bath in Palo Alto.",
           "Under budget at $1,500. Contact via SUpost (Stanford login)."],
  "clabel":"Find post →","curl":"https://supost.com/search/cat/3",
  "cnote":"Private bed+bath in PA, $1,500. Search 'A small private room with private bath in Palo Alto' on SUpost."},

 {"top":False,"title":"Private bedroom + bath, Mountain View","price":"$2,000/mo","src":"SUpost · Stanford-only",
  "area":"Mountain View (~15 min to Stanford)","status":("check","Private room+bath · at budget"),
  "offcriteria":"Private room in a shared place, not a whole unit.",
  "facts":["Private furnished bedroom with private bathroom in Mountain View.",
           "At your $2,000 ceiling. Contact via SUpost (Stanford login)."],
  "clabel":"Find post →","curl":"https://supost.com/search/cat/3",
  "cnote":"Private bed+bath at budget, Mountain View. Search 'Private furnished bedroom private bathroom Mountain View' on SUpost."},

 # ---- Additional listings YOU messaged on SUpost (recorded as reached out) ----
 {"top":False,"title":"1 Room in a 3BR Townhouse (avail June 1)","mid":"su-3br-townhouse-jun1","price":"$1,730/mo","src":"SUpost · Stanford-only",
  "area":"Mountain View (~15-20 min to Stanford)","status":("check","Room · 'ideally female' preferred"),
  "offcriteria":"Room in a 3BR townhouse (housemates), and poster prefers 'ideally female' — may be a soft no.",
  "facts":["1 room in a 3BR/2.5BA townhouse in Mountain View, available June 1.","Under budget at $1,730.",
           "Housemates: a 31yo attorney + 25yo software engineer. Poster prefers female."],
  "clabel":"Open post →","curl":"https://supost.com/post/index/130085280",
  "cnote":"You messaged this. Room in Mountain View 3BR townhouse; poster prefers female (soft)."},

 {"top":False,"title":"EV Studio Sublet (Jun 12–Sep 15, prorated)","mid":"su-ev-studio-jun12-sep15","price":"$2,039/mo","src":"SUpost · Stanford-only",
  "area":"On campus, Stanford (Escondido Village)","status":("check","Whole studio · slightly over budget"),
  "offcriteria":"$39 over your $2,000 limit.","facts":["Whole EV studio on campus, June 12 – Sept 15, rent prorated."],
  "clabel":"Find post →","curl":"https://supost.com/search/cat/3",
  "cnote":"You messaged this. Whole on-campus studio, full summer, $2,039 (prorated)."},

 {"top":False,"title":"EV Studio sublet (late June – mid Aug)","mid":"su-ev-studio-latejune-midaug","price":"$2,039/mo","src":"SUpost · Stanford-only",
  "area":"On campus, Stanford (Escondido Village)","status":("check","Whole studio · partial summer"),
  "offcriteria":"$39 over budget; covers late June to mid-August only.","facts":["Whole EV studio on campus, late June to mid-August."],
  "clabel":"Find post →","curl":"https://supost.com/search/cat/3",
  "cnote":"You messaged this. Whole on-campus studio, late June to mid-August, $2,039."},

 {"top":False,"title":"Furnished Private Room, Rains 2B1B (on campus)","mid":"su-rains-2b1b","price":"$1,628/mo","src":"SUpost · Stanford-only",
  "area":"On campus, Stanford (Rains)","status":("warn","FEMALE household · likely not eligible"),
  "offcriteria":"FEMALE household — you (male) are probably not eligible. You messaged it, but expect a no.",
  "facts":["Furnished private room in Rains graduate housing (2B1B), on campus.","Under budget at $1,628.",
           "Listing specifies a female household."],
  "clabel":"Open post →","curl":"https://supost.com/post/index/130085804",
  "cnote":"You messaged this, but it's a FEMALE household — likely a no. On-campus Rains room, $1,628."},

 {"top":False,"title":"Blackwelder Room Sublet (6/19–8/31)","mid":"su-blackwelder","price":"$1,165/mo","src":"SUpost · Stanford-only",
  "area":"On campus, Stanford (Blackwelder)","status":("check","Private room · cheapest"),
  "offcriteria":"A room (shared apartment), not a whole unit.",
  "facts":["Room sublet in Blackwelder, June 19 – Aug 31.","Cheapest of everything you've messaged: $1,165."],
  "clabel":"Find post →","curl":"https://supost.com/search/cat/3",
  "cnote":"You messaged this. On-campus Blackwelder room, $1,165, 6/19–8/31."},

 {"top":True,"title":"1BR Hulme Sublease (Jun 21–Sep 14)","mid":"su-hulme-1br","price":"$2,500/mo","src":"SUpost · Stanford-only",
  "area":"On campus, Stanford (Hulme)","status":("go","REPLIED · interest form submitted"),
  "replied":True,
  "reply":"andaru@stanford.edu replied and asked you to fill out the Hulme interest form (tinyurl.com/HulmeInterestForm). You submitted it — waiting to hear back.",
  "offcriteria":"$500 over your $2,000 limit — confirm the price before going further.",
  "facts":["Whole 1BR sublease in Hulme, June 21 – Sept 14.","Over budget at $2,500.",
           "Poster: andaru@stanford.edu (Stanford Verified)."],
  "clabel":"Find post →","curl":"https://supost.com/search/cat/3",
  "cnote":"REPLIED — you submitted the Hulme interest form (tinyurl.com/HulmeInterestForm). Awaiting their response."},

 {"top":False,"title":"Spacious room, EVGR-C grad housing","mid":"su-evgrc-spacious-room","price":"$2,039/mo","src":"SUpost · Stanford-only",
  "area":"On campus, Stanford (EVGR-C)","status":("check","Private room+bath · over budget"),
  "offcriteria":"Private room with 1 male roommate; $39 over budget; mid-June to mid-Sept.",
  "facts":["Large furnished room + private bath in EVGR-C, shared living/kitchen with 1 roommate.","Mid-June to mid-September, $2,039."],
  "clabel":"Find post →","curl":"https://supost.com/search/cat/3",
  "cnote":"You messaged this. EVGR-C private bed+bath (1 housemate), $2,039."},

 # ---- NEW leads from your direct links (not yet messaged) ----
 {"top":False,"title":"Stanford Studio (Jun 15–Aug 31)","mid":"su-stanford-studio-jun15","price":"$2,049/mo","src":"SUpost · Stanford-only",
  "area":"On campus, Stanford","status":("check","Whole studio · full summer · $49 over"),
  "offcriteria":"$49 over your $2,000 limit; no undergrads in the building.",
  "facts":["Whole studio, June 15 – Aug 31, full summer.","Master's student / affiliate only, no undergrads.","Messaged on SUpost — awaiting reply."],
  "clabel":"Open post →","curl":"https://supost.com/post/index/130035883",
  "cnote":"You messaged this. Whole studio, full summer, $2,049 (just over budget). Awaiting reply."},

 {"top":False,"title":"EV Low-rise room (Jun 15–Aug 31)","mid":"su-ev-lowrise-room","price":"$1,599/mo","src":"SUpost · Stanford-only",
  "area":"On campus, Stanford (EV Low-rise)","status":("check","Private room · under budget"),
  "offcriteria":"A room in a 2Bed/1Bath (likely have it to yourself most of the time), not a whole unit.",
  "facts":["1 room in an EV low-rise 2Bed/1Bath, June 15 – Aug 31.","Utilities, WiFi, laundry included. Under budget at $1,599.","NOT yet messaged."],
  "clabel":"Open post →","curl":"https://supost.com/post/index/130083646",
  "cnote":"NEW lead — on-campus room, $1,599, full summer, utilities incl. Message after the rate limit lifts."},

 {"top":False,"title":"EV Studio 1 (Jun 21–~Jul 20)","mid":"su-ev-studio1-jun21","price":"$2,039/mo","src":"SUpost · Stanford-only",
  "area":"On campus, Stanford (Escondido Village)","status":("check","Whole studio · short window · $39 over"),
  "offcriteria":"$39 over budget and short window (June 21 to ~July 20 only).",
  "facts":["Whole EV studio (Studio 1), June 21 to ~July 20, flexible.","Furnished. +$50 house dues.","Messaged on SUpost — awaiting reply."],
  "clabel":"Open post →","curl":"https://supost.com/post/index/130076651",
  "cnote":"You messaged this. Whole studio but only ~1 month (June 21–July 20), $2,039. Awaiting reply."},

 {"top":False,"title":"1B/1Ba EV Midrise (Jun 15–Sep 1)","mid":"su-ev-midrise-1b1b","price":"$2,663/mo","src":"SUpost · Stanford-only",
  "area":"On campus, Stanford (EV Midrise)","status":("warn","Whole 1B1B · over budget"),
  "offcriteria":"$663 over your $2,000 limit.",
  "facts":["Whole 1B/1Ba EV midrise apartment, June 15 – Sept 1, foothill view.","Fully furnished, utilities + laundry incl. NOT yet messaged."],
  "clabel":"Open post →","curl":"https://supost.com/post/index/130085275",
  "cnote":"NEW lead but $2,663 — well over budget. Only if you raise your ceiling."},

 {"top":False,"title":"Oak Creek 1B1B (Jun 10–Jul 25)","mid":"su-oakcreek-1b1b","price":"$2,300/mo","src":"SUpost · Stanford-only",
  "area":"Palo Alto (Oak Creek, ~10 min to Stanford)","status":("warn","Whole 1B1B · over budget · cat care"),
  "offcriteria":"$300 over budget, short window (June 10–July 25), and includes caring for 2 cats.",
  "facts":["Whole 1B1B (~800 sqft) in Oak Creek, June 10 – July 25.","$2,300 (discounted from $2,800 in exchange for cat-sitting). NOT yet messaged."],
  "clabel":"Open post →","curl":"https://supost.com/post/index/130084320",
  "cnote":"NEW lead but $2,300, short window, and you'd cat-sit. Off-budget."},
]

# Each SUpost card links to a Google search restricted to supost.com for its
# exact title. SUpost posts ARE public at supost.com/post/index/NNN, but I
# won't hard-code a specific post ID I can't verify (risk of linking the wrong
# post) — the search reliably lands you on the right one. You log in to message.
import urllib.parse as _uq
_SUPOST_Q = {
 "Fully Furnished EV Studio + Free Bike": "Fully Furnished EV Studio Free Bike Utilities Included summer 1900",
 "EVGR-B Private Studio sublet": "EVGR B Private Studio Sublet June 20 Sept 15 1600",
 "EV low-rise apartment sublet": "subletting EV low-rise apartment 1414",
 "EV Studio for rent (flexible dates)": "EV Studio For Rent June 8 Sept 12 2000",
 "On-campus Stanford studio sublet (June–July)": "Subletting Stanford On-Campus Studio June July 2000",
 "EVGR Summer sublease": "EVGR Sublease over Summer 2000",
 "1 bedroom in 2BHK — no flatmate": "Sublet Jun 15 Sept 15 1B in 2BHK No flatmate 1684",
 "Private garden suite (bed + bath, own entrance)": "private garden suite Palo Alto High School 2000",
 "Private bed + bath, 5-min walk to Stanford (2B2B)": "2B2B Private Bedroom Private Bath Walk-in Wardrobe 5-min Walk to Stanford 1600",
 "Furnished private room + bath, Palo Alto (available now)": "Furnished private room private bath available now June 1st Palo Alto 1450",
 "Small private room + private bath, Palo Alto": "small private room with private bath Palo Alto 1500",
 "Private bedroom + bath, Mountain View": "Private furnished bedroom private bathroom Mountain View 2000",
 "1 Room in a 3BR Townhouse (avail June 1)": "1 Room in a 3BR Townhouse Available June 1 1730",
 "EV Studio Sublet (Jun 12–Sep 15, prorated)": "EV Studio Sublet June 12 Sept 15 2039 prorated",
 "EV Studio sublet (late June – mid Aug)": "EV Studio sublet late June to mid-August 2039",
 "Furnished Private Room, Rains 2B1B (on campus)": "Furnished Private Room Rains 2B1B On-Campus 1628",
 "Blackwelder Room Sublet (6/19–8/31)": "Blackwelder Room Sublet 6/19 8/31 1165",
 "1BR Hulme Sublease (Jun 21–Sep 14)": "1BR Hulme Sublease June 21 Sept 14 2500",
 "Spacious room, EVGR-C grad housing": "Sublet Spacious room Stanford graduate housing EVGR-C 2039",
}
# Real direct SUpost post URLs (provided by you, identified by fetching each).
_SUPOST_DIRECT = {
 "su-hulme-1br": "https://supost.com/post/index/130085848",
 "su-evgrc-spacious-room": "https://supost.com/post/index/130085883",
 "su-blackwelder": "https://supost.com/post/index/130085820",
 "su-rains-2b1b": "https://supost.com/post/index/130085804",
 "su-ev-studio-latejune-midaug": "https://supost.com/post/index/130083894",
 "su-ev-studio-jun12-sep15": "https://supost.com/post/index/130085618",
 "su-3br-townhouse-jun1": "https://supost.com/post/index/130085280",
 "su-1b-2bhk-noflatmate": "https://supost.com/post/index/130085276",
 "su-ev-freebike": "https://supost.com/post/index/130085266",
}
for _L in SUPOST:
    _key = _L.get("mid") or _L["title"]
    if _key in _SUPOST_DIRECT:
        _L["curl"] = _SUPOST_DIRECT[_key]
        _L["clabel"] = "Open post →"
        continue
    _q = _SUPOST_Q.get(_L["title"])
    if _q:
        _L["curl"] = "https://www.google.com/search?q=" + _uq.quote(f"site:supost.com {_q}")
        _L["clabel"] = "Find post →"

def placeholder_svg(area, price):
    """Clean location placeholder for listings without a real photo —
    a labeled graphic (neighborhood + price), not a fake unit photo."""
    loc = (area.split("(")[0].strip() or area)
    words, lines, cur = loc.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 <= 20:
            cur = (cur + " " + w).strip()
        else:
            lines.append(cur); cur = w
        if len(lines) == 2: break
    if cur and len(lines) < 2: lines.append(cur)
    lines = lines[:2] or [loc[:20]]
    tspans = "".join(
        f'<tspan x="90" dy="{0 if i==0 else 17}">{html.escape(l)}</tspan>'
        for i, l in enumerate(lines))
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="180" height="162">'
           f'<rect width="180" height="162" fill="#f3f4f6"/>'
           f'<g fill="none" stroke="#9ca3af" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">'
           f'<path d="M56 64 L90 40 L124 64"/><path d="M64 60 V100 H116 V60"/>'
           f'<rect x="82" y="80" width="16" height="20"/></g>'
           f'<text x="90" y="120" text-anchor="middle" font-family="system-ui,sans-serif" '
           f'font-size="12" font-weight="600" fill="#4b5563">{tspans}</text>'
           f'<text x="90" y="152" text-anchor="middle" font-family="system-ui,sans-serif" '
           f'font-size="13" font-weight="700" fill="#15803d">{html.escape(price)}</text></svg>')
    return "data:image/svg+xml," + quote(svg)


def card(L):
    facts="".join(f"<li>{html.escape(f)}</li>" for f in L["facts"])
    top=" top" if L["top"] else ""
    scls,stext=L["status"]

    # Extract listing ID from URL for contact tracking
    url = L["curl"]
    listing_id = ""
    if "craigslist.org" in url:
        parts = url.split("/")
        if len(parts) > 0:
            listing_id = "cl-" + parts[-1].replace(".html", "")
    # Stable key for the manual "reached out" toggle (works for non-CL too).
    mark_id = L.get("mid") or listing_id or url

    dead = L.get("dead", False)
    offcriteria = L.get("offcriteria", "")
    replied = L.get("replied", False)

    contacted = mark_id in contacted_ids or listing_id in contacted_ids
    queued = (not contacted) and (listing_id in queued_ids)
    if dead:
        contacted_class = " dead"
        contacted_badge = '<div class="contact-badge dead">⊗ EXPIRED</div>'
    elif replied:
        contacted_class = " replied"
        contacted_badge = '<div class="contact-badge replied">💬 REPLIED</div>'
    elif contacted:
        contacted_class = " contacted"
        contacted_badge = '<div class="contact-badge">✓ CONTACTED</div>'
    elif queued:
        contacted_class = " queued"
        contacted_badge = '<div class="contact-badge queued">⏳ QUEUED · not sent</div>'
    else:
        contacted_class = ""
        contacted_badge = ""

    if offcriteria:
        contacted_class += " offcriteria"

    reply_html = (f'<div class="reply-note">💬 {html.escape(L["reply"])}</div>'
                  if L.get("reply") else "")
    offcriteria_html = (f'<div class="offcriteria-note">⚠ {html.escape(offcriteria)}</div>'
                        if offcriteria else "")

    imgs=L.get("imgs",[])
    phone=L.get("phone", "")
    email=L.get("email", "")

    # One photo per listing — the real first photo, or a clean location placeholder.
    if imgs:
        img_src = "/maps/" + html.escape(imgs[0])
    else:
        img_src = placeholder_svg(L["area"], L["price"])
    img_html = f'<div class="card-images"><img src="{img_src}" alt="Property photo"></div>'

    # Build contact box
    contact_items = []

    # Add "My Contact Email" first (highlighted)
    contact_items.append(f'''<div class="contact-item my-email">
        <svg fill="currentColor" viewBox="0 0 16 16"><path d="M.05 3.555A2 2 0 0 1 2 2h12a2 2 0 0 1 1.95 1.555L8 8.414.05 3.555ZM0 4.697v7.104l5.803-3.558L0 4.697ZM6.761 8.83l-6.57 4.027A2 2 0 0 0 2 14h12a2 2 0 0 0 1.808-1.144l-6.57-4.027L8 9.586l-1.239-.757Zm3.436-.586L16 11.801V4.697l-5.803 3.546Z"/></svg>
        <span style="font-weight:600">My Email: {html.escape(MY_EMAIL)}</span>
    </div>''')

    if phone:
        contact_items.append(f'''<div class="contact-item">
            <svg fill="currentColor" viewBox="0 0 16 16"><path d="M3.654 1.328a.678.678 0 0 0-1.015-.063L1.605 2.3c-.483.484-.661 1.169-.45 1.77a17.568 17.568 0 0 0 4.168 6.608 17.569 17.569 0 0 0 6.608 4.168c.601.211 1.286.033 1.77-.45l1.034-1.034a.678.678 0 0 0-.063-1.015l-2.307-1.794a.678.678 0 0 0-.58-.122l-2.19.547a1.745 1.745 0 0 1-1.657-.459L5.482 8.062a1.745 1.745 0 0 1-.46-1.657l.548-2.19a.678.678 0 0 0-.122-.58L3.654 1.328z"/></svg>
            <span>Landlord: <a href="tel:{phone.replace(' ', '')}">{html.escape(phone)}</a></span>
        </div>''')

    if email:
        contact_items.append(f'''<div class="contact-item">
            <svg fill="currentColor" viewBox="0 0 16 16"><path d="M.05 3.555A2 2 0 0 1 2 2h12a2 2 0 0 1 1.95 1.555L8 8.414.05 3.555ZM0 4.697v7.104l5.803-3.558L0 4.697ZM6.761 8.83l-6.57 4.027A2 2 0 0 0 2 14h12a2 2 0 0 0 1.808-1.144l-6.57-4.027L8 9.586l-1.239-.757Zm3.436-.586L16 11.801V4.697l-5.803 3.546Z"/></svg>
            <span>Landlord: <a href="mailto:{email}">{html.escape(email)}</a></span>
        </div>''')

    if not phone and not email:
        if "SUpost" in L.get("src", "") or "supost.com" in url:
            fallback = "Contact via SUpost (log in, then open the post)"
        elif "stanford.edu" in url:
            fallback = "Apply / email via the Stanford page"
        else:
            fallback = "Email via Craigslist reply button"
        contact_items.append(f'''<div class="contact-item">
            <svg fill="currentColor" viewBox="0 0 16 16"><path d="M0 4a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2V4Zm2-1a1 1 0 0 0-1 1v.217l7 4.2 7-4.2V4a1 1 0 0 0-1-1H2Zm13 2.383-4.708 2.825L15 11.105V5.383Zm-.034 6.876-5.64-3.471L8 9.583l-1.326-.795-5.64 3.47A1 1 0 0 0 2 13h12a1 1 0 0 0 .966-.741ZM1 11.105l4.708-2.897L1 5.383v5.722Z"/></svg>
            <span style="color:#999">{html.escape(fallback)}</span>
        </div>''')

    # Build contact history section
    contact_history_html = ""
    if listing_id in contact_history and contact_history[listing_id].get("contacts"):
        contacts = contact_history[listing_id]["contacts"]
        history_entries = []

        for contact in contacts:
            channel = contact.get("channel", "Unknown")
            timestamp = contact.get("timestamp", "")
            elapsed = time_elapsed(timestamp)
            message = contact.get("message", "")
            via_email = contact.get("email", "")
            via_phone = contact.get("phone", "")

            via_info = ""
            if via_email:
                via_info = f'Via: {html.escape(via_email)}'
            elif via_phone:
                via_info = f'Via: {html.escape(via_phone)}'

            history_entries.append(f'''
                <div class="contact-entry">
                    <div class="contact-entry-header">
                        <span class="contact-channel">{html.escape(channel)}</span>
                        <span class="contact-time">{html.escape(elapsed)}</span>
                    </div>
                    {f'<div class="contact-via">{via_info}</div>' if via_info else ''}
                    <div class="contact-message">{html.escape(message)}</div>
                </div>
            ''')

        contact_history_html = f'''
            <div class="contact-history">
                <div class="contact-history-title">Contact History ({len(contacts)} contact{"s" if len(contacts) > 1 else ""})</div>
                {"".join(history_entries)}
            </div>
        '''

    # Manual "I reached out" toggle — your attestation, persisted server-side.
    toggle_on = " on" if contacted else ""
    toggle_label = "✓ Reached out" if contacted else "Mark as reached out"
    toggle_html = (f'<button class="reach-toggle{toggle_on}" '
                   f'onclick="toggleReached(this, {json.dumps(mark_id)})">'
                   f'{toggle_label}</button>')

    contact_box = f'''<div class="contact-box">
        <div class="contact-title">CONTACT INFO</div>
        <div class="btn-group">
            <a class="btn" href="{html.escape(url)}" target="_blank">{html.escape(L.get("clabel","View listing"))}</a>
        </div>
        {toggle_html}
        {"".join(contact_items)}
        <div class="contact-note">{html.escape(L['cnote'])}</div>
        {contact_history_html}
    </div>'''

    # Generate unique ID for this card
    card_id = f"card-{listing_id}" if listing_id else f"card-{hash(url)}"
    noimg = ""  # every card now has a photo or a location placeholder

    return f"""<div class="card{top}{contacted_class}{noimg}" id="{card_id}">
{contacted_badge}
{img_html}
<div class="card-content">
<div class="card-head"><p class="card-title">{html.escape(L['title'])}</p><span class="price">{html.escape(L['price'])}</span></div>
<div class="area">{html.escape(L['area'])} · {html.escape(L['src'])}</div>
<span class="status {scls}">{html.escape(stext)}</span>
{reply_html}
{offcriteria_html}
<ul class="facts">{facts}</ul>
<button class="expand-toggle" onclick="toggleCard('{card_id}')">▼ Show more details</button>
</div>
{contact_box}
</div>"""

def render_body():
    # Recompute contacted set per request so manual toggles show on reload.
    global contacted_ids
    manual = load_manual()
    contacted_ids = set(sent_log.keys()) | set(contact_history.keys()) | manual

    # Live, combined stats across every contact source (for the status panel).
    n_auto   = len(sent_log)
    n_conf   = len(contact_history)
    n_manual = len(manual)
    n_total  = len(contacted_ids)
    # Listings shown on this dashboard (curated cards across all sections).
    all_cards = NON_CL + SUBLETS + REGULAR_RENTALS + SHORT_TERM + SUPOST
    def card_key(L):
        if L.get("mid"):
            return L["mid"]
        u = L["curl"]
        if "craigslist.org" in u:
            return "cl-" + u.split("/")[-1].replace(".html", "")
        return u
    n_cards = len(all_cards)
    n_card_contacted = sum(1 for L in all_cards if card_key(L) in contacted_ids)
    n_card_dead = sum(1 for L in all_cards if L.get("dead"))
    n_replied = sum(1 for L in all_cards if L.get("replied"))

    # Categorize SUpost listings by outreach status so the page reads as
    # clear buckets instead of one long mixed list.
    def sup_key(L): return L.get("mid") or L["title"]
    def is_ineligible(L):
        oc = L.get("offcriteria", "")
        return ("FEMALE" in oc or "female" in oc or "$663 over" in oc or "$300 over" in oc)
    def grp_sort(items):
        return sorted(items, key=lambda L: (not L["top"], L["title"]))
    sup_replied = grp_sort([L for L in SUPOST if L.get("replied")])
    sup_todo    = grp_sort([L for L in SUPOST if not L.get("replied") and not is_ineligible(L) and sup_key(L) not in contacted_ids])
    sup_msgd    = grp_sort([L for L in SUPOST if not L.get("replied") and not is_ineligible(L) and sup_key(L) in contacted_ids])
    sup_inelig  = grp_sort([L for L in SUPOST if not L.get("replied") and is_ineligible(L)])
    def sup_section(title, items):
        if not items: return ""
        return f'<h3 class="cat">{title} ({len(items)})</h3>' + "".join(card(L) for L in items)
    supost_grouped = (
        sup_section("💬 Replied — they responded", sup_replied)
        + sup_section("📨 Not yet messaged — send these next", sup_todo)
        + sup_section("✅ Messaged — awaiting reply", sup_msgd)
        + sup_section("⚠️ Ineligible / over budget — low priority", sup_inelig)
    )
    n_queue = len(queued_ids)
    n_queue_left = len([i for i in queued_ids if i not in contacted_ids])

    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Simon's Stanford Summer 2026 Housing Ledger</title>
<style>{CSS}</style>
<script>
async function toggleReached(btn, id) {{
    btn.disabled = true;
    try {{
        const r = await fetch('/api/toggle?id=' + encodeURIComponent(id), {{method:'POST'}});
        const d = await r.json();
        const on = d.contacted;
        btn.classList.toggle('on', on);
        btn.textContent = on ? '✓ Reached out' : 'Mark as reached out';
        const card = btn.closest('.card');
        if (card && !card.classList.contains('dead')) {{
            card.classList.toggle('contacted', on);
            if (on) card.classList.remove('queued');
            let badge = card.querySelector('.contact-badge');
            if (on) {{
                if (!badge) {{ badge = document.createElement('div'); card.prepend(badge); }}
                badge.className = 'contact-badge';
                badge.textContent = '✓ CONTACTED';
            }} else if (badge) {{ badge.remove(); }}
        }}
    }} catch (e) {{ alert('Could not save — is the server running?'); }}
    finally {{ btn.disabled = false; }}
}}
function toggleCard(cardId) {{
    const card = document.getElementById(cardId);
    const btn = card.querySelector('.expand-toggle');
    if (card.classList.contains('expanded')) {{
        card.classList.remove('expanded');
        btn.textContent = '▼ Show more details';
    }} else {{
        card.classList.add('expanded');
        btn.textContent = '▲ Show less';
    }}
}}
</script>
</head><body>
<header class="masthead">
<h1>Simon's Stanford Summer 2026 Housing</h1>
<p class="sub">Under $2,000/mo · Dedicated units, no housemates · Within 20 min of Stanford · East Palo Alto excluded</p>
</header>

<div class="banner">
<strong>Today (Jun 10) — switch to direct channels:</strong>
1) <strong>Call/text Bri</strong> 623-810-3457 (Kennedy Commons $1,570 — texted Jun 8, no reply) ·
2) <strong>Email andaru@stanford.edu</strong> re: Hulme next steps (form already submitted) ·
3) <strong>Book the Jun 9–20 campus stopgap</strong> ($1,200) to get out of the hotel ·
4) <strong>Post a "Housing Wanted" ad</strong> on SUpost + the FB Stanford Housing group ·
5) <strong>Email summerhousing@stanford.edu</strong> (official fallback).
Ready-to-send scripts for all five are in <strong>TODO_outreach.md</strong>.
</div>

<div class="banner">
<strong>Priority:</strong> Start with the <strong>$1,890 Palo Alto sublease</strong> — it's the ONLY whole-unit sublease that skips applications.
</div>

<div class="status-panel">
  <div class="status-row">
    <div class="stat"><div class="stat-num ok">{n_total}</div><div class="stat-lbl">reached out<br>(all sources)</div></div>
    <div class="stat"><div class="stat-num replied-num">{n_replied}</div><div class="stat-lbl">replied<br>(in conversation)</div></div>
    <div class="stat"><div class="stat-num warn">{n_queue_left}</div><div class="stat-lbl">in queue,<br>not contacted</div></div>
    <div class="stat"><div class="stat-num dead-num">{n_card_dead}</div><div class="stat-lbl">expired<br>(skip)</div></div>
  </div>
  <div class="status-detail">
    <strong>Combined outreach:</strong> {n_auto} auto/assisted send(s) · {n_conf} confirmed-with-message · {n_manual} marked by you on this page → <strong>{n_total} distinct landlord(s) contacted.</strong>
    {"<span style='color:#c62828'>Nothing has actually gone out yet.</span>" if n_total == 0 else ""}
  </div>
  <div class="status-detail">
    <strong>Search:</strong> Craigslist last scan Jun 4 ({len(queued_ids)} matches queued) · SUpost refreshed Jun 9 from your paste ({len(SUPOST)} offers) · Zillow/FB/Apartments/Reddit = manual links below.
  </div>
</div>

<h2>⭐ SUpost — Stanford marketplace ({len(SUPOST)} offers, grouped by status)</h2>
<div class="banner cl">
Stanford students/affiliates near campus — your best source. Grouped below: <strong>replied → to-send → messaged → low-priority.</strong> Use each card's button to open the post; paste me any reply and I'll log it.
</div>
{supost_grouped}

<h2>Official Stanford Housing (most reliable)</h2>
{"".join(card(L) for L in NON_CL)}

<h2>SUBLEASE — Skip applications (1 listing)</h2>
{"".join(card(L) for L in SUBLETS)}

<h2>Regular Rentals — Good neighborhoods (9 listings)</h2>
<div class="banner cl">
<strong>Note:</strong> These are regular rentals (/apa) — expect applications, credit checks, and deposits. East Palo Alto listings removed.
</div>
{"".join(card(L) for L in REGULAR_RENTALS)}

<h2>Short-term Options (partial summer coverage)</h2>
{"".join(card(L) for L in SHORT_TERM)}

<h2>More places to reach out (check manually)</h2>
<table>
<tr><th>Platform</th><th>URL</th><th>Notes</th></tr>
<tr><td colspan="3" style="background:#eef2ff;font-weight:700">Stanford-specific (try first)</td></tr>
<tr><td>Stanford R&DE</td><td><a href="https://rde.stanford.edu/conferences/summer-intern-housing">rde.stanford.edu</a></td><td>Official summer-intern housing — email summerhousing@stanford.edu</td></tr>
<tr><td>Stanford Summer Session</td><td><a href="https://summer.stanford.edu/">summer.stanford.edu</a></td><td>Email the program office — they often have a housing portal / partner list for summer students</td></tr>
<tr><td>SUpost</td><td><a href="https://supost.com">supost.com</a></td><td>Stanford-affiliated classifieds (your main source above)</td></tr>
<tr><td>Facebook — Stanford Housing</td><td><a href="https://www.facebook.com/groups/304588736883828/">Stanford Housing/Sublets</a></td><td>Active student market — post a "looking for" with your dates</td></tr>
<tr><td>Reddit r/Stanford</td><td><a href="https://www.reddit.com/r/stanford/">r/stanford</a></td><td>Search "housing" / "sublet summer 2026" or post a request</td></tr>
<tr><td colspan="3" style="background:#ecfdf5;font-weight:700">Intern / furnished short-term (great fit for you)</td></tr>
<tr><td>Furnished Finder</td><td><a href="https://www.furnishedfinder.com/">furnishedfinder.com</a></td><td>Built for interns/travelers — furnished, monthly, no long lease. Search Palo Alto</td></tr>
<tr><td>HousingAnywhere</td><td><a href="https://housinganywhere.com/">housinganywhere.com</a></td><td>International/student furnished sublets — Bay Area listings</td></tr>
<tr><td>Nextdoor</td><td><a href="https://nextdoor.com/">nextdoor.com</a></td><td>Neighbors in Palo Alto/Menlo Park renting rooms — search "room for rent"</td></tr>
<tr><td>Cornell sublets</td><td><a href="https://www.facebook.com/groups/cornellsublets/">FB: Cornell Sublets</a></td><td>Peers also heading to Stanford/Bay Area for summer — ask in Cornell groups</td></tr>
<tr><td>RedNote (小红书)</td><td><a href="https://www.xiaohongshu.com/">xiaohongshu.com</a></td><td>Very active for Bay Area student rentals — search "Stanford租房"</td></tr>
<tr><td colspan="3" style="background:#f3f4f6;font-weight:700">General rental sites (mostly long-lease)</td></tr>
<tr><td>Facebook Marketplace</td><td><a href="https://www.facebook.com/marketplace/category/propertyrentals">Marketplace rentals</a></td><td>Search "Palo Alto studio" / "Menlo Park sublet"</td></tr>
<tr><td>Zillow Rentals</td><td><a href="https://www.zillow.com/palo-alto-ca/apartments-under-2000/">zillow.com</a></td><td>Filter: Palo Alto + Menlo Park, max $2000 (blocks scraping — browse by hand)</td></tr>
<tr><td>Apartments.com</td><td><a href="https://www.apartments.com/">apartments.com</a></td><td>Filter by location and move-in date</td></tr>
<tr><td>Craigslist /apa</td><td><a href="https://sfbay.craigslist.org/search/pen/apa?max_price=2000">Search link</a></td><td>Regular rentals — filter for good areas</td></tr>
<tr><td>Craigslist /sub</td><td><a href="https://sfbay.craigslist.org/search/pen/sub?max_price=2000">Search link</a></td><td>Temporary/subleases — best for avoiding applications</td></tr>
</table>

<p style="margin-top:20px;color:#777;font-size:11px">Dashboard updated: June 10, 2026 · East Palo Alto excluded · Use the “Mark as reached out” button on each card to track outreach · Blue = reached out · Amber = queued · Red = expired</p>
</body></html>"""

class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        p = urlparse(self.path).path
        if p=="/":
            body = render_body().encode("utf-8")
            self.send_response(200); self.send_header("Content-Type","text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body))); self.end_headers()
            self.wfile.write(body)
        elif p.startswith("/maps/") and (p.endswith(".png") or p.endswith(".jpg")):
            fp=os.path.join(ROOT,"maps",os.path.basename(p))
            if os.path.isfile(fp):
                ctype = "image/jpeg" if p.endswith(".jpg") else "image/png"
                self.send_response(200); self.send_header("Content-Type",ctype); self.end_headers()
                with open(fp,"rb") as f: self.wfile.write(f.read())
            else:
                self.send_error(404,"Image not found")
        else:
            self.send_error(404)

    def do_POST(self):
        p = urlparse(self.path)
        if p.path == "/api/toggle":
            from urllib.parse import parse_qs
            mid = (parse_qs(p.query).get("id") or [""])[0]
            if not mid:
                self.send_error(400, "missing id"); return
            now_on = toggle_manual(mid)
            body = json.dumps({"id": mid, "contacted": now_on}).encode("utf-8")
            self.send_response(200); self.send_header("Content-Type","application/json")
            self.send_header("Content-Length", str(len(body))); self.end_headers()
            self.wfile.write(body)
        else:
            self.send_error(404)

    def log_message(self,fmt,*args): pass

if __name__=="__main__":
    if "--serve" not in sys.argv:
        print(render_body()); sys.exit(0)
    with socketserver.TCPServer(("",PORT),Handler) as httpd:
        print(f"[palo_alto_server] http://localhost:{PORT}/",flush=True)
        try: httpd.serve_forever()
        except KeyboardInterrupt: print("\n[palo_alto_server] stopped")
