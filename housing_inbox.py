"""Private, local housing inbox. No message content is included in static exports."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / '.outreach'
STATE = OUT / 'inbox.json'
AUDIT = OUT / '2026-09-29.json'


def now():
    return datetime.now(timezone.utc).isoformat()


def read(path, default=None):
    try:
        return json.loads(Path(path).read_text())
    except FileNotFoundError:
        return {} if default is None else default


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    temp.chmod(0o600)
    temp.replace(path)


def digest(*parts):
    return hashlib.sha256('\0'.join(str(x) for x in parts).encode()).hexdigest()[:24]


def canonical(text):
    text = re.sub(r'[\w.+-]+@\[Link removed\]', '', text or '', flags=re.I)
    text = re.sub(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}', '', text or '')
    return re.sub(r'[^a-z0-9]', '', text.lower())


def timestamp(value):
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()
    except (ValueError, AttributeError, TypeError):
        return 0


def channel_for(listing_id):
    return {'fb': 'Facebook Messenger', 'ff': 'Furnished Finder', 'sr': 'SpareRoom', 'cl': 'Craigslist · email',
            'su': 'SUpost · email', 'zi': 'Zillow', 'apt': 'Apartments.com · email'}.get(listing_id.split('-')[0], 'Email')


def merge_message(state, message):
    """Stable native IDs prevent duplicate imports. Historical evidence is retained."""
    if not message.get('body', '').strip():
        return False
    message.setdefault('observed_at', now())
    message.setdefault('kind', 'message')
    message.setdefault('id', digest(message.get('source'), message.get('source_id'),
                                     message.get('listing_id'), message.get('body')))
    for old in state.setdefault('messages', []):
        if old['id'] == message['id']:
            old.update(message)
            return False
    state['messages'].append(message)
    return True


def import_audit(state, audit):
    for i, msg in enumerate(audit.get('messages', [])):
        if not msg.get('verified_sent'):
            continue
        lid = msg['listing_id']
        merge_message(state, dict(id=f'audit-out-{i}', source='audit', listing_id=lid,
            channel=channel_for(lid), direction='outgoing', sender='Simon',
            body=msg.get('message', ''), at=msg.get('sent_at') or msg.get('verified_at'),
            date_label='Time not recorded', kind='message',
            delivery='Accepted · delivery queued' if lid == 'su-130109474' else 'Verified sent',
            thread_url=msg.get('thread_url'), proof=msg.get('proof_file') or msg.get('confirmation'),
            observed_at=audit.get('updated_at')))
    for msg in audit.get('previous_conversations', []):
        merge_message(state, dict(id='audit-prior-' + msg['listing_id'], source='audit',
            listing_id=msg['listing_id'], channel='SpareRoom', direction='outgoing', sender='Simon',
            body=msg.get('latest_message', ''), kind='message', date_label='Earlier message · time not recorded',
            thread_url=msg.get('thread_url'), delivery='Verified in earlier thread',
            observed_at=audit.get('updated_at')))
    for i, msg in enumerate(audit.get('received_messages', [])):
        lid = msg['listing_id']
        sms = 'SMS' in msg.get('channel', '')
        merge_message(state, dict(id=f'audit-in-{i}', source='sms-import' if sms else 'audit',
            listing_id=lid, channel='SMS · imported screenshot' if sms else channel_for(lid),
            direction='incoming', sender=msg.get('sender', 'Host'),
            body=msg.get('message') or msg.get('summary', ''), at=msg.get('received_at'),
            date_label=msg.get('received_at_display') or msg.get('displayed_times') or 'Time not recorded',
            kind='message' if msg.get('message') else 'summary',
            automated='automated' in (msg.get('sender', '') + msg.get('summary', '')).lower(),
            observed_at=msg.get('observed_at') or audit.get('updated_at'), proof=msg.get('evidence_file')))


def visible_messages(messages):
    """Coalesce duplicate evidence, not separate repeated messages from a host."""
    native = [dict(m) for m in messages if m['source'] not in ('audit', 'sms-import')]
    older = [dict(m) for m in messages if m['source'] in ('audit', 'sms-import')]
    result = []
    # Prefer platform text over its email notification, retain the email link as evidence.
    for msg in sorted(native, key=lambda m: m['source'] == 'gmail') + older:
        match = None
        for other in result:
            if msg.get('listing_id') != other.get('listing_id') or msg['direction'] != other['direction']:
                continue
            if msg['source'] == other['source'] and msg['source'] not in ('audit',):
                continue
            if 'sms' in msg['source'] or 'sms' in other['source']:
                continue
            delta = abs(timestamp(msg.get('at')) - timestamp(other.get('at')))
            dated = bool(timestamp(msg.get('at')) and timestamp(other.get('at')))
            same = canonical(msg['body']) == canonical(other['body'])
            similar = (min(len(msg['body']), len(other['body'])) > 65 and
                       SequenceMatcher(None, canonical(msg['body']), canonical(other['body'])).ratio() > .93)
            summary = msg.get('kind') == 'summary' and other.get('kind') == 'message'
            if ((same or similar) and (not dated or delta < 900)) or (summary and dated and delta < 90):
                match = other
                break
        if match:
            match.setdefault('also_seen', []).append({'channel': msg['channel'], 'url': msg.get('thread_url'), 'id': msg['id']})
            if not match.get('at') and msg.get('at'):
                match['at'] = msg['at']
        else:
            result.append(msg)
    return sorted(result, key=lambda m: (timestamp(m.get('at')) or 0, m.get('sequence', 0), m['id']))


def payload():
    state = read(STATE, {'messages': [], 'sources': {}, 'runs': []})
    audit = read(AUDIT)
    import_audit(state, audit)
    for msg in read(OUT / 'manual-messages.json', {'messages': []})['messages']:
        merge_message(state, msg)
    for msg in state['messages']:
        if msg['source'] == 'spareroom' and re.fullmatch(r'\d{2}/\d{2}/\d{4}', msg.get('date_label') or ''):
            msg['at'] = None  # The site supplies a date, not a midnight timestamp.
            msg['time_precision'] = 'date only'
    listings = read(ROOT / 'september_listings.json').get('listings', [])
    threads = {}
    tours = {t['listing_id']: dict(t) for t in audit.get('tours', [])}
    contacts = audit.get('address_matches', {})
    for item in listings:
        lid = item['id']
        tour = tours.get(lid)
        if tour and tour.get('status') == 'confirmed' and timestamp(tour.get('confirmed_start')) < datetime.now(timezone.utc).timestamp():
            tour['status'] = 'past_outcome_unknown'
            tour['note'] = 'The scheduled time has passed. Attendance and outcome have not been confirmed.'
        contact = contacts.get(lid, {})
        threads[lid] = dict(id=lid, title=item['title'], area=contact.get('address') or item['area'],
            source=channel_for(lid), rent=item['rent'], url=item['url'],
            status=item.get('outreach_status'), note=item.get('outreach_note'),
            rating=item.get('visual_review'), photos=item.get('photos', []),
            tour=tour, contact=contact, messages=[], contacted=bool(item.get('verified_contact')))
    for msg in visible_messages(state.get('messages', [])):
        lid = msg.get('listing_id') or 'platform-notices'
        if lid not in threads:
            threads[lid] = dict(id=lid, title='Housing platform notices' if lid == 'platform-notices' else 'Unmatched housing conversation',
                               area='Match pending' if lid != 'platform-notices' else '', source='Email', messages=[], contacted=False)
        threads[lid]['messages'].append(msg)
    for thread in threads.values():
        msgs = thread['messages']
        dated = sorted((m for m in msgs if m.get('kind') != 'summary' and not m.get('automated')), key=lambda m: timestamp(m.get('at')))
        last_in = max((timestamp(m.get('at')) for m in dated if m['direction'] == 'incoming'), default=0)
        last_out = max((timestamp(m.get('at')) for m in dated if m['direction'] == 'outgoing'), default=0)
        # Unknown dates do not imply a new reply.
        thread['needs_reply'] = last_in > last_out
        thread['latest_at'] = max((m.get('at') or '' for m in msgs), key=timestamp, default='')
        thread['channels'] = sorted({m['channel'] for m in msgs})
        thread['host'] = next((m['sender'] for m in reversed(msgs) if m['direction'] == 'incoming' and not m.get('automated')), '')
        if not thread['host']:
            recipient = next((m.get('recipient', '') for m in reversed(audit.get('messages', [])) if m['listing_id'] == thread['id']), '')
            if recipient and '@' not in recipient and len(recipient) < 40:
                thread['host'] = recipient
    scheduler = read(OUT / 'monitoring.json')
    return dict(updated_at=state.get('updated_at'), sources=state.get('sources', {}),
                runs=state.get('runs', [])[-20:][::-1], running=state.get('running'), scheduler=scheduler,
                threads=sorted(threads.values(), key=lambda t: (t['needs_reply'], timestamp(t['latest_at'])), reverse=True),
                verified_outgoing=audit.get('summary', {}).get('total_verified_outgoing_messages', 0),
                audit_updated_at=audit.get('updated_at'))
