#!/usr/bin/env python3
"""Scrape Zillow with user's filtered URL."""
import json
import time
import os
import re
from playwright.sync_api import sync_playwright

OUT = "/Users/test/Desktop/housing-S26/zillow_sf.json"
DEBUG_DIR = "/Users/test/Desktop/housing-S26/zillow_debug"

URL = "https://www.zillow.com/san-francisco-ca/rentals/?searchQueryState=%7B%22pagination%22%3A%7B%7D%2C%22isMapVisible%22%3Atrue%2C%22mapBounds%22%3A%7B%22west%22%3A-122.42924120157767%2C%22east%22%3A-122.37173464029837%2C%22south%22%3A37.76067585043668%2C%22north%22%3A37.80917671847406%7D%2C%22regionSelection%22%3A%5B%7B%22regionId%22%3A20330%2C%22regionType%22%3A6%7D%5D%2C%22filterState%22%3A%7B%22fr%22%3A%7B%22value%22%3Atrue%7D%2C%22fsba%22%3A%7B%22value%22%3Afalse%7D%2C%22fsbo%22%3A%7B%22value%22%3Afalse%7D%2C%22nc%22%3A%7B%22value%22%3Afalse%7D%2C%22lsact%22%3A%7B%22value%22%3Afalse%7D%2C%22cmsn%22%3A%7B%22value%22%3Afalse%7D%2C%22lscmsn%22%3A%7B%22value%22%3Afalse%7D%2C%22lszp%22%3A%7B%22value%22%3Afalse%7D%2C%22auc%22%3A%7B%22value%22%3Afalse%7D%2C%22fore%22%3A%7B%22value%22%3Afalse%7D%2C%22mp%22%3A%7B%22min%22%3A800%2C%22max%22%3A1400%7D%2C%22mf%22%3A%7B%22value%22%3Afalse%7D%2C%22land%22%3A%7B%22value%22%3Afalse%7D%2C%22manu%22%3A%7B%22value%22%3Afalse%7D%2C%22r4r%22%3A%7B%22value%22%3Atrue%7D%7D%2C%22isListVisible%22%3Atrue%2C%22mapZoom%22%3A14%7D"

# Co-living keywords to filter out
COLIVING_KEYWORDS = ["coliving", "co-living", "coliv", "shared room", "shared bedroom", "bunk", "pod", "capsule"]


def extract_listings(page):
    out = []
    try:
        nd = page.evaluate("() => { const el = document.getElementById('__NEXT_DATA__'); return el ? el.textContent : null; }")
        if nd:
            data = json.loads(nd)
            results = []
            try:
                results = data["props"]["pageProps"]["searchPageState"]["cat1"]["searchResults"]["listResults"]
            except (KeyError, TypeError):
                pass
            if not results:
                try:
                    results = data["props"]["pageProps"]["searchPageState"]["cat1"]["searchResults"]["mapResults"]
                except (KeyError, TypeError):
                    pass
            for r in (results or []):
                price = r.get("price", "") or r.get("unformattedPrice", "")
                units = r.get("units") or []
                if (not price) and units:
                    price = units[0].get("price", "")
                out.append({
                    "price": str(price),
                    "address": r.get("address", "") or r.get("streetAddress", ""),
                    "url": r.get("detailUrl", "") or r.get("hdpUrl", ""),
                    "beds": r.get("beds", ""),
                    "baths": r.get("baths", ""),
                    "area": r.get("area", "") or r.get("livingArea", ""),
                    "zpid": str(r.get("zpid", "") or r.get("id", "")),
                    "lat": (r.get("latLong") or {}).get("latitude"),
                    "lng": (r.get("latLong") or {}).get("longitude"),
                    "img": r.get("imgSrc", ""),
                    "status": r.get("statusText", "") or r.get("statusType", ""),
                    "units": units,
                })
    except Exception as e:
        print(f"    Extract err: {e}", flush=True)
    return out


