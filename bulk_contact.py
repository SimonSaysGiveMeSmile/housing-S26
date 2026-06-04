#!/usr/bin/env python3
"""
bulk_contact.py — Open all listings in browser tabs for rapid manual contact.

Since Craigslist blocks full automation with captchas, this script opens each
listing in a new browser tab so you can quickly click the "reply" button on
each one. Much faster than manual navigation, but keeps you in control.

Usage:
  python3 bulk_contact.py              # Opens Priority 1 (top 8)
  python3 bulk_contact.py --all        # Opens all 52 listings
  python3 bulk_contact.py --limit 15   # Opens first 15
"""
import argparse
import json
import time
import webbrowser
from watch_config import load_queue, build_intro, NAME, PHONE

def open_listings_in_browser(listings, delay=2):
    """Open each listing URL in a new browser tab with delay between opens."""
    print(f"\n{'='*70}")
    print(f"Opening {len(listings)} listings in your browser...")
    print(f"{'='*70}\n")

    print("YOUR CONTACT INFO:")
    print(f"  Name: {NAME}")
    print(f"  Phone: {PHONE}")
    print(f"\nMESSAGE TEMPLATE (copy this):")
    print("-" * 70)
    sample = build_intro({"price_numeric": 1200})
    print(sample)
    print("-" * 70)
    print("\nINSTRUCTIONS:")
    print("1. Each listing will open in a new tab")
    print("2. Click the 'reply' button on each listing")
    print("3. Paste the message above (replace $1,200 with actual price)")
    print("4. Send the message")
    print("5. Move to the next tab")
    print("\nOpening tabs in 5 seconds...")
    time.sleep(5)

    for i, listing in enumerate(listings, 1):
        url = listing.get("url", "")
        title = listing.get("title", "")[:50]
        price = listing.get("price_numeric", "?")

        print(f"{i}. Opening: ${price} - {title}")
        webbrowser.open_new_tab(url)

        # Add delay to avoid overwhelming the browser
        if i < len(listings):
            time.sleep(delay)

    print(f"\n✓ Opened {len(listings)} listings!")
    print(f"Now go through each tab and click 'reply' to send your message.\n")

def main():
    parser = argparse.ArgumentParser(description="Open Craigslist listings for rapid contact")
    parser.add_argument("--all", action="store_true", help="Open all 52 listings")
    parser.add_argument("--limit", type=int, help="Limit number of listings to open")
    parser.add_argument("--delay", type=float, default=2, help="Seconds between opening tabs (default: 2)")
    args = parser.parse_args()

    queue = load_queue()

    if not queue:
        print("No listings in queue!")
        return

    # Determine how many to open
    if args.limit:
        listings = queue[:args.limit]
        print(f"Opening first {args.limit} listings...")
    elif args.all:
        listings = queue
        print(f"Opening ALL {len(queue)} listings...")
    else:
        # Default: Priority 1 (best deals, typically first 8-10)
        listings = queue[:10]
        print(f"Opening Priority 1 listings (first 10)...")

    open_listings_in_browser(listings, delay=args.delay)

    print("\nTIPS:")
    print("  • Work through tabs left to right")
    print("  • Keep the message template handy")
    print("  • Check your email every hour for responses")
    print("  • Follow up within 1 hour of any reply")

if __name__ == "__main__":
    main()
