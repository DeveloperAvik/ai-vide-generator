# CipherCast

[![CI](https://github.com/OWNER/ciphercast/actions/workflows/ci.yml/badge.svg)](https://github.com/OWNER/ciphercast/actions/workflows/ci.yml)
[![License: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)

An automated production studio for **cybersecurity teaching videos**: curriculum → researched script → storyboard → narration → slides/diagrams/animations → rendered MP4 + SRT + thumbnail → **human approval** → private YouTube upload. It works fully offline with no paid services (mock LLM + local TTS); online providers are opt-in.

> Replace `OWNER` in the badge URLs with the GitHub account or organisation that hosts the repository.

## Vision
Make accurate, safe, reproducible security education cheap to produce. Every claim is fact-checked against official sources, every script and every video needs a human sign-off, and nothing the model writes is ever executed.

## Features
Everything below exists in the code; "tested" means covered by the backend test suite (307 tests) or run by the maintainers.

- Course → module → lesson generation with strict schema validation of LLM output.
- Source-backed review: allow-listed research fetching, claim extraction, CVE/CVSS verification against NVD, independent technical review by a second local model, and a blocking quality gate. See [docs/REVIEW_PIPELINE.md](docs/REVIEW_PIPELINE.md).
- Narration with measured sentence timing, and a deterministic animation engine synchronised to it ([docs/animation-engine.md](docs/animation-engine.md)).
- Two renderers: FFmpeg (default) and Remotion (optional; see the licence note below).
- Dashboard (Next.js) with approval gates, retry/resume, audit log; 13 n8n workflows for orchestration.
- Intentionally vulnerable, localhost-only lab app for recording demos ([lab/README.md](lab/README.md)).

**Not verified / limited:** HeyGen talking avatars (written from public docs, never run against a live account); MuseTalk (needs a CUDA GPU, not integrated); the Docker/n8n path (images built, workflow import and end-to-end runs untested); Linux (untested); Windows (unsupported).

## Architecture
```
Browser ─▶ Next.js dashboard ─▶ FastAPI (auth, pipeline, audit log) ─▶ PostgreSQL
n8n ── service token (cannot approve) ──▶ FastAPI ─▶ providers: LLM | voice | avatar
                                              └─▶ ffmpeg / Node+Remotion (isolated subprocesses)
```
Details: [docs/architecture.md](docs/architecture.md).

## Technology stack
Python 3.12+ · FastAPI · SQLAlchemy 2 · Alembic · PostgreSQL 16 · Next.js 15 / React 19 / Tailwind · Remotion 4 / React 18 / three.js · FFmpeg · n8n · Kokoro / Piper TTS · Anthropic or Ollama LLMs.

## Screenshots and demo
_Placeholders — no screenshots are committed yet._ Generate your own sample with `make demo` (output in `storage/demo/`, gitignored). Contributions of screenshots and a demo GIF are welcome.

## Installation
macOS is the tested platform. Full guide: [docs/installation.md](docs/installation.md).
```bash
brew install ffmpeg postgresql@16 node python@3.13 && brew services start postgresql@16
./scripts/setup.sh      # venv, .env with random secrets, DB + migrations, npm installs
```
Download the Kokoro voice files first (the default voice), see [voice/README.md](voice/README.md); otherwise the demo cannot synthesise speech.

## Environment configuration
Copy `.env.example` to `.env` (the setup script does this and generates random secrets). Every variable is documented in [docs/configuration.md](docs/configuration.md). Never commit `.env`.

## Quick start
```bash
echo 'FIRST_ADMIN_PASSWORD=<strong password>' >> .env   # creates the admin user on API start
make demo     # full pipeline with the mock LLM → storage/demo/demo_lesson.mp4 (+ .srt, thumbnail, manifest)
make start    # API http://localhost:8000/docs · dashboard http://localhost:3000
make test     # backend tests
make stop
```

## Video generation workflow
Research → script → technical review → **you approve the script** → voice/visuals/avatar → render → quality checks → **you approve the video** → optional private YouTube upload. Failed stages show the error; *Retry* resumes from the last good stage. See [docs/video-generation.md](docs/video-generation.md).

## Animation engine
The Remotion renderer draws each scene as deterministic, narration-synchronised motion graphics (typography, diagrams, code/terminal, and security visualisations such as stack frames, heap and packet flow). The FFmpeg renderer ignores animation metadata. See [docs/animation-engine.md](docs/animation-engine.md), including its known limits.

## Supported providers
| Kind | Options |
|---|---|
| LLM | `mock` (offline), `ollama`, `anthropic` |
| TTS | `kokoro` (default; Apache-2.0 weights), `piper` (GPL software, research-licensed voice), `macos_say` (dev only), `elevenlabs` |
| Avatar | `static` (still image), `heygen` (unverified), `musetalk` (not integrated) |
| Render | `ffmpeg`, `remotion` |

## Configuration examples
```bash
# fully offline
LLM_PROVIDER=mock VOICE_PROVIDER=kokoro RENDER_ENGINE=ffmpeg
# local LLM
LLM_PROVIDER=ollama OLLAMA_MODEL=<a model you have pulled>
# Anthropic (developer API key, not a Claude Pro subscription)
LLM_PROVIDER=anthropic ANTHROPIC_API_KEY=<your key>
```
Author a lesson by hand ("Mode A"): `cd backend && .venv/bin/python -m app.cli.import_lesson ../lessons/<x>/bundle.json --approve-script` (see `lessons/sqli_fundamentals/build_bundle.py`).

## Testing
```bash
cd backend && .venv/bin/python -m pytest -q          # 307 tests, temporary SQLite DB, mock LLM, no network
cd frontend && npx tsc --noEmit                       # dashboard typecheck
cd video-engine && npx tsc --noEmit                   # video engine typecheck
```
The 6 real-Remotion render tests skip until Chrome Headless Shell is downloaded (`REMOTION_RENDER_TESTS=1 .venv/bin/python -m pytest tests/test_motion_render.py` to opt in). Not covered by automated tests: live LLM/TTS/avatar/YouTube services, Docker + n8n end to end, the dashboard UI (no frontend tests yet).

## Security considerations
Strict schema validation · no LLM text is executed · argv-only subprocess allow-list · CVE/CVSS claims verified · secret/PII scan of scene text · uploads need a recorded human approval and default to private · the n8n service token cannot approve · rate limiting · audit log. Known limitations (e.g. JWT in `localStorage`) are listed in [docs/security-model.md](docs/security-model.md). Report vulnerabilities privately: [SECURITY.md](SECURITY.md). Only test systems you own or are authorised to test.

## Licensing — please read
Original code is **Apache-2.0** ([LICENSE](LICENSE)). Third-party software and models keep their own terms:
- **Remotion** (optional renderer) is source-available, not open source: free for individuals, for-profit companies with up to 3 employees and non-profits; **larger companies need a paid Remotion licence.** The default FFmpeg renderer does not use Remotion.
- **Piper** is GPL-3 and its Lessac voice is research-licensed; prefer Kokoro (Apache-2.0) for commercial use.
- **n8n** uses the Sustainable Use License.

See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and [MODEL_AND_ASSET_LICENSES.md](MODEL_AND_ASSET_LICENSES.md). No models or media are shipped in this repository.

## Contributing
See [CONTRIBUTING.md](CONTRIBUTING.md) and the [Code of Conduct](CODE_OF_CONDUCT.md).

## Layout
`backend/` FastAPI + SQLAlchemy + Alembic · `frontend/` Next.js dashboard · `video-engine/` Remotion · `automation/` 13 n8n workflows · `ai/` prompts + JSON schemas · `voice/`, `avatar/` provider docs · `infrastructure/` compose, nginx · `lab/` vulnerable demo app · `course/`, `lessons/` course content · `docs/` details.

## Acknowledgements
[Kokoro](https://huggingface.co/hexgrad/Kokoro-82M) and [kokoro-onnx](https://github.com/thewh1teagle/kokoro-onnx), [Remotion](https://www.remotion.dev), [FastAPI](https://fastapi.tiangolo.com), [Next.js](https://nextjs.org), [n8n](https://n8n.io), [FFmpeg](https://ffmpeg.org), Piper, and the OWASP, MITRE ATT&CK and NIST projects whose public material the course cites.

## License
Apache License 2.0 — see [LICENSE](LICENSE) and [NOTICE](NOTICE).
