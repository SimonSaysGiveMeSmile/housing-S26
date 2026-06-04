#!/usr/bin/env python3
"""Quick contact - Opens top 10 priority listings for immediate manual contact"""
import webbrowser
import time

# Top 10 best deals to contact RIGHT NOW
top_listings = [
    ("$850 - Good condo", "https://sfbay.craigslist.org/pen/roo/d/palo-alto-good-condo/7937669933.html"),
    ("$950 - Convenient location", "https://sfbay.craigslist.org/pen/apa/d/palo-alto-convinennt-location-great-for/7936522629.html"),
    ("$955 - Downtown Palo Alto (1)", "https://sfbay.craigslist.org/pen/apa/d/palo-alto-fantastic-room-available-in/7932602167.html"),
    ("$955 - Downtown Palo Alto (2)", "https://sfbay.craigslist.org/pen/apa/d/palo-alto-charming-room-available-in/7932557248.html"),
    ("$1,050 - Near Facebook", "https://sfbay.craigslist.org/pen/roo/d/menlo-park-private-furnished-room/7936051548.html"),
    ("$1,050 - Menlo Park", "https://sfbay.craigslist.org/pen/roo/d/menlo-park-nice-room-for-rent/7934903541.html"),
    ("$1,100 - Near Stanford", "https://sfbay.craigslist.org/pen/roo/d/palo-alto-near-stanford-all-female/7935947132.html"),
    ("$1,185 - College Terrace 1 block from Stanford", "https://sfbay.craigslist.org/pen/roo/d/stanford-college-terrace-block-from/7937645925.html"),
    ("$1,200 - Menlo Park (1)", "https://sfbay.craigslist.org/pen/roo/d/menlo-park-room-for-rent-cuarto-de/7936246919.html"),
    ("$1,200 - Menlo Park (2)", "https://sfbay.craigslist.org/pen/roo/d/menlo-park-cuarto-de-renta-menlo-park/7935678965.html"),
]

print("\n" + "="*70)
print("OPENING TOP 10 PRIORITY LISTINGS")
print("="*70)
print("\nYour message template:")
print("-"*70)
print("""Hi! I'm Simon, an incoming Stanford summer student starting on campus
June 1, 2026. I'm looking for a room for the summer and yours looks like
a great fit. (I saw it listed at $[PRICE]/mo, which works for me.) I'm a
non-smoker, no parties, quiet and clean. Is it still available, and would
a short summer stay work for you? Happy to arrange an in-person or video
tour at your convenience. Thanks so much for considering — Simon, 415-426-8741.""")
print("-"*70)
print("\nOpening listings in 3 seconds...\n")
time.sleep(3)

for i, (title, url) in enumerate(top_listings, 1):
    print(f"{i}. {title}")
    webbrowser.open_new_tab(url)
    time.sleep(1)

print("\n✓ All 10 listings opened!")
print("\nFor each tab:")
print("  1. Click 'reply' button")
print("  2. Paste your message (update the price)")
print("  3. Click 'send'")
print("  4. Move to next tab\n")
