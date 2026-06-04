#!/usr/bin/env python3
"""
show_contact_status.py - Quick view of contacted vs remaining properties
"""
import json

# Load data
with open('/Users/test/Desktop/housing-S26/send_queue.json') as f:
    queue = json.load(f)

with open('/Users/test/Desktop/housing-S26/watch_state.json') as f:
    state = json.load(f)

sent = state.get('sent', {})

# Filter good neighborhoods
good_neighborhoods = []
east_palo_alto = []

for listing in queue:
    location = listing.get('location', '').lower()
    body = listing.get('body', '').lower()

    if 'east palo alto' in location or 'east palo alto' in body or 'epa' in location:
        east_palo_alto.append(listing)
        continue

    if any(area in location or area in body for area in
           ['palo alto', 'menlo park', 'mountain view', 'los altos', 'atherton', 'stanford']):
        good_neighborhoods.append(listing)

good_neighborhoods.sort(key=lambda x: x.get('price_numeric', 9999))

print("\n" + "="*70)
print("HOUSING CONTACT STATUS")
print("="*70)
print(f"\nTotal listings: {len(queue)}")
print(f"  Good neighborhoods: {len(good_neighborhoods)}")
print(f"  East Palo Alto (excluded): {len(east_palo_alto)}")
print(f"\nAlready contacted: {len(sent)}")
print(f"Remaining to contact: {len(good_neighborhoods) - len(sent)}")

if sent:
    print("\n" + "-"*70)
    print("CONTACTED PROPERTIES:")
    print("-"*70)
    for listing in good_neighborhoods:
        if listing['id'] in sent:
            info = sent[listing['id']]
            print(f"✓ ${info.get('price'):4} - {listing.get('title', '')[:45]}")
            print(f"   {info.get('location')} - {info.get('when')}")

print("\n" + "-"*70)
print("REMAINING TO CONTACT:")
print("-"*70)

remaining = [l for l in good_neighborhoods if l['id'] not in sent]
for i, listing in enumerate(remaining[:15], 1):
    price = listing.get('price_numeric', '?')
    title = listing.get('title', '')[:45]
    location = listing.get('location', '')[:15]
    print(f"{i:2}. ${price:4} - {title} ({location})")

if len(remaining) > 15:
    print(f"\n... and {len(remaining) - 15} more")

print("\n" + "="*70)
print("\nCommands:")
print("  python3 track_contacts.py     - Mark properties as contacted")
print("  python3 show_contact_status.py - View this summary")
print("="*70 + "\n")
