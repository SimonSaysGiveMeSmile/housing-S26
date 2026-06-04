#!/usr/bin/env python3
"""
track_contacts.py - Interactive tracking of contacted properties

Mark each property as contacted as you send messages.
"""
import json
import time
from datetime import datetime

# Load data
with open('/Users/test/Desktop/housing-S26/send_queue.json') as f:
    queue = json.load(f)

with open('/Users/test/Desktop/housing-S26/watch_state.json') as f:
    state = json.load(f)

# Filter good neighborhoods only
good_neighborhoods = []
for listing in queue:
    location = listing.get('location', '').lower()
    body = listing.get('body', '').lower()

    if 'east palo alto' in location or 'east palo alto' in body or 'epa' in location:
        continue

    if any(area in location or area in body for area in
           ['palo alto', 'menlo park', 'mountain view', 'los altos', 'atherton', 'stanford']):
        good_neighborhoods.append(listing)

good_neighborhoods.sort(key=lambda x: x.get('price_numeric', 9999))

print("\n" + "="*70)
print("CONTACT TRACKING - Mark properties as you contact them")
print("="*70)
print(f"\nTotal good neighborhoods: {len(good_neighborhoods)}")
print(f"Already contacted: {len(state.get('sent', {}))}")
print("\n" + "="*70)
print("\nEnter listing numbers as you send messages (comma-separated)")
print("Example: 1,2,3  or just: 1")
print("Type 'done' when finished, 'list' to see all, 'status' for summary")
print("="*70)

# Show current list
print("\nListings to contact:")
print("-"*70)
for i, listing in enumerate(good_neighborhoods[:20], 1):
    price = listing.get('price_numeric', '?')
    title = listing.get('title', '')[:40]
    location = listing.get('location', '')[:15]
    contacted = '✓' if listing['id'] in state.get('sent', {}) else ' '
    print(f"{contacted} {i:2}. ${price:4} - {title:40} ({location})")

if len(good_neighborhoods) > 20:
    print(f"\n... and {len(good_neighborhoods) - 20} more (type 'list' to see all)")

print("\n" + "-"*70)

while True:
    user_input = input("\nMark contacted (numbers or 'done'): ").strip().lower()

    if user_input == 'done':
        break

    if user_input == 'list':
        print("\nAll listings:")
        for i, listing in enumerate(good_neighborhoods, 1):
            price = listing.get('price_numeric', '?')
            title = listing.get('title', '')[:40]
            location = listing.get('location', '')[:15]
            contacted = '✓' if listing['id'] in state.get('sent', {}) else ' '
            print(f"{contacted} {i:2}. ${price:4} - {title:40} ({location})")
        continue

    if user_input == 'status':
        sent = state.get('sent', {})
        print(f"\nStatus: {len(sent)}/{len(good_neighborhoods)} contacted")
        if sent:
            print("\nRecently contacted:")
            for lid, info in list(sent.items())[-5:]:
                print(f"  - {info.get('when')}: ${info.get('price')}")
        continue

    # Parse numbers
    try:
        numbers = [int(n.strip()) for n in user_input.split(',')]

        for num in numbers:
            if 1 <= num <= len(good_neighborhoods):
                listing = good_neighborhoods[num - 1]

                # Mark as sent
                if 'sent' not in state:
                    state['sent'] = {}

                state['sent'][listing['id']] = {
                    'when': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'url': listing['url'],
                    'price': listing.get('price_numeric'),
                    'location': listing.get('location')
                }

                print(f"  ✓ Marked #{num}: ${listing.get('price_numeric')} - {listing.get('title', '')[:40]}")
            else:
                print(f"  ✗ Invalid number: {num}")

        # Save state
        with open('/Users/test/Desktop/housing-S26/watch_state.json', 'w') as f:
            json.dump(state, f, indent=2)

        print(f"\n  Saved! Total contacted: {len(state['sent'])}/{len(good_neighborhoods)}")

    except ValueError:
        print("  Invalid input. Use numbers like: 1,2,3 or commands: list, status, done")

# Final summary
print("\n" + "="*70)
print("FINAL SUMMARY")
print("="*70)
sent = state.get('sent', {})
print(f"Total contacted: {len(sent)}/{len(good_neighborhoods)}")
print(f"Remaining: {len(good_neighborhoods) - len(sent)}")
print("\nGood work! Check your email regularly for responses.")
print("="*70 + "\n")
