# Lab: intentionally vulnerable demo app

> ⚠️ **`vuln_app.py` is deliberately insecure (SQL injection).** It exists only so the SQL-injection lesson can be recorded against real behaviour. Never deploy it, never expose it to a network, never put real data in it.

- Listens on `127.0.0.1:8099` only (hardcoded, with an assertion that rejects non-loopback hosts). It uses an in-memory SQLite database with fake products.
- Run: `python3 lab/vuln_app.py`, then `python3 lab/capture_session.py` records responses to `lab/session.json` (gitignored) and `lab/render_session_video.py` animates them.
- Do not run it inside a container with published ports, behind a reverse proxy, or on a shared machine. See [course/LAB_SAFETY.md](../course/LAB_SAFETY.md) and [docs/security-model.md](../docs/security-model.md).
- Only test systems you own or are explicitly authorised to test.