def main():
    os.makedirs(DEBUG_DIR, exist_ok=True)
    print("Zillow SF — filtered URL scrape ($800-$1,400 rentals)", flush=True)
    print("=" * 55, flush=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            viewport={"width": 1400, "height": 900},
            locale="en-US",
        )
        ctx.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US','en']});
        """)
        page = ctx.new_page()

        print("\n1) Loading filtered Zillow URL...", flush=True)
        page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        time.sleep(5)

        title = page.title()
        print(f"   Title: {title}", flush=True)

        if "denied" in title.lower() or "captcha" in page.content()[:2000].lower():
            print("   ⚠ Captcha — solve it now! (waiting 40s)", flush=True)
            time.sleep(40)
            title = page.title()
            print(f"   After captcha: {title}", flush=True)

        page.screenshot(path=os.path.join(DEBUG_DIR, "v6_filtered_01.png"))

        # Scroll and collect
        print("\n2) Collecting listings...", flush=True)
        all_listings = []

        for pg in range(1, 6):
            print(f"    Page {pg}...", flush=True)
            for _ in range(10):
                page.mouse.wheel(0, 1000)
                time.sleep(0.3)
            time.sleep(3)

            listings = extract_listings(page)
            if not listings:
                print(f"    No listings on page {pg}", flush=True)
                break

            all_listings.extend(listings)
            print(f"    Got {len(listings)} (total: {len(all_listings)})", flush=True)

            # Next page
            if pg < 5:
                try:
                    next_btn = page.locator('a[title="Next page"], a[aria-label="Next page"]').first
                    if next_btn.is_visible(timeout=3000):
                        next_btn.click()
                        time.sleep(6)
                    else:
                        break
                except Exception:
                    break

        # Also try the simple /rentals/ URL for comparison
        print("\n3) Also loading simple /rentals/ URL...", flush=True)
        page.goto("https://www.zillow.com/san-francisco-ca/rentals/", wait_until="domcontentloaded", timeout=60000)
        time.sleep(8)

        if "denied" in page.title().lower():
            print("   Captcha again — solve it! (35s)", flush=True)
            time.sleep(35)

        for _ in range(10):
            page.mouse.wheel(0, 1000)
            time.sleep(0.3)
        time.sleep(3)

        more = extract_listings(page)
        if more:
            all_listings.extend(more)
            print(f"    Got {len(more)} more from unfiltered page", flush=True)

        # Deduplicate
        uniq = {}
        for l in all_listings:
            k = l.get("url") or l.get("address") or l.get("zpid")
            if k and k not in uniq:
                uniq[k] = l
        all_unique = list(uniq.values())

        # Expand multi-unit buildings
        expanded = []
        for l in all_unique:
            units = l.get("units") or []
            if units:
                for u in units:
                    entry = dict(l)
                    entry["price"] = u.get("price", l.get("price", ""))
                    entry["beds"] = u.get("beds", l.get("beds", ""))
                    entry["units"] = []
                    expanded.append(entry)
            else:
                expanded.append(l)

        # Price filter + co-living filter
        budget_listings = []
        other_listings = []
        for l in expanded:
            # Skip co-living
            addr_lower = (l.get("address", "") or "").lower()
            status_lower = (l.get("status", "") or "").lower()
            combined = addr_lower + " " + status_lower
            if any(kw in combined for kw in COLIVING_KEYWORDS):
                continue

            nums = re.findall(r'[\d,]+', str(l.get("price", "")))
            if nums:
                price_val = int(nums[0].replace(',', ''))
                l["price_numeric"] = price_val
                if price_val <= 1400:
                    budget_listings.append(l)
                elif price_val <= 2000:
                    other_listings.append(l)
            else:
                other_listings.append(l)

        budget_listings.sort(key=lambda x: x.get("price_numeric", 99999))
        other_listings.sort(key=lambda x: x.get("price_numeric", 99999))

        print(f"\n{'=' * 55}", flush=True)
        print(f"Total unique properties: {len(all_unique)}", flush=True)
        print(f"Expanded units: {len(expanded)}", flush=True)
        print(f"Within budget (≤$1,400): {len(budget_listings)}", flush=True)
        print(f"Near budget ($1,401–$2,000): {len(other_listings)}", flush=True)

        if budget_listings:
            print(f"\nBudget listings:", flush=True)
            for l in budget_listings[:15]:
                pn = l.get('price_numeric', '?')
                addr = l.get('address', 'N/A')
                price_str = f"${pn:,}" if isinstance(pn, int) else str(pn)
                print(f"  {price_str} — {addr}", flush=True)

        if other_listings:
            print(f"\nNear budget:", flush=True)
            for l in other_listings[:10]:
                pn = l.get('price_numeric', '?')
                addr = l.get('address', 'N/A')
                price_str = f"${pn:,}" if isinstance(pn, int) else str(pn)
                print(f"  {price_str} — {addr}", flush=True)

        # Save
        output = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "source": f"Zillow SF rentals (filtered + unfiltered, {len(all_unique)} properties / {len(expanded)} units)",
            "total_scraped": len(expanded),
            "budget_count": len(budget_listings),
            "note": "Filtered URL $800-$1400 + unfiltered page combined",
            "results": {
                "budget_listings": budget_listings,
                "mid_range": other_listings[:20],
            },
            "all_unique": expanded,
        }
        with open(OUT, "w") as f:
            json.dump(output, f, indent=2)
        print(f"\nSaved -> {OUT}", flush=True)

        page.screenshot(path=os.path.join(DEBUG_DIR, "v6_filtered_final.png"))
        print("\nDone! Closing in 5s...", flush=True)
        time.sleep(5)
        browser.close()


if __name__ == "__main__":
    main()
