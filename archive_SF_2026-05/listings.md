# SF Short-Term Rentals — Simon

**Budget:** $800–$1,500/month
**Must-have:** Parking (off-street preferred), private bedroom, short-term OK (month-to-month or 1–3 month min)
**OK:** Community housing / group houses (private bedroom required)
**Not OK:** Shared bedrooms, co-living corporate buildings, sketchy areas
**Primary source:** Zillow (most legitimate landlords) + SpareRoom (verified)
**Available:** Now through June 2026
**Updated:** 2026-05-13

---

## Top picks — parking confirmed, short-term, available now

### 1. $900/mo — Room for rent ★ PARKING ★ SHORT-TERM ★
- **Available:** May 15, 2026
- **Parking:** Yes (off-street)
- **Min term:** None (month-to-month OK)
- **Furnished:** Yes
- **Short-term:** Yes
- https://www.spareroom.com/flatshare/san_francisco/any/103095158

### 2. $1,200/mo — Spacious Townhouse, Diamond Heights ★ PARKING ★
- **Available:** Now
- **Parking:** Yes (off-street), street parking also available
- **Min term:** None
- **Furnished:** No
- **Views:** Panoramic city views
- https://www.spareroom.com/flatshare/san_francisco/any/103043517

### 3. $1,350/mo — Parkmerced Townhome ★ PARKING ★
- **Available:** Now
- **Parking:** Yes (Parkmerced has dedicated parking)
- **Min term:** None
- **Furnished:** No
- **Notes:** Near SFSU, Muni M-line to Downtown
- https://www.spareroom.com/flatshare/san_francisco/any/103067014

### 4. $1,500/mo — Furnished bedroom + private bathroom ★ PARKING ★ SHORT-TERM ★
- **Available:** Now
- **Parking:** Yes (off-street)
- **Min term:** 1 month only
- **Furnished:** Yes
- **Private bath:** Yes
- https://www.spareroom.com/flatshare/san_francisco/any/102945614

### 5. $1,425/mo — Private room + own bathroom, 2BR/2BA ★ PARKING ★
- **Available:** Now
- **Parking:** Yes (off-street)
- **Min term:** 6 months (short-term considered)
- **Furnished:** No
- **Private bath:** Yes
- https://www.spareroom.com/flatshare/san_francisco/any/101449582

---

## More options — available now, short-term friendly

### With parking (ask about details)

