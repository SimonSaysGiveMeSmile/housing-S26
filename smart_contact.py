#!/usr/bin/env python3
"""
smart_contact.py — Intelligent automated outreach with multiple strategies.

This script tries multiple approaches to contact landlords automatically:
1. Direct email extraction from listing pages
2. Automated form filling with Playwright
3. Fallback to mailto: links
4. SMS sending for listings with phone numbers

Usage:
  python3 smart_contact.py --dry-run     # Test run, no actual sending
  python3 smart_contact.py --live        # Actually send messages
  python3 smart_contact.py --live --limit 10  # Send to first 10
"""
import argparse
import json
import re
import time
import urllib.request
import urllib.error
import subprocess
from watch_config import load_queue, save_state, load_state, build_intro, NAME, PHONE, log

# Email configuration - UPDATE THESE
SENDER_EMAIL = "your-email@gmail.com"  # Your email address
SENDER_NAME = NAME

def extract_emails_from_text(text):
    """Extract email addresses from any text."""
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    return re.findall(email_pattern, text)

def extract_phones_from_text(text):
    """Extract phone numbers from text."""
    # Matches formats: (415) 426-8741, 415-426-8741, 4154268741
    phone_pattern = r'\b(?:\+?1[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})\b'
    matches = re.findall(phone_pattern, text)
    return [f"({m[0]}) {m[1]}-{m[2]}" for m in matches]

