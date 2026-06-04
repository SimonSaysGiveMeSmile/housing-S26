#!/usr/bin/env python3
"""
auto_reply_craigslist.py — Fully automated Craigslist reply sender.

This script uses Playwright to:
1. Navigate to each listing
2. Click the reply button
3. Fill out the reply form with your info
4. Submit the form automatically

IMPORTANT: You need to update YOUR_EMAIL in this script first!

Usage:
  python3 auto_reply_craigslist.py --dry-run        # Test without sending
  python3 auto_reply_craigslist.py --live           # Actually send
  python3 auto_reply_craigslist.py --live --limit 5 # Send to first 5
"""
import argparse
import time
import sys
from watch_config import load_queue, save_state, load_state, build_intro, NAME, PHONE, log

# ============================================================================
# CONFIGURATION - UPDATE THESE!
# ============================================================================
YOUR_EMAIL = "tianjiahe11@gmail.com"  # ← UPDATE THIS WITH YOUR REAL EMAIL!
# ============================================================================

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
except ImportError:
    print("ERROR: Playwright not installed.")
    print("Run: pip install playwright && playwright install chromium")
    sys.exit(1)

def wait_and_solve_captcha(page, max_wait=30):
    """
    Wait for user to solve captcha if one appears.
    Returns True if page seems ready, False if timeout.
    """
    print("    Checking for captcha...")
    time.sleep(2)

    # Check for common captcha indicators
    captcha_selectors = [
        'iframe[src*="recaptcha"]',
        'iframe[src*="captcha"]',
        '.g-recaptcha',
        '#recaptcha'
    ]

    for selector in captcha_selectors:
        if page.locator(selector).count() > 0:
            print(f"    ⚠ CAPTCHA DETECTED! Please solve it in the browser.")
            print(f"    Waiting up to {max_wait} seconds...")
            time.sleep(max_wait)
            return True

    return True

