# Contributing to Cyber AI Studio

Thanks for helping! By contributing you agree that your contributions are licensed under the [Apache License 2.0](LICENSE) and that you follow the [Code of Conduct](CODE_OF_CONDUCT.md). Security issues: see [SECURITY.md](SECURITY.md), not public issues.

## Getting set up (macOS; Linux untested)
```bash
git clone <your fork> && cd cyber-ai-studio
brew install ffmpeg postgresql@16 node python@3.13 && brew services start postgresql@16
./scripts/setup.sh          # venv, .env with random secrets, DB, migrations, npm installs
make test                   # backend tests (use a temporary SQLite DB, mock LLM, no network)
make start                  # API :8000, dashboard :3000
```
Full instructions: [docs/installation.md](docs/installation.md), [docs/configuration.md](docs/configuration.md).

## Before opening a PR
- Backend: `cd backend && .venv/bin/python -m pytest -q` (≈7 minutes; all must pass). Add tests for behaviour changes.
- TypeScript: `cd frontend && npx tsc --noEmit` and `cd video-engine && npx tsc --noEmit`.
- Keep the safety invariants in [docs/security-model.md](docs/security-model.md): no execution of LLM text, no new shell calls (use `security/subprocess_safe.run`), human approval gates stay intact.
- **Never commit** `.env`, API keys, tokens, database dumps, generated media, or model files. The CI secret scan will fail the build.
- Do not add third-party code, images, fonts, voices or datasets without recording their licence in `THIRD_PARTY_NOTICES.md` / `MODEL_AND_ASSET_LICENSES.md`. If you can't establish the licence, don't add it.
- Match the surrounding style. Don't claim support (platforms, providers) you haven't tested; say what you tested in the PR.

## What can't run in CI
Live LLM (Anthropic/Ollama), ElevenLabs, HeyGen, YouTube, n8n, Docker end-to-end and model-based TTS need credentials, models or services. Tests for those use mocks; manual verification is described in the PR template.

## Reporting bugs / proposing features
Use the issue templates. Include versions, OS, and logs with secrets removed.
