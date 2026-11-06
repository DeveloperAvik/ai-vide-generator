# Video generation workflow

Each lesson moves through a state machine (`backend/app/services/pipeline.py`); failed stages can be retried and resume from the last good stage (3 automatic retries).

1. **Curriculum** – an LLM provider (or JSON you paste, "Mode A") creates a course → modules → lessons.
2. **Research** – fetches only allow-listed official hosts (`services/research.py`) and stores source excerpts.
3. **Script** – the LLM output is parsed into strict Pydantic models (`schemas/content.py`); invalid output is retried once, then rejected.
4. **Technical review** – claim extraction/judging, CVE verification against NVD, independent review by a second (local) model, and a blocking **quality gate**. See [REVIEW_PIPELINE.md](REVIEW_PIPELINE.md).
5. **Human gate 1** – a person approves the script.
6. **Assets** – narration per scene (`services/narration.py`, with a measured `*.timing.json`), slides/diagrams, optional avatar clips. Storyboard text is scanned for secrets/PII first.
7. **Render** – FFmpeg (Pillow-drawn slides, default) or Remotion (React motion graphics). Output: `lesson.mp4`, `subtitles.srt`, `render_manifest.json`, then ffprobe verification (codec, 1920×1080, 30 fps, A/V drift, full decode).
8. **Human gate 2** – a person approves the video.
9. **Upload** (optional) – private YouTube upload with scheduled publish time.

## Try it

```bash
make demo        # mock LLM + local voice → storage/demo/demo_lesson.mp4 (+ .srt, thumbnail, manifest)
cd backend && .venv/bin/python -m app.cli.demo --engine remotion --fresh   # options: --engine ffmpeg|remotion, --fresh, --online
```
`make demo` writes to the database and `storage/` configured in `.env`. The demo auto-passes the human gates **only** in this CLI, recorded as actor `demo-cli`.

Author a lesson by hand: see `lessons/sqli_fundamentals/build_bundle.py` and `python -m app.cli.import_lesson` (README).

Animation details: [animation-engine.md](animation-engine.md).