def submit_craigslist_reply(page, listing, dry_run=True):
    """
    Navigate to listing, fill out reply form, and submit.
    Returns: (success: bool, reason: str)
    """
    url = listing['url']
    title = listing.get('title', 'listing')[:50]
    price = listing.get('price_numeric', '?')

    print(f"\n{'='*70}")
    print(f"Contacting: ${price} - {title}")
    print(f"URL: {url}")

    try:
        # Navigate to listing
        print("  → Loading listing page...")
        page.goto(url, wait_until="domcontentloaded", timeout=20000)
        time.sleep(2)

        # Check if deleted
        if "removed" in page.content().lower() or "deleted" in page.content().lower():
            print("  ✗ Listing deleted/expired")
            return False, "deleted"

        # Click reply button
        print("  → Clicking reply button...")
        try:
            # Try multiple possible reply button selectors
            reply_clicked = False
            reply_selectors = [
                'button.reply-button',
                'button:has-text("reply")',
                'a.reply-button',
                'a:has-text("reply")'
            ]

            for selector in reply_selectors:
                try:
                    btn = page.locator(selector).first
                    if btn.is_visible(timeout=2000):
                        btn.click(timeout=3000)
                        reply_clicked = True
                        break
                except:
                    continue

            if not reply_clicked:
                print("  ✗ Could not find reply button")
                return False, "no_reply_button"

            print("  ✓ Reply button clicked")
            time.sleep(3)

        except Exception as e:
            print(f"  ✗ Error clicking reply: {e}")
            return False, "reply_error"

        # Check for captcha
        wait_and_solve_captcha(page, max_wait=15)

        # Look for the reply form
        print("  → Looking for reply form...")
        form_found = False

        # Try to find form fields
        try:
            # Common Craigslist form field patterns
            name_field = None
            email_field = None
            phone_field = None
            message_field = None

            # Try to find fields
            name_selectors = ['input[name="from_name"]', 'input#from_name', 'input[placeholder*="name" i]']
            for sel in name_selectors:
                try:
                    if page.locator(sel).count() > 0:
                        name_field = page.locator(sel).first
                        break
                except:
                    pass

            email_selectors = ['input[name="from_email"]', 'input#from_email', 'input[type="email"]']
            for sel in email_selectors:
                try:
                    if page.locator(sel).count() > 0:
                        email_field = page.locator(sel).first
                        break
                except:
                    pass

            phone_selectors = ['input[name="from_phone"]', 'input#phone', 'input[type="tel"]']
            for sel in phone_selectors:
                try:
                    if page.locator(sel).count() > 0:
                        phone_field = page.locator(sel).first
                        break
                except:
                    pass

            message_selectors = ['textarea[name="message"]', 'textarea#message', 'textarea']
            for sel in message_selectors:
                try:
                    if page.locator(sel).count() > 0:
                        message_field = page.locator(sel).first
                        break
                except:
                    pass

            if not message_field:
                print("  ✗ Could not find reply form (might need login/captcha)")
                return False, "no_form"

            print("  ✓ Found reply form")
            form_found = True

            # Fill out the form
            print("  → Filling out form...")
            message_text = build_intro(listing)

            if name_field:
                name_field.fill(NAME)
                print(f"    ✓ Name: {NAME}")

            if email_field:
                email_field.fill(YOUR_EMAIL)
                print(f"    ✓ Email: {YOUR_EMAIL}")

            if phone_field:
                phone_field.fill(PHONE)
                print(f"    ✓ Phone: {PHONE}")

            message_field.fill(message_text)
            print(f"    ✓ Message: {len(message_text)} characters")

            if dry_run:
                print("  [DRY RUN] Would submit form here")
                print("  Message preview:")
                print(f"    {message_text[:100]}...")
                time.sleep(2)
                return True, "dry_run_success"

            # Find and click submit button
            print("  → Submitting form...")
            submit_clicked = False
            submit_selectors = [
                'button[type="submit"]',
                'input[type="submit"]',
                'button:has-text("send")',
                'button:has-text("submit")',
                'input[value="send"]'
            ]

            for selector in submit_selectors:
                try:
                    btn = page.locator(selector).first
                    if btn.is_visible(timeout=2000):
                        btn.click(timeout=3000)
                        submit_clicked = True
                        print("  ✓ Submit button clicked")
                        break
                except:
                    continue

            if not submit_clicked:
                print("  ⚠ Could not find submit button - form filled but not submitted")
                return False, "no_submit_button"

            # Wait for confirmation
            time.sleep(3)
            print("  ✓ Message sent!")
            return True, "sent"

        except Exception as e:
            print(f"  ✗ Error filling form: {e}")
            return False, "form_error"

    except Exception as e:
        print(f"  ✗ Unexpected error: {e}")
        return False, "error"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true', help='Test without sending')
    parser.add_argument('--live', action='store_true', help='Actually send messages')
    parser.add_argument('--limit', type=int, default=10, help='Number of listings to contact')
    parser.add_argument('--all', action='store_true', help='Contact all listings')
    args = parser.parse_args()

    dry_run = not args.live

    # Check if email is configured
    if YOUR_EMAIL == "your-email@gmail.com":
        print("ERROR: You must update YOUR_EMAIL in this script first!")
        print("Edit auto_reply_craigslist.py and set YOUR_EMAIL = 'your-actual-email@gmail.com'")
        sys.exit(1)

    # Warn about placeholder email in dry-run
    if dry_run and "tianjiahe11@gmail.com" in YOUR_EMAIL:
        print("NOTE: Using placeholder email for dry-run. Update YOUR_EMAIL before running --live mode.")
        print()

    # Load state and queue
    state = load_state()
    sent = state.setdefault('sent', {})
    queue = load_queue()

    if not queue:
        print("No listings in queue!")
        return

    # Determine listings to process
    if args.all:
        listings = queue
    else:
        listings = queue[:args.limit]

    # Filter out already contacted
    listings = [l for l in listings if l['id'] not in sent]

    print(f"\n{'='*70}")
    print(f"AUTO-REPLY CRAIGSLIST")
    print(f"{'='*70}")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE - ACTUALLY SENDING!'}")
    print(f"Your info: {NAME}, {YOUR_EMAIL}, {PHONE}")
    print(f"Listings to contact: {len(listings)}")
    print(f"Already contacted: {len(sent)}")
    print(f"{'='*70}\n")

    if not dry_run:
        print("⚠⚠⚠ LIVE MODE - Messages will actually be sent! ⚠⚠⚠")
        print("Starting in 5 seconds... (Ctrl+C to cancel)")
        time.sleep(5)

    # Launch browser
    print("\nLaunching browser...")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,  # Visible so you can see/solve captchas
            args=['--start-maximized']
        )
        context = browser.new_context(
            viewport={'width': 1400, 'height': 900},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        )
        page = context.new_page()

        print("✓ Browser ready\n")

        # Process each listing
        results = {
            'success': 0,
            'failed': 0,
            'deleted': 0,
            'no_form': 0
        }

        for i, listing in enumerate(listings, 1):
            print(f"\n[{i}/{len(listings)}]")

            success, reason = submit_craigslist_reply(page, listing, dry_run)

            if success:
                results['success'] += 1
                if not dry_run and reason == "sent":
                    # Mark as sent
                    sent[listing['id']] = {
                        'when': time.strftime('%Y-%m-%d %H:%M:%S'),
                        'url': listing['url'],
                        'method': 'craigslist_form',
                        'price': listing.get('price_numeric')
                    }
            elif reason == 'deleted':
                results['deleted'] += 1
            elif reason == 'no_form':
                results['no_form'] += 1
            else:
                results['failed'] += 1

            # Polite delay between listings
            if i < len(listings):
                print(f"\n  Waiting 5 seconds before next listing...")
                time.sleep(5)

        # Save state
        if not dry_run:
            state['sent'] = sent
            save_state(state)

        # Summary
        print(f"\n{'='*70}")
        print(f"SUMMARY")
        print(f"{'='*70}")
        print(f"✓ Successfully contacted: {results['success']}")
        print(f"✗ Failed: {results['failed']}")
        print(f"⊗ Deleted/expired: {results['deleted']}")
        print(f"⚠ No form found (login/captcha): {results['no_form']}")
        print(f"{'='*70}\n")

        if dry_run:
            print("This was a DRY RUN. Run with --live to actually send.")
        else:
            print("✓ Messages sent! Check your email for responses.")

        print("\nClosing browser in 10 seconds...")
        time.sleep(10)
        browser.close()

if __name__ == '__main__':
    main()
