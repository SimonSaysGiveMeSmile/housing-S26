#!/usr/bin/env python3
"""
execute_mass_outreach.py — Final solution: Semi-automated batch processing

This opens listings in batches, auto-fills forms, you just:
1. Solve captchas when they appear
2. Click send buttons

Much faster than fully manual, works around Craigslist protections.
"""
import time
from playwright.sync_api import sync_playwright
from watch_config import load_queue, save_state, load_state, build_intro, NAME, PHONE

YOUR_EMAIL = "tianjiahe11@gmail.com"  # Update with your real email
BATCH_SIZE = 5  # Process 5 at a time
TOTAL_TO_CONTACT = 52  # All listings

def process_listing(page, listing, index, total):
    """Process one listing: navigate, click reply, fill form."""
    url = listing['url']
    title = listing.get('title', '')[:50]
    price = listing.get('price_numeric', '?')

    print(f"\n[{index}/{total}] ${price} - {title}")
    print(f"URL: {url}")

    try:
        page.goto(url, timeout=15000)
        time.sleep(2)

        # Click reply
        try:
            page.click('button:has-text("reply"), a:has-text("reply")', timeout=5000)
            print("  ✓ Clicked reply")
            time.sleep(3)
        except:
            print("  ⚠ No reply button - may be expired")
            return False

        # Check for direct email (some listings show email immediately)
        try:
            email_link = page.locator('a[href^="mailto:"]').first
            if email_link.is_visible(timeout=2000):
                email = email_link.get_attribute('href').replace('mailto:', '').split('?')[0]
                print(f"  ✓ Found email: {email}")
                print(f"  → Opening in mail app...")
                import subprocess, urllib.parse
                subject = urllib.parse.quote(f"Re: {title}")
                body = urllib.parse.quote(build_intro(listing))
                subprocess.run(['open', f'mailto:{email}?subject={subject}&body={body}'])
                time.sleep(2)
                return True
        except:
            pass

        # Fill form if present
        try:
            message_box = page.locator('textarea[name="message"], textarea').first
            if message_box.is_visible(timeout=3000):
                print("  ✓ Found form - filling...")

                # Fill fields
                try:
                    page.fill('input[name="from_name"]', NAME, timeout=2000)
                except: pass

                try:
                    page.fill('input[name="from_email"]', YOUR_EMAIL, timeout=2000)
                except: pass

                try:
                    page.fill('input[name="from_phone"]', PHONE, timeout=2000)
                except: pass

                # Fill message
                message_box.fill(build_intro(listing), timeout=3000)

                print("  ✓ Form filled!")
                print("  ⚠ CHECK FOR CAPTCHA then click SEND button")
                print("  Pausing 15 seconds for you to send...")
                time.sleep(15)
                return True
        except Exception as e:
            print(f"  ⚠ Form issue: {str(e)[:50]}")

    except Exception as e:
        print(f"  ✗ Error: {str(e)[:50]}")

    return False

def main():
    print("="*70)
    print("MASS OUTREACH EXECUTOR")
    print("="*70)
    print(f"Your info: {NAME}, {YOUR_EMAIL}, {PHONE}")
    print(f"Processing: {TOTAL_TO_CONTACT} listings in batches of {BATCH_SIZE}")
    print("="*70)
    print("\nYou will need to:")
    print("  1. Solve captchas when they appear")
    print("  2. Click SEND button after each form is filled")
    print("\nStarting in 5 seconds...")
    time.sleep(5)

    # Load queue
    queue = load_queue()[:TOTAL_TO_CONTACT]
    state = load_state()
    sent = state.setdefault('sent', {})

    # Filter already contacted
    to_contact = [l for l in queue if l['id'] not in sent]
    print(f"\nFound {len(to_contact)} listings to contact")

    if not to_contact:
        print("All listings already contacted!")
        return

    # Launch browser
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=['--start-maximized'])
        page = browser.new_page()

        contacted = 0
        for i, listing in enumerate(to_contact, 1):
            if process_listing(page, listing, i, len(to_contact)):
                contacted += 1
                # Mark as sent
                sent[listing['id']] = {
                    'when': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'url': listing['url'],
                    'price': listing.get('price_numeric')
                }

                # Save progress periodically
                if i % 5 == 0:
                    state['sent'] = sent
                    save_state(state)

            # Small delay between listings
            if i < len(to_contact):
                time.sleep(3)

        # Final save
        state['sent'] = sent
        save_state(state)

        print("\n" + "="*70)
        print(f"COMPLETE! Contacted {contacted}/{len(to_contact)} listings")
        print("="*70)
        print("\nClosing browser in 10 seconds...")
        time.sleep(10)
        browser.close()

if __name__ == '__main__':
    main()
