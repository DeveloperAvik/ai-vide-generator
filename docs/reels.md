# Instagram Reels maker

Topic in (plus optional photos), vertical 1080x1920 H.264/AAC MP4 out, up to 90 s, with narration, burned-in captions, a cover frame and a ready-to-paste caption + hashtags.

```bash
cd backend
.venv/bin/python -m app.cli.reel "5 habits of great engineers" --style trending --duration 30 --photos a.jpg b.jpg
.venv/bin/python -m app.cli.reel "lofi study tips" --style lofi --music lofi
.venv/bin/python -m app.cli.reel "how DNS works" --style educational --notes "for absolute beginners"
```

Output: `storage/local/reels/<id>/` (`reel.mp4`, `cover.jpg`, `caption.txt`, `subtitles.srt`, `status.json`).

## API (auth required)
- `POST /api/reels` multipart: `topic`, `style`, `style_notes`, `duration_s`, `voiceover`, `music`, `captions`, `photos` (0-12 files) -> `202 {id}`
- `GET /api/reels/{id}` status, progress, script plan, result; `GET /api/reels/{id}/video?download=true`, `/cover`, `/caption`; `GET /api/reels`; `GET /api/reels/options`

## Styles and music
Styles: `trending`, `lofi`, `educational`, `motivational`, `storytelling`, `promo`; `style_notes` steers any other kind of video. Music: `auto` (per style), `lofi`, `chill`, `upbeat`, `cinematic`, `none`. Music is synthesised locally (`reel_music.py`): no samples, nothing to license, ducked under the voice.

## Look and motion
Each style has its own theme (`reel_fx.THEMES`): palette, caption case, transitions and film-grain level. Every frame is rendered in Python and streamed to ffmpeg:
- animated colour-blob backgrounds with drifting bokeh, or graded Ken Burns moves on your photos (vignette and a shaded lower third so captions stay readable);
- word-by-word captions: the spoken word pops and takes the accent colour (timing comes from the real TTS audio boundaries);
- animated headline (pill on photo scenes, big kinetic title on photo-less scenes), progress bar, film grain;
- transitions between scenes (flash, slide, wipe, fade, chosen per style) and a zoom pulse locked to the music's beat.
Rendering costs roughly 2-3 s of CPU per second of video.

## Behaviour and limits
- **Real copy needs a real LLM.** With `LLM_PROVIDER=mock` the script is a generic template and the job is flagged `simulated`.
- Photos: scenes use them in order (the model may pick `photo_index`); each gets a Ken Burns move. With no photos, scenes are styled gradient cards. The app does not fetch stock footage or generate images.
- No TTS installed -> the reel is still rendered (captions + music) and `warnings` says so.
- Not fact-checked: unlike lessons, reels skip the research/review/approval pipeline. Review the script in `status.json` before posting.
- It does **not** post to Instagram (needs a Meta business account and Graph API app review). Download the MP4 and upload it.
- Dashboard: **Instagram Reels** in the sidebar (`/reels`): form, photo upload, live progress, preview/download, script and caption.
