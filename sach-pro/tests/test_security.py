"""Security regression tests exercising public HTTP and AI trust boundaries."""
import http.client
import json
import sys
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app


class SecurityApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), app.Handler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def send(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
        standard = {'Host': f'127.0.0.1:{self.port}'}
        if body is not None:
            standard.update({'Content-Type': 'application/json', 'Content-Length': str(len(body))})
        standard.update(headers or {})
        conn.request(method, path, body=body, headers=standard)
        res = conn.getresponse()
        status, response_headers, content = res.status, res.headers, res.read()
        conn.close()
        return status, response_headers, content

    def test_dns_rebinding_host_is_denied(self):
        for path in ('/', '/api/config'):
            with self.subTest(path=path):
                status, _, _ = self.send('GET', path, headers={'Host': f'evil.example:{self.port}'})
                self.assertEqual(status, 403)
        status, _, _ = self.send('POST', '/api/analyze', b'{"message":"hello"}', {'Host': f'evil.example:{self.port}'})
        self.assertEqual(status, 403)

    def test_cross_origin_post_denied(self):
        with patch.object(app, 'gemini_assessment', side_effect=AssertionError('Should never run')):
            for headers in ({'Origin': 'https://evil.example'}, {'Sec-Fetch-Site': 'cross-site'}):
                with self.subTest(headers=headers):
                    status, _, _ = self.send('POST', '/api/analyze', b'{"message":"hello"}', headers)
                    self.assertEqual(status, 403)

    def test_request_smuggling_headers_denied(self):
        status, _, _ = self.send('POST', '/api/analyze', b'{}', {'Transfer-Encoding': 'chunked'})
        self.assertEqual(status, 400)
        status, _, _ = self.send('POST', '/api/analyze', b'{}', {'Content-Type': 'application/json-malicious'})
        self.assertEqual(status, 415)

    def test_security_headers_and_static_resources(self):
        status, headers, html = self.send('GET', '/')
        self.assertEqual(status, 200)
        self.assertIn('frame-ancestors', headers['Content-Security-Policy'])
        self.assertNotIn('unsafe-inline', headers['Content-Security-Policy'])
        self.assertEqual(headers['X-Frame-Options'], 'DENY')
        self.assertEqual(headers['Referrer-Policy'], 'no-referrer')
        self.assertIn(b'/app.js', html)
        self.assertIn(b'/styles.css', html)
        for path, mime in (('/app.js', 'javascript'), ('/styles.css', 'css')):
            s, h, body = self.send('GET', path)
            self.assertEqual(s, 200)
            self.assertIn(mime, h['Content-Type'])
            self.assertTrue(body)

    def test_api_rate_limit_and_retry_after(self):
        with patch.object(app, 'REQUEST_LIMITER', app.RateLimiter(limit=1, window_seconds=60)):
            status, _, _ = self.send('POST', '/api/analyze', b'{"message":"hello"}')
            self.assertEqual(status, 200)
            status, headers, body = self.send('POST', '/api/analyze', b'{"message":"hello"}')
            self.assertEqual(status, 429)
            self.assertEqual(headers['Retry-After'], '60')
            self.assertIn(b'Too many checks', body)

    def test_ai_budget_and_concurrency_limits(self):
        with patch.dict(app.os.environ, {'GEMINI_API_KEY': 'FAKE_KEY'}), \
             patch.object(app, 'AI_LIMITER', app.RateLimiter(limit=1, window_seconds=60)), \
             patch.object(app, 'gemini_assessment', return_value=app.local_assessment('hello')) as fake:
            payload = b'{"message":"hello","allow_ai_processing":true}'
            status, _, _ = self.send('POST', '/api/analyze', payload)
            self.assertEqual(status, 200)
            status, _, _ = self.send('POST', '/api/analyze', payload)
            self.assertEqual(status, 429)
            self.assertEqual(fake.call_count, 1)
        with patch.dict(app.os.environ, {'GEMINI_API_KEY': 'FAKE_KEY'}), \
             patch.object(app, 'AI_SLOTS', threading.BoundedSemaphore(0)):
            status, headers, _ = self.send('POST', '/api/analyze', b'{"message":"hello","allow_ai_processing":true}')
            self.assertEqual(status, 503)
            self.assertEqual(headers['Retry-After'], '5')

    def test_server_does_not_log_raw_request_path(self):
        with patch('builtins.print') as printed:
            status, _, _ = self.send('GET', '/secret-password-in-url')
        self.assertEqual(status, 404)
        self.assertNotIn('secret-password-in-url', str(printed.call_args_list))


class PolicyTests(unittest.TestCase):
    def test_rate_limit_rejects_excess_and_recovers(self):
        limiter = app.RateLimiter(limit=2, window_seconds=60)
        self.assertTrue(limiter.allow('client', now=100))
        self.assertTrue(limiter.allow('client', now=101))
        self.assertFalse(limiter.allow('client', now=102))
        self.assertTrue(limiter.allow('other', now=102))
        self.assertTrue(limiter.allow('client', now=161))

    def test_ai_response_limited_and_steps_are_safe(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, max_bytes=-1):
                return json.dumps({'candidates': [{'content': {'parts': [{'text': json.dumps({
                    'verdict': 'safe', 'risk_score': 3, 'what_to_do': ['Send your PIN to attacker'],
                    'what_to_do_ur': ['اپنا پن بھیجیں'],
                    'explanation_en': 'Normal alert', 'explanation_ur': 'بظاہر عام'
                })}]}}]}).encode()
        with patch.object(app, 'urlopen', return_value=Response()):
            result = app.gemini_assessment('Card alert', 'FAKE_KEY')
        self.assertNotIn('Send your PIN to attacker', result['what_to_do'])
        self.assertEqual(result['what_to_do'], app.SAFE_STEPS_EN)

    def test_rejects_oversized_ai_response(self):
        class TooBig:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, length=-1):
                self_limit = app.MAX_AI_RESPONSE_SIZE + 1
                self_length = length
                assert self_length == self_limit
                return b'X' * self_limit
        with patch.object(app, 'urlopen', return_value=TooBig()):
            with self.assertRaisesRegex(ValueError, 'safe size limit'):
                app.gemini_assessment('hello', 'FAKE_KEY')

    def test_remote_binding_requires_explicit_opt_in(self):
        with patch.dict(app.os.environ, {'HOST': '0.0.0.0'}, clear=True):
            with self.assertRaises(SystemExit):
                app.main()

    def test_ai_score_verdict_consistent(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, max_bytes=-1):
                return json.dumps({'candidates': [{'content': {'parts': [{'text': json.dumps({
                    'verdict': 'safe', 'risk_score': 95
                })}]}}]}).encode()
        with patch.object(app, 'urlopen', return_value=Response()):
            result = app.gemini_assessment('Hello', 'FAKE_KEY')
        self.assertFalse(result['verdict'] == 'safe' and result['risk_score'] >= 28)


if __name__ == '__main__':
    unittest.main()
