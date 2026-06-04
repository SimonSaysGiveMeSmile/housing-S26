#!/usr/bin/env python3
"""
auto_send_with_alerts.py - Automated sending with captcha alerts

This script will:
1. Attempt to send messages automatically
2. Alert you (beep + notification) when captcha is needed
3. Wait for you to solve it
4. Continue automatically
5. Track all progress
"""
import time
import subprocess
from playwright.sync_api import sync_playwright
from watch_config import load_queue, save_state, load_state, build_intro, NAME, PHONE, notify

YOUR_EMAIL = "tianjiahe11@gmail.com"

def beep_alert():
    """Play system beep to alert user"""
    subprocess.run(['afplay', '/System/Library/Sounds/Glass.aiff'], check=False)

def check_for_captcha(page):
    """Check if captcha is present on page"""
    captcha_selectors = [
        'iframe[src*="recaptcha"]',
        'iframe[src*="captcha"]',
        '.g-recaptcha',
        '#recaptcha',
        '[class*="captcha"]'
    ]

    for selector in captcha_selectors:
        if page.locator(selector).count() > 0:
            return True
    return False

def wait_for_captcha_solve(page, listing_info):
    """Alert user and wait for captcha to be solved"""
    print("\n" + "!"*70)
    print("⚠️  CAPTCHA DETECTED!")
    print(f"    Listing: {listing_info}")
    print("!"*70)

    # Multiple alerts
    beep_alert()
    notify("Captcha Needed!", f"Please solve captcha for: {listing_info}")

    print("\n👉 PLEASE SOLVE THE CAPTCHA IN THE BROWSER WINDOW")
    print("   The script will wait for you...")
    print("\n   Checking every 5 seconds...")

    # Wait for captcha to be solved (check if form becomes available)
    max_wait = 120  # 2 minutes max
    waited = 0

    while waited < max_wait:
        time.sleep(5)
        waited += 5

        # Check if we can now access the form
        if page.locator('textarea[name="message"], textarea').count() > 0:
            print("\n✓ Captcha appears to be solved! Continuing...")
            beep_alert()
            return True

        print(f"   Still waiting... ({waited}s / {max_wait}s)")

    print("\n⚠️  Timeout waiting for captcha. Skipping this listing.")
    return False

def send_to_listing(page, listing, index, total):
    """Send message to one listing with captcha handling"""
    url = listing['url']
    title = listing.get('title', '')[:50]
    price = listing.get('price_numeric', '?')
    location = listing.get('location', '')

    print(f"\n{'='*70}")
    print(f"[{index}/{total}] ${price} - {title}")
    print(f"Location: {location}")
    print(f"URL: {url}")
    print("="*70)

    try:
        # Navigate
        print("  → Loading page...")
        page.goto(url, timeout=20000)
        time.sleep(2)

        # Check if deleted
        if "deleted" in page.content().lower() or "expired" in page.content().lower():
            print("  ✗ Listing deleted/expired")
            return False, "deleted"

        # Click reply
        print("  → Clicking reply button...")
        try:
            page.locator('button:has-text("reply"), a:has-text("reply")').first.click(timeout=8000)
            print("  ✓ Reply button clicked")
            time.sleep(3)
        except:
            print("  ✗ No reply button found")
            return False, "no_reply"

        # Check for captcha
        if check_for_captcha(page):
            if not wait_for_captcha_solve(page, f"${price} - {title}"):
                return False, "captcha_timeout"

        # Look for direct email link
        try:
            email_link = page.locator('a[href^="mailto:"]').first
            if email_link.is_visible(timeout=3000):
                href = email_link.get_attribute('href') or ''
                email = href.replace('mailto:', '').split('?')[0]
                print(f"  ✓ Found direct email: {email}")

                # Open in mail client
                import urllib.parse
                subject = urllib.parse.quote(f"Re: {title} - Stanford summer student")
                body = urllib.parse.quote(build_intro(listing))
                subprocess.run(['open', f'mailto:{email}?subject={subject}&body={body}'], check=False)

                print("  ✓ Opened in mail client - message composed!")
                time.sleep(3)
                return True, "email"
        except:
            pass

        # Try form submission
        print("  → Looking for reply form...")
        try:
            message_field = page.locator('textarea[name="message"], textarea').first

            if message_field.is_visible(timeout=5000):
                print("  ✓ Found form - filling out...")

                # Fill name
                try:
                    page.fill('input[name="from_name"]', NAME, timeout=2000)
                except: pass

                # Fill email
                try:
                    page.fill('input[name="from_email"], input[type="email"]', YOUR_EMAIL, timeout=2000)
                except: pass

                # Fill phone
                try:
                    page.fill('input[name="from_phone"], input[type="tel"]', PHONE, timeout=2000)
                except: pass

                # Fill message
                message_field.fill(build_intro(listing), timeout=3000)
                print("  ✓ Form filled!")

                # Try to submit
                print("  → Submitting form...")
                try:
                    submit_btn = page.locator('button[type="submit"], input[type="submit"], button:has-text("send")').first
                    if submit_btn.is_visible(timeout=2000):
                        submit_btn.click(timeout=3000)
                        print("  ✓ MESSAGE SENT!")
                        time.sleep(3)
                        return True, "form_sent"
                except:
                    print("  ⚠️  Form filled but couldn't auto-submit")
                    print("     Please click SEND button manually in the browser")
                    beep_alert()
                    notify("Manual Send Needed", f"Click SEND for: ${price} - {title}")
                    time.sleep(15)  # Give time to manually click
                    return True, "manual_send"
            else:
                print("  ✗ No form found")
                return False, "no_form"

        except Exception as e:
            print(f"  ✗ Form error: {str(e)[:50]}")
            return False, "form_error"

    except Exception as e:
        print(f"  ✗ Error: {str(e)[:50]}")
        return False, "error"

