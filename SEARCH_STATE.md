# Housing search — living state file

**Read this first.** It is the one document that holds the whole state of the Fall 2026 search:
constraints, what has been checked, what was found, what is blocked, and what to do next. Update it
whenever the search moves. Per-pass details live in the dated notes listed at the bottom.

_Last updated: September 27, 2026 (late night, after the South San Francisco sweep). Move-in is
September 29 — two days out._

## The brief

| | |
| --- | --- |
| Start | **September 29, 2026** |
| Lease | **Month-by-month or sublet only** — no 12-month leases, no long minimums. Confirmed as a hard constraint on Sept 27. |
| Budget | Preferably under **$1,500 per 30 days**, including recurring utilities and parking (~$50/day) |
| Must have | **Private full bathroom** · **parking for one car** |
| Where | Must work for **both San Francisco and Stanford** — ranked on the worse of the two drives. Widened on Sept 27 to include East Bay, north of Berkeley, SF, toward Sacramento, and the Peninsula south of SF. |
| Commute ceiling | **Nothing over 1.5 hours from *both* anchors** (added Sept 27). Applied to the worse of the two drive times; it removed all four Solano cards. |
| Type | A room in a shared house is fine; whole apartments/studios welcome |
| Platforms | Zillow, SUpost, Furnished Finder, **SpareRoom** (added Sept 27 — it turned out to hold the best leads). **Craigslist excluded** at the owner's request (Sept 25). |
| Decision (Sept 26) | **Hold all four constraints** rather than relax budget, bathroom, or dates. |

## Where things stand

**No host has been contacted. No host has confirmed September 29. Zero outreach has gone out.**
Every card says "No message has been sent." With two days left, replies — not inventory — are the
constraint.

**Searching SpareRoom on Sept 27 broke the deadlock.** It had never been swept, and it holds the only
leads that satisfy every hard constraint at once:

- **Millbrae, $1,500 including utilities** — private bathroom ("no sharing"), parking, **month-to-month
  stated, no minimum and no maximum term**, available now. 21 miles worst-case, and Millbrae is the one
  stop served by *both* BART and Caltrain. **Unfurnished** — the single trade-off for a one-month stay.
  *This is the best lead in the search.*
- **San Mateo townhouse master suite, $1,600 including utilities** — en-suite bath and balcony, garage,
  furnished, **no minimum or maximum term, short rentals considered**, available now. 21 miles
  worst-case, 4 blocks from downtown Burlingame. $100 over target.
- **Foster City, $1,600 including utilities** — brand-new private bath, garage, furnished, available
  now. Lists a three-month minimum but marks short rentals as considered, so one month must be agreed.

These beat every Solano card by ~50 miles on location *and* on lease terms.

**The earlier structural finding still holds** for Furnished Finder/SUpost/Zillow: the binding pair was
private bathroom + $1,500, and only El Sobrante cleared both (one night late). SpareRoom is the
exception because it lists genuine no-minimum-term rooms, which the others mostly do not.

## The board (12 cards) — `september_listings.json`, live at simonsaysgivemesmile.github.io/housing-S26

Ranked on the worse of the two drives (SF / Stanford):

| # | Lead | $/mo | Worst-case mi | Lease | Status |
| --- | --- | ---: | ---: | --- | --- |
| 1 | **Millbrae private room + bath** (SpareRoom) | 1,500 | 21 | **Month-to-month, no minimum** | **Full match. Unfurnished.** |
| 2 | **San Mateo townhouse master suite** (SpareRoom) | 1,600 | 21 | **No minimum term** | Full match; $100 over |
| 3 | Foster City, new private bath (SpareRoom) | 1,600 | 23 | 3-month min, shorts considered | Negotiate the term |
| 4 | El Sobrante en-suite (FF) | 1,475 | 49 | 1-month min | Sept 30 start, one night late |
| 5 | Hayward, private bath + entrance (FF) | 1,250 | 25 | **60-day minimum** | Cheapest; term conflicts |
| 6 | Palo Alto, 408 Grant (SUpost) | 1,430 | 34 | long-term preferred | Oct 1, female preferred |
| 7 | Palo Alto, downtown (SUpost) | 1,500 | 34 | unknown | Oct 2 |
| 8 | Alameda condo (FF) | 1,500 | 32 | 1-month min | Calendar Nov 2025 — verify |
| 9 | Berkeley, North hills (FF) | 1,350 | 40 | 1-month min | Calendar Jan 2026 — verify |
| 10 | Novato, furnished (FF) | 1,200 | 60 | 1-month min | Calendar Dec 2025; 88 min to campus — closest to the ceiling |
| — | **South San Francisco, Sunshine Gardens** (SpareRoom) | **1,050** | 24 | **No minimum or maximum** | **Watch list — lease pending, not accepting applications** |
| — | **Daly City suite, St. Francis** (SpareRoom) | **1,100** | 29 | Redacted in the ad | **Watch list — lease pending, not accepting applications** |

