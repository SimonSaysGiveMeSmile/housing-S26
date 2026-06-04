#!/usr/bin/env python3
"""Scrape SpareRoom listings in Pacific Heights area + Dogpatch/Mission Bay/Potrero Hill."""
import re, json, time, urllib.request

# SpareRoom area slugs for target neighborhoods
AREA_SLUGS = [
    # Within 1 mile of Pacific Heights
    'pacific_heights', 'lower_pacific_heights', 'cow_hollow',
    'presidio_heights', 'laurel_heights', 'marina',
    'cathedral_hill', 'nob_hill', 'russian_hill',
    # Additional target areas
    'dogpatch', 'mission_bay', 'potrero_hill',
]

BUDGET = 1600

def get_listing_ids_from_search():
    """Search SpareRoom for each area and collect listing IDs."""
    ids = set()
    for slug in AREA_SLUGS:
        url = f'https://www.spareroom.com/flatshare/san_francisco/{slug}'
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'})
            resp = urllib.request.urlopen(req)
            html = resp.read().decode()
            found = re.findall(r'/flatshare/san_francisco/[^/]+/(\d+)', html)
            ids.update(found)
            print(f'  {slug}: {len(found)} listings found')
        except Exception as e:
            print(f'  {slug}: ERR {e}')
        time.sleep(0.5)
    return list(ids)

print("Searching SpareRoom for target areas...")
LISTING_IDS = get_listing_ids_from_search()
print(f"\nFound {len(LISTING_IDS)} unique listing IDs to check\n")

results = []
for lid in LISTING_IDS:
    url = f'https://www.spareroom.com/flatshare/san_francisco/any/{lid}'
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        resp = urllib.request.urlopen(req)
        html = resp.read().decode()

        title_m = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
        title = title_m.group(1).strip() if title_m else ''

        # Price — SpareRoom uses &#36; for $ in the price section
        price = ''
        price_m = re.search(r'price_room_only.*?<dt[^>]*>&#36;([\d,]+)\s*(monthly|/mo|per month|pcm)?', html, re.DOTALL | re.IGNORECASE)
        if price_m:
            price = '$' + price_m.group(1)
        if not price:
            price_m = re.search(r'&#36;([\d,]+)\s*monthly', html)
            if price_m:
                price = '$' + price_m.group(1)

        # Key-value pairs
        features = dict(re.findall(r'<dt[^>]*>([^<]+)</dt>\s*<dd[^>]*>\s*(?:<span[^>]*>)?([^<]+)', html))

        avail = features.get('Available', '').strip()
        min_term = features.get('Minimum term', '').strip()
        furnished = features.get('Furnishings', '').strip()
        parking = features.get('Parking', 'Not mentioned').strip()

        # Area detection
        area = ''
        area_patterns = ['Pacific Heights', 'Lower Pacific Heights', 'Cow Hollow',
                        'Presidio Heights', 'Laurel Heights', 'Marina',
                        'Cathedral Hill', 'Nob Hill', 'Russian Hill',
                        'Dogpatch', 'Mission Bay', 'Potrero Hill',
                        'Castro', 'Lower Haight', 'NoPa', 'Mission Dolores']
        for ap in area_patterns:
            if ap.lower() in html.lower():
                area = ap
                break

        price_num = int(price.replace('$', '').replace(',', '')) if price else 99999
        if price_num > BUDGET:
            print(f'  SKIP ${price_num} > ${BUDGET} | {area:22s} | {title[:40]}')
            continue

        results.append({
            'id': lid, 'title': title, 'price': price,
            'price_numeric': price_num,
            'avail': avail, 'min_term': min_term,
            'furnished': furnished, 'parking': parking,
            'area': area, 'url': url,
        })
        print(f'  {price:10s} | {area:22s} | {title[:45]}')
    except Exception as e:
        print(f'ERR {lid}: {e}')
    time.sleep(0.5)

with open('/Users/test/Desktop/housing-S26/pac_heights_listings.json', 'w') as f:
    json.dump(results, f, indent=2)
print(f'\nSaved {len(results)} listings')