def main():
    print("\n" + "="*70)
    print("AUTOMATED CONTACT WITH CAPTCHA ALERTS")
    print("="*70)
    print(f"Your info: {NAME}, {YOUR_EMAIL}, {PHONE}")
    print("\nThis script will:")
    print("  • Automatically send messages when possible")
    print("  • BEEP and NOTIFY you when captcha is needed")
    print("  • Wait for you to solve captchas")
    print("  • Track all progress automatically")
    print("="*70)
    print("\nStarting in 5 seconds...")
    time.sleep(5)

    # Load data
    queue = load_queue()
    state = load_state()
    sent = state.setdefault('sent', {})

    # Filter good neighborhoods
    good_listings = []
    for listing in queue:
        location = listing.get('location', '').lower()
        body = listing.get('body', '').lower()

        if 'east palo alto' in location or 'east palo alto' in body:
            continue

        if any(area in location or area in body for area in
               ['palo alto', 'menlo park', 'mountain view', 'los altos', 'atherton', 'stanford']):
            good_listings.append(listing)

    # Sort by price
    good_listings.sort(key=lambda x: x.get('price_numeric', 9999))

    # Filter already contacted
    to_contact = [l for l in good_listings if l['id'] not in sent]

    print(f"\nFound {len(to_contact)} listings to contact (good neighborhoods only)")

    if not to_contact:
        print("All listings already contacted!")
        return

    # Launch browser
    print("\nLaunching browser...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=['--start-maximized'])
        page = browser.new_page()

        results = {
            'sent': 0,
            'failed': 0,
            'deleted': 0,
            'captcha_timeout': 0
        }

        for i, listing in enumerate(to_contact, 1):
            success, method = send_to_listing(page, listing, i, len(to_contact))

            if success:
                results['sent'] += 1
                # Mark as sent
                sent[listing['id']] = {
                    'when': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'url': listing['url'],
                    'price': listing.get('price_numeric'),
                    'location': listing.get('location'),
                    'method': method
                }

                # Save progress every 5 listings
                if i % 5 == 0:
                    state['sent'] = sent
                    save_state(state)
                    print(f"\n  💾 Progress saved: {results['sent']} sent so far")

            elif method == 'deleted':
                results['deleted'] += 1
            elif method == 'captcha_timeout':
                results['captcha_timeout'] += 1
            else:
                results['failed'] += 1

            # Small delay between listings
            if i < len(to_contact):
                print(f"\n  ⏸️  Waiting 5 seconds before next listing...")
                time.sleep(5)

        # Final save
        state['sent'] = sent
        save_state(state)

        # Summary
        print("\n" + "="*70)
        print("COMPLETE!")
        print("="*70)
        print(f"✓ Successfully sent: {results['sent']}")
        print(f"✗ Failed: {results['failed']}")
        print(f"⊗ Deleted: {results['deleted']}")
        print(f"⏱️  Captcha timeouts: {results['captcha_timeout']}")
        print(f"\nTotal contacted: {len(sent)}/{len(good_listings)}")
        print("="*70)

        notify("Outreach Complete!", f"Sent {results['sent']} messages. Check email for responses!")
        beep_alert()

        print("\nClosing browser in 10 seconds...")
        time.sleep(10)
        browser.close()

if __name__ == '__main__':
    main()
