#!/usr/bin/env python3
"""Scrape Zillow SF rentals — v5: UI interaction for filters + pagination."""
import json
import time
import os
import re
from playwright.sync_api import sync_playwright

OUT = "/Users/test/Desktop/housing-S26/zillow_sf.json"
DEBUG_DIR = "/Users/test/Desktop/housing-S26/zillow_debug"


def extract_listings(page):
    """Extract all listings from current page via __NEXT_DATA__."""
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


def set_price_filter(page, max_price):
    """Try to set max price via UI interaction."""
    try:
        # Click the price button/dropdown
        price_btn = page.locator('button:has-text("Price"), button:has-text("price"), [data-test="price-filter"]').first
        price_btn.click(timeout=5000)
        time.sleep(1)

        # Find max price input
        max_input = page.locator('input[placeholder*="Max"], input[aria-label*="max" i], input[id*="max" i]').first
        max_input.click()
        max_input.fill("")
        max_input.fill(str(max_price))
        time.sleep(0.5)

        # Apply
        apply_btn = page.locator('button:has-text("Apply"), button:has-text("Done"), button:has-text("Save")').first
        apply_btn.click(timeout=3000)
        time.sleep(3)
        return True
    except Exception as e:
        print(f"    Price filter UI failed: {e}", flush=True)
        return False


def paginate_and_collect(page, max_pages=5):
    """Collect listings from current page + next pages."""
    all_listings = []

    for pg in range(1, max_pages + 1):
        print(f"    Page {pg}...", flush=True)

        # Scroll to load content
        for _ in range(8):
            page.mouse.wheel(0, 1000)
            time.sleep(0.3)
        time.sleep(2)

        listings = extract_listings(page)
        if not listings:
            print(f"    No listings on page {pg}, stopping", flush=True)
            break

        all_listings.extend(listings)
        print(f"    Got {len(listings)} (total so far: {len(all_listings)})", flush=True)

        # Try to go to next page
        if pg < max_pages:
            try:
                next_btn = page.locator('a[title="Next page"], a[aria-label="Next page"], li.PaginationJumpItem a:last-child').first
                if next_btn.is_visible(timeout=3000):
                    next_btn.click()
                    time.sleep(6)
                else:
                    print("    No next page button", flush=True)
                    break
            except Exception:
                print("    No more pages", flush=True)
                break

    return all_listings


def main():
    os.makedirs(DEBUG_DIR, exist_ok=True)
    print("Zillow SF rental scraper v5 — UI filter + pagination", flush=True)
    print("=" * 55, flush=True)
    print(flush=True)
    input("Press Enter to start...")

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

        # Load rentals page
        print("\n1) Loading Zillow SF rentals...", flush=True)
        page.goto("https://www.zillow.com/san-francisco-ca/rentals/", wait_until="domcontentloaded", timeout=60000)
        time.sleep(5)

        title = page.title()
        print(f"   Title: {title}", flush=True)

        if "denied" in title.lower() or "captcha" in page.content()[:2000].lower():
            print("   ⚠ Captcha — solve it now! (waiting 35s)", flush=True)
            time.sleep(35)
            title = page.title()
            print(f"   After captcha: {title}", flush=True)

        page.screenshot(path=os.path.join(DEBUG_DIR, "v5_01_initial.png"))

        # Try to set price filter via UI
        print("\n2) Setting price filter to $2,000 max...", flush=True)
        filter_worked = set_price_filter(page, 2000)
        time.sleep(3)

        new_title = page.title()
        print(f"   After filter: {new_title}", flush=True)
        page.screenshot(path=os.path.join(DEBUG_DIR, "v5_02_after_filter.png"))

        # Collect listings (paginate up to 5 pages)
        print("\n3) Collecting listings...", flush=True)
        all_listings = paginate_and_collect(page, max_pages=5)

        # If filter didn't work, also grab unfiltered and filter client-side
        if not filter_worked or not all_listings:
            print("\n   Filter may not have worked. Grabbing unfiltered page...", flush=True)
            page.goto("https://www.zillow.com/san-francisco-ca/rentals/", wait_until="domcontentloaded", timeout=60000)
            time.sleep(8)
            all_listings = paginate_and_collect(page, max_pages=8)

        # Deduplicate
        uniq = {}
        for l in all_listings:
            k = l.get("url") or l.get("address") or l.get("zpid")
            if k and k not in uniq:
                uniq[k] = l
        all_unique = list(uniq.values())

        # Client-side price filter
        budget_listings = []
        other_listings = []
        for l in all_unique:
            nums = re.findall(r'[\d,]+', str(l.get("price", "")))
            if nums:
                price_val = int(nums[0].replace(',', ''))
                l["price_numeric"] = price_val
                if price_val <= 2000:
                    budget_listings.append(l)
                else:
                    other_listings.append(l)
            else:
                other_listings.append(l)

        # Sort by price
        budget_listings.sort(key=lambda x: x.get("price_numeric", 99999))
        other_listings.sort(key=lambda x: x.get("price_numeric", 99999))

        # Summary
        print(f"\n{'=' * 55}", flush=True)
        print(f"Total unique listings scraped: {len(all_unique)}", flush=True)
        print(f"Within budget (≤$2,000): {len(budget_listings)}", flush=True)
        print(f"Over budget: {len(other_listings)}", flush=True)

        if budget_listings:
            print(f"\nBudget listings:", flush=True)
            for l in budget_listings[:10]:
                print(f"  ${l.get('price_numeric', '?'):,} — {l.get('address', 'N/A')}", flush=True)

        # Save
        output = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_scraped": len(all_unique),
            "budget_count": len(budget_listings),
            "results": {
                "budget_listings": budget_listings,
                "other_listings": other_listings[:20],
            },
            "all_unique": all_unique,
        }
        with open(OUT, "w") as f:
            json.dump(output, f, indent=2)
        print(f"\nSaved -> {OUT}", flush=True)

        print("\nClosing in 5s...", flush=True)
        time.sleep(5)
        browser.close()


if __name__ == "__main__":
    main()
