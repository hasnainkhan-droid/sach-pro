"""Fresh regression checks for the SACH app and API."""
import base64
import json
import sys
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app


class AnalysisTests(unittest.TestCase):
    def test_credential_request_is_high_risk(self):
        result = app.local_assessment("Account blocked. Tell me your OTP right now.")
        self.assertEqual(result["verdict"], "scam")
        self.assertGreaterEqual(result["risk_score"], 78)
        self.assertTrue(result["red_flags_ur"])

    def test_legitimate_alert_and_safety_instruction_dont_trigger_otp_theft(self):
        for msg in [
            "Your card ending 4821 was charged PKR 1250. Use the official bank app if unknown.",
            "Never share your OTP or PIN with anybody.",
        ]:
            with self.subTest(msg=msg):
                result = app.local_assessment(msg)
                self.assertNotEqual(result["verdict"], "scam")
                self.assertNotIn("Requests your OTP, PIN, password, or card security code.", result["red_flags"])

    def test_bisp_and_payment_link_raise_risk(self):
        result = app.local_assessment("BISP 8171: claim prize now via http://bisp-claim.xyz. Pay Rs 1200 fee first.")
        self.assertEqual(result["verdict"], "scam")
        self.assertTrue(any(i["type"] == "link" for i in result["indicators"]))

    def test_shortened_link_detected_but_never_visited(self):
        result = app.local_assessment("See https://bit.ly/my-deal")
        self.assertEqual(result["indicators"][0]["level"], "high")
        self.assertEqual(result["indicators"][0]["value"], "https://bit.ly/my-deal")
        self.assertEqual(app.extract_indicators("bit.ly/no-scheme")[0]["level"], "high")

    def test_phone_and_shortcode_extract(self):
        found = app.extract_indicators("Call +92 3001234567 or check 8171")
        self.assertEqual([a["type"] for a in found], ["phone", "shortcode"])

    def test_image_validation(self):
        png = base64.b64encode(b"\x89PNG\r\n\x1a\nanything").decode()
        self.assertEqual(app.validate_image(png, "image/png"), (png, "image/png"))
        for encoded, mime in [(png, "image/jpeg"), ("not-base64!", "image/png"), (png, "image/svg+xml")]:
            with self.subTest(mime=mime, encoded=encoded[:10]), self.assertRaises(ValueError):
                app.validate_image(encoded, mime)

    def test_ai_cannot_downgrade_explicit_credential_theft(self):
        raw = {"verdict": "safe", "risk_score": 0, "explanation_en": "Looks okay", "explanation_ur": "ٹھیک"}
        payload = {"candidates": [{"content": {"parts": [{"text": json.dumps(raw)}]}}]}

        class FakeResponse:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, maximum=-1): return json.dumps(payload).encode()

        with patch.object(app, "urlopen", return_value=FakeResponse()) as mocked:
            result = app.gemini_assessment("Share your OTP code immediately", "FAKE_KEY")
        self.assertEqual(result["verdict"], "scam")
        self.assertGreaterEqual(result["risk_score"], 78)
        self.assertEqual(mocked.call_args.args[0].headers.get("X-goog-api-key"), "FAKE_KEY")
        self.assertNotIn("FAKE_KEY", mocked.call_args.args[0].full_url)


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def request(self, path, data=None, content_type="application/json"):
        body = None if data is None else json.dumps(data).encode()
        req = Request(f"http://127.0.0.1:{self.port}{path}", data=body,
                      headers={"Content-Type": content_type}, method="POST" if data is not None else "GET")
        try:
            with urlopen(req, timeout=5) as resp:
                return resp.status, resp.headers, resp.read()
        except HTTPError as err:
            return err.code, err.headers, err.read()

    def test_get_html_and_config(self):
        status, headers, body = self.request("/")
        self.assertEqual(status, 200)
        self.assertIn(b"Think twice", body)
        self.assertIn("no-store", headers["Cache-Control"])
        status, _, body = self.request("/api/config")
        self.assertEqual(status, 200)
        self.assertIn("ai_available", json.loads(body))

    def test_message_analyzed_without_ai_consent(self):
        with patch.dict(app.os.environ, {"GEMINI_API_KEY": "FAKE_KEY"}):
            with patch.object(app, "gemini_assessment", side_effect=AssertionError("AI must not run")):
                status, _, body = self.request("/api/analyze", {"message": "Please tell me your OTP"})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["verdict"], "scam")

    def test_image_only_requires_explicit_ai_consent(self):
        image = base64.b64encode(b"\x89PNG\r\n\x1a\nimage-bytes").decode()
        status, _, body = self.request("/api/analyze", {"message": "", "image_base64": image, "image_mime": "image/png"})
        self.assertEqual(status, 422)
        self.assertIn("consent", json.loads(body)["error"].lower())

    def test_image_only_ai_failure_is_not_misclassified_safe(self):
        image = base64.b64encode(b"\x89PNG\r\n\x1a\nimage-bytes").decode()
        with patch.dict(app.os.environ, {"GEMINI_API_KEY": "FAKE_KEY"}):
            with patch.object(app, "gemini_assessment", side_effect=URLError("unavailable")):
                status, _, body = self.request("/api/analyze", {"message": "", "image_base64": image, "image_mime": "image/png", "allow_ai_processing": True})
        self.assertEqual(status, 503)
        self.assertIn("unavailable", json.loads(body)["error"])

    def test_text_with_image_no_ai_reports_that_image_is_not_analyzed(self):
        image = base64.b64encode(b"\x89PNG\r\n\x1a\nimage-bytes").decode()
        status, _, body = self.request("/api/analyze", {"message": "hello", "image_base64": image, "image_mime": "image/png"})
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertFalse(data["image_analyzed"])
        self.assertIn("Screenshot not analyzed", data["analysis_mode"])

    def test_bad_inputs(self):
        for data in [[], {"message": [123]}, {"message": ""}, {"message": "x" * 5001}]:
            with self.subTest(input=str(data)[:30]):
                status, _, _ = self.request("/api/analyze", data)
                self.assertEqual(status, 400)


if __name__ == "__main__":
    unittest.main()
