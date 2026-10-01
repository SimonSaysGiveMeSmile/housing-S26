#!/usr/bin/env python3
"""Read-only housing message collector, run by launchd or the local Check now button.

Uses its own background tabs, DOM only. Never sends, types, activates tabs, or
launches Chrome. A failed source preserves its last successful messages/check.
"""
from __future__ import annotations
import argparse
import fcntl
import json
import os
import re
import sqlite3
import subprocess
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from housing_inbox import OUT, ROOT, STATE, AUDIT, read, write, now, digest, canonical, merge_message, import_audit

BROWSER = '/Applications/Sarea.app/Contents/Resources/bin/browseruse'
PACIFIC = ZoneInfo('America/Los_Angeles')
FF_URL = 'https://www.furnishedfinder.com/members/tenant-message?filter=all'
SR_URL = 'https://www.spareroom.com/roommate/mythreads_beta.pl'
GMAIL = 'https://mail.google.com/mail/u/0/'
FF_NAMES = {'Anna D': 'ff-848526_1', 'Leticia G': 'ff-669591_1', 'Don J P': 'ff-915271_1',
            'Mona Z': 'ff-657379_1', 'Laura B': 'ff-224172_1', 'Alice W': 'ff-933277_1',
            'Merci M': 'ff-306547_1', 'Nur M': 'ff-933335_1', 'Paul C': 'ff-415061_1', 'Sima D': 'ff-949142_1'}

FF_EXTRACT = r'''(()=>{const rows=[...document.querySelectorAll('li[data-message-id]')];return {url:location.href,
messages:rows.map((x,i)=>{let t=x.querySelector('time'); if(!t){for(let j=i+1;j<rows.length;j++){t=rows[j].querySelector('time');if(t)break;}}
const sender=x.querySelector('.str-chat__message-text > span')?.textContent?.replace(/^Message from /,'').replace(/,$/,'');
return {source_id:x.dataset.messageId,sender,direction:sender?.startsWith('Simon')?'outgoing':'incoming',
body:x.querySelector('[data-testid="message-text-inner-wrapper"]')?.innerText||'',at:t?.dateTime,sequence:i,
time_precision:x.querySelector('time')?'exact':'message group'};})};})()'''

SR_EXTRACT = r'''({url:location.href,messages:[...document.querySelectorAll('li.message[id]')].map((x,i)=>({
source_id:x.id,direction:x.classList.contains('message_out')?'outgoing':'incoming',
sender:x.classList.contains('message_out')?'Simon':x.querySelector('dd.message_from_details')?.innerText?.replace(/View the profile of.*/s,'').trim(),
body:x.querySelector('dd.message_body')?.innerText||'',date_label:x.querySelector('dd.message_date')?.innerText,
delivery:x.querySelector('.email-status')?.innerText,sequence:i}))})'''

GMAIL_ROWS = r'''({url:location.href,title:document.title,main:!!document.querySelector('[role=main]'),
rows:[...document.querySelectorAll('tr.zA')].map(x=>({text:x.textContent,subject:x.querySelector('.bog')?.textContent,
id:x.querySelector('[data-legacy-thread-id]')?.getAttribute('data-legacy-thread-id'),
date:x.querySelector('td.xW span[title]')?.title})),
empty:document.querySelector('[role=main]')?.textContent?.includes('No conversations found')})'''

GMAIL_EXTRACT = r'''({url:location.href,subject:document.querySelector('h2.hP')?.textContent,
messages:[...document.querySelectorAll('.adn[data-message-id]')].map(x=>{const b=x.querySelector('.a3s');
return {source_id:x.getAttribute('data-message-id'),sender:x.querySelector('.gD')?.getAttribute('email'),
sender_name:x.querySelector('.gD')?.getAttribute('name'),date_label:x.querySelector('.g3')?.title,
body:b?.innerText||b?.textContent||'',links:b?[...b.querySelectorAll('a[href]')].map(a=>({text:a.textContent,url:a.href})):[]};})})'''

NORMALIZE_JS = r'''s=>{let v=String(s||'');for(let i=0;i<3;i++){v=v.replace(/&amp;/g,'&').replace(/&quot;/g,'"').replace(/&#39;|&apos;/g,"'").replace(/&nbsp;/g,' ');}return v.replace(/\s+/g,' ').trim();}'''

