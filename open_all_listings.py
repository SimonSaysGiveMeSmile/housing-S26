#!/usr/bin/env python3
"""Open all listings under $1,400 in one browser window."""
import json
import subprocess
import time

ROOT = "/Users/test/Desktop/housing-S26"

urls = []

# SpareRoom listings
with open(f"{ROOT}/all_listings_current.json") as f:
    for r in json.load(f):
        price_str = r.get("price", "")
        import re
        nums = re.findall(r'[\d,]+', price_str.replace('$', ''))
        if nums and int(nums[0].replace(',', '')) <= 1400:
            if r.get("url"):
                urls.append(r["url"])

# Zillow budget
try:
    with open(f"{ROOT}/zillow_sf.json") as f:
        zd = json.load(f)
        for l in zd.get("results", {}).get("budget_listings", []):
            if l.get("price_numeric", 99999) <= 1400:
                url = l.get("url", "")
                if url and not url.startswith("http"):
                    url = "https://www.zillow.com" + url
                if url:
                    urls.append(url)
except Exception:
    pass

print(f"Opening {len(urls)} listings in your browser...")
for i, url in enumerate(urls):
    subprocess.run(["open", url])
    if i < len(urls) - 1:
        time.sleep(0.3)

print("Done. All tabs opened.")
