#!/usr/bin/env python3
"""Palo Alto / Stanford summer housing dashboard. Default port 5555.
Card layout: each listing shows contact method + location map image.
Updated to exclude East Palo Alto, focus on good neighborhoods only."""
import http.server, socketserver, os, sys, html, mimetypes, json
from urllib.parse import urlparse
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
body{font-family:-apple-system,system-ui,sans-serif;max-width:1200px;margin:0 auto;padding:12px;color:#1a1a2e;line-height:1.3;background:#fafafa;font-size:13px}
h1{margin:0 0 2px;color:#1a1a2e;font-size:22px}
.sub{color:#555;font-size:12px;margin-bottom:10px}
.banner{background:#fff8e1;border-left:3px solid #f9a825;padding:8px 12px;border-radius:4px;margin:10px 0;font-size:12px;line-height:1.4}
.banner.cl{background:#fff3f3;border-color:#e57373}
h2{margin:18px 0 6px;padding-bottom:3px;border-bottom:2px solid #1a1a2e;font-size:16px}
.card{border:1px solid #e0e0e0;border-radius:6px;margin:8px 0;background:#fff;box-shadow:0 1px 2px rgba(0,0,0,.05);padding:10px;display:grid;grid-template-columns:180px 1fr 240px;gap:10px;position:relative;height:150px;overflow:hidden}
.card.top{border:2px solid #4caf50;background:#f9fff9}
.card.contacted{border-left:4px solid #2196f3;background:#f5f9ff}
.card.queued{border-left:4px solid #f9a825;background:#fffdf5}
.card.dead{border-left:4px solid #c62828;opacity:.55}
.card.dead .card-images{filter:grayscale(1)}
.card.offcriteria{border-left:4px solid #9e9e9e}
.card.expanded{height:auto;max-height:600px;overflow-y:auto}
.contact-badge{position:absolute;top:6px;right:6px;background:#2196f3;color:#fff;padding:3px 8px;border-radius:3px;font-size:10px;font-weight:700;text-transform:uppercase;z-index:10}
.contact-badge.queued{background:#f9a825}
.contact-badge.dead{background:#c62828}
.offcriteria-note{font-size:10px;color:#b26a00;background:#fff3e0;border:1px solid #ffcc80;border-radius:3px;padding:3px 6px;margin-bottom:4px;line-height:1.3}
.status-panel{background:#fff;border:1px solid #e0e0e0;border-radius:8px;padding:12px 14px;margin:10px 0;box-shadow:0 1px 3px rgba(0,0,0,.06)}
.status-row{display:flex;gap:10px;margin-bottom:8px}
.stat{flex:1;text-align:center;background:#fafafa;border:1px solid #eee;border-radius:6px;padding:8px 4px}
.stat-num{font-size:26px;font-weight:800;line-height:1;color:#1a1a2e}
.stat-num.ok{color:#2e7d32}
.stat-num.warn{color:#e65100}
.stat-num.dead-num{color:#c62828}
.stat-lbl{font-size:10px;color:#666;margin-top:4px;line-height:1.2}
.status-detail{font-size:11px;color:#444;line-height:1.5;margin-top:4px}
.reach-toggle{margin-top:6px;width:100%;padding:6px 8px;border:1px solid #2196f3;background:#fff;color:#1565c0;border-radius:4px;font-size:11px;font-weight:700;cursor:pointer}
.reach-toggle:hover{background:#e3f2fd}
.reach-toggle.on{background:#2196f3;color:#fff;border-color:#1565c0}
.reach-toggle:disabled{opacity:.5;cursor:wait}
.card-images{width:180px;height:130px;display:flex;flex-direction:column;gap:3px;overflow:hidden}
.card-images img{width:100%;height:100%;object-fit:cover;border-radius:4px}
.card-images.multi{display:grid;grid-template-columns:1fr 1fr;grid-template-rows:1fr 1fr;gap:3px}
.card-images.multi img:first-child{grid-column:1/3;grid-row:1}
.card-content{display:flex;flex-direction:column;min-width:0;overflow:hidden}
.card-head{display:flex;justify-content:space-between;align-items:baseline;gap:8px;margin-bottom:3px}
.card-title{font-weight:700;font-size:14px;line-height:1.2}
.price{font-size:16px;font-weight:800;color:#2e7d32;white-space:nowrap}
.area{font-size:11px;color:#666;margin-bottom:4px}
.status{display:inline-block;font-size:10px;font-weight:700;padding:3px 7px;border-radius:3px;margin-bottom:4px}
.status.go{background:#c8e6c9;color:#2e7d32}
.status.check{background:#fff3e0;color:#e65100}
.status.warn{background:#ffebee;color:#c62828}
ul.facts{padding-left:16px;font-size:11px;color:#333;line-height:1.4;max-height:70px;overflow:hidden}
.card.expanded ul.facts{max-height:none}
ul.facts li{margin:2px 0}
.expand-toggle{background:none;border:none;color:#1565c0;font-size:11px;cursor:pointer;padding:4px 0;text-decoration:underline;margin-top:4px}
.expand-toggle:hover{color:#0d47a1}
.contact-box{border:1px solid #e0e0e0;border-radius:4px;padding:8px;background:#fafafa;display:flex;flex-direction:column;gap:4px;height:130px;overflow:hidden}
.card.expanded .contact-box{height:auto;overflow:visible}
.contact-title{font-size:11px;font-weight:700;color:#555;margin-bottom:2px;text-transform:uppercase}
.contact-item{font-size:12px;display:flex;align-items:center;gap:6px;padding:3px 0}
.contact-item svg{width:14px;height:14px;flex-shrink:0}
.contact-item a{color:#1565c0;text-decoration:none;word-break:break-all}
.contact-item a:hover{text-decoration:underline}
.contact-item.my-email{background:#e3f2fd;border:1px solid #90caf9;border-radius:3px;padding:4px 6px;margin-top:2px}
.contact-note{font-size:10px;color:#777;margin-top:4px;line-height:1.3}
.contact-history{margin-top:8px;padding-top:8px;border-top:1px solid #e0e0e0;display:none}
.card.expanded .contact-history{display:block}
.contact-history-title{font-size:11px;font-weight:700;color:#555;margin-bottom:4px;text-transform:uppercase}
.contact-entry{background:#fff;border:1px solid #e0e0e0;border-radius:4px;padding:6px;margin-bottom:6px;font-size:11px}
.contact-entry-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:4px}
.contact-channel{font-weight:700;color:#2196f3}
.contact-time{color:#999;font-size:10px}
.contact-via{color:#666;font-size:10px;margin-bottom:4px}
.contact-message{color:#333;line-height:1.4;font-style:italic;padding:4px;background:#f9f9f9;border-radius:3px}
.btn-group{display:flex;gap:6px;margin-top:6px}
.btn{display:inline-block;background:#1565c0;color:#fff!important;padding:6px 12px;border-radius:4px;font-weight:600;text-decoration:none;font-size:11px;text-align:center;flex:1}
.btn.secondary{background:#757575}
table{border-collapse:collapse;width:100%;margin:8px 0;font-size:12px;background:#fff}
th,td{border:1px solid #e0e0e0;padding:5px 8px;text-align:left;vertical-align:top}
th{background:#1a1a2e;color:#fff;font-weight:500;font-size:11px}
a{color:#1565c0}
@media print{body{background:#fff;max-width:100%}.card{break-inside:avoid;box-shadow:none;height:auto!important}h2{break-after:avoid}}
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
 {"top":True,"title":"EVGR-B Private Studio sublet","price":"$1,600/mo","src":"SUpost · Stanford-only",
  "area":"On campus, Stanford (EVGR-B)","status":("go","Whole studio · on campus · under budget"),
  "facts":["WHOLE studio (your own unit, no housemates) on campus in EVGR-B.",
           "Dates: June 20 – Sept 15. Covers all summer.",
           "Best match to your criteria found on SUpost: private + on-campus + under $2,000.",
           "Contact is via SUpost (Stanford login) — no email/phone exposed publicly."],
  "clabel":"Find on SUpost",
  "curl":"https://supost.com/search/cat/3",
  "cnote":"STRONG match — whole on-campus studio, $1,600, full summer. Search 'EVGR B Private Studio' on SUpost while logged in."},

 {"top":True,"title":"Private garden suite (bed + bath, own entrance)","price":"$2,000/mo","src":"SUpost · Stanford-only",
  "area":"Near Palo Alto High (~10 min to Stanford)","status":("go","Private suite · utilities included"),
  "facts":["Private garden suite: own bedroom + own bathroom + private entrance.",
           "Utilities, laundry, and internet INCLUDED in the $2,000/mo.",
           "Effectively a self-contained unit near Palo Alto High School.",
           "Contact via SUpost (Stanford login)."],
  "clabel":"Find on SUpost",
  "curl":"https://supost.com/search/cat/3",
  "cnote":"At your $2,000 ceiling but utilities included. Search 'Private garden suite Palo Alto High' on SUpost."},

 {"top":False,"title":"EV Studio II sublet","price":"$2,039/mo","src":"SUpost · Stanford-only",
  "area":"On campus, Stanford (Escondido Village)","status":("check","Whole studio · slightly over budget"),
  "offcriteria":"Just over your $2,000 limit ($2,039).",
  "facts":["Whole studio on campus (Escondido Village), no housemates.",
           "Dates: June 18 – Sept 4.",
           "Contact via SUpost (Stanford login)."],
  "clabel":"Find on SUpost",
  "curl":"https://supost.com/search/cat/3",
  "cnote":"Whole on-campus studio, $39 over budget. Search 'EV Studio II' on SUpost."},

 {"top":False,"title":"EVGR Summer sublease","price":"$2,000/mo","src":"SUpost · Stanford-only",
  "area":"On campus, Stanford (EVGR)","status":("check","On campus · at budget"),
  "facts":["EVGR sublease for the summer (confirm whether whole studio or room).",
           "At your $2,000 ceiling.",
           "Contact via SUpost (Stanford login)."],
  "clabel":"Find on SUpost",
  "curl":"https://supost.com/search/cat/3",
  "cnote":"At budget, on campus. Confirm if it's a studio or a room. Search 'EVGR Sublease over Summer' on SUpost."},

 {"top":False,"title":"EVGR-C room sublease (private bed + bath)","price":"$2,000/mo","src":"SUpost · Stanford-only",
  "area":"On campus, Stanford (EVGR-C)","status":("check","Private room+bath · short window"),
  "offcriteria":"Private room in a shared unit (not a whole unit); only covers Jul 5 – Aug 8.",
  "facts":["Private bedroom + private bathroom on campus (EVGR-C).",
           "Dates: July 5 – Aug 8 only (partial summer).",
           "Contact via SUpost (Stanford login)."],
  "clabel":"Find on SUpost",
  "curl":"https://supost.com/search/cat/3",
  "cnote":"On campus, private bed+bath, but only ~5 weeks. Search 'Room for sublease EVGR-C' on SUpost."},

 {"top":False,"title":"Room, Midtown Palo Alto","price":"$1,950/mo","src":"SUpost · Stanford-only",
  "area":"Midtown Palo Alto (~10 min to Stanford)","status":("check","Private room · under budget"),
  "offcriteria":"A room (likely shared house), not a dedicated unit.",
  "facts":["Room for rent in Midtown Palo Alto.",
           "Under budget at $1,950; confirm whether private bath and who you'd share with.",
           "Contact via SUpost (Stanford login)."],
  "clabel":"Find on SUpost",
  "curl":"https://supost.com/search/cat/3",
  "cnote":"Under budget, good PA location, but a room. Search 'Room for rent Midtown Palo Alto' on SUpost."},

 {"top":False,"title":"Furnished room, 15 min bike to the Oval","price":"$1,425/mo","src":"SUpost · Stanford-only",
  "area":"~15 min bike to Stanford","status":("check","Private room · well under budget"),
  "offcriteria":"A room (shared housing), not a dedicated unit.",
  "facts":["Furnished room, ~15 minutes by bike to the Oval.",
           "Well under budget at $1,425.",
           "Contact via SUpost (Stanford login)."],
  "clabel":"Find on SUpost",
  "curl":"https://supost.com/search/cat/3",
  "cnote":"Cheapest near-campus room here. A room, not a unit. Search 'Furnished room 15 minutes by bike to the Oval' on SUpost."},

 {"top":False,"title":"Private bedroom + bath, Mountain View","price":"$2,000/mo","src":"SUpost · Stanford-only",
  "area":"Mountain View (~15 min to Stanford)","status":("check","Private room+bath · at budget"),
  "offcriteria":"Private room in a shared place, not a whole unit.",
  "facts":["Private furnished bedroom with private bathroom in Mountain View.",
           "At your $2,000 ceiling.",
           "Contact via SUpost (Stanford login)."],
  "clabel":"Find on SUpost",
  "curl":"https://supost.com/search/cat/3",
  "cnote":"Private bed+bath at budget, Mountain View. Search 'Private furnished bedroom private bathroom Mountain View' on SUpost."},
]

# Each SUpost card links to a Google search restricted to supost.com for its
# exact title. SUpost posts ARE public at supost.com/post/index/NNN, but I
# won't hard-code a specific post ID I can't verify (risk of linking the wrong
# post) — the search reliably lands you on the right one. You log in to message.
import urllib.parse as _uq
_SUPOST_Q = {
 "EVGR-B Private Studio sublet": "EVGR B Private Studio Sublet summer",
 "Private garden suite (bed + bath, own entrance)": "private garden suite Palo Alto High School 2000",
 "EV Studio II sublet": "EV Studio II sublet summer",
 "EVGR Summer sublease": "EVGR Sublease over Summer 2000",
 "EVGR-C room sublease (private bed + bath)": "Room for sublease EVGR-C private bedroom bathroom",
 "Room, Midtown Palo Alto": "Room for rent Midtown Palo Alto 1950",
 "Furnished room, 15 min bike to the Oval": "Furnished room 15 minutes by bike to the Oval",
 "Private bedroom + bath, Mountain View": "Private furnished bedroom private bathroom Mountain View 2000",
}
for _L in SUPOST:
    _q = _SUPOST_Q.get(_L["title"])
    if _q:
        _L["curl"] = "https://www.google.com/search?q=" + _uq.quote(f"site:supost.com {_q}")
        _L["clabel"] = "Find post →"

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
    mark_id = listing_id or url

    dead = L.get("dead", False)
    offcriteria = L.get("offcriteria", "")

    contacted = mark_id in contacted_ids or listing_id in contacted_ids
    queued = (not contacted) and (listing_id in queued_ids)
    if dead:
        contacted_class = " dead"
        contacted_badge = '<div class="contact-badge dead">⊗ EXPIRED</div>'
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

    offcriteria_html = (f'<div class="offcriteria-note">⚠ {html.escape(offcriteria)}</div>'
                        if offcriteria else "")

    imgs=L.get("imgs",[])
    phone=L.get("phone", "")
    email=L.get("email", "")

    # Build image gallery HTML
    img_html = ''
    if imgs:
        multi_class = ' multi' if len(imgs) > 1 else ''
        img_tags = ''.join(f'<img src="/maps/{html.escape(img)}" alt="Property photo">' for img in imgs[:4])
        img_html = f'<div class="card-images{multi_class}">{img_tags}</div>'

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
        {"".join(contact_items)}
        <div class="btn-group">
            <a class="btn" href="{html.escape(url)}" target="_blank">{html.escape(L.get("clabel","View listing"))}</a>
        </div>
        {toggle_html}
        <div class="contact-note">{html.escape(L['cnote'])}</div>
        {contact_history_html}
    </div>'''

    # Generate unique ID for this card
    card_id = f"card-{listing_id}" if listing_id else f"card-{hash(url)}"

    return f"""<div class="card{top}{contacted_class}" id="{card_id}">
{contacted_badge}
{img_html}
<div class="card-content">
<div class="card-head"><p class="card-title">{html.escape(L['title'])}</p><span class="price">{html.escape(L['price'])}</span></div>
<div class="area">{html.escape(L['area'])} · {html.escape(L['src'])}</div>
<span class="status {scls}">{html.escape(stext)}</span>
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
        u = L["curl"]
        if "craigslist.org" in u:
            return "cl-" + u.split("/")[-1].replace(".html", "")
        return u
    n_cards = len(all_cards)
    n_card_contacted = sum(1 for L in all_cards if card_key(L) in contacted_ids)
    n_card_dead = sum(1 for L in all_cards if L.get("dead"))
    n_queue = len(queued_ids)
    n_queue_left = len([i for i in queued_ids if i not in contacted_ids])

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>Simon's Stanford Summer 2026 Housing</title>
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
<h1>Simon's Stanford Summer 2026 Housing</h1>
<p class="sub">Under $2,000/mo · Dedicated units only (no housemates) · Hard June 1 start · Within 20 min of Stanford · Good neighborhoods (East Palo Alto excluded)</p>

<div class="banner">
<strong>Priority:</strong> Start with the <strong>$1,890 Palo Alto sublease</strong> — it's the ONLY whole-unit sublease that skips applications.
</div>

<div class="status-panel">
  <div class="status-row">
    <div class="stat"><div class="stat-num ok">{n_total}</div><div class="stat-lbl">reached out<br>(all sources)</div></div>
    <div class="stat"><div class="stat-num">{n_card_contacted}/{n_cards - n_card_dead}</div><div class="stat-lbl">dashboard listings<br>contacted</div></div>
    <div class="stat"><div class="stat-num warn">{n_queue_left}</div><div class="stat-lbl">in queue,<br>not contacted</div></div>
    <div class="stat"><div class="stat-num dead-num">{n_card_dead}</div><div class="stat-lbl">expired<br>(skip)</div></div>
  </div>
  <div class="status-detail">
    <strong>Combined outreach:</strong> {n_auto} auto/assisted send(s) · {n_conf} confirmed-with-message · {n_manual} marked by you on this page → <strong>{n_total} distinct landlord(s) contacted.</strong>
    {"<span style='color:#c62828'>Nothing has actually gone out yet.</span>" if n_total == 0 else ""}
  </div>
  <div class="status-detail">
    <strong>Search:</strong> Craigslist last scan Jun 4 ({len(queued_ids)} matches queued) · SUpost refreshed Jun 5 from your paste ({len(SUPOST)} offers) · Zillow/FB/Apartments/Reddit = manual links below.
  </div>
</div>

<h2>⭐ SUpost — Stanford-only marketplace ({len(SUPOST)} offers · best fit · refreshed Jun 5)</h2>
<div class="banner cl">
<strong>Top priority — these are Stanford students/affiliates near campus.</strong> Pulled from the SUpost housing page you shared (offers only; "housing wanted" posts omitted; female-only and over-$2,000 filtered out). Each <em>View listing</em> button opens the SUpost housing page (supost.com/search/cat/3) — log in with your SUNet and search the title shown on the card (SUpost has no public per-post links). Grab the email/phone from the post and I'll add it here.
</div>
{"".join(card(L) for L in SUPOST)}

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

<h2>Social/peer-to-peer platforms (check manually)</h2>
<table>
<tr><th>Platform</th><th>URL</th><th>Notes</th></tr>
<tr><td>Stanford R&DE</td><td><a href="https://rde.stanford.edu/conferences/summer-intern-housing">rde.stanford.edu</a></td><td>Official Stanford option</td></tr>
<tr><td>SUpost</td><td><a href="https://supost.com">supost.com</a></td><td>Stanford-affiliated classifieds</td></tr>
<tr><td>Facebook Group</td><td><a href="https://www.facebook.com/groups/304588736883828/">Stanford Housing/Sublets</a></td><td>Active student housing market</td></tr>
<tr><td>Facebook Marketplace</td><td><a href="https://www.facebook.com/marketplace/category/propertyrentals">Marketplace rentals</a></td><td>Search: "Palo Alto studio" or "Menlo Park sublet"</td></tr>
<tr><td>RedNote (小红书)</td><td><a href="https://www.xiaohongshu.com/">xiaohongshu.com</a></td><td>Chinese platform — search "Stanford租房"</td></tr>
<tr><td>Reddit r/Stanford</td><td><a href="https://www.reddit.com/r/stanford/">r/stanford</a></td><td>Search "housing" or "sublet summer 2026"</td></tr>
<tr><td>Zillow Rentals</td><td><a href="https://www.zillow.com/homes/for_rent/">zillow.com</a></td><td>Filter: Palo Alto + Menlo Park, max $2000</td></tr>
<tr><td>Apartments.com</td><td><a href="https://www.apartments.com/">apartments.com</a></td><td>Filter by location and move-in date</td></tr>
<tr><td>Craigslist /apa</td><td><a href="https://sfbay.craigslist.org/search/pen/apa?max_price=2000">Search link</a></td><td>Regular rentals — filter for good areas</td></tr>
<tr><td>Craigslist /sub</td><td><a href="https://sfbay.craigslist.org/search/pen/sub?max_price=2000">Search link</a></td><td>Temporary/subleases — best for avoiding applications</td></tr>
</table>

<p style="margin-top:20px;color:#777;font-size:11px">Dashboard updated: June 4, 2026 · East Palo Alto excluded · Use the “Mark as reached out” button on each card to track outreach · Blue = reached out · Amber = queued · Red = expired</p>
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
