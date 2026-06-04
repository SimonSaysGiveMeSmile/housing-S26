#!/bin/bash
# execute_outreach.sh — Master script to automatically contact all listings
# This orchestrates the automated outreach process

echo "════════════════════════════════════════════════════════════════════"
echo "AUTOMATED HOUSING OUTREACH - EXECUTION SCRIPT"
echo "════════════════════════════════════════════════════════════════════"
echo ""
echo "This script will automatically contact housing listings for you."
echo ""

# Configuration check
echo "Step 1: Checking configuration..."
if ! grep -q "your-email@gmail.com" auto_reply_craigslist.py; then
    echo "  ✓ Email configuration looks set"
else
    echo "  ✗ ERROR: Email not configured!"
    echo ""
    echo "  Please edit auto_reply_craigslist.py and update:"
    echo "  YOUR_EMAIL = 'your-actual-email@gmail.com'"
    echo ""
    exit 1
fi

# Check dependencies
echo ""
echo "Step 2: Checking dependencies..."
if python3 -c "import playwright" 2>/dev/null; then
    echo "  ✓ Playwright installed"
else
    echo "  ✗ Installing Playwright..."
    pip3 install playwright
    playwright install chromium
fi

echo ""
echo "Step 3: Ready to execute!"
echo ""
echo "Choose execution mode:"
echo "  1) DRY RUN  - Test first 5 (safe, see what would happen)"
echo "  2) LIVE 10  - Contact first 10 listings (best deals)"
echo "  3) LIVE 20  - Contact first 20 listings"
echo "  4) LIVE ALL - Contact all 52 listings"
echo ""
read -p "Enter choice (1-4): " choice

case $choice in
    1)
        echo ""
        echo "Running DRY RUN on first 5 listings..."
        python3 auto_reply_craigslist.py --dry-run --limit 5
        ;;
    2)
        echo ""
        echo "⚠ LIVE MODE - Will actually send to 10 listings!"
        read -p "Are you sure? (yes/no): " confirm
        if [ "$confirm" = "yes" ]; then
            python3 auto_reply_craigslist.py --live --limit 10
        else
            echo "Cancelled."
        fi
        ;;
    3)
        echo ""
        echo "⚠ LIVE MODE - Will actually send to 20 listings!"
        read -p "Are you sure? (yes/no): " confirm
        if [ "$confirm" = "yes" ]; then
            python3 auto_reply_craigslist.py --live --limit 20
        else
            echo "Cancelled."
        fi
        ;;
    4)
        echo ""
        echo "⚠⚠⚠ LIVE MODE - Will send to ALL 52 listings! ⚠⚠⚠"
        read -p "Are you ABSOLUTELY sure? (yes/no): " confirm
        if [ "$confirm" = "yes" ]; then
            python3 auto_reply_craigslist.py --live --all
        else
            echo "Cancelled."
        fi
        ;;
    *)
        echo "Invalid choice"
        exit 1
        ;;
esac

echo ""
echo "════════════════════════════════════════════════════════════════════"
echo "Execution complete!"
echo "════════════════════════════════════════════════════════════════════"
