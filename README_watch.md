# Palo Alto Housing Watch

Automated monitor for the summer-2026 Palo Alto room search. Every 30 minutes it
scans Craigslist Peninsula rooms, finds **new listings that are below budget and
available by June 1**, filters out scam-looking posts, notifies you, and queues
matches for outreach. A safe sender drafts polite replies, and a reply tracker
watches your email inbox.

## What each file does

| File | Role |
|------|------|
| `watch_config.py` | Shared settings: budget ($2,000 ceiling), criteria, scam rules, the (truthful) intro message, state + notifications. |
| `watch_listings.py` | One scan cycle. Parses each Craigslist result's **own** price, keeps below-budget + preferred-area listings, queues new ones, notifies. |
| `auto_send.py` | Reads the queue, opens each **detail page**, re-checks budget + June-1 date + scam, then drafts a reply. **Dry-run by default.** |
| `check_replies.py` | Scans your email inbox (IMAP) for landlord replies; `--browser` opens platform inboxes to review. |
| `watch_status.py` | **Real-time status** of all three scripts — live terminal view, one-shot print, or web dashboard. |
| `run_watch.sh` | Runs all three in order. Called by the scheduler. |
| `com.simon.housing-watch.plist` | launchd job — runs `run_watch.sh` every 30 min. |
| `secrets.example.json` | Template for IMAP creds. Copy to `secrets.json`, fill in. |

## Safety design (why it won't embarrass you)

This sends real messages under your name, so it's built cautious on purpose:

- **Dry-run by default.** `auto_send.py` sends nothing until you pass `--live`. The
  scheduler keeps it dry (`AUTO_SEND_LIVE=0`) until you flip it.
- **Budget verified twice.** A listing must have a real price ≤ **$2,000** — once
  at scan time, then re-confirmed on the detail page before any send. No price =
  not sent.
- **June-1 date gate.** Detail-page body must not say July/Aug/mid-late-June.
- **Scam filter.** Wire-transfer / sight-unseen / absurdly-cheap posts are flagged
  and **never auto-messaged** — surfaced for you to eyeball instead.
- **Never double-messages** the same listing (tracked in `watch_state.json`).
- **Send cap** (5/run) and **quiet hours** (8am–9pm) so it never looks like a bot.
- **Human in the loop on send.** Craigslist replies open your mail client pre-filled
  — you click send, so you see every outgoing message.
- **Secrets stay local.** Passwords live in `secrets.json` (gitignored), read by key
  name, never printed.

## One-time setup

1. **Email reply tracking (optional but recommended):**
   ```bash
   cp secrets.example.json secrets.json
   ```
   Edit `secrets.json` with your IMAP host + an **app password** (not your login
   password — see notes in the file). Use the inbox that gets Craigslist replies.

2. **Try it by hand first** (safe, sends nothing):
   ```bash
   ./run_watch.sh
   ```
   You'll get macOS notifications for new matches and see `[DRY] WOULD SEND …`
   lines in `watch.log`. Read a few cycles' worth so you trust what it picks.

3. **Check replies, including platform inboxes:**
   ```bash
   python3 check_replies.py --browser
   ```

## Going live with sending

Only after you've watched the dry runs and are happy with the picks:

```bash
# log into Craigslist in the browser it opens, solve any captcha, then:
python3 auto_send.py --live --limit 3
```

Start with a small `--limit`. Each send opens your mail client with the reply
pre-filled — review and hit send. To let the **scheduler** send automatically,
edit `com.simon.housing-watch.plist` and set `AUTO_SEND_LIVE` to `1` (a visible
browser will pop up each cycle, so most people prefer to keep sending manual).

## Install the 30-minute scheduler

```bash
cp com.simon.housing-watch.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.simon.housing-watch.plist
# check it:
launchctl list | grep housing-watch
# stop it later:
launchctl unload ~/Library/LaunchAgents/com.simon.housing-watch.plist
```

Logs: `watch.log` (activity), `scheduler.out.log` / `scheduler.err.log` (launchd).

## Real-time status monitoring

See what each script is doing at a glance — running vs idle, when it last ran,
its last result, queue depth, sends, and replies.

```bash
python3 watch_status.py           # live terminal dashboard, refreshes in place
python3 watch_status.py --once    # print status once (good for scripting/piping)
python3 watch_status.py --serve   # web dashboard at http://localhost:3112/
```

It's also wired into your existing dashboard server — start `palo_alto_server.py`
and open **http://localhost:3111/status** (auto-refreshes every 5s).

How it works: each script writes a heartbeat to `run_status.json` when it starts
and finishes (state, timestamp, one-line result, run count). `watch_status.py` is
a pure reader — it never sends or edits anything. Status dots mean:

- **running** — the script is mid-cycle right now
- **idle** — finished cleanly, waiting for the next 30-min tick
- **stale** — no run in over 45 min (scheduler may be stopped)
- **error** — last run reported a failure
- **never run** — no heartbeat yet

## What this can't do (honest limits)

- **Phone texts/calls** to your number aren't trackable — scripts remind you to
  check your phone manually.
- **Stanford R&DE / SUpost / Facebook groups** block automated fetch. The monitor
  logs reminder links; check those by hand.
- **SpareRoom / Reddit / Zillow** reply parsing is review-only (`--browser`),
  because each platform's page layout is brittle to scrape reliably.
- Listing **search results** lack dates, so the per-listing date filter runs on the
  **detail page** at send time — that's why some queued items get held with
  "start date looks July/Aug."

## Tuning

Edit `watch_config.py`:
- `MAX_BUDGET` — the price ceiling (currently 2000).
- `PREFERRED_AREAS` — neighborhoods to keep.
- `SCAM_KEYWORDS` — phrases that flag a post.
- `SEND_START_HOUR` / `SEND_END_HOUR` — quiet hours.
- `build_intro()` — the outreach message. Keep it honest.
