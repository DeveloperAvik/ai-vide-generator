# Open-Source Release Audit — CipherCast

Audit date: 2026-11-07. Scope: the whole working directory (`ai-video-creation/ciphercast`). Method: file-content inspection, Gitleaks 8.30.1 (`--no-git`, redacted), installed-package metadata, and running the existing tests/typechecks. **No files were modified, deleted, or committed during this audit.** No secret values appear in this report.

Status legend: ✅ verified by a command in this audit · ⚠️ needs a decision or follow-up · ❌ release blocker.

## 1. Architecture

Pipeline: curriculum → researched script → technical review/claim check → **human script approval** → storyboard → voice → visuals/avatar → render (FFmpeg or Remotion) → quality gate → **human video approval** → private YouTube upload. n8n workflows drive the stages through a service token that cannot approve anything.

| Layer | Tech |
|---|---|
| API | FastAPI, SQLAlchemy 2, Alembic, Postgres 16 (SQLite in tests), JWT (HS256) + bcrypt, in-process rate limiter |
| Dashboard | Next.js 15.1.6 / React 19 / Tailwind 3 (token stored in `localStorage`) |
| Video engine | Remotion 4.0.290 + React 18 + three.js / react-three-fiber; default engine is FFmpeg (`render_engine=ffmpeg`) |
| Orchestration | 13 generated n8n workflows (`automation/generate_workflows.py`), n8n in Docker |
| AI | mock (default, offline), Ollama, Anthropic API |
| TTS | Kokoro (default per docs), Piper, macOS `say`, ElevenLabs |
| Avatar | static portrait, HeyGen (unverified against a live account), MuseTalk slot (not runnable here) |

## 2. Component inventory

| Dir | Contents | Publish? |
|---|---|---|
| `backend/app` | api, cli (8 modules), core, models, providers (llm/mock_llm/voice/avatar), schemas, security (auth, ratelimit, redaction…), services (19), workers | yes |
| `backend/migrations`, `backend/tests` | 6 Alembic versions; 22 test modules | yes |
| `frontend/` | Next.js dashboard (~40 source files) | yes (not `node_modules`, `.next`) |
| `video-engine/` | 27 source files: scenes, motion, diagrams, code, three.js, captions | yes (not `node_modules`) |
| `automation/` | 13 workflow JSONs + generator + `credentials.example.json` | yes after credential review (§5.3) |
| `infrastructure/` | docker-compose (all ports bound to 127.0.0.1), nginx, postgres snippet, n8n Dockerfile, helper scripts | yes |
| `scripts/` | setup/start/stop/backup/healthcheck/install_voice | yes |
| `ai/` | 10 prompts, 3 JSON schemas | yes |
| `lab/` | `vuln_app.py` (intentionally vulnerable; hardcoded `127.0.0.1:8099`), capture/render helpers | yes, with warnings (§5.4) |
| `course/`, `lessons/` | 12-module course markdown (42 files); `sqli_fundamentals` bundle | ⚠️ provenance/licence decision |
| `docs/`, `voice/`, `avatar/` | 9 docs; provider docs; `avatar/assets/instructor.png` | docs yes; assets see §6 |
| `storage/` (1.2 GB), `backups/`, `.run/`, `voice/models/`, `.env`, caches | generated/private | **no** |

## 3. Dependency inventory

