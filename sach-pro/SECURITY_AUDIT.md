# SACH PRO v3.1 — Security audit and mitigation notes

Scope: the provided v3 source archive (`app.py`, `index.html`, and tests). No server hosting, Google configuration, accounts or production infrastructure were inspected.

## Confirmed risks addressed

| Risk in prior archive | Mitigation | Evidence |
|---|---|---|
| Browser DNS rebinding could reach localhost API using attacker-controlled Host | Exact browser-visible Host allowlist | `test_dns_rebinding_host_is_denied` |
| Cross-origin browsers could submit crafted API requests, potentially spending AI quota | Origin and Fetch Metadata checks on POST; reject invalid JSON content types | `test_cross_origin_post_denied`, `test_request_smuggling_headers_denied` |
| Permissive script/style CSP allowed inline script execution if markup injection was later introduced | Extracted frontend assets and stricter CSP; anti-framing and privacy headers | `test_security_headers_and_static_resources` |
| Unlimited sequential or parallel Gemini calls could consume API quota | In-memory rate limits and bounded simultaneous AI work | `test_api_rate_limit_and_retry_after`, `test_ai_budget_and_concurrency_limits` |
| AI text could replace vetted next steps with attacker-directed instructions | Always use fixed safe next-step guidance; bound AI response size; align risk score/verdict | `test_ai_response_limited_and_steps_are_safe`, `test_rejects_oversized_ai_response`, `test_ai_score_verdict_consistent` |
| HTTP request paths were logged verbatim | Disable request-line logging | `test_server_does_not_log_raw_request_path` |
| Browser allowed double submission and showed obsolete verdicts after message edits | Abort outdated browser fetches; invalidate results on edits; one check at a time | `tests/browser_smoke.py` |

## Residual risks and deployment blockers

- **Do not expose Python's built-in threaded development server directly to the Internet**. It has no TLS or login flow, and incoming connections/threads are not hard capped; socket timeouts and request rate limiting alone do not prevent distributed denial of service. Use a production-grade front proxy, authentication, request/connection limits and TLS.
- With an API key configured, a trusted local application could call the AI endpoint directly. An unprotected reverse proxy would expose that spending capability. Protect access outside a single trusted device; set Google-side quotas and alerts.
- Pattern rules and Gemini output can make incorrect assessments; low risk is not proof of legitimacy. AI explanations and flags are still generated natural-language content and can contain errors or adversarial ideas; only next-step advice is fixed and trusted.
- Images are validated by size, MIME allowlist and file signature, not full image decoding or malware scanning. Treat uploads and screenshots as untrusted; do not pass them to other unprotected parsers.
- This is an application-level assessment, **not a penetration test, formal security certification, or guarantee of no vulnerabilities**. Live Gemini connectivity, production proxies, browser HTTP CSP enforcement and infrastructure security require verification in your deployment.

## Fresh checks

Run the commands listed in README's Verification of v3.1. Capture their output when validating against another operating system or deploying the service.