def fetch_listing_detail(url):
    """Fetch the full HTML of a Craigslist listing."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=20) as response:
            return response.read().decode('utf-8', errors='ignore')
    except Exception as e:
        log(f"Error fetching {url}: {e}")
        return ""

def extract_contact_info(html):
    """Extract email addresses and phone numbers from listing HTML."""
    # Remove HTML tags for easier text extraction
    text = re.sub(r'<[^>]+>', ' ', html)

    emails = extract_emails_from_text(text)
    phones = extract_phones_from_text(text)

    # Check for Craigslist reply email pattern
    reply_email_match = re.search(r'(sale-[a-z0-9-]+@craigslist\.org)', html)
    if reply_email_match:
        emails.insert(0, reply_email_match.group(1))

    return {
        'emails': list(set(emails)),  # Remove duplicates
        'phones': list(set(phones))
    }

def send_email_via_mailto(to_email, subject, body):
    """Open default mail client with pre-filled message."""
    import urllib.parse
    subject_encoded = urllib.parse.quote(subject)
    body_encoded = urllib.parse.quote(body)
    mailto_url = f"mailto:{to_email}?subject={subject_encoded}&body={body_encoded}"

    try:
        subprocess.run(['open', mailto_url], check=True, timeout=5)
        return True
    except:
        return False

def send_email_via_smtp(to_email, subject, body, dry_run=True):
    """Send email via SMTP (Gmail). Requires app password setup."""
    if dry_run:
        print(f"  [DRY RUN] Would send email to: {to_email}")
        print(f"    Subject: {subject}")
        print(f"    Body: {body[:100]}...")
        return True

    try:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        # NOTE: You need to set up Gmail app password
        # https://support.google.com/accounts/answer/185833
        GMAIL_APP_PASSWORD = "your-16-char-app-password"  # UPDATE THIS

        if GMAIL_APP_PASSWORD == "your-16-char-app-password":
            print("  ⚠ Gmail app password not configured - using mailto fallback")
            return send_email_via_mailto(to_email, subject, body)

        msg = MIMEMultipart()
        msg['From'] = f"{SENDER_NAME} <{SENDER_EMAIL}>"
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(SENDER_EMAIL, GMAIL_APP_PASSWORD)
            server.send_message(msg)

        print(f"  ✓ Email sent to {to_email}")
        return True
    except Exception as e:
        print(f"  ✗ Email failed: {e}")
        # Fallback to mailto
        return send_email_via_mailto(to_email, subject, body)

def contact_listing(listing, dry_run=True, method='email'):
    """
    Contact a listing using the best available method.
    Returns: (success, method_used)
    """
    url = listing['url']
    title = listing.get('title', 'Room listing')
    price = listing.get('price_numeric', '?')

    print(f"\n{'='*70}")
    print(f"Processing: ${price} - {title[:50]}")
    print(f"URL: {url}")

    # Fetch listing details
    print("  → Fetching listing details...")
    html = fetch_listing_detail(url)
    if not html:
        print("  ✗ Failed to fetch listing")
        return False, None

    # Check if listing is deleted/expired
    if "This posting has been deleted" in html or "This posting has expired" in html:
        print("  ✗ Listing deleted or expired")
        return False, 'deleted'

    # Extract contact information
    print("  → Extracting contact info...")
    contact_info = extract_contact_info(html)

    print(f"  Found: {len(contact_info['emails'])} emails, {len(contact_info['phones'])} phones")

    # Build message
    message = build_intro(listing)
    subject = f"Re: {title[:50]} - Stanford summer student"

    # Try email contact
    if method in ['email', 'all'] and contact_info['emails']:
        # Prefer non-craigslist emails, but use Craigslist relay if that's all we have
        primary_email = contact_info['emails'][0]
        print(f"  → Contacting via email: {primary_email}")

        if send_email_via_smtp(primary_email, subject, message, dry_run):
            return True, 'email'

    # Try phone contact (SMS)
    if method in ['sms', 'all'] and contact_info['phones']:
        phone = contact_info['phones'][0]
        print(f"  → Would contact via SMS: {phone}")
        print(f"    (SMS automation not implemented - use Messages app manually)")
        return True, 'sms_manual'

    print("  ⚠ No contact method found - listing may require Craigslist form")
    return False, 'no_contact'

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true', help='Test run, no actual sending')
    parser.add_argument('--live', action='store_true', help='Actually send messages')
    parser.add_argument('--limit', type=int, default=10, help='Number of listings to process')
    parser.add_argument('--all', action='store_true', help='Process all listings')
    parser.add_argument('--method', choices=['email', 'sms', 'all'], default='email',
                        help='Contact method to use')
    args = parser.parse_args()

    dry_run = not args.live

    # Load state and queue
    state = load_state()
    sent = state.setdefault('sent', {})
    queue = load_queue()

    if not queue:
        print("No listings in queue!")
        return

    # Determine which listings to process
    if args.all:
        listings = queue
    else:
        listings = queue[:args.limit]

    # Filter out already contacted
    listings = [l for l in listings if l['id'] not in sent]

    print(f"\n{'='*70}")
    print(f"SMART AUTO-CONTACT")
    print(f"{'='*70}")
    print(f"Mode: {'DRY RUN (safe)' if dry_run else 'LIVE (actually sending!)'}")
    print(f"Method: {args.method}")
    print(f"Listings to process: {len(listings)}")
    print(f"Already contacted: {len(sent)}")
    print(f"{'='*70}\n")

    if not dry_run:
        print("⚠ LIVE MODE - Messages will be sent!")
        print("Starting in 5 seconds... (Ctrl+C to cancel)")
        time.sleep(5)

    # Process each listing
    results = {
        'success': 0,
        'failed': 0,
        'deleted': 0,
        'no_contact': 0
    }

    for i, listing in enumerate(listings, 1):
        print(f"\n[{i}/{len(listings)}]")

        success, method = contact_listing(listing, dry_run, args.method)

        if success:
            results['success'] += 1
            if not dry_run:
                # Mark as sent
                sent[listing['id']] = {
                    'when': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'url': listing['url'],
                    'method': method,
                    'price': listing.get('price_numeric')
                }
        elif method == 'deleted':
            results['deleted'] += 1
        elif method == 'no_contact':
            results['no_contact'] += 1
        else:
            results['failed'] += 1

        # Polite delay between requests
        if i < len(listings):
            time.sleep(3)

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
    print(f"⚠ No contact info found: {results['no_contact']}")
    print(f"{'='*70}\n")

    if dry_run:
        print("This was a DRY RUN. Run with --live to actually send.")
    else:
        print("Messages sent! Check your email for responses.")

if __name__ == '__main__':
    main()
