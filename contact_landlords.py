#!/usr/bin/env python3
"""
Housing outreach automation - contacts landlords on SpareRoom, Facebook, Reddit, Zillow
Usage: python3 contact_landlords.py
"""
import json
import time
import sys
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

LIVE_LOG = "/Users/test/Desktop/housing-S26/outreach_live.log"

def log(msg):
    print(msg, flush=True)
    with open(LIVE_LOG, "a") as f:
        f.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")

# Replace print globally so existing code writes to live log too
_builtins_print = print
def print(*args, **kwargs):
    msg = " ".join(str(a) for a in args)
    _builtins_print(msg, flush=True, **{k: v for k, v in kwargs.items() if k != 'flush'})
    try:
        with open(LIVE_LOG, "a") as f:
            f.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")
    except Exception:
        pass

# Your contact info
PHONE = "415-426-8741"
NAME = "Simon"
INTRO = f"""Hi! I'm {NAME}, Cornell grad working at a startup in SF. Looking for a place starting June 1, budget $1,600/mo all-inclusive. Non-smoker, no parties, very clean. Is this still available? Happy to chat or tour anytime — {PHONE}."""

# Listings to contact — Pac Heights 1mi radius + Dogpatch/Mission Bay/Potrero Hill, ≤$1,600
LISTINGS = [
    # SpareRoom — target areas
    "https://www.spareroom.com/flatshare/san_francisco/any/102567992",   # $350/wk Marina
    "https://www.spareroom.com/flatshare/san_francisco/any/102629109",   # $1,200 Cathedral Hill
    "https://www.spareroom.com/flatshare/san_francisco/any/102941425",   # $1,500 Russian Hill
    # Craigslist — target areas
    "https://sfbay.craigslist.org/sfc/roo/d/san-francisco-room-available-in-the/7934420349.html",      # $1,400 Presidio/Pac Heights
    "https://sfbay.craigslist.org/sfc/roo/d/san-francisco-room-for-rent-in-bedroom/7928728983.html",   # $1,550 Pac Heights
    "https://sfbay.craigslist.org/sfc/roo/d/san-francisco-spacious-room-for-rent-in/7933018196.html",  # $873 Potrero Hill
    "https://sfbay.craigslist.org/sfc/roo/d/san-francisco-sunny-bedroom-in-shared/7934097470.html",    # $1,334 Mission Bay
    "https://sfbay.craigslist.org/sfc/roo/d/san-francisco-room-unique-with-views/7934015296.html",     # $1,580 Mission Bay
    "https://sfbay.craigslist.org/sfc/roo/d/san-francisco-pet-friendly-houseshare/7933973154.html",    # $1,150 Mission Bay
    "https://sfbay.craigslist.org/sfc/roo/d/san-francisco-room-for-rent-in-bernal/7934339161.html",    # $1,297 Mission Bay
    "https://sfbay.craigslist.org/sfc/roo/d/san-francisco-private-bedroom-plus/7934517528.html",       # $700 Cow Hollow
    "https://sfbay.craigslist.org/sfc/roo/d/san-francisco-presidio-home-bedroom/7934194422.html",      # $1,262 Cow Hollow/Presidio
]

def contact_spareroom(page, url, message):
    """Contact a SpareRoom listing"""
    print(f"  Opening {url}")
    page.goto(url, wait_until="domcontentloaded")
    time.sleep(2)

    # Click "Message" button
    try:
        msg_btn = page.locator('a:has-text("Message"), button:has-text("Message")').first
        msg_btn.click(timeout=5000)
        time.sleep(2)

        # Fill message textarea
        textarea = page.locator('textarea[name="message"], textarea#message, textarea').first
        textarea.fill(message)
        time.sleep(1)

        # Click send
        send_btn = page.locator('button:has-text("Send"), input[type="submit"][value*="Send"]').first
        send_btn.click()
        time.sleep(2)

        print(f"  ✓ Message sent to {url}")
        return True
    except PlaywrightTimeout:
        print(f"  ⚠ Could not find message button (may need login) - {url}")
        return False

def contact_facebook(page, url, message):
    """Contact a Facebook Marketplace listing"""
    print(f"  Opening {url}")
    page.goto(url, wait_until="domcontentloaded")
    time.sleep(2)

    try:
        # Click "Message seller"
        msg_btn = page.locator('span:has-text("Message"), div:has-text("Message seller")').first
        msg_btn.click(timeout=5000)
        time.sleep(2)

        # Type message
        textarea = page.locator('div[contenteditable="true"], textarea').first
        textarea.fill(message)
        time.sleep(1)

        # Send
        send_btn = page.locator('div[aria-label*="Send"], button:has-text("Send")').first
        send_btn.click()
        time.sleep(2)

        print(f"  ✓ Message sent to {url}")
        return True
    except PlaywrightTimeout:
        print(f"  ⚠ Could not send message (may need login) - {url}")
        return False