Python (`backend/requirements.txt`, unpinned `>=`, no lockfile): fastapi, uvicorn, sqlalchemy, psycopg[binary], pydantic(+settings), alembic, bcrypt, pyjwt, python-multipart, pillow, httpx, google-auth-oauthlib, google-api-python-client, pytest. Optional, installed by script/docs, **not** in requirements: `piper-tts`, `kokoro-onnx`, `soundfile`, `onnxruntime`.
Frontend (pinned, lockfile present): next, react, react-dom, tailwindcss, postcss, autoprefixer, typescript, @types/*.
Video engine (pinned/caret, lockfile present): remotion + @remotion/{bundler,cli,renderer,three,transitions}, react 18, three, @react-three/fiber, @fontsource/{inter,jetbrains-mono}.
System: ffmpeg, Postgres, Node, Python 3.13. Docker images: `postgres:16-alpine`, n8n.

Licence details are in §6.

## 4. Existing test coverage

| Check | Result |
|---|---|
| Backend `pytest` | ✅ **307 passed** in 7m14s (71 warnings, incl. short HMAC test keys). Uses a temp SQLite DB, mock LLM, no network. Some tests are marked `needs_ffmpeg` / `needs_say` and skip when absent. |
| Frontend `tsc --noEmit` | ✅ clean |
| Video-engine `tsc --noEmit` | ✅ clean |
| Frontend unit tests | ❌ none exist |
| Video-engine tests / `remotion` build | not run in this audit; no tests exist |
| Linting | ❌ no ruff/flake8/eslint/prettier configuration anywhere |
| README claim "77 tests" | ❌ stale; actual is 307 |

CI implication: backend tests are CI-safe (no credentials). Tests needing Postgres, Ollama, Anthropic, n8n, `say`, or GPU cannot run in CI and must be documented as such.

## 5. Security findings

### 5.1 Secrets scan (Gitleaks, working tree incl. all non-binary files)
- `.env` (local, gitignored): 5 findings — real `SECRET_KEY`, `SERVICE_TOKEN`, admin password, n8n encryption key, n8n password. ✅ Confirmed gitignored. ⚠️ Rotate before/after release as a precaution; **n8n encryption key rotation invalidates stored n8n credentials.**
- `backend/tests/test_api_and_models.py` (+ its `.pyc`): 1 `aws-access-token` — a **dummy fixture** for the redaction tests (obviously fake). False positive; add a Gitleaks allowlist entry.
- `storage/local/lessons/*/sections/*.json`: ~80 `generic-api-key` hits — verified to be content-hash cache keys (`"key": "<hex>"`), **false positives**. These files are not published anyway.
- No hardcoded provider keys, tokens, private keys, cloud credentials, MongoDB/AWS/Cloudflare strings found in source. `/Users/…` paths and the author's email do **not** appear in source/docs (only in `.run/*.log`, not published).
- Git history: **none** (not a git repo), so there is no history to leak or scrub.

### 5.2 Sensitive data that must not be published
| Item | Finding | Severity |
|---|---|---|
| `backups/db_*.sql.gz` | Full DB dump incl. `users` table with an email and a **bcrypt password hash**, plus workflow logs | ❌ blocker if included (gitignored today) |
| `backups/manifests_*.tgz` | storage manifests | exclude |
| `.env` | live secrets | exclude |
| `storage/` (1.2 GB) | 107 generated MP4s, 293 WAVs, lesson JSON, `n8n_test_report.json`, voice samples, `final/` video | exclude |
| `.run/` | API/e2e logs containing local absolute paths | exclude |
| `voice/models/` (~400 MB) | Piper + Kokoro binaries | exclude, document download |
| `backend/.pytest_cache`, `__pycache__`, `*.tsbuildinfo`, `.next`, `node_modules`, `.venv` | caches/deps | exclude |
| `lab/session.json` | captured responses from the *local fake* lab app; already gitignored; harmless but regenerable | exclude (as today) |
| `backend/_run_next_13.py` | one-off dev script operating on lesson id 13 | ⚠️ remove from release after confirmation |
| `.claude/` | empty | exclude |

`.gitignore` already covers most of this. Gaps to add: `.venv`-in-subdirs patterns are fine, but add `*.tsbuildinfo`, `*.log`, `*.pid`, `*.onnx`, `*.bin` under `voice/`, `*.mp4/*.wav` outside docs, `.DS_Store`, `.claude/`, `_run_next_*.py`, `*.tgz`, `storage/**` (currently only `storage/local/*` etc. are listed, so e.g. `storage/final/`, `storage/motion_samples/`, `storage/voice_samples/`, `storage/lab_clips`… are **not** all ignored). `.dockerignore` should be reviewed likewise.

### 5.3 Application security review (observations, not changed)
- ✅ `APP_ENV=production` refuses weak `SECRET_KEY`, wildcard CORS, mock providers.
- ⚠️ Development defaults: `secret_key="change-me-in-env"` (warning logged, not fatal), DB default `studio:studio@localhost`. Acceptable for dev; must be documented in `docs/security-model.md`.
- ⚠️ JWT (HS256, 12 h) stored in browser `localStorage` → XSS-exposed; document as a known trade-off.
- ⚠️ In-process rate limiter only (not shared across workers).
- ✅ Docker compose publishes only on `127.0.0.1`; `start.sh` binds the API to `127.0.0.1`. ⚠️ Next.js `npm start -p 3000` binds all interfaces by default — add `-H 127.0.0.1` or document.
- ✅ n8n workflows: no embedded URLs, bearer tokens, or webhook secrets found; they read env vars. `credentials.example.json` is placeholder-only. (Full node-by-node review still to do in Phase 5.)
- Dashboard can write the Anthropic API key to `storage/runtime_config.json` (documented mode 0600, gitignored). ⚠️ Confirm 0600 in code during Phase 2 fixes.
- Docker setup is, per `DEVELOPMENT_STATUS.md`, **not fully verified**; do not claim it works until tested.

### 5.4 Intentionally vulnerable lab
`lab/vuln_app.py` hardcodes `HOST="127.0.0.1", PORT=8099`, docstring warns not to expose it, uses SQLite with fake data. ⚠️ Needs a `lab/README.md` and a startup banner; consider refusing a non-loopback `HOST` override. Course content references LAB_SAFETY (`course/LAB_SAFETY.md`) — verify consistency.

## 6. Licensing findings

Project licence will be **Apache-2.0** for original code. Third-party status (versions as installed/locked):

| Component | Licence | Issue |
|---|---|---|
| **Remotion 4.0.290** (`remotion`, `@remotion/*`) | Remotion License (source-available, **not OSI**): free for individuals, ≤3-employee for-profit companies, non-profits; **companies larger than that need a paid licence** | ❌ **Blocker for the stated goal** "commercial usage must remain permitted". Apache-2.0 on our code does not relieve downstream users of Remotion's terms. Remotion is optional (default engine is FFmpeg) — see options below. |
| **piper-tts 1.8.0** (optional) | **GPL-3.0-or-later** | ⚠️ Not in `requirements.txt`, installed only by `scripts/install_voice.sh`. Do not vendor; document as optional external install. |
| Piper voice `en_US-lessac-medium` | ✅ Verified at source: trained on the Lessac *Blizzard 2013* data under a **Research Licence Agreement** | Commercial use **not established** → excluded, documented as research-only, Kokoro recommended. |
| Kokoro-82M v1.0 model + voices | Apache-2.0 per project docs (**verify at source**); `kokoro-onnx` licence metadata blank locally | ⚠️ Verify; exclude binaries; download instructions exist in `voice/README.md`. |
| espeak-ng (via `espeakng-loader`, used by Kokoro) | GPL-3.0 (runtime, not bundled) | ⚠️ Document. |
| n8n | Sustainable Use License (fair-code) | ⚠️ Used as a separate Docker service; not redistributed. Our workflow JSONs are original. Document; don't call n8n open-source. |
| `psycopg` / `psycopg-binary` | LGPL-3.0 | ✅ Dynamic dependency; compatible; list in notices. |
| Pillow | MIT-CMU (HPND) | ✅ |
| Other Python deps | MIT / BSD / Apache-2.0 | ✅ permissive |
| Frontend deps (≈110 pkgs) | MIT/ISC/Apache/BSD/0BSD; `caniuse-lite` CC-BY-4.0 (dev/build data); `@img/sharp-libvips` LGPL-3 (Next image optimisation, prebuilt binary) | ✅ compatible; attribute CC-BY and LGPL items |
| Video-engine deps (≈190 pkgs) | mostly MIT/BSD/ISC; Remotion family as above; one `UNKNOWN` (`@remotion/compositor-darwin-arm64` binary) and one `UNLICENSED` entry to identify | ⚠️ identify before publishing the inventory |
| `@fontsource/inter`, `@fontsource/jetbrains-mono` | OFL-1.1 | ✅ redistributable with notice; fonts are npm deps, not committed |
| three.js, react-three-fiber | MIT | ✅ |
| HeyGen, ElevenLabs, Anthropic, Ollama | external services/APIs; user supplies keys; subject to their ToS | ✅ document |
| MuseTalk | not integrated (adapter slot only) | ✅ no assets present |
| `avatar/assets/instructor.png` | ✅ **Resolved:** byte-identical (SHA-256 prefix `6323059d…`) to the output of `visuals.default_portrait()`; `pipeline.py` regenerates it when missing | No third-party content. Gitignored because it is auto-generated. |
| `course/` + `lessons/` content | Authorship/provenance not stated; cites MITRE ATT&CK, OWASP, NIST by name/URL only (no copied excerpts found in the bundle) | ⚠️ Owner must confirm it is original; choose a licence (Apache-2.0 vs CC BY 4.0). Do not copy OWASP (CC BY-SA 4.0) text into the repo. |
| Stored `research_sources` excerpts (DB/`storage`) | Third-party text snippets | exclude with `storage/`/backups |

**Options for the Remotion blocker (decision needed):**
1. Keep Remotion as an **optional, clearly labelled** renderer; default stays FFmpeg; prominent `THIRD_PARTY_NOTICES.md` + README warning that commercial users above Remotion's thresholds must buy a licence. Honest and no rewrite. *(Recommended.)*
2. Move the Remotion engine to a separate repo/plugin so the core is fully permissive.
3. Replace Remotion — a rewrite, out of scope.

## 7. Missing documentation / community files
Missing: `LICENSE`, `NOTICE`, `THIRD_PARTY_NOTICES.md`, `MODEL_AND_ASSET_LICENSES.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `CHANGELOG.md`, `.github/` (issue/PR templates, CI), `.gitattributes`, `lab/README.md`, `docs/{architecture,installation,configuration,video-generation,animation-engine,security-model,troubleshooting}.md` (existing equivalents: `ARCHITECTURE.md`, `INSTALLATION.md`, `MOTION_ENGINE.md`, `TROUBLESHOOTING.md` — to be reconciled, not duplicated), license headers, backend lockfile, lint config.
Stale/personal content: README "77 tests"; `DEVELOPMENT_STATUS.md` (36 KB, author's hardware/dev log) should be trimmed or moved to docs.

## 8. Files that must not be published
`.env`, `backups/`, `storage/` (all), `.run/`, `voice/models/`, `lab/session.json`, `backend/.venv`, `backend/.pytest_cache`, `**/__pycache__`, `frontend/{node_modules,.next}`, `video-engine/{node_modules,out}`, `*.tsbuildinfo`, `.claude/`, `backend/_run_next_13.py`, `avatar/assets/instructor.png` (pending provenance), generated MP4/WAV/PNG outside intentionally-added docs images.

## 9. Release blockers

| # | Blocker | Proposed remediation | Needs from you |
|---|---|---|---|
| B1 | Remotion's licence limits commercial use by larger companies | **Decided:** optional renderer + prominent notice (README, THIRD_PARTY_NOTICES) | — |
| B2 | ~~`instructor.png` unknown provenance~~ **RESOLVED** — generated by project code, auto-recreated | gitignored | — |
| B3 | ~~Piper licence unverified~~ **RESOLVED (documented)**: research-only dataset licence; piper-tts GPL-3 | Excluded; documented in MODEL_AND_ASSET_LICENSES.md; install script warns | — |
| B4 | `backups/` has a real user email + password hash | **Excluded** via `.gitignore`; files left on disk untouched; verified not in the git index or history | Your call whether to delete/move them |
| B5 | ~~`.gitignore` leaves `storage/*` subfolders unignored~~ **FIXED** | `storage/*` ignored except `.gitkeep`s; media/model/log/dump patterns added | — |
| B6 | Course/lesson content provenance & licence | **Decided:** original work, Apache-2.0 | — |
| B7 | Local `.env` secrets | `.env` is untracked and never entered git. Rotation is a precaution only | Your action (optional) |

Non-blocking: no linting/frontend tests, unpinned Python deps, Next.js binds all interfaces, README test count, Docker path unverified, `_run_next_13.py`.

## 10. Remediation and validation results (after decisions)

Done: Apache-2.0 `LICENSE` (unmodified text from apache.org) + `NOTICE`; `THIRD_PARTY_NOTICES.md`; `MODEL_AND_ASSET_LICENSES.md`; strengthened `.gitignore`, `.gitattributes`; contributor/community files; `.github/` CI + templates; docs; `git init -b main` and one local commit. **Nothing was deleted.** Nothing was pushed.

Fixes to existing files (all behaviour-preserving for configured machines):
- `scripts/start.sh`: dashboard now `-H 127.0.0.1`.
- `scripts/install_voice.sh`: licence notice + 5 s pause.
- `lab/vuln_app.py`: loopback-only assertion.
- `backend/app/cli/demo.py`: **`make demo` crashed with `StopIteration` on a fresh database** (the mock curriculum has no "SQL Injection Fundamentals" lesson); it now assigns that title to the first lesson.
- `backend/tests/test_media_pipeline.py`: a test depended on `kokoro-onnx` being installed; now stubs the imports.
- `backend/tests/test_motion_render.py`: real Remotion render tests **hung/failed on a fresh checkout** (Chrome download); they now skip unless Chrome Headless Shell exists or `REMOTION_RENDER_TESTS=1`.
- `backend/tests/test_n8n_fixture.py`, `infrastructure/scripts/n8n_test.py`: no longer require `.env` / generated lab clips to import or run.

Validation (fresh `git clone` of the commit into a scratch directory, new venv, `npm ci`):
| Check | Result |
|---|---|
| Original tree, `pytest` | ✅ 307 passed |
| Fresh clone, no `.env`/Chrome/clips, `pytest` | ✅ 300 passed, 7 skipped (6 Remotion render, 1 lab-clips), 0 failed |
| Fresh clone + Chrome (Node 22 `remotion browser ensure`), `test_motion_render.py` | ✅ 7 passed (real Remotion render + verification) |
| `tsc --noEmit` frontend / video-engine | ✅ / ✅ |
| `next build` (frontend) | ✅ |
| `remotion bundle` (video-engine) | ✅ |
| ruff (E9,F63,F7,F82) | ✅ |
| `make demo` equivalent: Kokoro + mock LLM, ffmpeg engine | ✅ 62 s, 1920×1080 H.264 + AAC + SRT + thumbnail |
| Same, `--engine remotion` | ✅ |
| API start (`uvicorn`), `/api/health`, `/docs`, auth required | ✅ |
| Gitleaks: staged tree, git history | ✅ no leaks |
| Docker compose / n8n workflow import / HeyGen / YouTube / Ollama / Anthropic live / Linux / `next start` dashboard login UI | ❌ **not tested** |
| GitHub Actions workflow | ❌ **not executed** (YAML parses; commands were run locally) |

Known environment issue: with **Node 26**, Remotion 4.0.290's Chrome archive extraction stalled (reproduced twice); Node 22 LTS works. Documented in `docs/installation.md` and `docs/troubleshooting.md`.

## 11. Remaining items for the maintainer
1. Replace `OWNER` in the README badge URLs; the copyright line in `NOTICE` says "CipherCast contributors" — change it if you want your name.
2. The git commit author is your local git identity (name/email from `git config`). Check it before pushing; GitHub's `users.noreply.github.com` address avoids publishing a personal email.
3. Add a dedicated conduct/security contact if desired (currently GitHub private vulnerability reporting). Enable *Private vulnerability reporting* in the repo settings.
4. Push, confirm CI is green, then tag `v1.0.0`.
5. Optional: rotate local `.env` secrets; delete or relocate `backups/`.
6. Add screenshots/GIF; consider adding ruff/eslint configs and frontend tests.
