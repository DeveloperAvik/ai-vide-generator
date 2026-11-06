# Security model

What the code enforces (verified by the test suite where noted), and what it does not.

## Enforced
- **Human approval.** YouTube upload requires lesson status APPROVED and a human approval row; the n8n service token is refused for approvals. Uploads default to private.
- **No LLM text is executed.** Output is parsed into strict schemas; terminal scenes are display-only. Subprocesses go through an allow-list of binaries with argv lists, no shell, timeouts and a scrubbed environment (`security/subprocess_safe.py`).
- **Secret/PII scan** of storyboard and scene text (keys, tokens, passwords, emails, non-lab private IPs) before assets are built (`security/redaction.py`).
- **Claim checks.** CVE IDs must verify against NVD; CVSS without a verified CVE fails. Research fetches HTTPS from allow-listed hosts only.
- **Auth.** bcrypt password hashes, JWT (HS256, 12 h). Login is rate-limited (10/min).
- **Production guards.** `APP_ENV=production` refuses weak `SECRET_KEY`, wildcard CORS, mock providers and `macos_say`.
- **Network exposure.** Docker compose publishes ports on `127.0.0.1` only; `scripts/start.sh` binds the API and dashboard to `127.0.0.1`.
- **Path-traversal guards** (`security/paths.py`) and an audit log (`workflow_logs`).

## Known limitations (not fixed)
- JWT is stored in browser `localStorage`; an XSS bug would expose it.
- The rate limiter is in-process and keyed on the socket IP (behind a reverse proxy all clients share one IP until proxy headers are trusted).
- No multi-user management UI or 2FA.
- Docker network egress is open (needed for Anthropic/YouTube).
- Upload scanning checks extension and ffprobe only, not pixel content.
- Development defaults (`SECRET_KEY=change-me-in-env`, default DB credentials) are insecure by design; only use them on localhost.
- Docker/n8n integration is only partly verified.

## The lab
`lab/vuln_app.py` is intentionally vulnerable, binds loopback only, holds fake data in memory. Never expose it. Only test systems you own or are authorised to test.

## Reporting
See [../SECURITY.md](../SECURITY.md).
