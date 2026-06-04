#!/usr/bin/env python3
"""Contact only good neighborhoods - NO East Palo Alto"""
import json
import webbrowser
import time

# Load queue
with open('/Users/test/Desktop/housing-S26/send_queue.json') as f:
    queue = json.load(f)

# Filter out East Palo Alto
good_neighborhoods = []
for listing in queue:
    location = listing.get('location', '').lower()
    body = listing.get('body', '').lower()
    title = listing.get('title', '').lower()

    # Skip if East Palo Alto
    if 'east palo alto' in location or 'east palo alto' in body or 'epa' in location:
        continue

    # Keep only good neighborhoods
    if any(area in location or area in body for area in
           ['palo alto', 'menlo park', 'mountain view', 'los altos', 'atherton', 'stanford']):
        good_neighborhoods.append(listing)

# Sort by price
good_neighborhoods.sort(key=lambda x: x.get('price_numeric', 9999))

print("\n" + "="*70)
print("GOOD NEIGHBORHOODS ONLY - NO EAST PALO ALTO")
print("="*70)
print(f"\nFiltered: {len(good_neighborhoods)} listings in good areas")
print(f"Removed: {len(queue) - len(good_neighborhoods)} East Palo Alto listings")
print("\nTop 15 Best Deals:")
print("-"*70)

for i, listing in enumerate(good_neighborhoods[:15], 1):
    price = listing.get('price_numeric', '?')
    title = listing.get('title', '')[:45]
    location = listing.get('location', '')
    print(f"{i:2}. ${price:4} - {title:45} ({location})")

print("\n" + "="*70)
print("\nYour message template:")
print("-"*70)
print("""Hi! I'm Simon, an incoming Stanford summer student starting on campus
June 1, 2026. I'm looking for a room for the summer and yours looks like
a great fit. (I saw it listed at $[PRICE]/mo, which works for me.) I'm a
non-smoker, no parties, quiet and clean. Is it still available, and would
a short summer stay work for you? Happy to arrange an in-person or video
tour at your convenience. Thanks so much for considering — Simon, 415-426-8741.""")
print("-"*70)
print(f"\nOpening top 15 in browser tabs in 3 seconds...")
time.sleep(3)

for listing in good_neighborhoods[:15]:
    webbrowser.open_new_tab(listing['url'])
    time.sleep(1)

print("\n✓ Opened 15 listings in good neighborhoods!")
print("\nGo through each tab and send your message!\n")

# Save filtered list
with open('/Users/test/Desktop/housing-S26/good_neighborhoods_only.json', 'w') as f:
    json.dump(good_neighborhoods, f, indent=2)

print(f"Saved filtered list to: good_neighborhoods_only.json")
