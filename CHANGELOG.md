# Changelog

All notable changes are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- **Instagram Reels maker** (`app/services/reels.py`, `POST /api/reels`, `python -m app.cli.reel`): any topic and optional photos become a 1080x1920 MP4 with narration, captions, Ken Burns motion and locally synthesised music. Frame-by-frame motion renderer (animated backgrounds, word-highlight captions, transitions, beat pulse). See `docs/reels.md`.
- Project renamed to **CipherCast** (previously "Cyber AI Studio"). The internal Postgres database/role name `cyber_studio` is unchanged so existing installs keep working.
- First public open-source release preparation: Apache-2.0 `LICENSE` and `NOTICE`, `THIRD_PARTY_NOTICES.md`, `MODEL_AND_ASSET_LICENSES.md`, `OPEN_SOURCE_AUDIT.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, GitHub issue/PR templates and CI, new docs (`configuration`, `video-generation`, `security-model`), `lab/README.md`.

### Changed (visuals)
- FFmpeg slides redesigned: shared gradient/grid background, numbered/lettered/tick "card" rows for bullets, quiz lettering, window chrome on code blocks, enlarged auto-cropped diagrams, footer progress bar, content kept clear of the caption zone.
- Thumbnail and instructor slide draw a branded shield graphic instead of the grey placeholder silhouette when no real portrait is configured (a real portrait still gets the circular ring treatment). The Remotion renderer is unchanged.

### Fixed
- `test_kokoro_reports_missing_files_instead_of_faking` no longer depends on `kokoro-onnx` being installed.
- Real-Remotion render tests skip on a fresh checkout until Chrome Headless Shell exists (they previously hung or failed offline); opt in with `REMOTION_RENDER_TESTS=1`.

### Changed
- `docs/` files renamed to lowercase (`architecture.md`, `installation.md`, `animation-engine.md`, `troubleshooting.md`).
- `scripts/start.sh` now binds the dashboard to `127.0.0.1` (previously all interfaces).
- `scripts/install_voice.sh` prints a licensing notice (Piper is GPL; the Lessac voice is research-licensed) before downloading.
- `lab/vuln_app.py` asserts a loopback-only host.
- `.gitignore` strengthened; added `.gitattributes`.
