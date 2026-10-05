"""Regression checks for private inbox identity, deduplication and access boundaries."""
import json
import threading
import unittest
import shutil
import subprocess
import urllib.request
import urllib.error
from http.server import ThreadingHTTPServer
from housing_inbox import merge_message, visible_messages, payload
from housing_monitor import parse_date, parse_facebook_labels, Collector, FACEBOOK_EXTRACT, FF_EXTRACT, SR_EXTRACT, ZILLOW_EXTRACT, GMAIL_EXTRACT, GMAIL_ROWS, GMAIL_EXPAND, NORMALIZE_JS
from palo_alto_server import Handler


class InboxTests(unittest.TestCase):
    def message(self, **kwargs):
        return dict(id='one', listing_id='ff-test', source='furnishedfinder', source_id='native-one',
                    direction='incoming', sender='Host', channel='Furnished Finder', body='Yes, 4 PM works for a tour.',
                    at='2026-09-30T10:00:00-07:00', kind='message', **kwargs)

    def test_native_ids_are_idempotent(self):
        state = {'messages': []}
        msg = self.message()
        self.assertTrue(merge_message(state, msg))
        self.assertFalse(merge_message(state, dict(msg)))
        self.assertEqual(len(state['messages']), 1)

    def test_notification_is_evidence_not_duplicate(self):
        msg = self.message()
        email = dict(msg, id='email', source='gmail', channel='Furnished Finder · email', thread_url='https://mail.google.com/example')
        result = visible_messages([email, msg])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['source'], 'furnishedfinder')
        self.assertEqual(result[0]['also_seen'][0]['id'], 'email')

    def test_repeated_message_on_different_day_is_preserved(self):
        msg = self.message()
        second = dict(msg, id='two', at='2026-10-01T10:00:00-07:00')
        self.assertEqual(len(visible_messages([msg, second])), 2)

    def test_same_body_at_other_property_not_merged(self):
        msg = self.message()
        other = dict(msg, id='other', source='gmail', listing_id='ff-other')
        self.assertEqual(len(visible_messages([msg, other])), 2)

    def test_platform_redaction_does_not_duplicate_sent_message(self):
        msg = self.message()
        msg['body'] = 'Please email therealsimontian@[Link removed]. Thanks!'
        original = dict(msg, id='audit', source='audit', body='Please email therealsimontian@gmail.com. Thanks!')
        self.assertEqual(len(visible_messages([msg, original])), 1)

    def test_sms_keeps_separate_provenance(self):
        msg = self.message()
        sms = dict(msg, id='sms', source='sms-import', channel='SMS')
        self.assertEqual(len(visible_messages([msg, sms])), 2)

    def test_sent_dates_keep_actual_zone(self):
        self.assertEqual(parse_date('Sep 29, 2026, 9:41\u202fPM'), '2026-09-29T21:41:00-07:00')

    def test_every_tracked_property_remains_accessible(self):
        p = payload()
        from latest_dashboard import load_listings
        self.assertEqual({t['id'] for t in p['threads'] if t.get('url')},
                         {item['id'] for item in load_listings()['listings']})
        self.assertIn('sms', p['sources'])

    def test_facebook_messages_keep_direction_and_stable_identity(self):
        first = 'Enter, Message sent 3:40 PM by You: Is monthly renewal possible?'
        host = 'Enter, Message sent 3:45 PM by Manas: I am checking.'
        messages = parse_facebook_labels([first, first, host, 'Enter, Message sent 3:45 PM by Manas'])
        self.assertEqual(len(messages), 2)
        self.assertEqual([m['direction'] for m in messages], ['outgoing', 'incoming'])
        self.assertIsNone(messages[0]['at'])
        later = parse_facebook_labels([first.replace('3:40 PM', 'Yesterday 3:40 PM')])[0]
        self.assertEqual(messages[0]['source_id'], later['source_id'])

    def test_redwood_reply_matches_even_without_quoted_original(self):
        collector = Collector({}, {}, None)
        self.assertEqual(collector.match_email('Re: SUpost - response: Private bedroom and bathroom available in 2bd/2ba - $1800',
                                              'Yes, monthly renewal works.', []), 'su-130001643')

    @unittest.skipUnless(shutil.which('node'), 'Node is needed for JavaScript syntax validation')
    def test_browser_extractors_compile_before_running(self):
        for expression in [FACEBOOK_EXTRACT, FF_EXTRACT, SR_EXTRACT, ZILLOW_EXTRACT, GMAIL_EXTRACT, GMAIL_ROWS, GMAIL_EXPAND, NORMALIZE_JS]:
            with self.subTest(expression=expression[:40]):
                result = subprocess.run(['node', '-e', 'new Function(process.argv[1])', expression], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)


class AccessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.url = f'http://127.0.0.1:{cls.server.server_port}'
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_messages_local_only_and_not_cacheable(self):
        with urllib.request.urlopen(self.url + '/api/inbox') as response:
            self.assertEqual(response.headers['Cache-Control'], 'no-store')
            self.assertIn('threads', json.load(response))
        request = urllib.request.Request(self.url + '/api/inbox', headers={'Host': 'unrelated.example'})
        with self.assertRaises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(request)
        self.assertEqual(error.exception.code, 403)

    def test_private_store_cannot_be_downloaded_as_static_file(self):
        with self.assertRaises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(self.url + '/.outreach/inbox.json')
        self.assertEqual(error.exception.code, 404)

    def test_cross_site_post_cannot_start_automation(self):
        request = urllib.request.Request(self.url + '/api/inbox/check', data=b'', headers={'Origin':'https://unrelated.example','X-Housing-Inbox':'1'})
        with self.assertRaises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(request)
        self.assertEqual(error.exception.code, 403)


if __name__ == '__main__':
    unittest.main()