def contact_reddit(page, url, message):
    """Send a Reddit DM to the post author"""
    print(f"  Opening {url}")
    page.goto(url, wait_until="domcontentloaded")
    time.sleep(2)

    try:
        # Get username from post
        author = page.locator('a[href^="/user/"], a[data-testid="post_author_link"]').first.inner_text()
        print(f"    Author: {author}")

        # Go to messages
        page.goto(f"https://www.reddit.com/message/compose/?to={author}")
        time.sleep(2)

        # Fill subject and message
        page.locator('input[name="subject"]').fill(f"Re: Your SF housing post")
        page.locator('textarea[name="text"]').fill(message)
        time.sleep(1)

        # Send
        page.locator('button:has-text("Send")').click()
        time.sleep(2)

        print(f"  ✓ DM sent to u/{author}")
        return True
    except PlaywrightTimeout:
        print(f"  ⚠ Could not send Reddit DM (may need login) - {url}")
        return False

def contact_zillow(page, url, message):
    """Contact a Zillow listing"""
    print(f"  Opening {url}")
    page.goto(url, wait_until="domcontentloaded")
    time.sleep(2)

    try:
        # Click "Request a tour" or "Contact"
        contact_btn = page.locator('button:has-text("Request"), button:has-text("Contact")').first
        contact_btn.click(timeout=5000)
        time.sleep(2)

        # Fill message
        textarea = page.locator('textarea[name="message"], textarea').first
        textarea.fill(message)
        time.sleep(1)

        # Submit
        submit_btn = page.locator('button[type="submit"]:has-text("Send"), button:has-text("Submit")').first
        submit_btn.click()
        time.sleep(2)

        print(f"  ✓ Message sent to {url}")
        return True
    except PlaywrightTimeout:
        print(f"  ⚠ Could not send message (may need login) - {url}")
        return False

def contact_craigslist(page, url, message):
    """Reply to a Craigslist listing"""
    print(f"  Opening {url}")
    page.goto(url, wait_until="domcontentloaded")
    time.sleep(2)

    try:
        # Click "reply" button
        reply_btn = page.locator('button.reply-button, button:has-text("reply")').first
        reply_btn.click(timeout=5000)
        time.sleep(2)

        # Look for email link or contact form
        email_link = page.locator('a.mailapp, a[href^="mailto:"]').first
        if email_link.is_visible(timeout=3000):
            email = email_link.get_attribute('href').replace('mailto:', '').split('?')[0]
            print(f"    Email found: {email}")
            # Compose via mailto
            import subprocess
            subject = "Re: Your room listing on Craigslist"
            mailto = f"mailto:{email}?subject={subject}&body={message}"
            subprocess.run(["open", mailto])
            time.sleep(3)
            print(f"  ✓ Email composed for {url}")
            return True

        # Try direct form if available
        textarea = page.locator('textarea#replytext, textarea[name="message"]').first
        if textarea.is_visible(timeout=3000):
            textarea.fill(message)
            send_btn = page.locator('button:has-text("Send"), button[type="submit"]').first
            send_btn.click()
            time.sleep(2)
            print(f"  ✓ Message sent to {url}")
            return True

        print(f"  ⚠ Could not find reply method - {url}")
        return False
    except PlaywrightTimeout:
        print(f"  ⚠ Could not reply (may need to solve captcha) - {url}")
        return False

def main():
    print("Housing Outreach Automation")
    print("=" * 60)
    print(f"Phone: {PHONE}")
    print(f"Listings to contact: {len(LISTINGS)}")
    print()

    if not LISTINGS:
        print("⚠ No listings configured. Add URLs to the LISTINGS array in the script.")
        return

    print("IMPORTANT: This will open a browser window.")
    print("You may need to log in to SpareRoom/Facebook/Reddit/Zillow manually.")
    print("The script will wait for you to log in, then proceed.")
    print()
    input("Press Enter to start...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # headless=False so you can see and login
        context = browser.new_context()
        page = context.new_page()

        results = {"sent": [], "failed": []}

        for i, url in enumerate(LISTINGS, 1):
            print(f"\n[{i}/{len(LISTINGS)}] Processing: {url}")

            try:
                if "spareroom.com" in url:
                    success = contact_spareroom(page, url, INTRO)
                elif "facebook.com" in url:
                    success = contact_facebook(page, url, INTRO)
                elif "reddit.com" in url:
                    success = contact_reddit(page, url, INTRO)
                elif "zillow.com" in url:
                    success = contact_zillow(page, url, INTRO)
                elif "craigslist.org" in url:
                    success = contact_craigslist(page, url, INTRO)
                else:
                    print(f"  ⚠ Unknown platform: {url}")
                    success = False

                if success:
                    results["sent"].append(url)
                else:
                    results["failed"].append(url)

                # Rate limit: wait between messages
                if i < len(LISTINGS):
                    print("  Waiting 10 seconds before next message...")
                    time.sleep(10)

            except Exception as e:
                print(f"  ✗ Error: {e}")
                results["failed"].append(url)

        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"✓ Sent: {len(results['sent'])}")
        print(f"✗ Failed: {len(results['failed'])}")

        if results["failed"]:
            print("\nFailed URLs (may need manual login or retry):")
            for url in results["failed"]:
                print(f"  - {url}")

        # Save log
        with open("/Users/test/Desktop/housing-S26/outreach_log.json", "w") as f:
            json.dump({
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "phone": PHONE,
                "results": results
            }, f, indent=2)

        print("\nLog saved to: /Users/test/Desktop/housing-S26/outreach_log.json")
        print("\nBrowser will close in 10 seconds...")
        time.sleep(10)

        browser.close()

if __name__ == "__main__":
    main()
