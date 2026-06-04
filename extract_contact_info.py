#!/usr/bin/env python3
"""Extract phone numbers and emails from specific Craigslist listings"""
import urllib.request
import re
import json

urls = [
    "https://sfbay.craigslist.org/pen/apa/d/menlo-park-lovely-cozy-little-cottage/7936493194.html",
    "https://sfbay.craigslist.org/pen/sub/d/palo-alto-one-bedroom-flat-for-rent/7936614381.html",
    "https://sfbay.craigslist.org/pen/apa/d/redwood-city-bd-ba-lower-level-in-law/7938345199.html",
    "https://sfbay.craigslist.org/pen/apa/d/menlo-park-open-house-605-willow-rd-am/7934591226.html",
    "https://sfbay.craigslist.org/pen/roo/d/palo-alto-good-condo/7937669933.html",
    "https://sfbay.craigslist.org/pen/roo/d/palo-alto-private-bathroom-master-suite/7937203708.html"
]

def fetch_listing(url):
    """Fetch HTML content"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=20) as response:
            return response.read().decode('utf-8', errors='ignore')
    except Exception as e:
        return None

def extract_phones(text):
    """Extract phone numbers from text"""
    # Remove HTML tags first
    text = re.sub(r'<[^>]+>', ' ', text)

    # Patterns for phone numbers
    patterns = [
        r'\b(\d{3})[.-]?(\d{3})[.-]?(\d{4})\b',  # 650-555-1234 or 6505551234
        r'\((\d{3})\)\s*(\d{3})[.-]?(\d{4})\b',  # (650) 555-1234
        r'\b1?[.-]?\(?(\d{3})\)?[.-]?(\d{3})[.-]?(\d{4})\b',  # Various formats
    ]

    phones = set()
    for pattern in patterns:
        matches = re.finditer(pattern, text)
        for match in matches:
            groups = match.groups()
            if len(groups) >= 3:
                phone = f"({groups[0]}) {groups[1]}-{groups[2]}"
                # Filter out common false positives
                if groups[0] not in ['000', '111', '123']:
                    phones.add(phone)

    return list(phones)

def extract_emails(text):
    """Extract email addresses"""
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    emails = re.findall(email_pattern, text)
    # Filter out Craigslist system emails
    return [e for e in emails if 'craigslist.org' in e or '@' in e]

def extract_title_and_price(html):
    """Extract listing title and price"""
    title_match = re.search(r'<title>(.*?)</title>', html)
    title = title_match.group(1) if title_match else "Unknown"

    price_match = re.search(r'class="price"[^>]*>([^<]+)', html)
    price = price_match.group(1) if price_match else "?"

    return title, price

print("\n" + "="*70)
print("CONTACT INFORMATION EXTRACTION")
print("="*70)

results = []

for i, url in enumerate(urls, 1):
    print(f"\n[{i}/{len(urls)}] Fetching: {url.split('/')[-2]}")

    html = fetch_listing(url)
    if not html:
        print("  ✗ Failed to fetch")
        continue

    if "removed" in html.lower() or "deleted" in html.lower():
        print("  ✗ Listing deleted/expired")
        continue

    title, price = extract_title_and_price(html)
    phones = extract_phones(html)
    emails = extract_emails(html)

    result = {
        "url": url,
        "title": title[:60],
        "price": price,
        "phones": phones,
        "emails": emails
    }
    results.append(result)

    print(f"  Title: {title[:60]}")
    print(f"  Price: {price}")

    if phones:
        print(f"  ✓ Phone(s) found: {', '.join(phones)}")
    else:
        print(f"  ✗ No phone numbers found")

    if emails:
        print(f"  ✓ Email(s) found: {', '.join(emails)}")
    else:
        print(f"  ✗ No emails found (may require Craigslist reply form)")

# Save results
output_file = "/Users/test/Desktop/housing-S26/contact_info_extracted.json"
with open(output_file, 'w') as f:
    json.dump(results, f, indent=2)

print("\n" + "="*70)
print("SUMMARY")
print("="*70)

for i, result in enumerate(results, 1):
    print(f"\n{i}. {result['title']}")
    print(f"   Price: {result['price']}")
    if result['phones']:
        print(f"   📞 Phone: {', '.join(result['phones'])}")
    else:
        print(f"   📞 Phone: Not listed (use Craigslist reply form)")
    if result['emails']:
        print(f"   📧 Email: {', '.join(result['emails'])}")
    else:
        print(f"   📧 Email: Use Craigslist reply form")
    print(f"   🔗 {result['url']}")

print(f"\n💾 Detailed results saved to: {output_file}")
print("="*70 + "\n")
