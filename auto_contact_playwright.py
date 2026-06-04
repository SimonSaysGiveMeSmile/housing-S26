#!/usr/bin/env python3
"""
auto_contact_playwright.py — Automated contact with human verification step.

Opens browser with Playwright, navigates to each listing, and AUTO-FILLS the
reply form. You just need to:
1. Solve any captchas that appear
2. Click the final "Send" button on each

Much faster than fully manual, but keeps you in control of what sends.

Usage:
  python3 auto_contact_playwright.py              # First 10 listings
  python3 auto_contact_playwright.py --limit 20   # First 20 listings
  python3 auto_contact_playwright.py --all        # All 52 listings
"""
import argparse
import time
import sys
from watch_config import load_queue, build_intro, NAME, PHONE, log

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
except ImportError:
    print("ERROR: playwright not installed.")
    print("Install with: pip install playwright && playwright install chromium")
    sys.exit(1)

def contact_listing(page, listing, auto_send=False):
    """
    Navigate to listing, click reply, fill out form.
    If auto_send=True, attempts to click send button.
    If auto_send=False, waits for you to click send manually.
    """
    url = listing["url"]
    title = listing.get("title", "")[:50]
    price = listing.get("price_numeric", "?")

    print(f"\n{'='*70}")
    print(f"Contacting: ${price} - {title}")
    print(f"URL: {url}")
    print(f"{'='*70}")

    try:
        # Navigate to listing
        page.goto(url, wait_until="domcontentloaded", timeout=15000)
        time.sleep(2)

        # Click reply button
        try:
            reply_btn = page.locator('button.reply-button, button:has-text("reply")').first
            reply_btn.click(timeout=8000)
            print("✓ Clicked reply button")
            time.sleep(3)
        except PWTimeout:
            print("⚠ Could not find reply button - listing may be expired")
            return False

        # Check for email link (direct contact)
        try:
            email_link = page.locator('a.mailapp, a[href^="mailto:"]').first
            if email_link.is_visible(timeout=3000):
                href = email_link.get_attribute("href") or ""
                email = href.replace("mailto:", "").split("?")[0]
                print(f"✓ Found direct email: {email}")

                # Open in mail client
                import subprocess, urllib.parse
                subject = urllib.parse.quote("Re: your room listing — Stanford summer student")
                message = build_intro(listing)
                body = urllib.parse.quote(message)
                subprocess.run(["open", f"mailto:{email}?subject={subject}&body={body}"], check=False)
                print("✓ Opened in mail client - review and send!")
                time.sleep(2)
                return True
        except:
            pass

        # Look for reply form (Craigslist's web form)
        try:
            # Common Craigslist form field IDs/names
            from_name = page.locator('input[name="from_name"], input#from_name').first
            from_email = page.locator('input[name="from_email"], input#from_email').first
            phone = page.locator('input[name="from_phone"], input#phone').first
            message = page.locator('textarea[name="message"], textarea#message').first

            if from_name.is_visible(timeout=3000):
                print("✓ Found reply form - filling out...")

                # Fill form
                from_name.fill(NAME, timeout=2000)
                from_email.fill("your-email@example.com", timeout=2000)  # YOU NEED TO UPDATE THIS
                if phone.is_visible():
                    phone.fill(PHONE, timeout=2000)

                msg_text = build_intro(listing)
                message.fill(msg_text, timeout=2000)

                print("✓ Form filled out")

                if auto_send:
                    # Try to find and click send button
                    send_btn = page.locator('button[type="submit"], button:has-text("send"), input[type="submit"]').first
                    if send_btn.is_visible(timeout=2000):
                        print("⚠ SEND button found - waiting 5 seconds for you to review...")
                        time.sleep(5)
                        print("  Press Ctrl+C now if you want to stop!")
                        time.sleep(2)
                        send_btn.click()
                        print("✓ Message sent!")
                        time.sleep(3)
                        return True
                else:
                    print("⚠ Form ready - CLICK THE SEND BUTTON MANUALLY")
                    print("  Waiting 15 seconds for you to send...")
                    time.sleep(15)
                    return True
        except PWTimeout:
            print("⚠ No reply form found - may need captcha or login")
            print("  The page is open - solve captcha if needed and submit manually")
            time.sleep(10)
            return False

    except Exception as e:
        print(f"✗ Error: {e}")
        return False

    return False

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="Contact all listings")
    parser.add_argument("--limit", type=int, default=10, help="Number of listings to contact")
    parser.add_argument("--auto-send", action="store_true", help="Auto-click send button (risky)")
    args = parser.parse_args()

    queue = load_queue()
    if not queue:
        print("No listings in queue!")
        return

    if args.all:
        listings = queue
    else:
        listings = queue[:args.limit]

    print(f"\n{'='*70}")
    print(f"AUTO-CONTACT SCRIPT")
    print(f"{'='*70}")
    print(f"Will process {len(listings)} listings")
    print(f"Auto-send: {'YES (risky!)' if args.auto_send else 'NO (you click send)'}")
    print(f"\nStarting in 5 seconds... (Ctrl+C to cancel)")
    print(f"{'='*70}\n")
    time.sleep(5)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=["--start-maximized"])
        context = browser.new_context(viewport={"width": 1400, "height": 900})
        page = context.new_page()

        print("\n✓ Browser open")
        print("  Solve any captchas that appear")
        print("  Check each message before it sends\n")

        contacted = 0
        for i, listing in enumerate(listings, 1):
            print(f"\n[{i}/{len(listings)}]")
            if contact_listing(page, listing, auto_send=args.auto_send):
                contacted += 1

            # Pause between listings
            if i < len(listings):
                print(f"\nMoving to next listing in 5 seconds...")
                time.sleep(5)

        print(f"\n{'='*70}")
        print(f"DONE!")
        print(f"{'='*70}")
        print(f"Successfully contacted: {contacted}/{len(listings)}")
        print(f"Check your email for responses!")
        print(f"\nClosing browser in 10 seconds...")
        time.sleep(10)

        browser.close()

if __name__ == "__main__":
    main()
