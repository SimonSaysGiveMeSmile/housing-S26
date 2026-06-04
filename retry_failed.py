#!/usr/bin/env python3
"""Retry failed + Zillow outreach — user already logged in."""
import json
import time
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

PHONE = "415-426-8741"
NAME = "Simon"
INTRO = f"Hi! I'm {NAME}, Cornell grad working at a startup in SF. Looking for a place starting June 1. Non-smoker, no parties, very clean. Is this still available? Happy to chat or tour anytime — {PHONE}."

SPAREROOM_RETRY = [
    "https://www.spareroom.com/flatshare/san_francisco/diamond_heights/103043517",
    "https://www.spareroom.com/flatshare/san_francisco/central_richmond/102808240",
    "https://www.spareroom.com/flatshare/san_francisco/nob_hill/102629109",
    "https://www.spareroom.com/flatshare/san_francisco/diamond_heights/102729216",
    "https://www.spareroom.com/flatshare/san_francisco/ingleside_heights/103067014",
    "https://www.spareroom.com/flatshare/san_francisco/park_merced/102739337",
]

REDDIT_RETRY = [
    "https://www.reddit.com/r/SFBayHousing/comments/1szl2qn/2_rooms_available_june_1_mcallister_house/",
    "https://www.reddit.com/r/SFBayHousing/comments/1snbzy8/1_room_in_13person_community_house_in_sf/",
    "https://www.reddit.com/r/SFBayHousing/comments/1slxsx5/room_for_rent_hayes_valley_western_addition_11k/",
]

ZILLOW = [
    "https://www.zillow.com/apartments/san-francisco-ca/columbus-residence/CpcHVY/",
    "https://www.zillow.com/apartments/san-francisco-ca/klimm-apartments/CjgrxV/",
    "https://www.zillow.com/apartments/san-francisco-ca/cameo-apartments/ChVckw/",
]


def send_spareroom(page, url):
    print(f"  Opening {url}")
    page.goto(url, wait_until="networkidle", timeout=30000)
    time.sleep(5)

    # Look for message/contact button
    selectors = [
        'a:has-text("Message")',
        'button:has-text("Message")',
        'a:has-text("Contact")',
        'a:has-text("Send message")',
        'button:has-text("Send message")',
        'a.message-btn',
        'a[href*="message"]',
    ]

    clicked = False
    for sel in selectors:
        try:
            btn = page.locator(sel).first
            if btn.is_visible(timeout=2000):
                btn.click()
                clicked = True
                time.sleep(3)
                break
        except Exception:
            continue

    if not clicked:
        print(f"  ✗ No message button found")
        return False

    # Find visible textarea (not the recaptcha one)
    try:
        textareas = page.locator('textarea:visible')
        count = textareas.count()
        if count == 0:
            print(f"  ✗ No visible textarea after clicking message")
            return False

        textarea = textareas.first
        textarea.fill(INTRO)
        time.sleep(1)

        send_btn = page.locator('button:has-text("Send"), input[type="submit"][value*="Send"], button[type="submit"]:visible').first
        send_btn.click(timeout=5000)
        time.sleep(3)
        print(f"  ✓ Sent!")
        return True
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        return False


def send_reddit(page, url):
    print(f"  Opening {url}")
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    time.sleep(5)

    author = ""
    for sel in ['a[href*="/user/"]', '[data-testid="post_author_link"]']:
        try:
            el = page.locator(sel).first
            text = el.inner_text(timeout=5000)
            author = text.replace("u/", "").replace("/", "").strip()
            if author and author != "[deleted]":
                break
        except Exception:
            continue

    if not author:
        print(f"  ✗ Can't find author")
        return False

    print(f"  Author: u/{author}")
    page.goto(f"https://www.reddit.com/message/compose/?to={author}", wait_until="domcontentloaded", timeout=30000)
    time.sleep(5)

    if "login" in page.url.lower():
        print(f"  ✗ Not logged into Reddit")
        return False

    try:
        subj = page.locator('input[name="subject"], textarea[name="subject"]').first
        subj.wait_for(state="visible", timeout=10000)
        subj.fill("Re: Your SF housing post")
        time.sleep(0.5)

        body = page.locator('textarea[name="text"], textarea[name="message"]').first
        body.fill(INTRO)
        time.sleep(1)

        page.locator('button:has-text("Send"), button[type="submit"]').first.click(timeout=5000)
        time.sleep(3)
        print(f"  ✓ DM sent to u/{author}!")
        return True
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        return False


