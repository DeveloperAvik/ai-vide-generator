# Configuration

All settings are environment variables read from `.env` in the repository root (via `pydantic-settings`; `backend/app/core/config.py` is the source of truth). `.env.example` documents every variable with placeholders only. `scripts/setup.sh` copies it to `.env` and generates random `SECRET_KEY`, `SERVICE_TOKEN` and `N8N_ENCRYPTION_KEY`. **Never commit `.env`.**

Settings the dashboard can change (LLM provider/model, Ollama URL, Anthropic key, voice/avatar provider) are saved to `storage/runtime_config.json` (gitignored, mode 0600) and override `.env`.

## Core

| Variable | Default | Notes |
|---|---|---|
| `APP_ENV` | `development` | `production` refuses the mock LLM, `macos_say`, weak/short `SECRET_KEY` and wildcard CORS. |
| `DATABASE_URL` | local Postgres `studio:studio@localhost` | Dev default only. Tests use SQLite. Use a strong password anywhere reachable. |
| `SECRET_KEY` | `change-me-in-env` (logs a warning) | JWT signing key; ≥32 chars in production. `openssl rand -hex 32`. |
| `SERVICE_TOKEN` | empty | Bearer token for n8n. Cannot approve anything. |
| `FIRST_ADMIN_EMAIL` / `FIRST_ADMIN_PASSWORD` | `admin@example.com` / empty | Creates the first admin on API start when a password is set; clear it afterwards. |
| `CORS_ORIGINS` | `http://localhost:3000` | Comma-separated. |
| `POSTGRES_PASSWORD`, `N8N_ENCRYPTION_KEY` | placeholders | Used by docker compose. Changing the n8n key invalidates credentials stored in n8n. |

## AI providers

| `LLM_PROVIDER` | Needs | Notes |
|---|---|---|
| `mock` (default) | nothing | Offline, deterministic; rejected in production. |
| `ollama` | a running Ollama, `OLLAMA_URL`, `OLLAMA_MODEL` | Local models. |
| `anthropic` | `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` | Developer API key from console.anthropic.com. |

`LLM_FALLBACK_PROVIDER` is used when the primary fails. See [API_SETUP.md](API_SETUP.md) and [FREE_STACK.md](FREE_STACK.md).

## Voice

| `VOICE_PROVIDER` | Needs | Licence notes |
|---|---|---|
| `kokoro` (default in `.env.example`) | `kokoro-onnx`, model files in `voice/models/kokoro/`, `KOKORO_VOICE`, `KOKORO_SPEED` | Apache-2.0 weights |
| `piper` | `piper-tts`, `PIPER_BINARY`, `PIPER_MODEL` | GPL-3 software; Lessac voice is research-licensed |
| `macos_say` | macOS | development only |
| `elevenlabs` | `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID` | paid service |
| `auto` | — | picks piper → macos_say |

## Avatar, rendering, YouTube, n8n

- `AVATAR_PROVIDER`: `static` (default; still image, not a talking avatar), `heygen` (`HEYGEN_API_KEY`, `HEYGEN_AVATAR_ID`; **not verified against a live account**), `musetalk` (`MUSETALK_DIR`; needs a CUDA machine, not integrated here).
- `RENDER_ENGINE`: `ffmpeg` (default) or `remotion` (3D/visualisation scenes require it; see licence note in [installation.md](installation.md)).
- `YOUTUBE_CLIENT_SECRETS`, `YOUTUBE_REDIRECT_URI`: see [YOUTUBE_SETUP.md](YOUTUBE_SETUP.md). Uploads are private by default and need a recorded human approval.
- `NOTIFY_WEBHOOK_URL`, `STUDIO_DASHBOARD_URL`: optional n8n notification settings. See [N8N_SETUP.md](N8N_SETUP.md).

## Examples

Fully offline development: `LLM_PROVIDER=mock`, `VOICE_PROVIDER=kokoro`, `RENDER_ENGINE=ffmpeg`.
Local LLM: `LLM_PROVIDER=ollama`, `OLLAMA_MODEL=<a model you have pulled>`.