GMAIL_EXPAND = r'''[...document.querySelectorAll('[data-tooltip="Expand all"],[aria-label="Expand all"]')].forEach(x=>x.click());
[...document.querySelectorAll('.adn[data-message-id]')].filter(x=>!x.querySelector('.a3s')).forEach(x=>x.querySelector('.gE')?.click());true'''

ZILLOW_EXTRACT = r'''(()=>{const list=document.querySelector('[data-testid="message-list"]');let day='';return {url:location.href,
messages:list?[...list.children].flatMap((x,i)=>{if(x.tagName==='TIME'){day=x.textContent;return [];}const b=x.querySelector('[data-testid="interactive-chat-bubble"]');if(!b)return [];const ps=[...b.querySelectorAll('p')];
return [{sender:ps[0]?.innerText,direction:ps[0]?.innerText==='You'?'outgoing':'incoming',body:ps.slice(1).map(p=>p.innerText).join('\n'),
date_label:day+' '+(x.querySelector('[data-testid="timestamp"]')?.innerText||''),sequence:i}];}):[]};})()'''


def parse_date(label, zone=PACIFIC):
    if not label:
        return None
    text = re.sub(r'\s+', ' ', label.replace('\u202f', ' ')).strip()
    if 'EDT' in text or 'EST' in text:
        zone = ZoneInfo('America/New_York')
        text = re.sub(r' E[DS]T$', '', text)
    today = datetime.now(zone).date()
    for word, date in [('Today', today), ('Yesterday', today - timedelta(days=1))]:
        if text.startswith(word):
            text = date.strftime('%Y-%m-%d') + text[len(word):].replace(',', '')
    for fmt in ['%b %d, %Y, %I:%M %p', '%Y-%m-%d %I:%M %p', '%Y-%m-%d %I:%M%p', '%m/%d/%Y', '%b %d, %Y %I:%M%p']:
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=zone).isoformat()
        except ValueError:
            pass
    return None


class Browser:
    def __init__(self):
        with urllib.request.urlopen('http://127.0.0.1:9333/json/version', timeout=5) as response:
            self.ws = json.load(response)['webSocketDebuggerUrl']
        self.tabs = []
        self.call('await session.connect({wsUrl:' + json.dumps(self.ws) + '});return true;')

    def call(self, code):
        env = os.environ.copy()
        env['BROWSERUSE_PORT'] = '9884'
        env['BROWSERUSE_LOG'] = str(OUT / 'browser-monitor.log')
        p = subprocess.run([BROWSER, 'eval', code], capture_output=True, text=True, env=env, timeout=35)
        if p.returncode:
            raise RuntimeError((p.stderr or p.stdout)[-500:])
        output = p.stdout.strip()
        if not output:
            return None
        try:
            return json.loads(output)
        except ValueError:
            return output

    def page(self, url):
        value = self.call('return await session.Target.createTarget({url:' + json.dumps(url) + ',background:true});')
        tid = value['targetId']
        self.tabs.append(tid)
        self.call('await session.use(' + json.dumps(tid) + ');await session.Emulation.setFocusEmulationEnabled({enabled:true});return true;')
        return tid

    def evaluate(self, tid, expression):
        code = ('await session.use(' + json.dumps(tid) + ');await session.Emulation.setFocusEmulationEnabled({enabled:true});const r=await session.Runtime.evaluate({expression:' +
                json.dumps(expression) + ',returnByValue:true,timeout:8000});if(r.exceptionDetails)throw Error(r.exceptionDetails.exception?.description||r.exceptionDetails.text);return r.result.value;')
        return self.call(code)

    def wait(self, tid, expression, seconds=22):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            value = self.evaluate(tid, expression)
            if value:
                return value
            time.sleep(1)
        raise RuntimeError('Inbox did not finish loading within the check window')

    def navigate(self, tid, url):
        self.call('await session.use(' + json.dumps(tid) + ');await session.Page.navigate({url:' + json.dumps(url) + '});return true;')
        time.sleep(.7)

    def close(self):
        for tid in list(self.tabs):
            self.close_page(tid)

    def close_page(self, tid):
        if tid in self.tabs:
            try:
                self.call('return await session.Target.closeTarget({targetId:' + json.dumps(tid) + '});')
                self.tabs.remove(tid)
            except Exception:
                pass


