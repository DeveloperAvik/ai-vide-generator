# Third-Party Notices

CipherCast's original source code is licensed under the Apache License 2.0 (see [LICENSE](LICENSE)). **Third-party software keeps its own licence; Apache-2.0 does not apply to it.** This repository does not vendor third-party code: dependencies are installed from their package registries. Licences below were read from package metadata installed on the maintainer's machine (2026-11-07) and are a best-effort inventory, not legal advice. Re-check before relying on it, especially after dependency updates.

## ⚠️ Read first: components with non-permissive terms

| Component | Where used | Terms | What it means for you |
|---|---|---|---|
| **Remotion** (`remotion`, `@remotion/*` 4.0.290) | `video-engine/`, optional `RENDER_ENGINE=remotion` | [Remotion License](https://remotion.dev/license): free for individuals, for-profit organisations with up to 3 employees, and non-profits; **larger companies must buy a Remotion company licence**. Source-available, not OSI open source. | CipherCast's own code stays Apache-2.0, but **if you use the Remotion renderer you must comply with Remotion's licence.** The default FFmpeg renderer does not use Remotion. |
| **piper-tts** (optional, `scripts/install_voice.sh`) | `VOICE_PROVIDER=piper` | GPL-3.0-or-later | Not a dependency of this project and not distributed here. If you install it, its GPL terms apply to that installation. |
| **n8n** (Docker image) | `infrastructure/`, `automation/` | [Sustainable Use License](https://docs.n8n.io/sustainable-use-license/) (fair-code) | Run as a separate service; not distributed here. Check n8n's terms for your use case (e.g. offering it as a hosted service). Our workflow JSON files are original to this project. |
| **espeak-ng** (used by Kokoro for phonemisation, via `espeakng-loader`) | `VOICE_PROVIDER=kokoro` | GPL-3.0 | Runs locally as a library installed by pip; not bundled in this repository. |
| **FFmpeg** (system binary) | rendering | LGPL/GPL depending on your build (the maintainer's Homebrew build was configured with `--enable-gpl`) | Installed by you; not bundled. |

## Python (backend)

From `backend/requirements.txt`; versions are those installed when audited.

| Package | Version | Licence |
|---|---|---|
| fastapi | 0.162.0 | MIT |
| uvicorn | 0.54.0 | BSD-3-Clause |
| sqlalchemy | 2.1.6 | MIT |
| psycopg / psycopg-binary | 3.3.6 | **LGPL-3.0** (used as an unmodified, dynamically linked library) |
| pydantic / pydantic-settings | 2.14.2 / 2.16.2 | MIT |
| alembic | 1.20.1 | MIT |
| bcrypt | 5.0.0 | Apache-2.0 |
| pyjwt | 2.15.1 | MIT |
| python-multipart | 0.0.32 | Apache-2.0 |
| pillow | 13.0.0 | MIT-CMU (HPND) |
| httpx | 0.28.1 | BSD-3-Clause |
| google-auth-oauthlib, google-api-python-client | 1.5.0 / 2.201.0 | Apache-2.0 |
| pytest | 9.2.0 | MIT |

Optional voice packages (not in `requirements.txt`): `kokoro-onnx` 0.6.1 (MIT per upstream repository), `soundfile` 0.14.0 (BSD-3-Clause), `onnxruntime` 1.31.1 (MIT), `piper-tts` 1.8.0 (GPL-3.0-or-later, see above). Transitive Python dependencies were not exhaustively enumerated; generate the full list yourself with `pip-licenses` if you redistribute a bundle.

## JavaScript — dashboard (`frontend/`)

Direct dependencies: next 15.1.6, react / react-dom 19.0.0, tailwindcss 3.4.17, postcss, autoprefixer, typescript, @types/* — all MIT, except typescript (Apache-2.0). Of ~110 installed packages (including transitive): MIT 90, Apache-2.0 9, ISC 7, BSD-3-Clause 1, 0BSD 1, and two that need attribution:

- `caniuse-lite` — CC-BY-4.0 (browser-support data used by build tooling).
- `@img/sharp-libvips-darwin-arm64` — LGPL-3.0-or-later (prebuilt libvips used by Next.js image optimisation).

## JavaScript — video engine (`video-engine/`)

Direct dependencies: remotion + `@remotion/{bundler,cli,renderer,three,transitions}` 4.0.290 (**Remotion License**, see top), react / react-dom 18.3.1 (MIT), three ^0.169.0 (MIT), @react-three/fiber ^8.17.10 (MIT), @types/*, typescript 5.6.3 (Apache-2.0), `@fontsource/inter` 5.3.0 and `@fontsource/jetbrains-mono` 5.3.0 (**SIL OFL-1.1**; fonts are fetched from npm at install time, not committed). Of ~190 installed packages: MIT 146, ISC 15, BSD-2/3-Clause 15, Apache-2.0 5, Unlicense 2, 0BSD 1, OFL-1.1 2, CC-BY-4.0 1 (`caniuse-lite`), and the Remotion packages (including the prebuilt `@remotion/compositor-*` binaries, which declare no licence field and fall under the Remotion License).

## External services (no code or data redistributed)

Anthropic API, Ollama, ElevenLabs, HeyGen, YouTube Data API. You supply your own credentials and are bound by each provider's terms. HeyGen support is implemented from public documentation and has **not** been verified against a live account.

## Reference material

The course and prompts cite MITRE ATT&CK, OWASP and NIST by name and URL only. No copied text from those sources is intended to be in this repository; if you add any, respect their licences (e.g. OWASP cheat sheets are CC BY-SA 4.0).