The two watch-list rows are filed under the new `waitlist` group: they are the cheapest private-bath
rooms found anywhere in the search, but neither can be contacted right now.

**Under the month-by-month rule, Hayward's 60-day minimum is a real conflict, not a formality.**

**The four Solano cards (Fairfield ×3, Vacaville) were withdrawn on Sept 27** under the new 1.5-hour
ceiling: Fairfield is 100 minutes to Stanford and Vacaville 109, both over the limit even at free-flow
speeds. Novato survives at 88 minutes, but it is the first card that would fail the rule in traffic.

## Ruled out, and why (do not re-check)

- **Vallejo Zillow room** — page now resolves to a *sold house*, not a rental. Removed.
- **Redwood City 2B/2B, $1,847** — private bath + parking, but **12-month lease** with screening.
- **Foster City townhouse, $2,367** — private bath, **available exactly Sept 29** (the only exact date match found anywhere), but 58% over budget; parking unmentioned.
- **Foster City family house, $1,390** — shared bath, **12-month lease to Sept 2027**.
- **Redwood City 2B1B, $1,500** — shared bath (one bathroom), wants ~a year.
- **San Carlos Hills, $1,400** (SpareRoom) — 2BR/**1BA**, shared bath, utilities not included.
- **San Mateo Bay View, $1,588** (SpareRoom) — **6-month minimum**.
- **Foster City, $1,300** (SpareRoom) — 3 bedrooms sharing 1.5 baths; male preferred.
- **Bayshore furnished room, $1,200** (SpareRoom) — **6-month minimum**, parking "No" (street only), and the ad contradicts itself: the structured field says private bathroom, the description says "shared bathroom on the main level".
- **Noe Valley, $1,500** (SpareRoom) — private bath, utilities included, but a **24-month minimum** and a minimum age of 40.
- **Oceanview, $1,150** (SpareRoom) — genuinely month-to-month and available now, but **shared bath, no parking, unfurnished**. The nearest miss in the target price band.
- **West Portal house share, $1,290** (SpareRoom) — parking, furnished, utilities, 1–3 month term, but the $1,290 room **shares one of three bathrooms**; only the $2,000 room has a private bath. House rules are extreme: no visitors ever, no locking your bedroom, silence 8pm–10am, "one shower a day as short as possible".
- **Two "TurboTenant" Daly City ads, $950 and $1,380** — both **shared baths**, both syndicated by one advertiser listing across Wildomar, Susanville, Visalia, Long Beach and more, with prices stripped out of the description and contact pushed to a personal WhatsApp. Treated as lead-generation, not real local rooms. **Do not send anything to these.**
- **South SF studio, $1,950–2,050** — whole unit, but over budget, one-year preferred.
- **San Leandro, $1,500** — private bath, but **12-month minimum**.
- **Palo Alto cheap rooms** (College Terrace $850, Loma Verde $1,400, South PA $1,400) — all share a bathroom.
- **Whole apartments/studios** — the floor is ~$1,700–$2,000 and all start after Sept 29. None under $1,500 exist on approved platforms this week.
- Sunnyvale / Newark / Concord / Brentwood / Livermore / Antioch / Millbrae leads from the Sept 24 shortlist — **all Craigslist**, excluded.

## Geography (both anchors measured for 31 cities — `distance_estimates.json`)

Best-balanced towns: **Burlingame 18** · San Mateo 21 · Millbrae 21 (the one BART+Caltrain stop) ·
San Bruno 22 · Foster City 23 · South SF 24 · Belmont 25 · **Hayward 25** · San Carlos 26 · Redwood
City 27. Nine of the ten are on the Peninsula. Current cards for comparison: El Sobrante 49, Novato 60.

**The 1.5-hour ceiling, in minutes on the worse anchor:** South SF 36 · Millbrae 33 · San Mateo 29 ·
Foster City 32 · Daly City 40 · Hayward 36 · Palo Alto 47 · Alameda 48 · Berkeley 61 · El Sobrante 69 ·
Novato 88 — then the cut: Fairfield 100, Vacaville 109, both removed.

## Blocked / unchecked — genuinely unknown, not empty

**Furnished Finder is serving Cloudflare challenges to this machine** (since Sept 26). Every request
comes back "Attention Required." Zeros from these are *blocks*, not results:

- Whole-unit sweep: Richmond, San Pablo, El Cerrito, Pinole, Hercules, Vallejo
- Room sweep: Daly City, South San Francisco, Emeryville, Sausalito, fresh Palo Alto pass
- The entire Peninsula on Furnished Finder (only SUpost was searched there)
- **The Burlingame garden cottage** — whole two-level home, two full baths, walk to Broadway
  Caltrain, in the best-balanced town. Price is on FF property 906435_1. **Most promising
  unverified lead on the board.**

SpareRoom and Kopa: first URL guesses were 404s; proper search URLs not yet found.

## Next moves, in order of value

1. **Message Millbrae first.** It is the only lead meeting every hard constraint; ask about a
   September 29 start and whether any furniture can be left or rented. Then San Mateo (garage,
   furnished, no minimum) and Foster City (can one month work?).
2. **Then the older three** (drafted on each card — "Copy inquiry"): Hayward (can you do one
   month?), El Sobrante (Sept 29 instead of 30?), the unpriced Stanford-hospital 1B1B (what's the
   rent?). Outreach is the owner's call; nothing has been sent.
3. Retry Furnished Finder once the block clears — the Burlingame cottage first, then the blocked
   cities. FF's entire inventory is monthly minimums, so it is the best source for this constraint.
4. **Re-check the two watch-list rooms daily.** South San Francisco at $1,050 (private bath, parking,
   furnished, utilities included, $500 deposit, no minimum *or* maximum term) is the best-value lead
   the search has produced; it is lease-pending only. Daly City at $1,100 is the same story. Pending
   leases in this band fall through often — if either reopens, it beats Millbrae on price by $400+.
5. Sweep the rest of SpareRoom. **Done Sept 27:** South San Francisco, Daly City, San Bruno, Brisbane,
   Westlake, Serramonte, Pacifica, Colma, and the southern SF neighborhoods (Ingleside, Excelsior,
   Visitacion Valley, Outer Mission). **Still untouched:** Belmont, San Carlos, Redwood City,
   Burlingame proper, and the whole East Bay (Alameda + Contra Costa counties).

## How to work on this

- Listing pages refuse plain HTTP (FF 403, SUpost 429). Drive Chrome over CDP, **headless on port
  9333 with the project's own profile** — never the owner's browser. Scripts from the last session
  lived in the session scratchpad (`cdp.py`, `ffsearch.py`, `sweep.py`).
- FF search URL: `/housing/us--ca--<city>?budget=&filters=&map=&moveDate={"in":"2026-09-29"}&page=`.
  Results state "1 private bathroom" vs "N shared bathrooms" directly.
- **SpareRoom** (best hit rate, not rate-limited): search
  `spareroom.com/rooms-for-rent/<county>/<city>?parking=Y` (e.g. `san_mateo_county/millbrae`); ad
  pages spell out **Minimum term / Maximum term / Short rentals considered**, "(Private bathroom)"
  on the room line, utilities-included, deposit and parking. Photos at
  `photos.spareroom.com/images/flatshare/listings/large/...` download with a normal UA + Referer.
  Filter by price with `?max_rent=1500&per=pcm`; **`offset=` does not paginate** — each town returns
  about 10 ads and page 2 repeats page 1, so cover an area by searching neighbouring towns instead,
  whose radii overlap. A closed ad reads **"The advertiser is not currently accepting applications"**
  at the foot of the page — the "LEASE PENDING" badge alone does not prove it, so open the ad.
- After editing `september_listings.json` or `latest_dashboard.py`: `python3 test_dashboard.py`,
  restart the local server on :5555 (it doesn't hot-reload), commit + push (auto-deploys).
- Every new city needs an entry in `distance_estimates.json` with *both* anchors, or the render
  raises KeyError — the test guards this.

## Dated notes

- `september_29_2026_shortlist.md` — Sept 24 original shortlist (mostly Craigslist, now excluded)
- `multi_source_september_25.md` — SUpost + Furnished Finder leads, first Solano cards
- `north_bay_distance_research.md` — SF distance method, Marin/Sonoma findings
- `zillow_september_25_research.md` — Craigslist removal, Zillow exclusions
- `east_bay_september_25.md` — re-verification of every card, Vallejo withdrawal, East Bay adds
- `peninsula_september_27.md` — Peninsula measured and searched; Cloudflare block documented
- `spareroom_september_27.md` — SpareRoom sweep; the three month-to-month Peninsula leads
- `south_sf_september_27.md` — South San Francisco sweep; the $1,000–$1,200 band and why it is closed