class Collector:
    def __init__(self, state, audit, browser):
        self.state, self.audit, self.browser = state, audit, browser
        self.added = 0
        self.screens = {}

    def add(self, source, lid, channel, msg, url):
        msg = dict(msg, source=source, listing_id=lid, channel=channel, thread_url=url)
        msg.setdefault('source_id', digest(lid, msg.get('direction'), msg.get('body'), msg.get('at')))
        msg['id'] = source + '-' + msg['source_id']
        msg.setdefault('sender', 'Simon' if msg['direction'] == 'outgoing' else 'Host')
        if re.fullmatch(r'\d{2}/\d{2}/\d{4}', msg.get('date_label') or ''):
            msg['at'] = None
            msg['time_precision'] = 'date only'
        self.added += merge_message(self.state, msg)

    def ff(self):
        b = self.browser
        tid = b.page(FF_URL)
        b.wait(tid, 'document.querySelectorAll("[data-testid=channel-button]").length')
        names = b.evaluate(tid, '[...document.querySelectorAll("[data-testid=channel-button]")].map(x=>x.querySelector("span.truncate")?.textContent.trim())')
        captured = []
        for name in names:
            lid = FF_NAMES.get(name, 'ff-unmatched-' + digest(name))
            b.evaluate(tid, '(()=>{const x=[...document.querySelectorAll("[data-testid=channel-button]")].find(x=>x.querySelector("span.truncate")?.textContent.trim()===' + json.dumps(name) + ');x?.click();return !!x;})()')
            b.wait(tid, 'document.querySelector(".str-chat__channel-header-title")?.textContent.trim()===' + json.dumps(name) + '&&document.querySelectorAll("li[data-message-id]").length')
            time.sleep(.35)
            data = b.evaluate(tid, FF_EXTRACT)
            captured.append(dict(host=name, **data))
            for msg in data['messages']:
                self.add('furnishedfinder', lid, 'Furnished Finder', msg, data['url'])
        self.screens['furnishedfinder'] = captured
        return f'{len(captured)} conversations checked'

    def sr(self):
        b = self.browser
        tid = b.page(SR_URL)
        b.wait(tid, '!!document.querySelector("a[href*=thread_id]")')
        links = b.evaluate(tid, '[...document.querySelectorAll("a[href*=thread_id]")].map(a=>a.href)')
        b.navigate(tid, SR_URL + '?folder=sent')
        b.wait(tid, '!!document.querySelector("a[href*=thread_id]")')
        links += b.evaluate(tid, '[...document.querySelectorAll("a[href*=thread_id]")].map(a=>a.href)')
        threads = {}
        for m in self.audit.get('messages', []) + self.audit.get('previous_conversations', []):
            url = m.get('thread_url') or ''
            if 'spareroom.com' in url and 'thread_id=' in url:
                threads[m['listing_id']] = url
        for url in links:
            match = re.search(r'thread_id=\d+_(\d+)', url)
            if match:
                threads['sr-' + match[1]] = url
        captured = []
        errors = []
        for lid, url in threads.items():
            try:
                b.navigate(tid, url)
                expected = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)['thread_id'][0]
                b.wait(tid, 'document.querySelector("input[name=thread_id]")?.value===' + json.dumps(expected) + '&&document.querySelectorAll("li.message[id]").length', seconds=12)
                data = b.evaluate(tid, SR_EXTRACT)
                captured.append(dict(listing_id=lid, **data))
                for msg in data['messages']:
                    msg['at'] = parse_date(msg.get('date_label'), ZoneInfo('America/New_York'))
                    msg['automated'] = lid == 'sr-103201950' and msg['direction'] == 'incoming'
                    self.add('spareroom', lid, 'SpareRoom', msg, data['url'])
            except Exception as error:
                errors.append(lid + ': ' + str(error))
        self.screens['spareroom'] = captured
        if errors:
            raise RuntimeError(f'{len(captured)} conversations checked; ' + '; '.join(errors))
        return f'{len(captured)} conversations checked, including direct threads missing from Sent'

    def zillow(self):
        b = self.browser
        tid = b.page('https://www.zillow.com/renter-hub/inbox/')
        b.wait(tid, 'document.querySelectorAll("[data-testid=conversation-item]").length')
        count = b.evaluate(tid, 'document.querySelectorAll("[data-testid=conversation-item]").length')
        captured = []
        for i in range(count):
            text = b.evaluate(tid, f'document.querySelectorAll("[data-testid=conversation-item]")[{i}].innerText')
            # Limit monitoring to this housing search, leaving other conversations alone.
            lid = 'zi-15736519' if 'Humbolt' in text or 'Casa Bonita' in text else 'zi-2057204067' if '195 N 13th' in text else None
            if not lid:
                continue
            b.evaluate(tid, f'document.querySelectorAll("[data-testid=conversation-item]")[{i}].querySelector("button").click();true')
            time.sleep(.7)
            expected_id = '6030395653632422920' if lid == 'zi-15736519' else '665930284983440123'
            b.wait(tid, 'location.pathname.includes(' + json.dumps(expected_id) + ')&&document.querySelectorAll("[data-testid=interactive-chat-bubble]").length')
            data = b.evaluate(tid, ZILLOW_EXTRACT)
            captured.append(dict(listing_id=lid, **data))
            for msg in data['messages']:
                msg['at'] = parse_date(msg.get('date_label'))
                self.add('zillow', lid, 'Zillow', msg, data['url'])
        self.screens['zillow'] = captured
        if len(captured) != 2:
            raise RuntimeError(f'Only {len(captured)} of two tracked Zillow conversations could be read')
        return 'Both tracked conversations checked'

    def match_email(self, subject, body, links):
        if subject.startswith('Follow up with rentals'):
            return None
        if 'screening' in subject.lower() and re.search(r'\b(?:mona|ramona) z\.', body, re.I):
            return 'ff-657379_1'
        combined = subject + '\n' + body + '\n' + '\n'.join(x['url'] for x in links)
        for msg in self.audit.get('messages', []):
            known = msg.get('subject', '').removeprefix('Re: ')
            if known and known.lower() in subject.lower():
                return msg['listing_id']
            recipient = msg.get('recipient', '')
            if '@' in recipient and recipient in combined:
                return msg['listing_id']
        for lid in [x['id'] for x in read(ROOT / 'september_listings.json')['listings']]:
            if lid.split('-', 1)[-1] in combined:
                return lid
        names = {'anna': 'ff-848526_1', 'leticia': 'ff-669591_1', 'don': 'ff-915271_1',
                 'mona': 'ff-657379_1', 'ramona': 'ff-657379_1', 'alice': 'ff-933277_1', 'laura': 'ff-224172_1',
                 'sima': 'ff-949142_1', 'merci': 'ff-306547_1', 'nur': 'ff-933335_1', 'paul': 'ff-415061_1'}
        if 'New Message from ' in subject:
            host = subject.split('New Message from ', 1)[1].split()[0].lower()
            return names.get(host)
        if 'Humbolt' in combined or 'Casa Bonita' in combined:
            return 'zi-15736519'
        if '195 N 13th' in combined:
            return 'zi-2057204067'
        if 'andoht@stanford.edu' in combined or '1 bed with private bath available in Downtown Palo Alto' in combined:
            return 'su-130107280'
        if 'SF House' in combined or 'sfhouse.com' in combined:
            return 'apt-sfhouse-229ellis'
        return None

    def gmail(self):
        b = self.browser
        # Explicit correspondents and housing services; no general personal mail.
        correspondents = sorted({m['recipient'] for m in self.audit.get('messages', []) if '@' in m.get('recipient', '')})
        query = 'newer_than:14d {' + ' '.join('{' + 'from:' + a + ' to:' + a + '}' for a in correspondents)
        query += ' from:craigslist.org from:furnishedfinder.com from:leads.furnishedfinder.com from:spareroom.com from:zillow.com from:supost.com from:sfhouse.com from:apartments.com}'
        tid = b.page(GMAIL + '#search/' + urllib.parse.quote(query, safe=''))
        b.wait(tid, 'document.querySelectorAll("tr.zA").length||document.querySelector("[role=main]")?.textContent?.includes("No conversations found")', seconds=28)
        rows = b.evaluate(tid, GMAIL_ROWS)
        if 'tianjiahe11@gmail.com' not in rows.get('title', ''):
            raise RuntimeError('The expected signed-in Gmail account was not available')
        useful = []
        ignore = re.compile(r'daily matches|save the date|newsletter|renter profile|welcome to|rental recommendations|new listings|new for rent|discover your|your search|verification code|verify your email|confirm your SUpost|podcast|magic link|sign.in|log.in|password|authentication', re.I)
        for row in rows['rows']:
            subject = row.get('subject') or ''
            if row.get('id') and not ignore.search(subject):
                useful.append(row)
        captured = []
        errors = []
        cache = self.state.setdefault('gmail_thread_signatures', {})
        for row in useful:
            signature = digest(row['text'], row.get('date'))
            if cache.get(row['id']) == signature:
                continue
            thread_tab = None
            try:
                # Gmail sometimes leaves the previous DOM mounted after a hash navigation.
                # A fresh owned background page gives each thread an independent load.
                thread_tab = b.page(GMAIL + '#all/' + row['id'])
                b.wait(thread_tab, '(()=>{const norm=' + NORMALIZE_JS + ';return norm(document.querySelector("h2.hP")?.textContent)===norm(' + json.dumps(row['subject']) + ')&&document.querySelectorAll(".adn[data-message-id]").length;})()', seconds=20)
                # Expand only message headers, never a reply/compose control.
                b.evaluate(thread_tab, GMAIL_EXPAND)
                time.sleep(.3)
                data = b.evaluate(thread_tab, GMAIL_EXTRACT)
                captured.append(data)
                if not data.get('messages'):
                    raise RuntimeError('No message body was accessible')
                for msg in data['messages']:
                    if not msg['body'].strip():
                        raise RuntimeError('One or more messages remained collapsed')
                    subject = data.get('subject') or row['subject']
                    lid = self.match_email(subject, msg['body'], msg.get('links', []))
                    msg['subject'] = subject
                    msg['direction'] = 'outgoing' if msg.get('sender') in ('tianjiahe11@gmail.com', 'therealsimontian@gmail.com', 'ipo@stanford.edu') else 'incoming'
                    msg['at'] = parse_date(msg.get('date_label'))
                    msg['automated'] = any(x in (msg.get('sender') or '') for x in ('furnishedfinder.com', 'zillow.com', 'spareroom.com', 'apartments.com', 'supost.com'))
                    # FF notifications duplicate the actual human message; retain native text + email evidence.
                    if 'New Message from ' in subject and 'Property Manager' in msg['body'] and 'Reply to This Message' in msg['body']:
                        msg['body'] = msg['body'].split('Property Manager', 1)[1].split('Reply to This Message', 1)[0].strip()
                        msg['automated'] = False
                        msg['sender'] = subject.split('New Message from ', 1)[1].split(' for ', 1)[0]
                    elif 'New Message from ' in subject and 'furnishedfinder.com' in (msg.get('sender') or ''):
                        matching = [m for m in self.state['messages'] if m['source'] == 'furnishedfinder' and m.get('listing_id') == lid
                                    and m['direction'] == 'incoming' and len(canonical(m['body'])) > 3 and canonical(m['body']) in canonical(msg['body'])]
                        if matching:
                            native = max(matching, key=lambda m: len(m['body']))
                            msg['body'], msg['sender'] = native['body'], native['sender']
                        msg['automated'] = False
                    if msg.get('sender') == 'andoht@stanford.edu' or subject.startswith('SUpost - ') and ' response:' in subject:
                        msg['automated'] = False
                    self.add('gmail', lid, channel_for_email(lid), msg, data['url'])
                cache[row['id']] = signature
                write(STATE, self.state)
                print('  email: ' + subject[:90], flush=True)
            except Exception as error:
                errors.append(row['subject'] + ': ' + str(error))
                if len(errors) >= 3:
                    errors.append('Stopped this source after three load failures; previous messages preserved.')
                    break
            finally:
                if thread_tab:
                    b.close_page(thread_tab)
        self.screens['gmail'] = {'search': rows, 'threads': captured}
        # The query is expected to stay below the first page for this finite search.
        # If it grows, fail visibly rather than silently omitting page two.
        if len(rows['rows']) >= 50:
            errors.append('Search reached 50 rows; more pages may need checking')
        if errors:
            raise RuntimeError(f'{len(captured)} refreshed threads; ' + '; '.join(errors)[:600])
        return f'{len(useful)} housing email threads checked; {len(captured)} new/changed threads imported · tianjiahe11@gmail.com'


