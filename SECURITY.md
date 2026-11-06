# Security Policy

## Supported versions
Only the latest release on the `main` branch receives security fixes.

## Reporting a vulnerability
**Please do not open a public issue for security problems.** Use GitHub's private reporting: the repository's **Security → Report a vulnerability** page. Include affected version/commit, reproduction steps, impact, and any suggested fix. Do not include real credentials or personal data in the report.

We aim to acknowledge reports within a few days and to coordinate disclosure with you. This is a volunteer project; there is no bug bounty.

## Scope
In scope: the backend API, dashboard, pipeline guards (approval gates, redaction, subprocess allow-list), n8n workflows, and scripts in this repository.
Out of scope: `lab/vuln_app.py` (intentionally vulnerable, loopback only, fake data), third-party software and services (report those upstream), and issues that require an already-compromised host.

## Hardening notes
Read [docs/security-model.md](docs/security-model.md) for what is enforced and the known limitations (e.g. JWT in `localStorage`, in-process rate limiting). Never commit `.env`, API keys, OAuth tokens or database dumps; if you accidentally do, rotate the credential immediately.