| Price | Area | Min term | Furnished | Avail | Notes | Link |
|------:|------|----------|-----------|-------|-------|------|
| $1,150 | Merced Heights | 1 month | Yes | now | Quiet home, street parking mentioned | [link](https://www.spareroom.com/flatshare/san_francisco/any/102739337) |
| $1,125 | Central Richmond | 3 months | No | now | Rooftop deck, 4BR/2BA | [link](https://www.spareroom.com/flatshare/san_francisco/any/102808240) |
| $1,200 | Cathedral Hill | 3 months | No | now | Near Lafayette Park | [link](https://www.spareroom.com/flatshare/san_francisco/any/102629109) |
| $1,250 | Diamond Heights | 3 months | No | now | Scenic views | [link](https://www.spareroom.com/flatshare/san_francisco/any/102729216) |
| $1,275 | Castro | None | No | now | 2 blocks from Castro MUNI | [link](https://www.spareroom.com/flatshare/san_francisco/any/103047309) |

### SoMa / North Beach (furnished, 3-month min)

| Price | Area | Min term | Furnished | Avail | Notes | Link |
|------:|------|----------|-----------|-------|-------|------|
| $1,195 | SoMa | 3 months | Yes | now | Private room in the heart of SOMA | [link](https://www.spareroom.com/flatshare/san_francisco/any/102595585) |
| $1,195 | SoMa | 3 months | Yes | now | Furnished single room in SOMA | [link](https://www.spareroom.com/flatshare/san_francisco/any/102595586) |
| $1,195 | North Beach | 3 months | Yes | now | Furnished private room in North Beach | [link](https://www.spareroom.com/flatshare/san_francisco/any/102595587) |

### June availability (short-term friendly)

| Price | Area | Min term | Furnished | Avail | Notes | Link |
|------:|------|----------|-----------|-------|-------|------|
| $1,200 | Sunnyside | 3 months | Yes | Jun 14 | Spacious house, bills included | [link](https://www.spareroom.com/flatshare/san_francisco/any/102874080) |
| $1,465 | Sunset District | 3 months | No | Jun 4 | Lovely flat with outdoor space | [link](https://www.spareroom.com/flatshare/san_francisco/any/102793209) |
| $1,495 | Lower Haight | 3 months | No | Jun 9 | Renovated home with deck & fenced yard | [link](https://www.spareroom.com/flatshare/san_francisco/any/102581124) |
| $1,500 | Noe Valley | 3 months | No | Jun 3 | Gorgeous home with spectacular views | [link](https://www.spareroom.com/flatshare/san_francisco/any/102618690) |

---

## Zillow — run the scraper for full results

Zillow bot-blocks automated fetches. Run this on your Mac to pull all Zillow listings:

```bash
cd /Users/test/Desktop/housing-S26 && python3 scrape_zillow.py
```

Or browse manually (these links open Zillow with your filters):

- [Whole units ≤$1,500 + parking](https://www.zillow.com/san-francisco-ca/rentals/?searchQueryState=%7B%22filterState%22%3A%7B%22price%22%3A%7B%22max%22%3A1500%7D%2C%22mp%22%3A%7B%22max%22%3A1500%7D%2C%22fr%22%3A%7B%22value%22%3Atrue%7D%2C%22parkingSpots%22%3A%7B%22min%22%3A1%7D%7D%7D)
- [Studios/1BR ≤$1,700 + parking](https://www.zillow.com/san-francisco-ca/rentals/?searchQueryState=%7B%22filterState%22%3A%7B%22price%22%3A%7B%22max%22%3A1700%7D%2C%22mp%22%3A%7B%22max%22%3A1700%7D%2C%22beds%22%3A%7B%22max%22%3A1%7D%2C%22fr%22%3A%7B%22value%22%3Atrue%7D%2C%22parkingSpots%22%3A%7B%22min%22%3A1%7D%7D%7D)
- [Rooms for rent ≤$1,500](https://www.zillow.com/san-francisco-ca/rentals/?searchQueryState=%7B%22filterState%22%3A%7B%22price%22%3A%7B%22max%22%3A1500%7D%2C%22beds%22%3A%7B%22min%22%3A0%2C%22max%22%3A0%7D%2C%22fr%22%3A%7B%22value%22%3Atrue%7D%7D%7D)

---

## Whole-unit building (only one in budget)

| Address | Area | Price | Notes |
|---------|------|-------|-------|
| **1000-1010 Bush St** | Lower Nob Hill | $1,150–$1,250 studios | Only whole-unit building under $1,500 in SF — [Rent.com](https://www.rent.com/apartment/1000-1010-bush-street-san-francisco-ca-lc5905883) |

Call leasing office to ask about parking and short-term lease options.

---

## Reddit r/SFBayHousing — active offers

| Price | Area | Notes | Link |
|------:|------|-------|------|
| $1,069–$1,077 | NoPa / Alamo Square | McAllister House, 2 rooms Jun 1, Victorian group house | [link](https://www.reddit.com/r/SFBayHousing/comments/1szl2qn/) |
| $1,287 | NoPa | 13-person community house, Jun 1 | [link](https://www.reddit.com/r/SFBayHousing/comments/1snbzy8/) |
| $1,100 | Hayes Valley | 2BR/1BA furnished, flexible timing | [link](https://www.reddit.com/r/SFBayHousing/comments/1slxsx5/) |
| — | Russian Hill | 2BR/2BA condo, private bed + bath | [link](https://www.reddit.com/r/SFBayHousing/comments/1sxr70h/) |

---

## Parking-friendly neighborhoods in SF (for context)

Best parking at this budget:
- **Parkmerced / Merced Heights / Ingleside** — suburban feel, free street parking, some units have garages
- **Outer Richmond / Outer Sunset** — residential, easy street parking
- **Diamond Heights / Glen Park** — quieter, parking available
- **Excelsior / Silver Terrace** — affordable, parking easy

Worst parking (avoid if car is essential):
- **Downtown / FiDi / SoMa** — metered, expensive garages
- **North Beach / Chinatown** — very tight
- **Nob Hill / Russian Hill** — steep hills + permit zones

---

## Scam flags

- Owner "out of the country" / refuses to meet
- Zelle/Venmo deposit before tour
- Price 30%+ below comparable listings
- No property address given
- Refuses video call or in-person showing