def channel_for_email(lid):
    return {'cl': 'Craigslist · email', 'su': 'SUpost · email', 'apt': 'Apartments.com · email',
            'ff': 'Furnished Finder · email', 'sr': 'SpareRoom · email', 'zi': 'Zillow · email'}.get((lid or '').split('-')[0], 'Housing email')


def run(selected=None):
    OUT.mkdir(exist_ok=True)
    with open(OUT / 'monitor.lock', 'w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print('A housing check is already running.', flush=True)
            return 0
        monitor = read(OUT / 'monitoring.json')
        if monitor.get('ends_at') and datetime.fromisoformat(monitor['ends_at']) < datetime.now(PACIFIC):
            monitor['status'] = 'ended'
            write(OUT / 'monitoring.json', monitor)
            return 0
        state = read(STATE, {'messages': [], 'sources': {}, 'runs': []})
        audit = read(AUDIT)
        import_audit(state, audit)
        started = now()
        run_id = digest(started)
        state['running'] = {'started_at': started, 'pid': os.getpid(), 'run_id': run_id}
        write(STATE, state)
        browser = None
        errors = []
        added = 0
        try:
            browser = Browser()
            collector = Collector(state, audit, browser)
            for name, method in [('furnishedfinder', collector.ff), ('spareroom', collector.sr), ('zillow', collector.zillow), ('gmail', collector.gmail)]:
                if selected and name not in selected:
                    continue
                status = state.setdefault('sources', {}).setdefault(name, {})
                status['last_attempt'] = now()
                try:
                    detail = method()
                    status.update(status='ok', last_success=now(), detail=detail)
                    print(name + ': ' + detail, flush=True)
                except Exception as error:
                    detail = str(error)[:900]
                    status.update(status='error', detail=detail)
                    errors.append(name + ': ' + detail)
                    print(name + ': ' + detail, flush=True)
                write(OUT / 'monitor-snapshots' / (run_id + '-' + name + '.json'), collector.screens.get(name, {}))
                status['proof'] = run_id + '-' + name
                write(STATE, state)
            added = collector.added
        except Exception as error:
            errors.append('Browser unavailable: ' + str(error))
            for name in selected or ('furnishedfinder', 'spareroom', 'zillow', 'gmail'):
                state.setdefault('sources', {}).setdefault(name, {}).update(status='error', last_attempt=now(), detail=errors[-1])
        finally:
            if browser:
                browser.close()
        gmail_status = state.get('sources', {}).get('gmail', {})
        for name in ('craigslist', 'supost', 'apartments'):
            state.setdefault('sources', {})[name] = dict(gmail_status, via='gmail', detail='Replies monitored through the connected Gmail account. ' + gmail_status.get('detail', ''))
        # Explicit gaps: screenshots are historical evidence, not live SMS access.
        state['sources']['sms'] = dict(status='not_connected', detail='macOS Messages database cannot be read by this process. User-provided screenshots are imported; new texts are not monitored.')
        state['sources']['rednote'] = dict(status='not_connected', detail='Login required; no live Rednote messages accessible.')
        state['sources']['therealsimontian@gmail.com'] = dict(status='not_connected', detail='This requested reply address is not connected. The signed-in account is tianjiahe11@gmail.com.')
        state['sources']['ipo@stanford.edu'] = dict(status='not_connected', detail='Stanford inbox is not connected. Replies arriving only here cannot be checked.')
        state['running'] = None
        state['updated_at'] = now()
        state.setdefault('runs', []).append(dict(id=run_id, started_at=started, completed_at=now(), status='partial' if errors else 'success', errors=errors, imported_records=added, sources=selected or ['furnishedfinder', 'spareroom', 'zillow', 'gmail'], trigger='launchd' if os.environ.get('XPC_SERVICE_NAME') == 'com.simon.housing-inbox-monitor' else 'Check now / command line'))
        state['runs'] = state['runs'][-100:]
        write(STATE, state)
        monitor = read(OUT / 'monitoring.json', monitor)
        monitor.update(last_attempt=state['updated_at'], last_run_status=state['runs'][-1]['status'],
                       last_completed_check=state['updated_at'])
        # launchd's interval can coalesce across sleep; do not invent an exact next-run time.
        monitor.pop('nextRunAt', None)
        if not errors and not selected:
            monitor['last_successful_check'] = state['updated_at']
        write(OUT / 'monitoring.json', monitor)
        print(f'Complete: {added} new source records; {len(errors)} source errors.', flush=True)
        return 1 if errors else 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--sources', nargs='+', choices=['furnishedfinder', 'spareroom', 'zillow', 'gmail'])
    args = parser.parse_args()
    raise SystemExit(run(args.sources))
