# SACH PRO — Message Safety Desk

A redesigned Pakistan-focused scam-message checker based on the supplied SACH prototype. Runs locally using only Python's standard library, with optional Google Gemini text/image analysis.

## Run on your computer

1. Install **Python 3.10 or newer**.
2. Open a terminal in this folder.
3. Run `python app.py` (on some computers use `python3 app.py`).
4. Visit **http://127.0.0.1:8000** in your browser.

On Windows PowerShell, to enable optional Gemini analysis for the *current terminal session*:

```powershell
$env:GEMINI_API_KEY = "YOUR_API_KEY"
python app.py
```

On macOS/Linux:

```bash
GEMINI_API_KEY="YOUR_API_KEY" python3 app.py
```

Never add API keys to `app.py`, browser code, or Git. The Gemini checkbox is disabled if no server-side key is configured. It is **off by default**: text remains local unless the user explicitly enables remote AI processing. Screenshot-only analysis requires an AI key and explicit checkbox consent. When AI is unavailable, screenshot-only checks return an error rather than a falsely reassuring verdict.

You can change port with `PORT=8080` and bind address with `HOST=...` (defaults to `127.0.0.1`; do not expose publicly without HTTPS, authentication and rate limiting).

## Features

- Professional responsive interface; light/dark mode; accessible keyboard controls.
- Text risk triage for common Pakistan-specific scams (OTP and PIN theft, BISP/8171 claims, lottery, jobs, customs and delivery impersonation).
- URL/phone/shortcode extraction shown as **non-clickable text**, without visiting links.
- Optional Gemini enhanced analysis and screenshot interpretation, with explicit data-sharing consent.
- English/Urdu explanations, warning flags, and recommended next steps.
- Copy, print, download a plain-text report, or share a short warning through WhatsApp.
- Recent checks **only in this tab's memory**. Message history is not written to disk by this app. The light/dark theme preference may be saved locally.
- Input validation, upload magic-byte verification, response headers, and server-side API key handling.

## Important limitations

SACH provides **pattern-based educational guidance**, not live URL reputation scanning, a certified anti-fraud verdict, sender identification or guaranteed protection. Risk scores are **not probabilities**. A safe-looking message can still be fraudulent. Do not paste real OTPs, card secrets, passwords or sensitive IDs into any checker. When AI processing is enabled, messages/images are sent to Google's Gemini API and are subject to that provider's data handling.

The official National Cyber Crime Investigation Agency (NCCIA) complaint portal is linked in the app: https://complaint.nccia.gov.pk/ .

## Verification

```bash
python -m unittest discover -s tests -v
```

Optional Chromium + Playwright UI smoke test (uses deterministic fake API responses to test page interactions, not the live Gemini service):

```bash
python tests/browser_smoke.py
```

The `/health` and `/api/config` routes return server status and optional AI availability. The existing `POST /api/analyze` contract remains compatible with the original text inputs and output fields; additional fields are provided for Urdu lists, link indicators, and screenshot status.

## Files

- `app.py` — Python backend, local risk checks, optional Gemini integration, API.
- `index.html` — accessible frontend HTML, with no build step.
- `styles.css`, `app.js` — standalone frontend assets for stricter Content Security Policy.
- `tests/test_app.py` — deterministic original unit/API regression tests.
- `tests/test_security.py` — adversarial security regression tests.
- `tests/browser_smoke.py` — optional desktop/mobile browser smoke test and screenshot creator.
- `SECURITY_AUDIT.md` — security findings, controls, residual risks and evidence.

## Security hardening (v3.1)

- **Localhost-only by default** (`127.0.0.1`). The server rejects unknown `Host` headers, cross-origin POSTs and cross-site browser requests. This limits DNS rebinding / browser-origin abuse of a locally running service.
- **Strict Content Security Policy**: JavaScript and CSS are served as separate local assets, with no `unsafe-inline` script or style allowance. Security, anti-framing and privacy headers apply to HTML, assets and API replies. Google Fonts remain an optional third-party resource and receive normal browser font requests (not submitted messages).
- **Request safeguards**: 6 MB overall body limit, 5,000-character text limit, 4 MB screenshot limit, 15-second connection timeout, strict JSON MIME type, and rejection of ambiguous transfer encodings / lengths.
- **Abuse controls**: 60 analyses/minute/client IP, at most 6 Gemini analyses/minute/client IP, and at most two concurrent Gemini requests per process. Exceeding quotas returns HTTP 429 with `Retry-After` (or HTTP 503 when both AI slots are busy). These are *in-memory, per-process* limits, not a distributed DDoS defense. Clients behind a reverse proxy may share one source IP and thus one quota.
- **AI and privacy controls**: Gemini remains opt-in; API keys stay server-side; AI replies are bounded to 1 MB; model-generated next-step instructions never replace SACH's vetted guidance. Suspected links are never fetched. HTTP request paths, raw message bodies and secret keys are not logged by the application.
- **Browser correctness**: repeated submissions are suppressed while a check is in flight; editing, clearing or switching consent cancels the browser request and hides stale assessment results. Cancellation does **not** retract a Gemini request already submitted to the provider.

### Deployment warning

**Not hardened or approved for direct Internet exposure.** Keep the default loopback binding for personal use. A remote binding explicitly requires both `SACH_ALLOW_REMOTE=I_UNDERSTAND` and `SACH_ALLOWED_HOSTS=your-hostname` to avoid accidentally exposing the service. If you deploy behind a proxy, additionally use **HTTPS, real authentication/access control, a WAF or edge request limits, connection/thread limits, provider-side API quotas/budget alerts, and monitoring**. The built-in server does not provide these protections. Set `SACH_ALLOWED_HOSTS` to public browser-visible hostnames; don't rely on untrusted forwarded headers for security. Avoid publishing the server without those protections.

### Verification of v3.1

```bash
python -m unittest discover -s tests -v
python -m py_compile app.py
node --check app.js            # if Node.js is installed
python tests/browser_smoke.py   # if Playwright and Chromium are installed
```

Browser smoke uses locally inlined test assets and stubbed HTTP responses because the test environment restricts browser networking; it does not test deployment TLS or a real Gemini API key. Separate HTTP contract tests check the actual response security headers and static resource routing.
