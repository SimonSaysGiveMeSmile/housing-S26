#!/usr/bin/env python3
"""Palo Alto / Stanford summer housing dashboard. Default port 5555.
Card layout: each listing shows contact method + location map image.
Updated to exclude East Palo Alto, focus on good neighborhoods only."""
import http.server, socketserver, os, sys, html, mimetypes, json, re
from urllib.parse import urlparse, quote
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))  # repo dir — works locally and in CI
PORT = 5555
MY_EMAIL = "ipo@stanford.edu"  # Email used for contacting landlords

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
.status.go{background:#dcfce7;color:#15803d}.status.check{background:#fef3c7;color:#b45309}.status.warn{background:#fee2e2;color:#b91c1c}.status.dead{background:#e5e7eb;color:#6b7280;text-decoration:line-through}
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
.filtered-out,.sec-hidden{display:none!important}
.filterbar{position:sticky;top:0;z-index:50;background:rgba(255,255,255,.97);backdrop-filter:saturate(1.4) blur(4px);border:1px solid #e2e2e2;border-radius:10px;padding:10px 12px;margin:14px 0;box-shadow:0 1px 6px rgba(0,0,0,.05)}
.fb-row{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.fb-row+.fb-row{margin-top:8px}
.fb-search{flex:1 1 200px;min-width:160px;font-size:14px;padding:8px 12px 8px 30px;border:1px solid #d1d5db;border-radius:7px;background:#fff url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='15' height='15' fill='none' stroke='%239ca3af' stroke-width='2' viewBox='0 0 24 24'%3E%3Ccircle cx='11' cy='11' r='7'/%3E%3Cpath d='M21 21l-4-4'/%3E%3C/svg%3E") 9px center no-repeat}
.fb-search:focus{outline:none;border-color:#2563eb;box-shadow:0 0 0 3px rgba(37,99,235,.12)}
.fb-label{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.04em;color:#9ca3af;margin-right:2px}
.chip{font-size:12.5px;font-weight:600;padding:6px 11px;border:1px solid #d1d5db;border-radius:20px;background:#fff;color:#374151;cursor:pointer;user-select:none;transition:.12s}
.chip:hover{border-color:#9ca3af;background:#f9fafb}
.chip.on{background:#111;color:#fff;border-color:#111}
.chip.on.go{background:#15803d;border-color:#15803d}
.chip.on.check{background:#b45309;border-color:#b45309}
.fb-count{margin-left:auto;font-size:12.5px;color:#6b7280;font-weight:600;white-space:nowrap}
.fb-count b{color:#111}
.fb-preset{font-size:12.5px;font-weight:700;padding:8px 14px;border:none;border-radius:7px;background:#2563eb;color:#fff;cursor:pointer;white-space:nowrap}
.fb-preset:hover{background:#1d4ed8}
.fb-reset{font-size:12px;color:#2563eb;cursor:pointer;background:none;border:none;padding:4px 6px;font-weight:600}
.fb-reset:hover{text-decoration:underline}
#noResults{display:none;text-align:center;color:#6b7280;font-size:14px;padding:40px 20px;border:1px dashed #d1d5db;border-radius:10px;margin:16px 0}
.chip:focus-visible,.fb-search:focus-visible{outline:2px solid #2563eb;outline-offset:2px}
#toTop{position:fixed;right:18px;bottom:18px;z-index:60;width:42px;height:42px;border-radius:50%;border:1px solid #d1d5db;background:#111;color:#fff;font-size:18px;cursor:pointer;opacity:0;pointer-events:none;transition:opacity .2s;box-shadow:0 2px 10px rgba(0,0,0,.18);display:flex;align-items:center;justify-content:center}
#toTop.show{opacity:.9;pointer-events:auto}
#toTop:hover{opacity:1}
@media print{#toTop{display:none}}
.table-wrap{overflow-x:auto;-webkit-overflow-scrolling:touch}
td a{word-break:break-word}
/* collapsible disclosures (declutter the top) + channel directory */
details.disc{border:1px solid #e2e2e2;border-radius:8px;margin:10px 0;background:#fafafa}
details.disc>summary{cursor:pointer;padding:10px 14px;font-weight:600;font-size:13px;color:#333;list-style:none}
details.disc>summary::-webkit-details-marker{display:none}
details.disc>summary::before{content:"▸ ";color:#9ca3af}
details.disc[open]>summary::before{content:"▾ "}
details.disc .disc-body{padding:0 14px 12px;font-size:13px;line-height:1.6;color:#444}
details.disc .disc-body strong{color:#111}
.chan-top{background:#ecfdf5;border:1px solid #a7f3d0;border-radius:8px;padding:12px 14px;margin:10px 0}
.chan-top .lbl{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.04em;color:#15803d}
.chan-top ol{margin:8px 0 0 20px;font-size:13px;line-height:1.7}
details.chan{border:1px solid #e2e2e2;border-radius:8px;margin:8px 0;background:#fff}
details.chan>summary{cursor:pointer;padding:11px 14px;font-weight:700;font-size:14px;color:#111;list-style:none;display:flex;justify-content:space-between;gap:10px}
details.chan>summary::-webkit-details-marker{display:none}
details.chan>summary .cnt{color:#9ca3af;font-weight:500;font-size:12px;white-space:nowrap}
details.chan[open]>summary{border-bottom:1px solid #eee}
.chan-list{padding:4px 14px 10px}
.chan-row{display:flex;flex-wrap:wrap;gap:4px 10px;padding:7px 0;border-top:1px solid #f3f4f6;font-size:13px;align-items:baseline}
.chan-row:first-child{border-top:none}
.chan-row .nm{font-weight:600;flex:0 0 auto}
.chan-row .wy{color:#555;flex:1 1 240px;min-width:150px}
.chan-row .ct{color:#9ca3af;font-size:11.5px;flex:0 0 auto}
/* outreach templates */
.tpl{border:1px solid #e2e2e2;border-radius:8px;margin:8px 0;background:#fff;overflow:hidden}
.tpl-head{display:flex;justify-content:space-between;align-items:center;gap:10px;padding:9px 12px;border-bottom:1px solid #eee;background:#fafafa}
.tpl-title{font-weight:700;font-size:13.5px;color:#111}
.tpl-when{font-size:11.5px;color:#888;padding:6px 12px 0}
.tpl-text{white-space:pre-wrap;font-family:inherit;font-size:12.5px;color:#333;line-height:1.5;padding:8px 12px 12px;margin:0}
.tpl-copy{flex:0 0 auto;border:1px solid #2563eb;background:#fff;color:#2563eb;border-radius:6px;font-size:12px;font-weight:700;padding:5px 14px;cursor:pointer}
.tpl-copy:hover{background:#eff6ff}
.tpl-copy.ok{background:#15803d;color:#fff;border-color:#15803d}
/* to-do list */
.todo-group{margin:6px 0 10px}
.todo-gtitle{font-weight:700;font-size:13px;color:#111;margin:8px 0 4px}
.todo{display:flex;gap:9px;align-items:flex-start;padding:5px 2px;font-size:13px;line-height:1.45;cursor:pointer;border-radius:5px}
.todo:hover{background:#f9fafb}
.todo input{margin-top:2px;flex:0 0 auto;width:16px;height:16px;cursor:pointer}
.todo.done span{text-decoration:line-through;color:#9ca3af}
details.disc.todobox{background:#fff;border-color:#d1d5db}
details.disc.todobox>summary{color:#111;font-size:14px;font-weight:700}
.prog{background:#fffbeb;border:1px solid #fde68a;border-radius:6px;padding:8px 12px;margin:0 0 12px}
.prog-t{font-weight:700;font-size:13px;color:#92400e;margin-bottom:4px}
.prog ul{margin:0;padding-left:18px}
.prog li{font-size:12.5px;line-height:1.5;color:#444;margin:3px 0}
.actionplan{background:#eff6ff;border:1px solid #bfdbfe;border-left:4px solid #2563eb;border-radius:8px;padding:12px 16px;margin:12px 0}
.actionplan .ap-title{font-size:14px;font-weight:800;color:#1e3a8a;margin-bottom:8px}
.actionplan ol{margin:0;padding-left:22px}
.actionplan li{font-size:13px;line-height:1.5;color:#1f2937;margin:5px 0}
.actionplan li strong{color:#111}
.actionplan .ap-out{color:#b91c1c;font-weight:600}
@media (max-width:720px){body{padding:12px}.card,.card.noimg{grid-template-columns:1fr;height:auto}.card-images{width:100%;height:160px}.status-row{flex-wrap:wrap}.stat{flex:1 0 50%;border-bottom:1px solid #eee}.fb-count{margin-left:0;flex-basis:100%}.card-head{flex-wrap:wrap}.price{white-space:normal}table{min-width:560px}}
@media print{.card{break-inside:avoid;height:auto!important}h2{break-after:avoid}.filterbar{display:none}}
"""

# ---- listing data ----------------------------------------------------------
NON_CL = [
 {"top":True,"title":"Stanford R&DE — Official Summer Housing (apply NOW, space-available)","price":"$2,039/mo single studio","status":("check","Apply now · past Apr 30 = not guaranteed"),
  "area":"On campus, Stanford","facts":[
          "ELIGIBLE: Summer Session students from other institutions qualify. BUT the guarantee required applying by Apr 30 — late applicants (you, in June) are assigned SPACE-AVAILABLE after matriculated students. Apply anyway; it's still your most reliable on-campus path.",
          "Cheapest SINGLE-occupancy (private studio): Escondido Village Standard Studio — $2,039/mo ($39 over budget). 8-wk Jun 20–Aug 16 = $3,806; 10-wk to Sep 1 = $4,826.",
          "Other private studios: EV Kennedy Premium $2,515 · EVGR Premium $2,628 · Munger Standard $2,712.",
          "Everything UNDER $2,000 is shared (double/triple): EV Junior 2bd high-rise $1,165, Kennedy Junior 2bd $1,517, Rains 4bd $1,614, EV/Lyman/Rains 2bd $1,628.",
          "Includes furniture + all utilities (water/heat/electric/garbage/sewer) + laundry. Add ~$95 tech fee/qtr, $30 mail fee, house dues.",
          "Default summer-session start July 3; 8-wk ends Aug 16, 10-wk ends Sep 1."],
  "clabel":"Apply → myhousing.stanford.edu",
  "curl":"https://myhousing.stanford.edu",
  "email":"housingassignments@stanford.edu",
  "cnote":"ACTION (Jun 17 — confirmed by HA): (1) Apply at myhousing.stanford.edu → Graduate Housing Application → 2026 Summer → submit. (2) Reply-all to the HA thread (⭐ template) — confirm you applied, ask the right category + bridge. Do NOT email summerhousing@/Conferences — NSSH can't house Summer Session students. Cheapest private studio is EV Standard at $2,039 ($39 over); sub-$2k = shared rooms only.",
  "src":"Stanford R&DE · rates pulled Jun 11"},
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
  "area":"On campus, Stanford (Kennedy grad housing)","status":("dead","TAKEN · found someone"),"dead":True,"replied":True,
  "reply":"bhavyac@stanford.edu (Bhavya Chauhan) replied Jun 19: “I have already found someone for the room.” Closed.",
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
  "area":"Hillsborough (~25 min — out of scope)","status":("go","Cheapest · confirm June start"),
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

 # ---- NEW Jun 14 paste — fresh valuable offers to reach out to ----
 {"top":True,"title":"Studio Apartment in Palo Alto (Jul 6–Aug 22)","mid":"su-pa-studio-jul6-1950","price":"$1,950/mo","src":"SUpost · Stanford-only",
  "area":"Palo Alto","status":("go","Whole studio · under budget · summer"),
  "facts":["WHOLE studio apartment in Palo Alto — your own unit, no housemates.","Dates: July 6 – August 22 (core of the summer).","Under budget at $1,950 — rare for a whole PA unit.","Photo on SUpost. Confirm exact address + utilities."],
  "clabel":"Find post →","curl":"https://www.google.com/search?q=site%3Asupost.com+Studio+Apartment+Available+Palo+Alto+July+6+August+22+1950",
  "cnote":"NEW Jun 10 — one of the only whole PA studios under budget. Message fast; lead with 'in PA now, can tour today, ready to sign + deposit.'"},

 {"top":False,"title":"Private bedroom in house — Palo Alto Professorville","mid":"su-pa-professorville-1850","price":"$1,850/mo","src":"SUpost · Stanford-only",
  "area":"Palo Alto (Professorville)","status":("check","Private room · great location · confirm bath"),
  "facts":["Private bedroom in a house in Palo Alto's Professorville — central, walkable.","Under budget at $1,850. Photo on SUpost.","Confirm: private vs shared bath, exact dates, June/July availability."],
  "clabel":"Find post →","curl":"https://www.google.com/search?q=site%3Asupost.com+Private+bedroom+house+Palo+Alto+Professorville+1850",
  "cnote":"NEW Jun 14 — central PA room, $1,850. Ask if the bath is private and whether it can start in June."},

 {"top":False,"title":"Single bedroom in a 3B/2B apartment","mid":"su-3b2b-single-1456","price":"$1,456/mo","src":"SUpost · Stanford-only",
  "area":"Mountain View (~15 min — out of scope)","status":("check","Room in 3B2B · cheap · confirm location"),
  "facts":["Spacious single bedroom in a 3-bed/2-bath apartment. Photo on SUpost.","Cheap at $1,456 — well under budget.","Location not stated in the post — confirm it's within ~20 min of campus (not EPA/SF) and dates."],
  "clabel":"Find post →","curl":"https://www.google.com/search?q=site%3Asupost.com+Spacious+single+bedroom+3B2B+apartment+1456",
  "cnote":"NEW Jun 13 — cheap room ($1,456). First question: where exactly is it + is it June-able? Skip if EPA/SF/San Jose."},

 {"top":False,"title":"2 rooms in 3BR/2BA next to California Ave (Jul 1)","mid":"su-calave-2rooms-1550","price":"$1,550/mo","src":"SUpost · Stanford-only",
  "area":"Palo Alto (California Ave)","status":("check","Private room · Cal Ave PA · Jul 1"),
  "facts":["Room in a 3BR/2BA apartment next to California Ave, Palo Alto — close to Caltrain + campus.","July 1 move-in. Under budget at $1,550. Photo on SUpost.","Two rooms available — confirm private vs shared bath."],
  "clabel":"Find post →","curl":"https://www.google.com/search?q=site%3Asupost.com+2+Rooms+3BR+2BA+California+Ave+1550",
  "cnote":"NEW Jun 11 — Cal Ave PA room, $1,550, July 1. Good location near Caltrain. Confirm bath + whether June start is possible."},

 {"top":False,"title":"Room in 2BD/2BA — downtown University Ave","mid":"su-dtpa-univave-1900","price":"$1,900/mo","src":"SUpost · Stanford-only",
  "area":"Palo Alto (downtown, University Ave)","status":("check","Room in 2B2B · prime downtown PA"),
  "facts":["1 bedroom in a 2BD/2BA — downtown Palo Alto on University Ave, walk to everything. Photo on SUpost.","Under budget at $1,900.","Confirm private bath, dates, and June/July start."],
  "clabel":"Find post →","curl":"https://www.google.com/search?q=site%3Asupost.com+1+bedroom+2bed+2bath+downtown+University+Avenue+1900",
  "cnote":"NEW (reposted) — prime downtown PA location, $1,900. Confirm dates + private bath."},

 {"top":False,"title":"Den room in a co-op — downtown Palo Alto (short-term)","mid":"su-dtpa-coop-den-1300","price":"$1,300/mo","src":"SUpost · Stanford-only",
  "area":"Palo Alto (downtown co-op)","status":("check","Co-op den · short-term · cheap"),
  "offcriteria":"It's a 'den' room in a co-op (shared house, likely shared bath) and flagged short-term — confirm it covers your full stay.",
  "facts":["Den room in a downtown Palo Alto co-op house. Photo on SUpost.","Cheap at $1,300, central location.","Short-term flagged — confirm length and that it spans your dates."],
  "clabel":"Find post →","curl":"https://www.google.com/search?q=site%3Asupost.com+Den+room+co-op+Palo+Alto+downtown+1300",
  "cnote":"NEW Jun 14 — cheap central co-op room. Good stopgap; confirm it's not just a few weeks."},

 {"top":False,"title":"Furnished 1BR + attached bath — West Menlo Park","mid":"su-westmenlo-1br-2250","price":"$2,250/mo","src":"SUpost · Stanford-only",
  "area":"West Menlo Park (biking distance to Stanford & SLAC)","status":("warn","WHOLE 1BR+bath · ~$250 over budget"),
  "offcriteria":"Over budget at $2,250 (~$250 over your $2,000 cap). Worth it only if you want a whole private 1BR — rare at this size.",
  "facts":["Furnished WHOLE 1BR with its own attached bath — a real private unit, not a room. Photo on SUpost.","West Menlo Park, biking distance to Stanford & SLAC.","$2,250/mo — over budget; flag as a stretch for a whole unit."],
  "clabel":"Find post →","curl":"https://www.google.com/search?q=site%3Asupost.com+Furnished+1+BR+Attached+Bath+West+Menlo+2250",
  "cnote":"NEW Jun 12 — over budget ($2,250) but a genuine furnished whole 1BR+bath. Only chase if you'll stretch ~$250 for a private unit."},

 {"top":False,"title":"Top-floor Redwood City studio (balcony, pool)","mid":"su-rwc-topfloor-studio-2200","price":"$2,200/mo","src":"SUpost · Stanford-only",
  "area":"Redwood City (~15–20 min to Stanford)","status":("warn","WHOLE studio · ~$200 over budget"),
  "offcriteria":"Over budget at $2,200 (~$200 over). Whole studio though — a real private unit. Redwood City, a bit farther out.",
  "facts":["Top-floor whole studio with a large balcony, foothill views, pool, and parking. Photo on SUpost.","Redwood City — ~15–20 min to campus.","$2,200/mo — over budget; flag as a whole-unit stretch."],
  "clabel":"Find post →","curl":"https://www.google.com/search?q=site%3Asupost.com+Top+Floor+Redwood+City+Studio+Large+Balcony+2200",
  "cnote":"NEW Jun 9 — over budget ($2,200) but a whole studio with balcony/pool in RWC. Stretch option if whole-unit matters more than the $200."},

 # ---- WHOLE UNITS (studios / apartments) — best fit ----
 {"top":True,"title":"Fully Furnished EV Studio + Free Bike","mid":"su-ev-freebike","price":"$1,900/mo","src":"SUpost · Stanford-only",
  "area":"On campus, Stanford (Escondido Village)","status":("go","Whole studio · utilities incl · full summer"),
  "facts":["WHOLE studio on campus — your own unit, no housemates.",
           "Dates: June 9 – Sept 22 (covers the whole summer).",
           "Utilities INCLUDED; comes with a free bike.",
           "Under budget at $1,900. Contact via SUpost (Stanford login)."],
  "clabel":"Find post →","curl":"https://supost.com/search/cat/3",
  "cnote":"STRONG — whole studio, utilities incl, full summer, $1,900. Search 'Fully Furnished EV Studio Free Bike' on SUpost."},

 {"top":False,"title":"EVGR-B Private Studio sublet","mid":"su-evgrb-studio","price":"$1,600/mo","src":"SUpost · Stanford-only",
  "area":"On campus, Stanford (EVGR-B)","status":("dead","TAKEN · full sublease period gone"),
  "dead":True,"replied":True,
  "reply":"Faatira (faatiraa@stanford.edu) replied Jun 8: the studio is already taken for the full sublease period. Wished you luck — closed.",
  "facts":["WHOLE studio (your own unit, no housemates) on campus in EVGR-B.",
           "Dates: June 20 – Sept 15. Covers all summer.",
           "Cheapest full-summer whole studio in this batch.",
           "Contact via SUpost (Stanford login)."],
  "clabel":"Find post →","curl":"https://supost.com/search/cat/3",
  "cnote":"TAKEN — Faatira replied Jun 8, full period already subleased. Closed."},

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
 {"top":True,"title":"Private garden suite (bed + bath, own entrance)","mid":"su-garden-suite-130085923","price":"$2,000/mo","src":"SUpost · Stanford-only",
  "area":"Near Palo Alto High (~10 min to Stanford)","status":("dead","REPLIED · available Aug–mid-Sep only (wrong dates)"),"dead":True,"replied":True,
  "reply":"codywang@stanford.edu (Chenxi/Cody Wang) replied Jun 19: unit is available early August – mid-September 2026, offered to send videos. Doesn't fit a June start (and moot now that residential is secured). Closed — but genuinely still open for Aug-onward dates.",
  "offcriteria":"Jun 13 sweep found the dated post: available Aug 1 – Sep 15, 2026 only — does NOT cover your June/July gap; useful only as an Aug-onward bridge.",
  "facts":["Private garden suite: own bedroom + own bathroom + private entrance.",
           "Utilities, laundry, and internet INCLUDED in the $2,000/mo.",
           "Dates: Aug 1 – Sep 15, 2026 (confirmed via direct post Jun 13).",
           "Effectively self-contained near Palo Alto High."],
  "clabel":"Open post →","curl":"https://supost.com/post/index/130085923",
  "cnote":"At budget, utilities incl, private entrance — BUT Aug 1–Sep 15 only (no June/July). Direct post verified Jun 13."},

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
  "area":"On campus, Stanford (Blackwelder)","status":("dead","STOOD DOWN · chose the EVGR assignment"),
  "dead":True,"replied":True,
  "reply":"Sujay Holla Rao (sujayrao@stanford.edu) reopened this Jun 21 via Stanford's official R&DE sublicense path — a genuinely strong, authorized, under-budget backup. STOOD DOWN Jun 25: my EVGR Housing Assignment came through with a confirmed Jun 26 check-in, so I'm going with the assigned unit. Worth a quick thank-you note to Sujay to close it out kindly.",
  "offcriteria":"A room in a shared apartment, not a whole unit.",
  "facts":["Room sublet in Blackwelder, June 19 – Aug 31. Was the cheapest I'd messaged: $1,165, under budget.","AUTHORIZED route: official R&DE sublicense (form + proof of affiliation + office approval) — the legitimacy the EVGR-B / $2,700 option lacked.","Closed because the EVGR assignment landed first with a set check-in; kept here as a record of a solid authorized backup."],
  "clabel":"Find post →","curl":"https://supost.com/search/cat/3",
  "cnote":"Closed by choice — went with the confirmed EVGR assignment (check-in Jun 26). This was a strong authorized backup; no longer needed."},

 {"top":True,"title":"1BR Hulme Sublease (Jun 21–Sep 14)","mid":"su-hulme-1br","price":"$2,500/mo","src":"SUpost · Stanford-only",
  "area":"On campus, Stanford (Hulme)","status":("dead","WAITLISTED · wrong dates · declined"),"dead":True,"replied":True,
  "reply":"andaru@stanford.edu (Keanu Andaru) replied Jun 19: another tenant already moved forward via the R&DE process, so you're waitlisted; offered 7/25–9/1 instead. You declined (needed a June start). Closed.",
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
  "area":"On campus, Stanford (Escondido Village)","status":("dead","TAKEN · poster Selim confirmed"),
  "dead":True,"replied":True,
  "reply":"Selim Amar (selama@stanford.edu) replied Jun 11: it's taken, wished you luck. You replied 'all the best.' Closed.",
  "offcriteria":"$39 over budget and short window (June 21 to ~July 20 only).",
  "facts":["Whole EV studio (Studio 1), June 21 to ~July 20, flexible.","Furnished. +$50 house dues.","Messaged on SUpost — awaiting reply."],
  "clabel":"Open post →","curl":"https://supost.com/post/index/130076651",
  "cnote":"TAKEN — Selim confirmed Jun 11. Closed."},

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

 # ---- Jun 13 SUpost paste — filtered NEW offers (wanted-posts/EPA/SF/over-budget/female-only removed) ----
 {"top":True,"title":"Renovated Rains sublet (Jun 22–Sep 18)","mid":"su-rains-renov-1600","price":"$1,600/mo","src":"SUpost · Jun 13 paste",
  "area":"On campus, Stanford (Rains grad housing)","status":("dead","TAKEN · renter found"),
  "dead":True,"replied":True,
  "reply":"worledge@stanford.edu — the post title now reads “[Renter found!!!!]” (Jun 16). Taken. Closed.",
  "facts":["Renovated Rains sublet, June 22 – Sept 18 — covers nearly your whole summer.","Under budget at $1,600, on campus.","Best new date-match of this paste."],
  "clabel":"Find post →","curl":"https://supost.com/search/cat/3",
  "cnote":"TAKEN Jun 16 — poster (worledge@) marked it “Renter found.” Closed."},

 {"top":True,"title":"Stanford Lyman 2B/1B, furnished (Jun 27–Aug 22)","mid":"su-lyman-2b1b-1684","price":"$1,684/mo","src":"SUpost · Jun 13 paste",
  "area":"On campus, Stanford (Lyman grad housing)","status":("go","On campus · furnished · under budget"),
  "offcriteria":"Lyman = grad housing — confirm whole-unit vs a room in the 2B/1B + eligibility.",
  "facts":["Fully furnished Stanford Lyman 2B/1B, June 27 – Aug 22.","Under budget at $1,684, on campus."],
  "clabel":"Find post →","curl":"https://supost.com/search/cat/3",
  "cnote":"NEW Jun 13 — Lyman 2B/1B furnished, $1,684, Jun 27–Aug 22, on campus. Confirm room vs unit + eligibility."},

 {"top":True,"title":"EVGR on-campus sublet (Jul–Sep)","mid":"su-evgr-julsep-1659","price":"$1,659/mo","src":"SUpost · Jun 13 paste",
  "area":"On campus, Stanford (EVGR)","status":("dead","TAKEN · room no longer available"),"dead":True,"replied":True,
  "reply":"smirchan@stanford.edu (Suvir Mirchandani) replied Jun 19: “the room is no longer available.” Taken. Closed.",
  "offcriteria":"Starts in July — leaves a June gap (pair with a June bridge). Confirm studio vs room + eligibility.",
  "facts":["On-campus EVGR summer sublet, July – September.","Under budget at $1,659."],
  "clabel":"Find post →","curl":"https://supost.com/search/cat/3",
  "cnote":"NEW Jun 13 — EVGR on-campus, $1,659, Jul–Sep. June gap — pair with a bridge. Confirm studio vs room + eligibility."},

 {"top":True,"title":"Private room + private bath, Atherton","mid":"su-atherton-room-1300","price":"$1,300/mo","src":"SUpost · Jun 13 paste",
  "area":"Atherton (~15 min to Stanford)","status":("go","Private room+bath · cheap · close"),
  "offcriteria":"Private room in a house (not a whole unit); confirm dates + June availability.",
  "facts":["Private room WITH private bath in Atherton (photo on SUpost).","Under budget at $1,300 — one of the cheapest room+bath options.","~15 min to Stanford, upscale/quiet area."],
  "clabel":"Find post →","curl":"https://supost.com/search/cat/3",
  "cnote":"NEW Jun 13 — Atherton private room+bath, $1,300, close to campus. Cheap + private bath. Confirm dates."},

 {"top":False,"title":"Room — Palo Alto (Stanford Villa), late June/early July","mid":"su-stanfordvilla-1701","price":"$1,701/mo","src":"SUpost · Jun 13 paste",
  "area":"Palo Alto (Stanford Villa)","status":("check","Room · late-June move-in"),
  "offcriteria":"Room (shared), not a whole unit; confirm private bath + exact dates.",
  "facts":["Room in Palo Alto (Stanford Villa), move-in late June / early July.","Under budget at $1,701 — June-ish start helps your hotel gap."],
  "clabel":"Find post →","curl":"https://supost.com/search/cat/3",
  "cnote":"NEW Jun 13 — PA Stanford Villa room, $1,701, late-June/early-July. Confirm private bath + dates."},

 {"top":False,"title":"Room — huge modern Downtown Palo Alto house","mid":"su-dtpa-house-1850","price":"$1,850/mo","src":"SUpost · Jun 13 paste",
  "area":"Downtown Palo Alto","status":("check","Room · top location"),
  "offcriteria":"Room (shared house), not a whole unit; confirm private bath + dates.",
  "facts":["Room in a huge modern house in Downtown Palo Alto.","Under budget at $1,850; walkable downtown location."],
  "clabel":"Find post →","curl":"https://supost.com/search/cat/3",
  "cnote":"NEW Jun 13 — Downtown PA house room, $1,850. Great location. Confirm bath + dates."},

 {"top":False,"title":"Room — quiet Palo Alto neighborhood","mid":"su-quietpa-1600","price":"$1,600/mo","src":"SUpost · Jun 13 paste",
  "area":"Palo Alto","status":("check","Room · under budget"),
  "offcriteria":"Room (shared), not a whole unit; confirm private bath + dates.",
  "facts":["Room in a quiet, beautiful Palo Alto neighborhood (photo on SUpost).","Under budget at $1,600."],
  "clabel":"Find post →","curl":"https://supost.com/search/cat/3",
  "cnote":"NEW Jun 13 — quiet PA room, $1,600. Confirm bath + dates."},

 {"top":False,"title":"Room in 2bd/1ba — Menlo Park (Jul 1)","mid":"su-menlo-2bd-1400","price":"$1,400/mo","src":"SUpost · Jun 13 paste",
  "area":"Menlo Park (~10 min to Stanford)","status":("check","Room · cheap · close"),
  "offcriteria":"Room (one housemate), shared bath; starts July 1 (June gap).",
  "facts":["One room in a 2bed/1bath apartment in Menlo Park, available July 1 (photo on SUpost).","Under budget at $1,400 — cheap and close to campus."],
  "clabel":"Find post →","curl":"https://supost.com/search/cat/3",
  "cnote":"NEW Jun 13 — Menlo 2bd/1ba room, $1,400, Jul 1. Cheap + close. June gap; shared bath."},

 {"top":False,"title":"EV Studio 6 sublet (Jul 2–Sep 17)","mid":"su-ev-studio6-2049","price":"$2,049/mo","src":"SUpost · Jun 13 paste",
  "area":"On campus, Stanford (Escondido Village)","status":("warn","Whole studio · $49 over · July start"),
  "offcriteria":"$49 over your $2,000 limit; starts July 2 (June gap).",
  "facts":["Whole EV studio (Studio 6) on campus, July 2 – Sept 17 (photo on SUpost).","$2,049, just over budget — but a whole unit on campus."],
  "clabel":"Find post →","curl":"https://supost.com/search/cat/3",
  "cnote":"NEW Jun 13 — whole EV Studio 6, $2,049, Jul 2–Sep 17. Just over budget + June gap."},

 {"top":False,"title":"EV studio stopgap ($700 total · Jun 27–Jul 6)","mid":"su-ev-studio-700","price":"$700 total (~10 days)","src":"SUpost · Jun 13 sweep",
  "area":"On campus, Stanford (Escondido Village)","status":("warn","Whole studio · ~10-day STOPGAP only"),
  "offcriteria":"Covers only Jun 27 – Jul 6 (~10 days) — a stopgap, not a summer place; and there's a gap from today to Jun 27 it doesn't cover. Eligibility likely requires Stanford affiliation.",
  "facts":["Whole EV studio on campus, June 27 – July 6 (~10 days), $700 for the period (the '$700' was a short-stay total, not monthly).","Verified-active (posted Jun 11).","Use only to get out of the hotel briefly while you lock a longer place."],
  "clabel":"Open post →","curl":"https://supost.com/post/index/130086936",
  "cnote":"Jun 13 sweep clarified: this is a ~10-day stopgap (Jun 27–Jul 6) at $700 total, not a cheap monthly studio. Bridge only."},

 {"top":True,"title":"On-campus whole studio (Jun 15–Aug 31, all-incl)","mid":"su-studio-15jun-31aug-2100","price":"$2,100/mo","src":"SUpost · Jun 13 sweep",
  "area":"On campus, Stanford","status":("check","Whole studio · full summer · at tolerance"),
  "offcriteria":"$100 over your $2,000 base (within ~$2,100 tolerance). Restricted to Stanford affiliates, undergrads excluded — confirm you qualify. Move-in Jun 15 is days away — act fast.",
  "facts":["Whole/dedicated studio on campus, June 15 – Aug 31 (full summer), fully furnished.","All utilities included; 0-min commute.","Verified-active (posted May 29)."],
  "clabel":"Open post →","curl":"https://supost.com/post/index/130085715",
  "cnote":"Jun 13 sweep — whole on-campus furnished studio, Jun 15–Aug 31, all-incl, $2,100. Confirm eligibility; move-in is imminent."},

 {"top":False,"title":"Idyllwild co-op room (Jun 17–Sep 15)","mid":"su-idyllwild-coop-950","price":"$950/mo (~$1,200 all-in)","src":"SUpost · Jun 13 sweep",
  "area":"Los Altos Hills (~10 min to Stanford)","status":("check","Co-op room · cheapest · full summer"),
  "offcriteria":"Private room in a shared co-op (8–10 residents); private bath NOT confirmed (likely communal). Requires co-op participation: cook ~3x/month + chores.",
  "facts":["Room in the Idyllwild co-op, June 17 – Sept 15 (full summer, dates negotiable).","~$1,200/mo ALL-IN — food AND utilities included — far under budget.","Established Stanford-affiliated co-op, ~10 min to campus. Verified-active (posted May 5)."],
  "clabel":"Open post →","curl":"https://supost.com/post/index/130076375",
  "cnote":"Jun 13 sweep — Idyllwild co-op, ~$1,200 all-in (incl. food), Jun 17–Sep 15. Cheapest full-summer option; co-op chores required."},

 # ---- Jun 13 SUpost paste #2 (earlier pages Jun 3–8) — additional NEW offers ----
 {"top":True,"title":"EVGR Premium 2b/2b for 1 person (Jul 7–Aug 18)","mid":"su-evgr-premium-2b2b-2000","price":"$2,000/mo","src":"SUpost · Jun 13 paste",
  "area":"On campus, Stanford (EVGR Premium)","status":("go","Effectively whole · on campus · at budget"),
  "offcriteria":"Starts July 7 (June gap); ends Aug 18 (no Sept). 'For 1 person' = you'd have the 2b/2b to yourself. Confirm eligibility (grad/affiliate).",
  "facts":["EVGR Premium 2b/2b sublet for ONE person — effectively a whole apartment to yourself, on campus.","At your $2,000 ceiling; July 7 – Aug 18.","Fully on-campus, 0-min commute."],
  "clabel":"Find post →","curl":"https://supost.com/search/cat/3",
  "cnote":"NEW Jun 13 — EVGR Premium 2b/2b for 1 (you'd have it alone), $2,000, Jul 7–Aug 18, on campus. Confirm eligibility + the June gap."},

 {"top":False,"title":"EVGR-C private bed + bath (Jul 5–Aug 8)","mid":"su-evgrc-jul5-aug8-2000","price":"$2,000/mo","src":"SUpost · Jun 13 paste",
  "area":"On campus, Stanford (EVGR-C)","status":("check","Private room+bath · on campus · at budget"),
  "offcriteria":"Jul 5 – Aug 8 only (June gap + no Sept). Private room in a shared apartment. Confirm eligibility.",
  "facts":["Private bedroom AND private bathroom in EVGR-C on campus.","At your $2,000 ceiling; July 5 – Aug 8.","On campus, 0-min commute."],
  "clabel":"Find post →","curl":"https://supost.com/search/cat/3",
  "cnote":"NEW Jun 13 — EVGR-C private bed+bath, $2,000, Jul 5–Aug 8, on campus. June gap; confirm eligibility."},

 {"top":False,"title":"Room — Rains 2BR (Jul 3–Aug 14)","mid":"su-rains-2br-jul3-1700","price":"$1,700/mo","src":"SUpost · Jun 13 paste",
  "area":"On campus, Stanford (Rains)","status":("check","Room · on campus · under budget"),
  "offcriteria":"Room in a 2BR (one housemate); Jul 3 – Aug 14 only (June gap + no Sept). Confirm eligibility (grad housing).",
  "facts":["Room in a 2BR Rains apartment on campus, July 3 – Aug 14.","Under budget at $1,700."],
  "clabel":"Find post →","curl":"https://supost.com/search/cat/3",
  "cnote":"NEW Jun 13 — Rains 2BR room, $1,700, Jul 3–Aug 14, on campus. June gap; confirm eligibility."},

 {"top":False,"title":"Private bed + bath, College Terrace 2B/2B","mid":"su-collegeterrace-2b2b-2150","price":"$2,150/mo","src":"SUpost · Jun 13 paste",
  "area":"College Terrace, Palo Alto (adjacent to campus)","status":("warn","Private room+bath · top location · over budget"),
  "offcriteria":"$150 over your $2,000 base (above the ~$2,100 stretch). Private room in a 2B/2B (one housemate), not a whole unit.",
  "facts":["Private bedroom + private bathroom in a 2B/2B College Terrace apartment (photo on SUpost).","College Terrace is right next to campus — excellent location.","$2,150 — over budget; confirm dates."],
  "clabel":"Find post →","curl":"https://supost.com/search/cat/3",
  "cnote":"NEW Jun 13 — College Terrace private bed+bath, $2,150 (over), great location. Confirm dates; only if you stretch budget."},

 {"top":False,"title":"Private bed + attached bath, Stanford West 2B/2B","mid":"su-stanfordwest-2b2b-2200","price":"$2,200/mo","src":"SUpost · Jun 13 paste",
  "area":"Stanford West (on/near campus)","status":("dead","TAKEN · rented out"),"dead":True,"replied":True,
  "reply":"ljy007@stanford.edu (Jiayi Li) replied Jun 19: the Stanford West room “has already been rented out.” Closed.",
  "offcriteria":"$200 over your $2,000 base. Private room in a 2B/2B (one housemate), not a whole unit.",
  "facts":["Spacious private bedroom with attached bathroom in a 2B/2B Stanford West apartment (photo on SUpost).","$2,200 — over budget; confirm dates."],
  "clabel":"Find post →","curl":"https://supost.com/search/cat/3",
  "cnote":"NEW Jun 13 — Stanford West private bed+bath, $2,200 (over). Confirm dates; only if you stretch."},

 {"top":False,"title":"Room — downtown PA 4B2B (Jul 1)","mid":"su-dtpa-4b2b-jul1-1794","price":"$1,794/mo","src":"SUpost · Jun 13 paste",
  "area":"Downtown Palo Alto","status":("check","Room · top location · under budget"),
  "offcriteria":"Room in a 4B2B (shared bath, several housemates); July 1 start (June gap). Confirm private vs shared bath.",
  "facts":["Sunny room in a 4B2B in downtown Palo Alto, move-in July 1 (photo on SUpost).","Under budget at $1,794; walkable downtown location."],
  "clabel":"Find post →","curl":"https://supost.com/search/cat/3",
  "cnote":"NEW Jun 13 — downtown PA 4B2B room, $1,794, Jul 1. Great location; confirm bath + June gap."},

 {"top":False,"title":"Master bedroom, 2B2B near campus (Aug 1)","mid":"su-2b2b-nearcampus-aug1-1700","price":"$1,700/mo","src":"SUpost · Jun 13 paste",
  "area":"Near Stanford campus","status":("check","Room · under budget · Aug start"),
  "offcriteria":"Move-in ~Aug 1 — does NOT cover June/July. Room in a 2B2B (one housemate). Useful only as an Aug-onward option.",
  "facts":["Master bedroom in a 2B2B apartment near campus, move-in around Aug 1.","Under budget at $1,700."],
  "clabel":"Find post →","curl":"https://supost.com/search/cat/3",
  "cnote":"NEW Jun 13 — 2B2B master near campus, $1,700, ~Aug 1. Aug-onward only; confirm private bath."},

 {"top":False,"title":"2 rooms — Menlo Park (Jul 1)","mid":"su-menlo-2rooms-jul1-1590","price":"$1,590/mo","src":"SUpost · Jun 13 paste",
  "area":"Menlo Park (~10 min to Stanford)","status":("check","Room · cheap · close · Jul 1"),
  "offcriteria":"Room (shared), July 1 start (June gap). Confirm private vs shared bath.",
  "facts":["2 rooms for rent in Menlo Park, starting July 1.","Under budget at $1,590; ~10 min to campus."],
  "clabel":"Find post →","curl":"https://supost.com/search/cat/3",
  "cnote":"NEW Jun 13 — Menlo Park rooms, $1,590, Jul 1. Cheap + close; confirm bath + June gap."},

 {"top":False,"title":"2 rooms — Menlo Park 3bd/2ba near campus","mid":"su-menlo-3bd-nearcampus-1390","price":"$1,390/mo","src":"SUpost · Jun 13 paste",
  "area":"Menlo Park (near campus)","status":("check","Room · cheapest Menlo · near campus"),
  "offcriteria":"Room in a 3bd/2ba (shared bath, housemates). Confirm dates + June availability.",
  "facts":["2 room openings in a 3bedroom/2bath near campus, Menlo Park.","Cheapest Menlo room at $1,390."],
  "clabel":"Find post →","curl":"https://supost.com/search/cat/3",
  "cnote":"NEW Jun 13 — Menlo 3bd/2ba rooms, $1,390, near campus. Cheap; confirm dates + bath."},

 {"top":False,"title":"Barnes Midrise 1BR — STOPGAP (Jun 21–28)","mid":"su-barnes-midrise-jun21-28-800","price":"$800 (~1 week)","src":"SUpost · Jun 13 paste",
  "area":"On campus, Stanford (Barnes Midrise)","status":("warn","Whole 1BR · ~1-week STOPGAP only"),
  "offcriteria":"Covers only Jun 21–28 (~1 week) — a bridge, not a summer place. Confirm eligibility.",
  "facts":["Subletting a 1BR in Barnes Midrise on campus, June 21 – 28.","$800 for the ~1-week window.","Use only to bridge out of the hotel while locking a longer place."],
  "clabel":"Find post →","curl":"https://supost.com/search/cat/3",
  "cnote":"NEW Jun 13 — Barnes Midrise 1BR, $800, Jun 21–28 (~1 wk). Bridge only."},
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
 # Jun 13 paste — text-only offers (no URL in paste): land on a Google search.
 "Renovated Rains sublet (Jun 22–Sep 18)": "Renovated Rains Sublet June 22 September 18 1600",
 "Stanford Lyman 2B/1B, furnished (Jun 27–Aug 22)": "Stanford Lyman 2B 1B fully furnished June 27 August 22 1684",
 "EVGR on-campus sublet (Jul–Sep)": "On-Campus Summer Sublet EVGR July September 1659",
 "Private room + private bath, Atherton": "Private room private bath Atherton 1300",
 "Room — Palo Alto (Stanford Villa), late June/early July": "Room Palo Alto Stanford Villa move-in late June early July 1701",
 "Room — huge modern Downtown Palo Alto house": "Room Available Huge Modern Downtown Palo Alto House 1850",
 "Room — quiet Palo Alto neighborhood": "room quiet and beautiful neighborhood Palo Alto 1600",
 "Room in 2bd/1ba — Menlo Park (Jul 1)": "One room 2 bed 1 bath apartment Menlo Park July 1st 1400",
 # Jun 13 paste #2 — earlier-page offers (no URL in paste): Google search.
 "EVGR Premium 2b/2b for 1 person (Jul 7–Aug 18)": "EVGR Premium 2b 2b Sublet July 7 Aug 18 1 person 2000",
 "EVGR-C private bed + bath (Jul 5–Aug 8)": "Room sublease 7/5 8/8 EVGR-C private bed bathroom 2000",
 "Room — Rains 2BR (Jul 3–Aug 14)": "Room 2BR Rains apartment July 3 August 14 1700",
 "Private bed + bath, College Terrace 2B/2B": "Private bedroom bathroom 2B 2B College Terrace 2150",
 "Private bed + attached bath, Stanford West 2B/2B": "Spacious private bedroom attached bathroom 2B 2B Stanford West 2200",
 "Room — downtown PA 4B2B (Jul 1)": "Sunny room downtown PA 4B2B move in July 1st 1794",
 "Master bedroom, 2B2B near campus (Aug 1)": "Master bedroom 2B2B apartment near Campus August 1 1700",
 "2 rooms — Menlo Park (Jul 1)": "2 rooms for rent Menlo Park July 1 1590",
 "2 rooms — Menlo Park 3bd/2ba near campus": "2 rooms openings 3bedroom 2bathroom near campus Menlo Park 1390",
 "Barnes Midrise 1BR — STOPGAP (Jun 21–28)": "Subletting 1 BR Barnes Midrise June 21 28 800",
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
 # Jun 13 — direct post URLs confirmed by the web sweep.
 "su-ev-studio6-2049": "https://supost.com/post/index/130086984",
 "su-ev-studio-700": "https://supost.com/post/index/130086936",
 "su-studio-15jun-31aug-2100": "https://supost.com/post/index/130085715",
 "su-idyllwild-coop-950": "https://supost.com/post/index/130076375",
  # ---- Jun 15: direct URLs matched + verified by the SUpost-match workflow ----
 "Furnished private room + bath, Palo Alto (available now)": "https://supost.com/post/index/130085126",
 "On-campus Stanford studio sublet (June\u2013July)": "https://supost.com/post/index/130035641",
 "Private bed + bath, 5-min walk to Stanford (2B2B)": "https://supost.com/post/index/130083357",
 "Small private room + private bath, Palo Alto": "https://supost.com/post/index/130085567",
 "su-2b2b-nearcampus-aug1-1700": "https://supost.com/post/index/130086561",
 "su-barnes-midrise-jun21-28-800": "https://supost.com/post/index/130086462",
 "su-calave-2rooms-1550": "https://supost.com/post/index/130086870",
 "su-campus-stopgap-jun9": "https://supost.com/post/index/130086276",
 "su-dtpa-coop-den-1300": "https://supost.com/post/index/130087136",
 "su-dtpa-house-1850": "https://supost.com/post/index/130086850",
 "su-ev-lowrise-apt": "https://supost.com/post/index/130084710",
 "su-ev-studio-jun8-sep12": "https://supost.com/post/index/130085893",
 "su-evgr-julsep-1659": "https://supost.com/post/index/130086655",
 "su-evgr-premium-2b2b-2000": "https://supost.com/post/index/130086385",
 "su-evgrc-jul5-aug8-2000": "https://supost.com/post/index/130086250",
 "su-garden-suite-130085923": "https://supost.com/post/index/130085923",
 "su-lyman-2b1b-1684": "https://supost.com/post/index/130086714",
 "su-pa-professorville-1850": "https://supost.com/post/index/130087131",
 "su-pa-studio-jul6-1950": "https://supost.com/post/index/130086786",
 "su-quietpa-1600": "https://supost.com/post/index/130087117",
 "su-rains-2br-jul3-1700": "https://supost.com/post/index/130085267",
 "su-rains-renov-1600": "https://supost.com/post/index/130086959",
 "su-stanfordvilla-1701": "https://supost.com/post/index/130086784",
 "su-stanfordwest-2b2b-2200": "https://supost.com/post/index/130086112",
}
# Poster emails captured from Simon's SUpost Messages inbox (Jun 14) — lets him
# follow up directly instead of going back through the SUpost relay.
_SUPOST_EMAIL = {
 "su-ev-studio-700": "lamprini@stanford.edu",
 "su-rains-renov-1600": "worledge@stanford.edu",
 "su-evgrb-studio": "faatiraa@stanford.edu",
 "su-ev-studio1-jun21": "selama@stanford.edu",
 "su-1b-2bhk-noflatmate": "prashp@stanford.edu",
 "su-3br-townhouse-jun1": "silvaste@alumni.stanford.edu",
 "su-ev-studio-jun12-sep15": "trutter@stanford.edu",
 "su-ev-studio-latejune-midaug": "hlepp@stanford.edu",
 "su-rains-2b1b": "sankired@stanford.edu",
 "su-blackwelder": "sujayrao@stanford.edu",
 "su-evgrc-spacious-room": "wurgaft@stanford.edu",
 "su-evgr-summer": "rrfang@stanford.edu",
 "su-ev-studio-jun8-sep12": "bbass@stanford.edu",
 "su-stanford-studio-jun15": "genge@stanford.edu",
 "su-hulme-1br": "andaru@stanford.edu",
 "su-kennedy-jun23-sep10": "bhavyac@stanford.edu",
 "su-kennedy-commons-1570": "ba624@stanford.edu",
 "su-ev-freebike": "jalimi@stanford.edu",
 "su-ev-lowrise-apt": "matthho@stanford.edu",
  # ---- Jun 16: poster emails captured from Simon's direct-email sends ----
 "su-studio-15jun-31aug-2100": "osahin25@stanford.edu",
 "su-ev-lowrise-room": "afrancav@stanford.edu",
  # ---- Jun 15: poster emails captured during the URL match ----
 "Furnished private room + bath, Palo Alto (available now)": "arberg@stanford.edu",
 "On-campus Stanford studio sublet (June\u2013July)": "elestant@stanford.edu",
 "Private bed + bath, 5-min walk to Stanford (2B2B)": "hrmeym@stanford.edu",
 "Small private room + private bath, Palo Alto": "yangt@stanford.edu",
 "su-2b2b-nearcampus-aug1-1700": "zihanzhu@stanford.edu",
 "su-barnes-midrise-jun21-28-800": "juliarz@stanford.edu",
 "su-calave-2rooms-1550": "cbargell@stanford.edu",
 "su-campus-stopgap-jun9": "horence@stanford.edu",
 "su-dtpa-coop-den-1300": "asix@stanford.edu",
 "su-dtpa-house-1850": "agarwald@stanford.edu",
 "su-ev-lowrise-apt": "matthho@stanford.edu",
 "su-ev-studio-jun8-sep12": "bbass@stanford.edu",
 "su-evgr-julsep-1659": "smirchan@stanford.edu",
 "su-evgr-premium-2b2b-2000": "youngdav@stanford.edu",
 "su-evgrc-jul5-aug8-2000": "ruricher@stanford.edu",
 "su-garden-suite-130085923": "codywang@stanford.edu",
 "su-lyman-2b1b-1684": "shoaib@stanford.edu",
 "su-pa-professorville-1850": "aalbuque@alumni.stanford.edu",
 "su-pa-studio-jul6-1950": "rajaj@stanford.edu",
 "su-quietpa-1600": "agnestin@alumni.stanford.edu",
 "su-rains-2br-jul3-1700": "sankired@stanford.edu",
 "su-rains-renov-1600": "worledge@stanford.edu",
 "su-stanfordvilla-1701": "rcenteio@stanford.edu",
 "su-stanfordwest-2b2b-2200": "ljy007@stanford.edu",
}
for _L in SUPOST:
    _key = _L.get("mid") or _L["title"]
    if _key in _SUPOST_EMAIL and not _L.get("email"):
        _L["email"] = _SUPOST_EMAIL[_key]
    if _key in _SUPOST_DIRECT:
        _L["curl"] = _SUPOST_DIRECT[_key]
        _L["clabel"] = "Open post →"
        continue
    _q = _SUPOST_Q.get(_L["title"])
    if _q:
        _L["curl"] = "https://www.google.com/search?q=" + _uq.quote(f"site:supost.com {_q}")
        _L["clabel"] = "Find post →"

# ---- FRESH LEADS — Jun 13 web sweep (off-SUpost: Craigslist, sublet.com, coliving, etc.)
# 3 parallel search waves across ~30 sources, each lead verified live. Ordered by
# status (go → check → warn). The bottom line: under-$2k WHOLE units barely exist
# for a summer sublet — the realistic path is a furnished private-room+private-bath
# in Mountain View / Los Altos / Redwood City, plus the on-campus SUpost studios.
FRESH_LEADS = [
 # ---- GO: in budget, June-able, whole-unit or private-bath ----
 {"top":True,"title":"Suite Spot coliving — private en-suite room (Redwood City)","mid":"web-suitespot-209madison","price":"$1,700/mo (6+mo) · $2,300 short","src":"Suite Spot · Jun 13 sweep",
  "area":"Redwood City (209 Madison Ave, ~15-20 min to Stanford)","status":("go","Private room+ensuite · June 19 · pro-managed"),
  "offcriteria":"The $1,700 rate needs a 6+ month lease (runs past summer); a pure-summer term is quoted $2,300 (over budget). Private room in a managed 4BD/4BA home, not a whole unit.",
  "facts":["Furnished private room WITH private en-suite bath in a professionally-managed coliving home.","$1,700/mo on the 6+ month rate (in budget); June 19 move-in; flexible lease.","Verified live on AppFolio. Contact golan@suitespotmgmt.com / 562-479-7609 — ask for a summer-length term."],
  "clabel":"View listing","curl":"https://suitespot.appfolio.com/listings/detail/826b3b1a-1ffc-45d6-91c4-3b07e2679c41",
  "cnote":"STRONGEST new lead: managed coliving, private en-suite, $1,700 (6+mo), Jun 19, RWC. Email to negotiate a summer term (short-term quoted $2,300)."},

 {"top":True,"title":"Furnished room + private bath, Redwood City (Orchard Ave)","mid":"web-subletcom-4777217","price":"$1,200/mo (utils incl)","src":"sublet.com · Jun 13 sweep",
  "area":"Redwood City (Orchard Ave, ~15-20 min to Stanford)","status":("go","Private room+bath · cheap · month-to-month"),
  "offcriteria":"Private room (in a studio unit), not a whole unit. No posting date shown → likely-active; confirm June availability + exact address via the listing's message form.",
  "facts":["Furnished private room WITH private bath, utilities included.","$1,200/mo — well under budget; true month-to-month, renewable.","Earliest move-in flexible (covers June). Verified on the individual sublet.com listing page."],
  "clabel":"View listing","curl":"https://www.sublet.com/property/4777217/",
  "cnote":"Great value: $1,200 furnished room+private bath, RWC, M2M, utils incl. Confirm June + address. Likely active Jun 13."},

 {"top":True,"title":"Fully furnished studio, available now (Sunnyvale)","price":"$1,970/mo + utils","src":"Craigslist /apa · Jun 13 sweep",
  "area":"Sunnyvale (San Ramon Ave, ~20-25 min to Stanford)","status":("go","Whole studio · furnished · available NOW"),
  "offcriteria":"Sunnyvale is ~20-25 min out (at/just past your radius edge). Utilities NOT included; bring own bedding. Post showed a 'flagged' marker — book a showing ASAP before it's removed.",
  "facts":["Whole/dedicated furnished studio (0BR/1BA): private patio, walk-in closet, in-unit W/D, weekly cleaning, WiFi, parking.","$1,970 — under budget; available NOW for an immediate June move-in.","Verified-active (posted May 25). Contact 'Attia'."],
  "clabel":"View listing","curl":"https://sfbay.craigslist.org/sby/apa/d/sunnyvale-fully-furnished-studio-washer/7936765857.html",
  "cnote":"Best whole-unit-available-now: furnished Sunnyvale studio, $1,970, in-unit W/D + weekly cleaning. ~20-25 min out; act fast (flagged). Verified Jun 13."},

 {"top":True,"title":"Private room + bath, separate entrance (Emerald Hills, RWC)","price":"$1,475/mo","src":"Craigslist /roo · Jun 13 sweep",
  "area":"Emerald Hills, Redwood City (~15-20 min to Stanford)","status":("go","Private room+bath · cheapest · June 5"),
  "offcriteria":"Landlord prefers 'full-time working professionals' / 'no work-from-home' — confirm they'll take a summer student. 3-month min, single occupant, utilities shared (not incl).",
  "facts":["Furnished private room (~300 sqft) + private bath + SEPARATE entrance + private living area/balcony in a single-family home.","$1,475 — cheapest private-bath option found; June 5 start; off-street parking.","Verified-active (posted May 17, updated Jun 10)."],
  "clabel":"View listing","curl":"https://sfbay.craigslist.org/pen/roo/d/redwood-city-large-bedroom-private-bath/7934928950.html",
  "cnote":"Cheapest private bath ($1,475), sep entrance, furnished, June 5, RWC. Confirm they accept a student. Verified Jun 13."},

 {"top":True,"title":"Private room + private marble bath, all-incl (Menlo Park)","price":"$1,495/mo (all utils + fiber)","src":"Craigslist /roo · Jun 13 sweep",
  "area":"Menlo Park (Hollyburne Ave, ~10-15 min to Stanford)","status":("go","Private room+bath · all incl · under budget"),
  "offcriteria":"Move-in date NOT on the listing — confirm June start + that it runs through Aug/Sep. Shared single-family home with one housemate (not a whole unit). Below-market price → view in person, don't wire deposits sight-unseen.",
  "facts":["Private bedroom WITH private marble bath (walk-in shower) in a 2BR home.","ALL utilities + AT&T fiber included; furnished; in-unit W/D; walk-in closet; deck; parking.","$1,495 — well under budget. Verified-active (posted Jun 5, updated Jun 10)."],
  "clabel":"View listing","curl":"https://sfbay.craigslist.org/pen/roo/d/menlo-park-beautiful-one-bedroom-with/7939097965.html",
  "cnote":"Strong: Menlo private marble bath, all utils+fiber incl, furnished, $1,495. Confirm dates; view in person. Verified Jun 13."},

 {"top":True,"title":"Furnished private room + private bath, all-incl (Los Altos)","mid":"web-losaltos-homestead-1850","price":"$1,850/mo (all incl + maid)","src":"Craigslist /roo · Jun 13 sweep",
  "area":"Los Altos (Homestead Rd, ~15-20 min to Stanford)","status":("go","Private room+bath · available now · all incl"),
  "offcriteria":"Shared kitchen/dining (not a whole unit). URL slug says 'Cupertino' — confirm exact address (far-Homestead can push past 20 min). No end date — confirm summer-only.",
  "facts":["Furnished private room WITH (luxury) private bath; all utilities + internet + monthly maid + parking + laundry included.","$1,850 — under budget; available now for June.","Several near-identical rooms posted this week (posts 7940421389 / 7940664077 / 7940421350) — pursue whichever is open. Verified-active."],
  "clabel":"View listing","curl":"https://sfbay.craigslist.org/pen/roo/d/cupertino-clean-furnished-private-1br/7940421389.html",
  "cnote":"All-inclusive furnished room+private bath, $1,850, Los Altos, available now (multiple rooms). Confirm address + dates. Verified Jun 13."},

 {"top":True,"title":"Private room + bath, Rengstorff condo (Mountain View)","price":"$1,500/mo (utils incl)","src":"Craigslist /apa · Jun 13 sweep",
  "area":"Mountain View (701 N Rengstorff Ave, ~15-20 min to Stanford)","status":("go","Private room+bath · June 8 · cheap"),
  "offcriteria":"Room in a shared 4-bed condo (2 housemates), not a whole unit; 6-month minimum — confirm a summer term or early exit.",
  "facts":["Furnished private bedroom + private bath in a 4-bed condo; nearly all utilities included; in-unit W/D.","$1,500 — under budget; available June 8 (good for your hotel gap).","Address corroborated on apartments.com/Zillow/Redfin; also seen on Uloop."],
  "clabel":"View listing","curl":"https://sfbay.craigslist.org/pen/apa/d/mountain-view-cozy-bed-bath-room-in/7939756133.html",
  "cnote":"$1,500 furnished room+private bath, MV, June 8, utils incl. Confirm summer-only (6-mo min listed). Verified Jun 13."},

 # ---- CHECK: fits, confirm a detail ----
 {"top":False,"title":"850 Calderon — whole studio (Mountain View)","price":"$2,000/mo","src":"Craigslist /apa · Jun 13 sweep",
  "area":"Mountain View (850 Calderon Ave, ~15-20 min to Stanford)","status":("check","Whole studio · June 18 · at budget"),
  "offcriteria":"Furnished status not stated (likely unfurnished); managed complex normally does 6-/12-mo leases — confirm a summer-only term. June 18 (a few more hotel nights). Utilities not specified.",
  "facts":["Self-contained studio (0BR/1BA), freshly renovated, in-unit W/D + off-street parking.","$2,000 — exactly at your ceiling; available June 18; listed month-to-month.","Verified-active (posted Jun 5, updated Jun 10)."],
  "clabel":"View listing","curl":"https://sfbay.craigslist.org/pen/apa/d/mountain-view-850-calderon-apartments/7938951036.html",
  "cnote":"Whole MV studio, $2,000, Jun 18, in-unit W/D. Confirm furnished + summer-only term. Verified Jun 13."},

 {"top":False,"title":"In-law unit — own kitchen + bath + entrance (San Mateo)","price":"$1,550/mo","src":"Craigslist /roo · Jun 13 sweep",
  "area":"San Mateo (Sunnybrae, ~20-25 min to Stanford)","status":("check","Whole in-law unit · July 1"),
  "offcriteria":"Starts July 1 (gap from your June hotel stay). Furnished status not stated. San Mateo ~20-25 min (far edge). Utilities not stated.",
  "facts":["Whole/dedicated in-law unit (450 sqft 1BR/1BA): separate entrance, own kitchen, private bath, on-site laundry.","$1,550 — well under budget; 'good for one person'.","Verified-active (fresh Jun 11 post). Contact 'Steven'."],
  "clabel":"View listing","curl":"https://sfbay.craigslist.org/pen/roo/d/san-mateo-san-mateo-inlaw-unit-for-rent/7940362301.html",
  "cnote":"Whole in-law w/ own kitchen+bath+entrance, $1,550, San Mateo. July 1 start (gap); confirm furnished. Verified Jun 13."},

 {"top":False,"title":"Private room + bath, midtown Palo Alto (Emerson St)","price":"$1,490/mo","src":"Craigslist /roo · Jun 13 sweep",
  "area":"Midtown Palo Alto (Emerson St, very close to Stanford)","status":("check","Private room+bath · best PA location"),
  "offcriteria":"MAJOR: listing requires a 12-MONTH lease + proof of income, targets long-term tech pros — conflicts with summer-only. Ask about a summer term; expect resistance. Room shared with a couple (not a whole unit).",
  "facts":["Private 11x11 room WITH private bath in a 3BR/2BA Palo Alto house; furnished (bed, desk, dresser); W/D, WiFi incl.","$1,490 — well under budget; best location of the private-bath rooms (PA proper).","Verified-active (posted May 28, updated Jun 11)."],
  "clabel":"View listing","curl":"https://sfbay.craigslist.org/pen/roo/d/palo-alto-private-bathroom-master-suite/7937203708.html",
  "cnote":"Best-located private bath ($1,490, midtown PA) BUT wants a 12-mo lease — contact and ask about summer. Verified Jun 13."},

 {"top":False,"title":"Private room, own bath + balcony (Los Altos, Matts Ct)","price":"$1,650/mo","src":"Craigslist · Jun 13 sweep",
  "area":"Los Altos (951 Matts Court, ~20 min to Stanford)","status":("check","Private room+bath · month-to-month"),
  "offcriteria":"MAJOR: 'No indoor kitchen use' (outdoor cooking only). Only partially furnished (dresser + air mattress, no real bed). Utilities split. Shared house.",
  "facts":["Private room WITH private bath + private balcony in a 3-story house; month-to-month accepted; available now.","$1,650 — under budget. Address externally corroborated (hosts a real law office) — not a scam template.","Verified-active (posted Jun 12)."],
  "clabel":"View listing","curl":"https://sfbay.craigslist.org/pen/apa/d/los-altos-room-for-rent/7940506126.html",
  "cnote":"Room+private bath+balcony, $1,650, M2M, Los Altos — BUT no indoor kitchen + air mattress only. Verified Jun 13."},

 {"top":False,"title":"Back unit, separate entrance (Redwood City)","price":"$2,000/mo (all incl)","src":"Craigslist /sub · Jun 13 sweep",
  "area":"Redwood City (~15-20 min to Stanford)","status":("check","Whole unit · in-law style · at budget"),
  "offcriteria":"No move-in date stated — June availability UNCONFIRMED. Furnished status not stated. Title/body conflict (2bd/1.5ba vs 1bd/1ba). Needs 680+ credit, no pets/smoking. Post had a 'flagged' marker.",
  "facts":["Separate-entrance back unit (in-law style) — your own space; utilities + internet + W/D + parking included.","$2,000 — at your ceiling.","Posted May 15, updated May 30."],
  "clabel":"View listing","curl":"https://sfbay.craigslist.org/pen/sub/d/redwood-city-back-unit-rental-redwood/7934565136.html",
  "cnote":"Whole back unit, RWC, $2,000 all incl. Confirm June availability + bd/ba count. Likely active Jun 13."},

 {"top":False,"title":"Private room + bath, garden cottage (Menlo/Atherton)","mid":"web-ff-816226","price":"$2,000/mo (furnished, utils incl)","src":"FurnishedFinder · Jun 13 sweep",
  "area":"Menlo Park/Atherton line (~20 min to Stanford)","status":("check","Private room+bath · June unconfirmed"),
  "offcriteria":"June-2026 availability UNCONFIRMED (documented availability from Nov 2025, 1-yr preferred) — a year tenancy could run through fall. Detail page was blocked → likely-active. Shared common areas (not a whole unit).",
  "facts":["Private room WITH private bath/shower + separate entrance in a cottage; furnished; utilities included.","$2,000 — at your ceiling; ~20 min, not EPA.","Contact host via FurnishedFinder to confirm a June summer-length opening."],
  "clabel":"View listing","curl":"https://www.furnishedfinder.com/property/816226_1",
  "cnote":"Garden cottage private room+bath, $2,000, furnished, utils incl — but confirm June availability (only Nov-2025/1-yr documented). Likely active Jun 13."},

 {"top":False,"title":"Olive Startup House — private room (South Palo Alto co-living)","mid":"web-olive-startuphouse","price":"$1,750–$1,950/mo (utils + cleaning incl)","src":"Startup House · Jun 13 sweep",
  "area":"South Palo Alto (330 E Charleston Rd, <20 min to Stanford)","status":("check","Co-living room · in PA · month-to-month"),
  "offcriteria":"Private room with SHARED bath + kitchen (not the private-bath tier). Verify summer-2026 availability + furnished + any private-bath rooms by applying at startuphouse.co.",
  "facts":["Private room in a South Palo Alto co-living house; all utilities + weekly cleaning included.","$1,750–$1,950 — in budget; month-to-month (30+ day min, no 12-mo lease); accepting applications.","Real PA location (not EPA), <20 min to campus."],
  "clabel":"Apply / info","curl":"https://www.startuphouse.co/",
  "cnote":"In-budget PA co-living room, M2M, utils+cleaning incl, $1,750-1,950 — but shared bath. Apply at startuphouse.co; confirm summer dates. Likely active Jun 13."},

 {"top":False,"title":"Palo Alto studio (4129 El Camino Way)","mid":"web-pa-4129-elcamino","price":"$1,950/mo + ~$100-150 utils","src":"SUpost · Jun 13 sweep",
  "area":"Palo Alto (walk/bike to Stanford)","status":("check","Whole studio · July 6 – Aug 22"),
  "offcriteria":"Dates: July 6 – Aug 22 only — does NOT cover your June gap, no September; ~7-week window. Utilities billed separately (+~$100-150 → ~$2,050-2,100 effective).",
  "facts":["Dedicated 450 sqft studio in Palo Alto proper — closest to campus, walk/bikeable; partially furnished + kitchen utensils.","$1,950 base — under budget. Verified-active (posted Jun 10)."],
  "clabel":"Open post →","curl":"https://supost.com/post/index/130086786",
  "cnote":"Whole PA studio, walk to campus, $1,950 base — but Jul 6–Aug 22 only + utilities extra. Verified Jun 13."},

 # ---- WARN: near-miss (shared bath / over budget / too far) ----
 {"top":False,"title":"Furnished room, private patio entrance — SHARED bath (Palo Alto)","price":"$1,695/mo (all utils incl)","src":"Craigslist /roo · Jun 13 sweep",
  "area":"Midtown Palo Alto (walk to Stanford)","status":("warn","Shared bath · July 4 start"),
  "offcriteria":"Bathroom is SHARED (not private). Available July 4 — misses your June need (needs a bridge). Good backup if private bath isn't essential.",
  "facts":["Furnished private room (144 sqft) in a shared house, private patio entrance; pool, AC, W/D, shared kitchen; all utilities included.","$1,695 — under budget; PA proper, walk to Stanford; housemates mostly Stanford affiliates.","Verified-active (updated Jun 12)."],
  "clabel":"View listing","curl":"https://sfbay.craigslist.org/pen/roo/d/palo-alto-avail-4-furn-room-priv-patio/7938711274.html",
  "cnote":"Great PA location, all utils incl, $1,695 — but shared bath + July 4 start. Backup. Verified Jun 13."},

 {"top":False,"title":"Furnished room, separate entrance — SHARED bath (West Palo Alto)","price":"$1,550–$1,650/mo all-in","src":"Craigslist /roo · Jun 13 sweep",
  "area":"West Palo Alto (bikeable to Stanford)","status":("warn","Shared bath · July 1 start"),
  "offcriteria":"Bathroom is SHARED with one student/intern (not private). Available July 1 — misses your June need.",
  "facts":["Furnished private bedroom with separate/private entrance in a house; shared kitchenette + W/D; single occupancy.","$1,550 (1-yr) / $1,600 (6-mo) + $50 flat utils/WiFi (~$1,600-1,650 all-in); PA proper, bikeable.","Verified-active (posted May 31, updated Jun 10)."],
  "clabel":"View listing","curl":"https://sfbay.craigslist.org/pen/roo/d/palo-alto-modern-furnished-private/7937990394.html",
  "cnote":"PA proper, furnished, ~$1,600 all-in — but shared bath + July 1 start. Backup. Verified Jun 13."},

 {"top":False,"title":"Fully furnished studio, available now (Burlingame)","price":"$2,050/mo (all incl)","src":"Craigslist /apa · Jun 13 sweep",
  "area":"Burlingame/Hillsborough (~20-25 min to Stanford)","status":("warn","Whole studio · available NOW · over budget"),
  "offcriteria":"$2,050 is over the $2,000 cap (within ~$2,100 tolerance); Burlingame/Hillsborough ~20-25 min (outer edge). No pets. Confirm it runs through Aug/Sep.",
  "facts":["Self-contained furnished studio: own kitchenette, full private bath, private entrance; all utilities + internet + parking included.","Available NOW — solves the hotel gap today.","Verified-active (posted Jun 6, updated Jun 9)."],
  "clabel":"View listing","curl":"https://sfbay.craigslist.org/pen/apa/d/burlingame-beautiful-fully-furnished/7939249340.html",
  "cnote":"Available-now whole studio, furnished, all incl, $2,050 (just over) + ~20-25 min. Verified Jun 13."},

 {"top":False,"title":"Master bedroom + private bath (Sunnyvale)","mid":"web-uloop-sunnyvale-bradford","price":"$1,750/mo","src":"Uloop · Jun 13 sweep",
  "area":"Sunnyvale (~8 mi / likely >20 min to Stanford)","status":("warn","Private room+bath · likely >20 min"),
  "offcriteria":"Sunnyvale ~8 mi — likely over 20 min in traffic. No explicit dates; host prefers 6-month lease (conflicts with summer-only). Room in a shared house.",
  "facts":["~200 sqft master suite with private bath + patio access in a newly built shared house; fiber internet; parking.","$1,750 — under budget. Confirm dates + that they'll do a summer term."],
  "clabel":"View listing","curl":"https://stanford.uloop.com/housing/view.php/2739304165/Modern-Sunnyvale-Master-Bedroom-for-Rent",
  "cnote":"Sunnyvale master+bath, $1,750 — but likely >20 min + 6-mo lease pref. Likely active Jun 13."},

 {"top":False,"title":"Room + private bath (Half Moon Bay / El Granada)","price":"$1,300/mo (all utils incl)","src":"Craigslist /sub · Jun 13 sweep",
  "area":"El Granada / Half Moon Bay (~35-45 min over Hwy 92)","status":("warn","Private room+bath · too far · fallback only"),
  "offcriteria":"LOCATION disqualifier: ~35-45 min over the hills — well outside your 20-min ring; needs a car. Keep only if nothing closer works.",
  "facts":["Furnished private room + private bath in a 2BR/2BA townhome; all utilities included; in-unit W/D.","$1,300 — well under budget; flexible dates (email your window).","Verified-active (posted May 17)."],
  "clabel":"View listing","curl":"https://sfbay.craigslist.org/pen/sub/d/el-granada-room-and-private-bath-for/7934945431.html",
  "cnote":"Cheapest room+bath ($1,300) but 35-45 min away — last-resort only. Verified Jun 13."},
]

# ---- LOCATION FILTER (Jun 15): ON-CAMPUS STANFORD HOUSING ONLY. Simon tightened
# to Stanford-campus sublets only — even off-campus Palo Alto (downtown, Professorville,
# College Terrace, Oak Creek, El Camino, etc.) is now out. Applied in-place so every
# count, section, and filter reflects it.
# Off-campus markers: present => NOT campus (unless a hard on-campus building also appears).
_LOC_OFF = ("college terrace", "oak creek", "stanford villa", "professorville", "downtown",
            "university ave", "california ave", "cal ave", "el camino", "midtown",
            "palo alto high", "5-min walk", "5 min walk", "near campus", "co-op",
            "community house", "mountain view", "menlo", "redwood", "atherton", "los altos",
            "east palo alto", "san jose", "fremont", "oakland", "berkeley", "san francisco",
            "hillsborough", "san mateo", "burlingame", "sunnyvale")
# Hard on-campus Stanford housing building names (override the off-markers if present).
_LOC_BLDG = ("escondido", "evgr", "ev studio", "ev low", "ev mid", "ev high",
             "ev south", "ev junior", "ev apartment", "munger", "rains", "blackwelder",
             "lyman", "barnes", "mirrielees", "mireless", "mirelees", "stanford west",
             "hulme", "comstock", "kennedy")
# General on-campus signals.
_LOC_ON = _LOC_BLDG + ("on campus", "on-campus", "heart of campus",
                       "heart of the stanford campus", "r&de", "graduate housing",
                       "grad housing", "campus house", "house in the heart")
def _campus_only(L):
    s = (L.get("area", "") + " " + L.get("title", "") + " " + " ".join(L.get("facts", []))).lower()
    if any(t in s for t in _LOC_OFF):
        return any(t in s for t in _LOC_BLDG)  # keep only if a real on-campus building is named
    return any(t in s for t in _LOC_ON)

# ---- LEASE-LENGTH FILTER (Jun 16): Simon needs a ~3-4 month lease (full June->September,
# extendable) — drop short stopgaps & 1-2 month partial sublets. Keep spans >= ~10 weeks
# plus flexible/unknown-length (summer / academic-year) listings he can ask to extend.
_MON = {'jan':1,'feb':2,'mar':3,'apr':4,'may':5,'jun':6,'june':6,'jul':7,'july':7,'aug':8,
        'sep':9,'sept':9,'september':9,'oct':10,'nov':11,'dec':12,'january':1,'august':8}
_MIN_LEASE_DAYS = 70  # ~10 weeks; on-campus summer sublets top out near the quarter
_SHORT_PHRASES = ("stopgap", "1 week", "~1 week", "(june july)", "june–july", "june-july",
                  "june - july", "late june – mid aug", "late june - mid aug",
                  "mid-june to mid-july", "mid june to mid july", "short-term", "short term")
def _lease_span_days(blob):
    tl = blob.lower()
    pts = []
    for mname, day in re.findall(r'\b(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec|june|july|august|september)\.?\s*(\d{1,2})\b', tl):
        pts.append((_MON[mname], int(day)))
    for mm, dd in re.findall(r'\b(1[0-2]|[1-9])\s*/\s*(\d{1,2})\b', tl):
        pts.append((int(mm), int(dd)))
    mr = re.search(r'\b(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec|june|july|august|september)\.?\s*\d{1,2}\s*[–\-]\s*(\d{1,2})\b', tl)
    if mr and pts:
        pts.append((_MON[mr.group(1)], int(mr.group(2))))
    ds = []
    for mo, dy in pts:
        if 1 <= mo <= 12 and 1 <= dy <= 31:
            try:
                d = datetime(2026, mo, dy)
                if datetime(2026, 5, 1) <= d <= datetime(2026, 10, 15):
                    ds.append(d)
            except ValueError:
                pass
    if len(ds) < 2:
        return None
    return (max(ds) - min(ds)).days
def _lease_ok(L):
    blob = L["title"] + " " + L["status"][1] + " " + L.get("offcriteria", "") + " " + " ".join(L.get("facts", []))
    if any(p in blob.lower() for p in _SHORT_PHRASES):
        return False
    span = _lease_span_days(blob)
    if span is not None and span < _MIN_LEASE_DAYS:
        return False
    return True  # long enough, or flexible/unknown (ask about extending)
for _lst in (NON_CL, SUBLETS, REGULAR_RENTALS, SHORT_TERM, SUPOST, FRESH_LEADS):
    _lst[:] = [L for L in _lst if _campus_only(L) and _lease_ok(L)]

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


def _price_num(price):
    """Representative (lowest) monthly number from a price string, for filtering.
    "$1,750–1,950" -> 1750 · "$1,700 (6+mo) · $2,300" -> 1700 · "" -> 0."""
    m = re.search(r"\$?\s*(\d[\d,]*)", price or "")
    return int(m.group(1).replace(",", "")) if m else 0

def _is_june(L):
    """True if the listing can plausibly start in June (Simon's strong preference)."""
    t = " ".join([L.get("title",""), L.get("area",""), L["status"][1],
                  L.get("offcriteria",""), " ".join(L.get("facts",[]))]).lower()
    # match "june" / "jun 9" / "jun-" / "jun/" but NOT "junior"
    return bool(re.search(r"\bjune\b|\bjun[ ./\-]", t))

def _search_text(L):
    """Lowercased haystack for the client-side text filter."""
    return " ".join([L.get("title",""), L.get("area",""), L.get("src",""),
                     L["status"][1], L.get("offcriteria",""),
                     " ".join(L.get("facts",[]))]).lower()

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
        img_src = "maps/" + html.escape(imgs[0])  # relative so it works on GitHub Pages project path
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
                   f'data-markid="{html.escape(str(mark_id))}" '
                   f'onclick="toggleReached(this)">'
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

    # Data attributes powering the live filter bar.
    data_attrs = (
        f' data-price="{_price_num(L["price"])}"'
        f' data-status="{scls}"'
        f' data-contacted="{1 if contacted else 0}"'
        f' data-dead="{1 if dead else 0}"'
        f' data-june="{1 if _is_june(L) else 0}"'
        f' data-text="{html.escape(_search_text(L))}"'
    )

    return f"""<div class="card{top}{contacted_class}{noimg}"{data_attrs} id="{card_id}">
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

# ---- Outreach channels: 79 verified websites/channels (Jun 15 multi-agent sweep)
# Grouped + simplified. Each: (name, url, why, cost). do_first = best in group.
OUTREACH_CHANNELS = [
 ("🏛 Stanford-official & affiliated", "Places4Students", [
   ("Places4Students", "https://www.places4students.com/schools/108", "Stanford's official vetted off-campus board — email studenthousing@stanford.edu your offer for a login", "rooms $1.2–2k"),
   ("R&DE Short-Term Visitors", "https://rde.stanford.edu/studenthousing/short-term-visitors", "gateway: what proof to send to unlock the listings", "gateway"),
   ("R&DE Sublicense board", "https://rde.stanford.edu/studenthousing/sublicense", "on-campus grad sublets (EV/Munger/Rains), often below-market — needs Stanford login", "often <$2k"),
   ("Stanford FSH mailing lists", "https://fsh.stanford.edu/mailing_lists", "faculty/staff housing alerts + direct-from-owner portal", "some <$2.1k"),
   ("Summer Session — Live on Campus", "https://summer.stanford.edu/residential", "⚠️ NOT your path — R&DE redirected you to the Graduate Housing Application (myhousing); Curie says NSSH/Summer-Session residential can't house Summer Session students. Verify only.", "OUT for you"),
   ("Summer housing application portal", "https://summerapply.stanford.edu/", "Summer Session program portal — use to confirm commuter status only; your housing path is myhousing.stanford.edu", "portal"),
   ("SabbaticalHomes — GSB sublets", "https://www.sabbaticalhomes.com/housing/stanford-graduate-school-of-business", "MBAs sublet furnished units Jun–Aug — strong window", "furnished"),
   ("Intl visitor resources", "https://community.stanford.edu/engage/engaging-globally/resources-international-visitors-stanford-appointments", "Stanford-curated homestay/visitor links (cheap rooms)", "homestay"),
 ]),
 ("🎓 Student & intern sublet boards", "BayIntern", [
   ("BayIntern", "https://www.bayintern.com/", "built for Bay Area summer interns — confirmed live PA room $1,850", "≤$2k tiers"),
   ("Kopa", "https://www.kopa.co/", "furnished mid-term student rentals, Stanford-origin", "$1–2k"),
   ("SubLeaps", "https://subleaps.com/subleases/stanford", ".edu-verified subleases (low scam risk)", "<$2k rooms"),
   ("Uloop — Stanford", "https://stanford.uloop.com/housing/index.php/sublets", "browse sublets + post a free 'housing wanted'", "mixed"),
   ("Ohana", "https://liveohana.ai/university/stanford", "Stanford sublet marketplace, protected booking", "$1.2–2.5k"),
   ("The Student Sublet", "https://thestudentsublet.com/blog/student-housing-guide-stanford-university", "student sublets + Stanford guide", "<$2k rooms"),
   ("Semester Sublet", "https://semestersublet.com/", "national student subletting — confirm Bay Area coverage", "below-mkt"),
   ("InternHousingHub", "https://www.internhousinghub.com/", "aggregates dorm + intern programs", "$1–2k dorms"),
   ("Menlo College intern housing", "https://www.menlo.edu/about/conference-services/internship-housing/summer-housing-information/", "furnished Atherton dorm singles, ~10–15 min — summerhousing@menlo.edu", "~$1–1.8k"),
 ]),
 ("🏘 Coliving operators", "Suite Spot Co-Living", [
   ("Suite Spot Co-Living (RWC)", "https://www.suitespotcoliving.com/", "private-bed/bath suites, one Caltrain stop — golan@suitespotmgmt.com", "~$1.6–2.1k"),
   ("Olive / Startup House (PA + Menlo)", "https://startuphouse.co/", "in-target PA/Menlo houses, month-to-month — insist on a private room", "~$1.3–2k"),
   ("Coliving.com — Mountain View", "https://coliving.com/mountain-view", "private room from ~$1,500, MV (allowed)", "from ~$1.5k"),
   ("HackerHome", "https://www.hackerhouse.io/", "tech furnished shared houses — confirm it's within 20 min", "~$1.2–2k"),
   ("Diggz + Roomi", "https://www.diggz.co/san-francisco-coliving-apartments", "independent coliving rooms branded operators miss", "~$1.2–2k"),
   ("everythingcoliving.com", "https://www.everythingcoliving.com/", "directory to find more Peninsula operators", "directory"),
 ]),
 ("🛋 Furnished / monthly-stay", "Furnished Finder", [
   ("Furnished Finder — PA", "https://www.furnishedfinder.com/housing/Palo-Alto/California", "direct-from-landlord, no fee — best in-budget furnished route", "$1.45–2.4k"),
   ("Airbnb (monthly)", "https://www.airbnb.com/palo-alto-ca/stays/monthly", "28+ night discount — message hosts for more; skip EPA", "rooms fit"),
   ("2nd Address — Menlo intern", "https://www.2ndaddress.com/intern-housing/menlo-park", "furnished M2M, intern vertical, verified hosts", "rooms ~$1.3k+"),
   ("Zumper short-term", "https://www.zumper.com/apartments-for-rent/palo-alto-ca/short-term", "short-term + furnished tabs", "varies"),
   ("Vrbo (monthly)", "https://www.vrbo.com/vacation-rentals/usa/california/san-francisco-bay-ar/palo-alto", "~19% monthly discount on 28+ nights", "whole homes"),
   ("HouseStay", "https://www.housestay.com/rent/furnished-monthly-rentals-in-palo-alto-ca/", "Bay Area furnished monthly — PA + Menlo pages", "skews $2k+"),
   ("Nestpick", "https://www.nestpick.com/menlo-park/", "furnished mid-term aggregator — MP rooms from ~$880", "$800–1.5k"),
   ("Anyplace", "https://www.anyplace.com/", "30+ day furnished, no contract — thin Peninsula", "$2k+"),
   ("WoodSpring Suites PA", "https://www.woodspring.com/", "budget extended-stay + kitchen — ask 30-night rate", "~$1.8–2.4k"),
   ("Extended Stay America MV", "https://www.extendedstayamerica.com/hotels/ca/san-jose/mountain-view", "kitchen suites, monthly rate — verify it's MV not San Jose", "~$1.9–2.5k"),
   ("Blueground", "https://www.theblueground.com/furnished-apartments-san-francisco-bay-area-usa/s/palo-alto", "turnkey serviced — over budget solo, benchmark", "$3.2k+"),
   ("HousingAnywhere / Spotahome", "https://housinganywhere.com/s/San-Francisco--United-States/student-accommodation", "mid-term w/ protections — thin Peninsula supply", "few matches"),
 ]),
 ("💬 Social & community — post a 'Housing Wanted'", "SUpost", [
   ("SUpost Housing", "https://housing.supost.com/", "your main source — check newest daily, reply same-day, post a wanted ad", "$1.1–2k"),
   ("Craigslist Peninsula /sub", "https://sfbay.craigslist.org/search/pen/sub", "'pen' filter keeps it near Stanford; also /roo /apa", "$1.2–2k"),
   ("FB: Stanford Housing groups", "https://www.facebook.com/groups/stanfordhousing/", "join all sister groups + post a wanted ad", "$1.2–2k"),
   ("Cornell Silicon Valley alumni", "https://www.facebook.com/CornellSiliconValley/", "your edge — warm intros, low scam, often below-market", "below-mkt"),
   ("SpareRoom (US)", "https://www.spareroom.com/rooms-for-rent/san_francisco_bay_area", "most-trusted room site — make a 'room wanted' profile", "$1.2–2.2k"),
   ("Roomies", "https://www.roomies.com/rooms/san-francisco-ca", "free messaging room finder", "$1.2–2.2k"),
   ("Nextdoor PA", "https://nextdoor.com/city/palo-alto--ca/", "neighbor room/ADU sublets not on CL — needs local address", "$1.5–2.1k"),
   ("Reddit r/stanford + r/sublets", "https://www.reddit.com/r/stanford/", "search '2026 sublet' + post a [Housing Wanted]", "$1.2–2k"),
   ("FB: Bay Area rentals", "https://www.facebook.com/groups/bayarearentals/", "widest reach — specify Peninsula-only", "noisy"),
   ("Stanford Discord", "https://discord.com/invite/WzVjTeP", "#housing channel + real-time advice", "leads"),
   ("Real Intern SF / Meetup", "https://www.therealinternsf.com/", "find someone to split a whole unit under budget", "split"),
   ("OfferUp", "https://offerup.com/", "low-volume supplement — search 'room for rent'", "occasional"),
 ]),
 ("🌏 International / Chinese-student boards", "RedNote (小红书)", [
   ("小红书 / RedNote", "https://www.xiaohongshu.com/", "search 斯坦福租房 — many grad sublets appear here first; DM posters", "$0.9–1.6k"),
   ("1point3acres 租房", "https://www.1point3acres.com/bbs/tag-8868-1.html?filter=renting", "interns leaving for summer — post a 求租 thread", "$1–1.7k"),
   ("WeChat 租房 groups (bay123)", "https://www.bay123.com/", "highest-velocity — join via QR in the 斯坦福租房群 thread", "$0.9–1.7k"),
   ("Moonbbs 北美微论坛", "https://www.moonbbs.com/forum-106-1.html", "Bay Area 租房 board with sublet filter", "$0.9–1.7k"),
   ("硅谷信息港 (bay123 forum)", "http://www.bay123.com/forum-40-1.html", "Peninsula-centric rental forum", "$1–1.8k"),
   ("Huaren.us", "https://huaren.us/", "large NA Chinese forum — search 'Stanford 租房'", "skews $3k+"),
   ("uhomes / Uhouzz", "https://en.uhomes.com/us/stanford", "intl-student agent (EN+中文) — widen to nearby cities", "$1.5–2.3k"),
   ("Dealmoon 省钱快报", "https://www.dealmoon.com/", "directory linking the boards above", "directory"),
 ]),
 ("🏢 Local property managers & hotels (stretch/backup)", "Marymount Tower", [
   ("Marymount Tower (RWC)", "https://www.marymountapts.com/", "rare near-budget WHOLE 1BR — ask lowest 1BR + short summer lease", "~$2.15k+"),
   ("Cardinal Hotel (monthly)", "https://cardinalhotel.com/", "cheapest central-PA hotel — negotiate monthly shared-bath rate", "negotiate"),
   ("Stanford Guest House", "https://stanfordguesthouse.p3hotels.com/", "Stanford-owned — ask 30+ night educational rate", "$160–230/nt"),
   ("Prometheus (PA/MV)", "https://prometheusapartments.com/ca/mountain-view-apartments", "ask about 3-month summer leases — needs a roommate", "$2.8k+"),
   ("Equity Residential (RWC/MV)", "https://www.equityapartments.com/san-francisco-bay/redwood-city-apartments", "ask short-term terms — unfurnished", "$2.7k+"),
   ("Essex (Peninsula)", "https://www.essexapartmenthomes.com/apartments/redwood-city", "broad Peninsula inventory — ask short-term", "$2.6k+"),
   ("Avalon MV (Furnished+)", "https://www.avaloncommunities.com/california/mountain-view-apartments/avalon-mountain-view/", "furniture+utils+flex bundled — realistic only if sharing", "$3.9k+"),
   ("Sharon Green (Menlo)", "https://www.sharongreenmenlo.com/", "furnished/corporate near Sand Hill", "$3k+"),
   ("Oakwood / corporate housing", "https://www.corporatehousing.com/ca/mountain-view", "fully-serviced furnished — only if sharing", "$4k+"),
   ("Synergy / SilverDoor (DT PA)", "https://www.synergyhousing.com/key-locations/furnished-apartments-silicon-valley", "actual PA serviced apt — corporate quotes", "$2k+"),
   ("Key Housing (broker)", "https://www.keyhousing.com/corporate-housing-city/palo-alto/", "sources hard-to-find furnished PA units", "$2k+"),
   ("Residence Inn (MV / Los Altos)", "https://www.marriott.com/en-us/hotels/sfomv-residence-inn-palo-alto-mountain-view/overview/", "kitchen suites — ask 30+ night rate", "$2k+"),
   ("Crowne Plaza Cabana PA", "https://www.cabanapaloalto.com/", "central PA — bridge for the first week", "bridge"),
 ]),
 ("🔎 General aggregators (browse + set alerts)", "Zumper", [
   ("Zumper /cheap", "https://www.zumper.com/apartments-for-rent/palo-alto-ca/cheap", "best for affordable inventory — start at /cheap, set max $2k + June", "<$2k"),
   ("Zillow ($0–2k + alert)", "https://www.zillow.com/palo-alto-ca/rentals/", "deepest inventory — saved-search email alert; add MV/MP/RWC", "studios <$2k"),
   ("HotPads", "https://hotpads.com/palo-alto-ca/apartments-for-rent", "instant new-listing alerts — contact landlords first", "$2.5k+"),
   ("PadMapper", "https://www.padmapper.com/apartments/palo-alto-ca", "map-first; short-term + 'furnished' keyword + /cheap", "$2.5k+"),
   ("Apartments.com", "https://www.apartments.com/palo-alto-ca/", "managed buildings — /furnished/ + /short-term/ filters", "$2.9k+"),
   ("Dwellsy", "https://dwellsy.com/", "no-fee, mom-and-pop rentals the big sites miss", "some <$2k"),
   ("Trulia", "https://www.trulia.com/for_rent/Palo_Alto,CA/", "neighborhood pages closest to Stanford", "studios <$2k"),
   ("Realtor.com", "https://www.realtor.com/apartments/Palo-Alto_CA", "MLS-fed condos/houses that may allow summer leases", "$2k+"),
   ("Rent.com / RentCafe / Homes.com", "https://www.rent.com/california/palo-alto-apartments", "managed-building cross-checks; expand to MV/Sunnyvale", "$2.5k+"),
   ("Apartment List", "https://www.apartmentlist.com/ca/palo-alto", "quiz-driven matching — expand radius for <$2k", "engine"),
   ("HomeToGo / cozycozy", "https://www.hometogo.com/", "metasearch over Airbnb/Vrbo — cheapest monthly source", "metasearch"),
 ]),
]
OUTREACH_TOP8 = [
 ("Places4Students", "https://www.places4students.com/schools/108", "Stanford's vetted board — your highest-value, lowest-scam channel"),
 ("SUpost Housing", "https://housing.supost.com/", "check newest daily + post a 'Housing Wanted'"),
 ("Furnished Finder", "https://www.furnishedfinder.com/housing/Palo-Alto/California", "direct-from-landlord, no fee — best in-budget furnished"),
 ("BayIntern", "https://www.bayintern.com/", "built for summer interns; live PA inventory"),
 ("Suite Spot Co-Living", "https://www.suitespotcoliving.com/", "private en-suite, one Caltrain stop"),
 ("R&DE Sublicense board", "https://rde.stanford.edu/studenthousing/sublicense", "on-campus grad sublets, below-market"),
 ("Craigslist Peninsula", "https://sfbay.craigslist.org/search/pen/sub", "'pen' filter stays near campus"),
 ("RedNote 小红书", "https://www.xiaohongshu.com/", "search 斯坦福租房 — grad sublets first"),
]

def render_channels():
    top = "".join(
        f'<li><a href="{html.escape(u)}" target="_blank"><strong>{html.escape(n)}</strong></a> — {html.escape(w)}</li>'
        for n, u, w in OUTREACH_TOP8)
    out = [f'<div class="chan-top"><div class="lbl">⭐ Start here — 8 highest-leverage channels</div><ol>{top}</ol></div>']
    for group, do_first, rows in OUTREACH_CHANNELS:
        items = []
        for n, u, w, c in rows:
            star = ' <span class="star">★</span>' if n.startswith(do_first) else ""
            items.append(
                f'<div class="chan-row"><span class="nm"><a href="{html.escape(u)}" target="_blank">{html.escape(n)}</a>{star}</span>'
                f'<span class="wy">{html.escape(w)}</span><span class="ct">{html.escape(c)}</span></div>')
        out.append(
            f'<details class="chan"><summary>{html.escape(group)}<span class="cnt">{len(rows)} · ★ {html.escape(do_first)}</span></summary>'
            f'<div class="chan-list">{"".join(items)}</div></details>')
    return "".join(out)

# ---- Copy-paste outreach message templates (shown on the dashboard) ----
OUTREACH_TEMPLATES = [
 ("Expedite EVGR move-in (done — check-in confirmed Fri Jun 26)", "Kept for the record. This asked the EVGR office to move the date up; check-in is now CONFIRMED for Fri Jun 26, 3:00 PM, so it's no longer needed. Reuse only if plans change.",
  "Subject: Moving in a little earlier\n\n"
  "Dear EVGR Housing Office,\n\n"
  "My name is Simon Tian and my SUNet ID is [sunet]. I've been assigned to [building/unit] for Summer 2026 "
  "through Housing Assignments, and I'm writing to ask if I might be able to move in a little earlier than "
  "my scheduled date of [currently scheduled date]. I'm hoping for something closer to [target date] if "
  "that's possible.\n\n"
  "My original off campus plan fell through at the last minute, so I've been staying in a hotel while I "
  "wait, and the cost is adding up. Everything on my end is already taken care of. All of my documents are "
  "complete, I have my own car, and I can be moved in within a few hours of hearing from you. From what I "
  "understand the unit is sitting empty right now, so coming in early shouldn't get in anyone's way.\n\n"
  "I would be really grateful for any help you can offer. Thank you so much.\n\n"
  "Warm regards,\nSimon Tian\nipo@stanford.edu\n607-262-9704"),
 ("Reply to Vicky / Summer Session — RESIDENTIAL switch (done)", "Handled — the residential switch went through and check-in is confirmed for Jun 26. Kept for the record (ticket 61011, summersession@stanford.edu).",
  "Hi Vicky,\n\n"
  "Thank you so much — this is great news! I've already submitted my housing application, so I think I'm "
  "set on that front. A few quick questions:\n"
  "1. Could you confirm the application I submitted is the correct one for the residential switch, and "
  "that nothing further is needed from me?\n"
  "2. When can I move in, and what should I plan around this weekend?\n"
  "3. Is there anything else you need to finish processing?\n\n"
  "Thank you again — I really appreciate your help, and I'm looking forward to this weekend!\n\n"
  "Best,\nSimon Tian · ipo@stanford.edu · 607-262-9704"),
 ("Email 1 of 2 — thank-you to Curie", "Send to: csevilla@stanford.edu (keep it short)",
  "Subject: Thank you!\n\n"
  "Hi Curie,\n\n"
  "Thank you so much for the pointers and for sending me to Housing Assignments — much appreciated. "
  "I've submitted my application for the 2026 Summer rolling round. Grateful for your help!\n\n"
  "Best,\nSimon Tian · ipo@stanford.edu"),
 ("Email 2 of 2 — Housing Assignments (backup path)", "Send to: housingassignments@stanford.edu — only if the Summer Session residential switch falls through",
  "Subject: Application submitted (2026 Summer) — what's next?\n\n"
  "Hi Szonja,\n\n"
  "Thank you for the pointers — I've submitted my application at myhousing.stanford.edu for the 2026 "
  "Summer rolling round. What are the next steps from here? And since classes start June 22 and I'm "
  "already in the area, is there any way to expedite the assignment (or any interim housing in the "
  "meantime)? Happy to send anything you need.\n\n"
  "Thanks so much!\n\n"
  "Best,\nSimon Tian · ipo@stanford.edu · 607-262-9704"),
 ("EVGR direct email — to a named poster", "When you have the poster's name + email (e.g. an EVGR unit); proofread/cleaned version",
  "Subject: Still available? — Simon (incoming Stanford summer student)\n\n"
  "Hi [name],\n\n"
  "I'm Simon, an incoming graduate student (previously at Cornell) staying on campus for the summer. "
  "Sorry for the double message if you've already received my SUpost note. I'm looking to sublet a unit "
  "at EVGR — I'm a Stanford affiliate, so I should be eligible for the sublicense (happy to confirm "
  "whatever's needed on my end). Your place looks great and the location seems like a good fit. "
  "Is it still available? Kindly let me know — thank you! 😊\n\n"
  "Best,\nSimon · ipo@stanford.edu · 607-262-9704"),
 ("Direct email — re-check (school starts Jun 22)", "Email posters directly (BCC the list); apologizes for the repeat",
  "Subject: Still available? — Simon (incoming Stanford summer student)\n\n"
  "Hi! Apologies if you've already heard from me — my earlier note may have gone through the SUpost relay, so I'm reaching out directly this time. I'm Simon, an incoming Stanford student and classes start June 22, so I'm trying to lock in summer housing. Is your place still available? I'm already in Palo Alto, can come see it today, and can sign + pay a deposit right away. Thanks so much, and sorry again for the repeat message!\n\nSimon · ipo@stanford.edu · 607-262-9704"),
 ("First message — standard", "Your opener when you find a post",
  "Hi! I'm Simon, an incoming Stanford Summer Session student (coming from Cornell). "
  "Your place looks great and the location is perfect. Is it still available? I'm already "
  "in Palo Alto, so I can come see it today and I'm ready to sign and pay a deposit right "
  "away. I'm tidy, quiet, and easygoing. Thanks so much!\n\nSimon · ipo@stanford.edu · 607-262-9704"),
 ("Fast-mover opener — lead with speed", "For the flooded on-campus sublets — send within minutes",
  "Hi! I'm Simon, an incoming Stanford summer student — already in Palo Alto, so I can tour "
  "TODAY and sign + pay the deposit immediately. Your place looks perfect. Is it still available?"
  "\n\nSimon · ipo@stanford.edu · 607-262-9704"),
 ("Follow-up — no reply (~3 days)", "Gentle nudge",
  "Hi! Just following up on my earlier message about your place — still very interested and "
  "happy to come by for a tour anytime (I'm already in Palo Alto). No worries at all if it's "
  "been taken, just wanted to check in. Thanks so much!\n\nSimon · ipo@stanford.edu · 607-262-9704"),
 ("Keep me as backup — reply to “it's taken”", "Send on EVERY “already taken” to keep leads warm",
  "Totally understand, thanks for letting me know! If it ends up falling through, I'd jump on "
  "it immediately — would you mind keeping me in mind? Good luck either way!"
  "\n\nSimon · ipo@stanford.edu · 607-262-9704"),
 ("Stanford R&DE / Summer Session — initial cold email (already sent)", "Send to: housingassignments@stanford.edu, summersession@stanford.edu, shsublease@lists.stanford.edu — NOT summerhousing@ (NSSH can't house Summer Session students). Superseded by the ⭐ reply-all template above.",
  "Subject: Incoming Summer Session student — any on-campus housing still possible?\n\n"
  "Hi,\n\n"
  "I'm Simon, an incoming Stanford Summer Session student (joining from Cornell), and I'm hoping "
  "you can help with a last-minute housing situation. I had been planning to live off campus, but "
  "my off-campus lease application ran into problems and fell through — leaving me searching for "
  "housing on very short notice, despite having started early. With classes beginning June 22 and "
  "me already in Palo Alto, I'm now hoping to find something on campus.\n\n"
  "Could you let me know:\n"
  "1. Whether any on-campus rooms or studios are still available for the summer (space-available "
  "is completely fine), and the rates; and\n"
  "2. Whether it's too late to apply — and if there's still a window, exactly how I submit the "
  "application?\n\n"
  "I can complete any paperwork and pay a deposit right away, and I'd be genuinely grateful for "
  "any guidance you can offer. Thank you so much for your help!\n\n"
  "Best,\nSimon · ipo@stanford.edu · 607-262-9704"),
 ("“Housing Wanted” post", "Post on SUpost, FB Stanford Housing, r/stanford",
  "Looking: on-campus Stanford summer sublet, June – early Sept, up to $2,000/mo\n\n"
  "Hi! I'm Simon, an incoming Stanford Summer Session student (from Cornell). Looking for an "
  "on-campus room or studio sublet for the summer (dates flexible), budget up to $2,000/mo. "
  "I'm tidy, quiet, already in Palo Alto, and can tour same-day + sign immediately. If you or "
  "a friend has something opening up, please reach out — thank you!"
  "\n\nSimon · ipo@stanford.edu · 607-262-9704"),
]

def render_templates():
    out = []
    for title, when, text in OUTREACH_TEMPLATES:
        out.append(
            f'<div class="tpl"><div class="tpl-head"><span class="tpl-title">{html.escape(title)}</span>'
            f'<button class="tpl-copy" onclick="copyTpl(this)">Copy</button></div>'
            f'<div class="tpl-when">{html.escape(when)}</div>'
            f'<pre class="tpl-text">{html.escape(text)}</pre></div>')
    return "".join(out)

# ---- To-do list (checkable, persists per-browser) ----
TODOS = [
 ("1 · Settle in — now that you're moved in ✅", [
   "Cancel the hotel for any nights you no longer need — that was the whole point of getting in.",
   "Confirm renter's insurance is actually in force and file the proof — R&DE insures the building, not your belongings (theft, water, fire are on you).",
   "Pick up your permanent SUID once it's ready and return the temporary card (it's your durable door + dining access).",
   "Lock in your summer move-out / contract end date and the check-out steps now — missing them triggers holdover or cleaning penalties.",
   "Submit a fix-it work order for anything broken (don't self-repair) — get it on record before the move-out inspection.",
   "Make sure your check-in room-condition photos + damage notes are saved somewhere safe — they're your defense against move-out charges.",
   "Sort your Stanford Transportation parking permit if you brought the car, and set up dining (Meal Plan / Cardinal Dollars); if it's a shared apt, opt into the Roommate Portal in MyHousing.",
   "If your plans ever change and you don't need the unit, tell Housing Assignments in writing right away ((650) 725-2810) — silence keeps you billed.",
   "Save these in your phone: EVGR front desk (650) 497-7995, supervisor Eric Podgorny (650) 497-8021, after-hours lockout/maintenance (650) 725-1602, Housing Assignments (650) 725-2810.",
 ]),
 ("2 · Done at check-in — Fri Jun 26, 3:00 PM · 735 Campus Drive, Suite 100 🔑 (for the record)", [
   "Picked up the finalized apartment/unit, mailing address, and keys/fob at the EVGR Housing Service Center (photo ID required).",
   "Got a temporary card at the desk since the permanent SUID wasn't printed yet (past the 2-weeks-ahead photo cutoff).",
   "Walked the room-condition form + photographed everything BEFORE signing — anything unrecorded gets billed at move-out.",
   "Confirmed the two cost questions: whether a meal plan is mandatory, and the housing fee.",
   "If any of these are still open, chase them now: front desk (650) 497-7995; after-hours emergency (650) 725-1602.",
 ]),
]

# ---- Progress log (newest first) ----
PROGRESS = [
 ("Jul 1 (moved in — settle-in mode 🏡)", "Rolling the board forward: check-in day (Fri Jun 26, 3:00 PM at EVGR) has passed, so the search + move-in prep is done and the board is now in settle-in mode. The active checklist is the post-move-in items — cancel any leftover hotel nights, confirm renter's insurance is actually in force, pick up the permanent SUID and return the temporary card, file work orders for anything broken, and lock in the summer move-out date. Housing is resolved; the watcher can stay on only as a just-in-case backstop. (If anything about the actual move-in went differently, update this entry.)"),
 ("Jun 25 (CHECK-IN CONFIRMED 🔑)", "Official EVGR welcome letter from the Housing Service Center (Eric Podgorny): tentatively assigned to an EVGR location, with the specific furnished apartment + mailing address handed over AT check-in. Check-in CONFIRMED for Friday, June 26 at 3:00 PM — EVGR HSC, 735 Campus Drive Suite 100 (extended hours 8am–8pm, 7 days through move-in; bring a government photo ID). Biggest catch: I'm past the 'upload SUID photo ≥2 weeks before move-in' cutoff, so my card won't be pre-printed — uploading the photo now anyway and will get a temporary card at the desk. Built the full move-in checklist (tonight / at check-in / after) below. Blackwelder stood down — going with the EVGR assignment."),
 ("Jun 24 (assignment cleared — expediting move-in 🏃)", "The HSA housing assignment came through (EVGR) and it's a good fit — so the residential path is effectively settled; now it's EVGR's move-in step. Catch: the scheduled move-in is about a week out, and I'm paying out of pocket for a hotel until then while the assigned unit reportedly sits vacant. Drafted an expedite request to the EVGR Housing Service Center (cc Housing Assignments): I'm fully ready (all docs/forms done), have my own vehicle, need zero logistical help, and an earlier move-in wouldn't displace anyone — asking to move in as early as possible to cut the hotel cost. Email ready under Outreach → '⭐ Expedite EVGR move-in'."),
 ("Jun 22 (timing confirmed ⏱️)", "Spoke with the housing department: max wait for the DORM assignment is ~1 week (≈ by Jun 29); the Blackwelder SUBLET sublicense takes ~2 weeks to approve (≈ by Jul 6). So the dorm is the faster path by about a week. Can EXPEDITE either one by going to the housing office IN PERSON to nudge them. Net: dorm = quicker bed (and already secured); Blackwelder = cheaper but ~1 week slower to authorize. Decision still hinges on cost — especially whether the dorm forces a (mandatory) meal plan on top of the housing fee."),
 ("Jun 21 (Blackwelder REOPENED ✅)", "Sujay (sujayrao@stanford.edu) — my earlier Blackwelder contact who'd gone with someone else — re-engaged: the $1,165/mo room (Jun 19–Aug 31) is available again AND he's running it through Stanford's OFFICIAL R&DE sublicense process (subleasing office approves; he needs my proof of affiliation + a move-in date). This is the legitimacy the EVGR-B / $2,700 option lacked — and it's UNDER budget, on-campus, full summer. Replied Jun 21: yes I have proof (incoming Summer Session student), asked him to confirm unit/rate/end-date; targeting an early-July authorized start (forms must go in ≥2 weeks ahead, so no truly-immediate authorized move-in). DECISION NOW: dorm vs. this room — keep the secured dorm until this is approved + SIGNED; compare the dorm housing fee against $1,165/mo before signing. Don't double-book."),
 ("Jun 19 (sublet option — ON HOLD)", "A mutual friend offered a private sublet of an EVGR-B Premium Studio (735 Campus Dr #366), $2,700/mo, Jun 22–Aug 31. ⚠️ It's ON-campus R&DE grad housing — private subletting needs OFFICIAL R&DE sublicense authorization, which this informal 1-page agreement (host-signed only) doesn't show; it's also over budget ($2.7k vs $2k) and would double-book against my assigned residential dorm. DECISION: NOT signing / not paying the $810-due-today; sent a warm hold-off note citing the R&DE-authorization + pending-assignment checks (true reason that doubles as a clean no-fault exit). Keeping as a backup ONLY; default remains the assigned residential dorm. If the host won't show R&DE authorization → walk."),
 ("Jun 19 (CONFIRMED ✅)", "Vicky (15:38): “You will soon receive a housing assignment — periodically check your housing portal.” = ROOM SECURED, just awaiting the specific assignment (building/room/move-in will appear in MyHousing). Residential switch adds a HOUSING FEE — estimate it at summer.stanford.edu/cost/tuition-fees-calculator. Only to-dos left: watch the portal + check the cost. Search effectively DONE."),
 ("Jun 19 (sublets)", "Logged poster replies — all dead or wrong-dates (moot now that residential is secured): Suvir/EVGR, Jiayi/Stanford West, Bhavya/Kennedy, Ayush/EVGR flat, Sahithi = TAKEN; Keanu/Hulme = waitlisted + offered 7/25–9/1 (declined, needed June); Chenxi-Cody/garden suite = available Aug–mid-Sep only (wrong dates). On-campus June sublet market is basically exhausted — confirms the official residential path was the right call."),
 ("Jun 19 (PM)", "🎉 BREAKTHROUGH — Vicky B. (Stanford Summer Session) is switching me from the commuter program to the RESIDENTIAL program: “there is still space available in the dorms.” Housing application SUBMITTED via MyHousing. Replied on ticket 61011 asking how to expedite + whether there are extra charges for the switch. STILL TO CONFIRM: that the submitted app is the correct residential one (Vicky sent a specific StarRez link), and my move-in date / this-weekend check-in. On-campus housing essentially secured; June 22 gap solved if move-in is this weekend."),
 ("Jun 19 (AM)", "✅ Application SUBMITTED for the 2026 Summer rolling round (R&DE/HA path). Replied to confirm + flag the Undergraduate-vs-Graduate header. Now a BACKUP to the Summer Session residential switch."),
 ("Jun 18", "Inside the housing application — every section complete through the Application Summary Page. Reached the “Suggested Groupmates” step (got an 88% match suggestion). Decided to stay SOLO for fastest placement (not cold-inviting a stranger). To confirm: that it's the GRADUATE app (header said Undergraduate) and that it's actually SUBMITTED."),
 ("Jun 17", "Email thread resolved: NSSH/Conferences can't house Summer Session students; R&DE Student Housing Assignments (Szonja) + Curie confirmed the GRADUATE summer rolling-round application is the path. Replied to the thread."),
]
def render_progress():
    if not PROGRESS: return ""
    rows = "".join(f'<li><b>{html.escape(d)}</b> — {html.escape(t)}</li>' for d, t in PROGRESS)
    return f'<div class="prog"><div class="prog-t">📍 Progress (latest first)</div><ul>{rows}</ul></div>'

def render_todos():
    out = []
    for gi, (title, items) in enumerate(TODOS):
        rows = "".join(
            f'<label class="todo" data-tid="td-{gi}-{ii}"><input type="checkbox" onchange="toggleTodo(this)">'
            f'<span>{html.escape(t)}</span></label>'
            for ii, t in enumerate(items))
        out.append(f'<div class="todo-group"><div class="todo-gtitle">{html.escape(title)}</div>{rows}</div>')
    return "".join(out)

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
    all_cards = NON_CL + SUBLETS + REGULAR_RENTALS + SHORT_TERM + SUPOST + FRESH_LEADS
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
    sup_taken   = grp_sort([L for L in SUPOST if L.get("dead")])
    sup_replied = grp_sort([L for L in SUPOST if L.get("replied") and not L.get("dead")])
    sup_todo    = grp_sort([L for L in SUPOST if not L.get("dead") and not L.get("replied") and not is_ineligible(L) and sup_key(L) not in contacted_ids])
    sup_msgd    = grp_sort([L for L in SUPOST if not L.get("dead") and not L.get("replied") and not is_ineligible(L) and sup_key(L) in contacted_ids])
    sup_inelig  = grp_sort([L for L in SUPOST if not L.get("dead") and not L.get("replied") and is_ineligible(L)])
    def sup_section(title, items):
        if not items: return ""
        return f'<h3 class="cat">{title} ({len(items)})</h3>' + "".join(card(L) for L in items)
    supost_grouped = (
        sup_section("💬 Replied — live conversation", sup_replied)
        + sup_section("📨 Not yet messaged — send these next", sup_todo)
        + sup_section("✅ Messaged — awaiting reply", sup_msgd)
        + sup_section("⚠️ Ineligible / over budget — low priority", sup_inelig)
        + sup_section("❌ Taken / declined — closed", sup_taken)
    )
    n_queue = len(queued_ids)
    # "To contact" = current on-campus cards not yet reached out, not dead, not replied.
    n_to_contact = sum(1 for L in all_cards
                       if card_key(L) not in contacted_ids
                       and not L.get("dead") and not L.get("replied"))

    # Fresh Jun-13 web-sweep leads, grouped by status tier.
    def fresh_section(title, code):
        items = [L for L in FRESH_LEADS if L["status"][0] == code]
        if not items: return ""
        return f'<h3 class="cat">{title} ({len(items)})</h3>' + "".join(card(L) for L in items)
    fresh_grouped = (
        fresh_section("🏆 Best new — in budget, June-able", "go")
        + fresh_section("📍 Worth a look — confirm one detail", "check")
        + fresh_section("⚠️ Near-miss — shared bath / over budget / far", "warn")
    )
    n_fresh = len(FRESH_LEADS)
    fresh_sec = (f'<h2>🆕 Fresh leads (off-SUpost, {n_fresh})</h2>{fresh_grouped}' if FRESH_LEADS else "")

    # Conditional sections — empty ones (after the on-campus/PA filter) are hidden.
    official_sec = (f'<h2>Official Stanford Housing (most reliable)</h2>{"".join(card(L) for L in NON_CL)}'
                    if NON_CL else "")
    sublease_sec = (f'<h2>SUBLEASE — Skip applications ({len(SUBLETS)} listing)</h2>{"".join(card(L) for L in SUBLETS)}'
                    if SUBLETS else "")
    rentals_sec = (f'<h2>Regular Rentals — Good neighborhoods ({len(REGULAR_RENTALS)})</h2>'
                   f'<div class="banner cl"><strong>Note:</strong> regular rentals (/apa) — expect applications, credit checks, deposits.</div>'
                   f'{"".join(card(L) for L in REGULAR_RENTALS)}' if REGULAR_RENTALS else "")
    shortterm_sec = (f'<h2>Short-term Options (partial summer coverage)</h2>{"".join(card(L) for L in SHORT_TERM)}'
                     if SHORT_TERM else "")

    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Simon's Stanford Summer 2026 Housing Ledger</title>
<style>{CSS}</style>
<script>
// "Reached out" state persists in this browser (localStorage) so it works on the
// static GitHub Pages build with no server. The page is rebuilt from
// manual_contacts.json on each push; localStorage holds any newer toggles on top.
var CONTACT_KEY = 'housingContacted';
function loadOverrides() {{
    try {{ return JSON.parse(localStorage.getItem(CONTACT_KEY) || '{{}}'); }}
    catch (e) {{ return {{}}; }}
}}
function saveOverrides(o) {{
    try {{ localStorage.setItem(CONTACT_KEY, JSON.stringify(o)); }} catch (e) {{}}
}}
function paintContact(card, btn, on) {{
    if (!card || card.classList.contains('dead')) return;
    btn.classList.toggle('on', on);
    btn.textContent = on ? '✓ Reached out' : 'Mark as reached out';
    card.classList.toggle('contacted', on);
    card.dataset.contacted = on ? '1' : '0';
    if (on) card.classList.remove('queued');
    var badge = card.querySelector('.contact-badge');
    if (on) {{
        if (!badge) {{ badge = document.createElement('div'); card.prepend(badge); }}
        badge.className = 'contact-badge';
        badge.textContent = '✓ CONTACTED';
    }} else if (badge) {{ badge.remove(); }}
}}
function toggleReached(btn) {{
    var id = btn.dataset.markid;
    if (!id) return;
    var on = !btn.classList.contains('on');
    var ov = loadOverrides();
    ov[id] = on;
    saveOverrides(ov);
    paintContact(btn.closest('.card'), btn, on);
    applyFilters();
}}
function initContactState() {{
    var ov = loadOverrides();
    document.querySelectorAll('.reach-toggle').forEach(function(btn) {{
        var id = btn.dataset.markid;
        if (id && Object.prototype.hasOwnProperty.call(ov, id)) {{
            paintContact(btn.closest('.card'), btn, !!ov[id]);
        }}
    }});
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

// ---- live filter bar -------------------------------------------------------
var FB = {{maxPrice: Infinity, status: 'all'}};
function fbChip(el, group) {{
    document.querySelectorAll('.chip[data-group="'+group+'"]').forEach(function(c){{c.classList.remove('on');}});
    el.classList.add('on');
    if (group === 'price') FB.maxPrice = el.dataset.val === 'all' ? Infinity : Number(el.dataset.val);
    if (group === 'status') FB.status = el.dataset.val;
    applyFilters();
}}
function fbToggle(el) {{ el.classList.toggle('on'); applyFilters(); }}
function fbSetChip(group, val) {{
    document.querySelectorAll('.chip[data-group="'+group+'"]').forEach(function(c){{c.classList.toggle('on', c.dataset.val===val);}});
    if (group === 'price') FB.maxPrice = val === 'all' ? Infinity : Number(val);
    if (group === 'status') FB.status = val;
}}
function fbPreset() {{
    // Simon's actionable working set: in budget, June-able, not yet contacted, no expired.
    document.getElementById('fbSearch').value = '';
    fbSetChip('price', '2000');
    fbSetChip('status', 'check');
    document.getElementById('fbExpired').classList.add('on');
    document.getElementById('fbUncontacted').classList.add('on');
    document.getElementById('fbJune').classList.add('on');
    applyFilters();
    window.scrollTo({{top: 0, behavior: 'smooth'}});
}}
function fbReset() {{
    document.getElementById('fbSearch').value = '';
    FB.maxPrice = Infinity; FB.status = 'all';
    document.querySelectorAll('.chip[data-group="price"]').forEach(function(c){{c.classList.toggle('on', c.dataset.val==='all');}});
    document.querySelectorAll('.chip[data-group="status"]').forEach(function(c){{c.classList.toggle('on', c.dataset.val==='all');}});
    ['fbExpired','fbUncontacted','fbJune'].forEach(function(id){{
        var t = document.getElementById(id);
        t.classList.toggle('on', id === 'fbExpired'); // hide-expired stays ON by default
    }});
    applyFilters();
}}
function applyFilters() {{
    var q = (document.getElementById('fbSearch').value || '').toLowerCase().trim();
    var hideExpired = document.getElementById('fbExpired').classList.contains('on');
    var uncontacted = document.getElementById('fbUncontacted').classList.contains('on');
    var juneOnly    = document.getElementById('fbJune').classList.contains('on');
    var shown = 0, total = 0;
    document.querySelectorAll('.card').forEach(function(c) {{
        total++;
        var ok = true;
        if (hideExpired && c.dataset.dead === '1') ok = false;
        if (ok && FB.status !== 'all') {{
            if (FB.status === 'go'    && c.dataset.status !== 'go') ok = false;
            if (FB.status === 'check' && !(c.dataset.status === 'go' || c.dataset.status === 'check')) ok = false;
        }}
        if (ok && FB.maxPrice !== Infinity) {{
            var p = Number(c.dataset.price || 0);
            if (p > FB.maxPrice) ok = false;
        }}
        if (ok && uncontacted && c.dataset.contacted === '1') ok = false;
        if (ok && juneOnly && c.dataset.june !== '1') ok = false;
        if (ok && q && (c.dataset.text || '').indexOf(q) === -1) ok = false;
        c.classList.toggle('filtered-out', !ok);
        if (ok) shown++;
    }});
    updateSections();
    document.getElementById('fbShown').textContent = shown;
    document.getElementById('fbTotal').textContent = total;
    document.getElementById('noResults').style.display = shown === 0 ? 'block' : 'none';
}}
function updateSections() {{
    var kids = Array.prototype.slice.call(document.body.children);
    function rangeStats(start, isH2) {{
        var cards = 0, vis = 0;
        for (var i = start + 1; i < kids.length; i++) {{
            var el = kids[i];
            if (el.tagName === 'H2') break;
            if (!isH2 && el.tagName === 'H3' && el.classList.contains('cat')) break;
            if (el.classList.contains('card')) {{
                cards++;
                if (!el.classList.contains('filtered-out')) vis++;
            }}
        }}
        return {{cards: cards, vis: vis}};
    }}
    var h2Hidden = false;
    kids.forEach(function(el, idx) {{
        if (el.tagName === 'H2') {{
            var s = rangeStats(idx, true);
            h2Hidden = s.cards > 0 && s.vis === 0;
            el.classList.toggle('sec-hidden', h2Hidden);
        }} else if (el.tagName === 'H3' && el.classList.contains('cat')) {{
            var s2 = rangeStats(idx, false);
            el.classList.toggle('sec-hidden', h2Hidden || (s2.cards > 0 && s2.vis === 0));
        }} else if (el.classList.contains('banner')) {{
            el.classList.toggle('sec-hidden', h2Hidden);
        }}
    }});
}}
// keyboard support for the span-based chips (Enter / Space)
document.addEventListener('keydown', function(e) {{
    if ((e.key === 'Enter' || e.key === ' ') && e.target.classList && e.target.classList.contains('chip')) {{
        e.preventDefault(); e.target.click();
    }}
}});
// checkable to-do list (persists in this browser)
function loadTodos() {{ try {{ return JSON.parse(localStorage.getItem('housingTodos') || '{{}}'); }} catch (e) {{ return {{}}; }} }}
function toggleTodo(cb) {{
    var lab = cb.closest('.todo'); var id = lab.dataset.tid;
    var o = loadTodos(); o[id] = cb.checked;
    try {{ localStorage.setItem('housingTodos', JSON.stringify(o)); }} catch (e) {{}}
    lab.classList.toggle('done', cb.checked);
    updateTodoCount();
}}
function initTodos() {{
    var o = loadTodos();
    document.querySelectorAll('.todo').forEach(function(l) {{
        if (o[l.dataset.tid]) {{ l.querySelector('input').checked = true; l.classList.add('done'); }}
    }});
    updateTodoCount();
}}
function updateTodoCount() {{
    var all = document.querySelectorAll('.todo'); if (!all.length) return;
    var done = document.querySelectorAll('.todo.done').length;
    var el = document.getElementById('todoCount');
    if (el) el.textContent = done + '/' + all.length + ' done';
}}
// copy an outreach template to the clipboard
function copyTpl(btn) {{
    var pre = btn.closest('.tpl').querySelector('.tpl-text');
    var txt = pre.innerText;
    function done() {{
        var o = btn.textContent; btn.textContent = '✓ Copied'; btn.classList.add('ok');
        setTimeout(function() {{ btn.textContent = o; btn.classList.remove('ok'); }}, 1500);
    }}
    if (navigator.clipboard && navigator.clipboard.writeText) {{
        navigator.clipboard.writeText(txt).then(done).catch(select);
    }} else {{ select(); }}
    function select() {{
        var r = document.createRange(); r.selectNodeContents(pre);
        var s = window.getSelection(); s.removeAllRanges(); s.addRange(r);
        try {{ document.execCommand('copy'); done(); }} catch (e) {{}}
    }}
}}
// back-to-top button
function scrollTop() {{ window.scrollTo({{top: 0, behavior: 'smooth'}}); }}
window.addEventListener('scroll', function() {{
    var b = document.getElementById('toTop');
    if (b) b.classList.toggle('show', window.scrollY > 600);
}}, {{passive: true}});
document.addEventListener('DOMContentLoaded', function() {{
    document.querySelectorAll('.chip').forEach(function(c) {{
        c.setAttribute('role', 'button'); c.setAttribute('tabindex', '0');
    }});
    initContactState();
    initTodos();
    applyFilters();
}});
</script>
</head><body>
<header class="masthead">
<h1>Simon's Stanford Summer 2026 Housing</h1>
<p class="sub">🏡 MOVED IN — your EVGR check-in was <strong>Friday, June 26 at 3:00 PM</strong> (Housing Service Center, 735 Campus Drive, Suite 100). The board is now in <strong>settle-in mode</strong>: the short checklist below is what's left — cancel leftover hotel nights, confirm renter's insurance, pick up the permanent SUID, file any work orders, and lock in your summer move-out date.</p>
</header>

<div class="actionplan">
<div class="ap-title">🏡 Moved in at EVGR — settle-in mode (Fri Jun 26 check-in done · updated Jul 1)</div>
<ol>
<li><strong>✅ Checked in: Friday, June 26 at 3:00 PM</strong> — EVGR Housing Service Center, 735 Campus Drive, Suite 100. Search + move-in prep are done; what's left is settling in.</li>
<li><strong>Money leaks to close:</strong> cancel the hotel for any nights you no longer need, and confirm your renter's insurance is actually in force with the proof filed.</li>
<li><strong>ID + access:</strong> pick up your <strong>permanent SUID</strong> once it's ready and return the temporary card — it's your durable door + dining access.</li>
<li><strong>Protect yourself later:</strong> keep your check-in room-condition photos safe, file a work order for anything broken (don't self-repair), and <strong>lock in the summer move-out date</strong> + check-out steps so you don't get hit with holdover/cleaning fees.</li>
<li><strong>✅ Search resolved</strong> — EVGR assignment taken; Blackwelder stood down. Full settle-in checklist below.</li>
</ol>
</div>

<details class="disc todobox" open>
<summary>✅ Action-plan checklist — tick these off in order <span id="todoCount" style="font-weight:500;color:#9ca3af;font-size:12px"></span></summary>
<div class="disc-body">
{render_progress()}
{render_todos()}
</div>
</details>

<div class="banner" style="background:#ecfdf5;border-color:#a7f3d0">
<strong>Scope:</strong> <strong>on-campus Stanford housing</strong>, <strong>~3–4 month leases (full June→September, extendable)</strong> only. Off-campus Palo Alto and short-term sublets (stopgaps, 1–2 month partials) removed. Tap <strong>⚡ My next moves</strong> below to see what to contact today.
</div>

<details class="disc">
<summary>📋 Strategy (resolved) — the official R&amp;DE path won</summary>
<div class="disc-body">
<p><strong>Outcome:</strong> the official path delivered. R&amp;DE Student Housing Assignments placed you in an <strong>EVGR</strong> unit (Summer Session residential), and you <strong>checked in Fri June 26, 3:00 PM</strong>. That beat chasing private sublets on cost, reliability, and authorization. The settle-in checklist above is the only live to-do now.</p>
<p style="color:var(--muted)"><strong>How it played out (for the record):</strong> applied via myhousing.stanford.edu, worked the email thread (Curie → Housing Assignments → Summer Session / Vicky, ticket 61011), and ran on-campus sublets in parallel as a hedge. The strongest sublet backup — Sujay's authorized Blackwelder room — was stood down once the EVGR assignment landed with a set check-in.</p>
<p><strong>Official contacts:</strong> R&amp;DE Housing Assignments <strong>housingassignments@stanford.edu</strong> (650-725-2810) · EVGR Housing Service Center <strong>(650) 497-7995</strong>. <span class="ap-out">Not summerhousing@ / Conferences — NSSH can't house Summer Session students.</span></p>
</div>
</details>

<details class="disc">
<summary>✉️ Copy-paste outreach messages ({len(OUTREACH_TEMPLATES)} templates — all signed ipo@stanford.edu)</summary>
<div class="disc-body">
{render_templates()}
</div>
</details>

<div class="status-panel">
  <div class="status-row">
    <div class="stat"><div class="stat-num ok">{n_card_contacted}</div><div class="stat-lbl">reached out<br>(on this board)</div></div>
    <div class="stat"><div class="stat-num replied-num">{n_replied}</div><div class="stat-lbl">replied<br>(in conversation)</div></div>
    <div class="stat"><div class="stat-num warn">{n_to_contact}</div><div class="stat-lbl">to contact<br>(not yet)</div></div>
    <div class="stat"><div class="stat-num dead-num">{n_card_dead}</div><div class="stat-lbl">expired<br>(skip)</div></div>
  </div>
  <div class="status-detail">
    <strong>{len(all_cards)} on-campus listings</strong> · {n_card_contacted} reached out, {n_replied} replied, {n_to_contact} still to send, {n_card_dead} expired. Across all sources (incl. now-filtered off-campus ones) you've contacted <strong>{n_total} distinct landlord(s)</strong>.
    {"<span style='color:#c62828'>Nothing has actually gone out yet.</span>" if n_total == 0 else ""}
  </div>
  <div class="status-detail">
    <strong>Scope:</strong> on-campus Stanford · ~3–4 month leases (full summer, extendable) · {len(SUPOST)} SUpost offers + R&amp;DE · updated Jun 16, 2026. Use <strong>⚡ My next moves</strong> for the not-yet-contacted shortlist.
  </div>
</div>

<div class="filterbar">
  <div class="fb-row">
    <input id="fbSearch" class="fb-search" type="search" placeholder="Search title, area, notes… (e.g. studio, Menlo, private bath)" oninput="applyFilters()">
    <button class="fb-preset" onclick="fbPreset()" title="In budget · June-able · not yet contacted">⚡ My next moves</button>
    <span class="fb-count"><b id="fbShown">0</b> of <span id="fbTotal">0</span> showing</span>
  </div>
  <div class="fb-row">
    <span class="fb-label">Max&nbsp;rent</span>
    <span class="chip" data-group="price" data-val="1500" onclick="fbChip(this,'price')">≤ $1,500</span>
    <span class="chip" data-group="price" data-val="1800" onclick="fbChip(this,'price')">≤ $1,800</span>
    <span class="chip" data-group="price" data-val="2000" onclick="fbChip(this,'price')">≤ $2,000</span>
    <span class="chip on" data-group="price" data-val="all" onclick="fbChip(this,'price')">Any</span>
    <span class="fb-label" style="margin-left:6px">Quality</span>
    <span class="chip go" data-group="status" data-val="go" onclick="fbChip(this,'status')">🟢 Best</span>
    <span class="chip check" data-group="status" data-val="check" onclick="fbChip(this,'status')">🟡 Worth a look</span>
    <span class="chip on" data-group="status" data-val="all" onclick="fbChip(this,'status')">All</span>
  </div>
  <div class="fb-row">
    <span class="fb-label">Quick&nbsp;filters</span>
    <span id="fbExpired" class="chip on" onclick="fbToggle(this)">🚫 Hide expired</span>
    <span id="fbUncontacted" class="chip" onclick="fbToggle(this)">📭 Not contacted yet</span>
    <span id="fbJune" class="chip" onclick="fbToggle(this)">📅 June-start</span>
    <button class="fb-reset" onclick="fbReset()">Reset all</button>
  </div>
</div>
<div id="noResults">No listings match these filters. Try raising the price cap or clearing a filter.</div>

{fresh_sec}

<h2>⭐ SUpost — Stanford marketplace ({len(SUPOST)} offers, grouped by status)</h2>
<div class="banner cl">
Stanford students/affiliates near campus — your best source. Grouped below: <strong>replied → to-send → messaged → low-priority.</strong> Use each card's button to open the post; paste me any reply and I'll log it.
</div>
{supost_grouped}

{official_sec}
{sublease_sec}
{rentals_sec}
{shortterm_sec}

<h2>📒 All places to reach out ({sum(len(g[2]) for g in OUTREACH_CHANNELS)} channels — Jun 15 sweep)</h2>
<div class="banner cl">
Every channel below was found + URL-checked by a multi-agent web sweep. Tap a group to expand. The ★ in each group is the one to try first.
</div>
{render_channels()}

<button id="toTop" onclick="scrollTop()" title="Back to top" aria-label="Back to top">↑</button>
<p style="margin-top:20px;color:#777;font-size:11px">Dashboard updated: June 15, 2026 · {len(SUPOST)} SUpost offers + {n_fresh} fresh leads · {sum(len(g[2]) for g in OUTREACH_CHANNELS)} outreach channels · East Palo Alto excluded · Tap “Mark as reached out” to track outreach · Blue = reached out · Amber = queued · Red = expired</p>
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
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("",PORT),Handler) as httpd:
        print(f"[palo_alto_server] http://localhost:{PORT}/",flush=True)
        try: httpd.serve_forever()
        except KeyboardInterrupt: print("\n[palo_alto_server] stopped")