def send_zillow(page, url):
    print(f"  Opening {url}")
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    time.sleep(5)

    # Handle captcha
    title = page.title()
    if "denied" in title.lower():
        print("  ⚠ Captcha — solve it now! (waiting 30s)")
        time.sleep(30)

    # Look for contact/apply/request tour button
    selectors = [
        'button:has-text("Request")',
        'button:has-text("Contact")',
        'button:has-text("Apply")',
        'a:has-text("Request")',
        'a:has-text("Contact")',
        'button:has-text("Send")',
    ]

    clicked = False
    for sel in selectors:
        try:
            btn = page.locator(sel).first
            if btn.is_visible(timeout=3000):
                btn.click()
                clicked = True
                time.sleep(3)
                break
        except Exception:
            continue

    if not clicked:
        print(f"  ✗ No contact button found")
        return False

    # Fill form fields
    try:
        # Name field
        for sel in ['input[name="name"]', 'input[placeholder*="Name"]', 'input#name']:
            try:
                inp = page.locator(sel).first
                if inp.is_visible(timeout=2000):
                    inp.fill(NAME)
                    break
            except Exception:
                continue

        # Phone field
        for sel in ['input[name="phone"]', 'input[placeholder*="Phone"]', 'input#phone', 'input[type="tel"]']:
            try:
                inp = page.locator(sel).first
                if inp.is_visible(timeout=2000):
                    inp.fill(PHONE)
                    break
            except Exception:
                continue

        # Message field
        textarea = page.locator('textarea:visible').first
        textarea.wait_for(state="visible", timeout=5000)
        textarea.fill(INTRO)
        time.sleep(1)

        # Submit
        submit = page.locator('button[type="submit"]:visible, button:has-text("Send"):visible, button:has-text("Submit"):visible').first
        submit.click(timeout=5000)
        time.sleep(3)
        print(f"  ✓ Sent!")
        return True
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        return False


def main():
    print("Outreach Round 2 — SpareRoom retry + Reddit + Zillow")
    print("=" * 60)
    print()

    all_urls = SPAREROOM_RETRY + REDDIT_RETRY + ZILLOW
    print(f"Total to contact: {len(all_urls)}")
    print(f"  SpareRoom retry: {len(SPAREROOM_RETRY)}")
    print(f"  Reddit retry: {len(REDDIT_RETRY)}")
    print(f"  Zillow new: {len(ZILLOW)}")
    print()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            viewport={"width": 1400, "height": 900},
        )
        page = ctx.new_page()

        # Open SpareRoom login page directly
        print("Opening SpareRoom login page — log in now (60s)...")
        page.goto("https://www.spareroom.com/roommate/logon.pl", wait_until="domcontentloaded")
        time.sleep(60)
        print("Continuing...")

        results = {"sent": [], "failed": []}

        for i, url in enumerate(all_urls, 1):
            platform = "SpareRoom" if "spareroom" in url else "Reddit" if "reddit" in url else "Zillow"
            print(f"\n[{i}/{len(all_urls)}] [{platform}] {url.split('/')[-1] or url.split('/')[-2]}")

            try:
                if "spareroom.com" in url:
                    ok = send_spareroom(page, url)
                elif "reddit.com" in url:
                    ok = send_reddit(page, url)
                elif "zillow.com" in url:
                    ok = send_zillow(page, url)
                else:
                    ok = False

                results["sent" if ok else "failed"].append(url)

                if i < len(all_urls):
                    time.sleep(8)
            except Exception as e:
                print(f"  ✗ Error: {e}")
                results["failed"].append(url)

        print(f"\n{'=' * 60}")
        print(f"RESULTS: ✓ {len(results['sent'])} sent, ✗ {len(results['failed'])} failed")

        if results["sent"]:
            print("\nSuccessfully contacted:")
            for u in results["sent"]:
                print(f"  ✓ {u}")

        if results["failed"]:
            print("\nFailed:")
            for u in results["failed"]:
                print(f"  ✗ {u}")

        print("\nClosing in 5s...")
        time.sleep(5)
        browser.close()


if __name__ == "__main__":
    main()
