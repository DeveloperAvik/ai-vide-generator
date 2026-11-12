"""Instagram Reels maker: topic (+ optional photos) -> 1080x1920 H.264/AAC MP4 with narration, captions and music.

Pipeline: plan (LLM) -> narration (local TTS, sentence-accurate timing) -> per-scene visuals (Ken Burns on the user's photos, or a
generated gradient card when there are none) -> burned-in captions -> mix with synthesised music -> verify with ffprobe.
Job state lives in storage/reels/<id>/status.json (no database tables). Nothing is posted anywhere: you download the MP4 and upload it."""
import json
import re
import shutil
import tempfile
import uuid
import wave
from pathlib import Path
from typing import Callable

from PIL import Image, ImageOps

from app.core.config import get_settings
from app.providers import voice as voice_mod
from app.providers.llm import LLMError, get_llm
from app.schemas.reel import ReelPlan, ReelRequest, ReelScene
from app.security.subprocess_safe import popen_stdin, run
from app.services import narration, reel_fx, reel_music, subtitles
from app.services.storage import get_storage
from app.utils import media

W, H, FPS = reel_fx.W, reel_fx.H, reel_fx.FPS
MAX_PHOTOS, MAX_PHOTO_BYTES = 12, 15_000_000
_ID = re.compile(r"^[0-9a-f]{12}$")
TAIL_S = 0.35  # breathing room after each scene's narration


class ReelError(RuntimeError):
    pass


# ---------------------------------------------------------------- style presets
STYLE_GUIDE = {
    "trending": ("Fast, punchy, curiosity-driven. Open with a scroll-stopping hook in the first sentence. Short sentences, modern casual voice, "
                 "one surprising fact or take per scene, end with a call to action (follow / save / share).", "upbeat", 2.9),
    "lofi": ("Calm, cozy, reflective, like a late-night study session. Soft, warm, unhurried sentences.", "lofi", 2.2),
    "educational": ("A clear mini-lesson for a beginner: hook question, then 3-5 simple steps or ideas with a concrete example, then a one-line recap. "
                    "Accurate, no jargon without explanation.", "chill", 2.5),
    "motivational": ("Energetic and uplifting, second person ('you'), strong verbs, ends on a memorable line.", "cinematic", 2.6),
    "storytelling": ("A tight story with a hook, a turn and a payoff. Vivid, concrete details.", "cinematic", 2.4),
    "promo": ("Benefit-led product or brand promo: problem, solution, proof, call to action. Honest; no invented statistics or claims.", "upbeat", 2.8),
}

PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"}, "caption": {"type": "string"}, "hashtags": {"type": "array", "items": {"type": "string"}},
        "scenes": {"type": "array", "items": {"type": "object", "properties": {
            "headline": {"type": "string"}, "narration": {"type": "string"}, "photo_index": {"type": ["integer", "null"]}},
            "required": ["headline", "narration"]}},
    },
    "required": ["title", "caption", "hashtags", "scenes"],
}


def scene_count(duration_s: int, n_photos: int) -> int:
    return max(3, min(12, max(round(duration_s / 5), min(n_photos, 12))))


def plan_reel(req: ReelRequest, n_photos: int, llm=None) -> tuple[ReelPlan, bool]:
    """Returns (plan, simulated). The offline mock model cannot write real copy, so it yields an honest template flagged simulated=True."""
    llm = llm or get_llm()
    n = scene_count(req.duration_s, n_photos)
    words = int(req.duration_s * STYLE_GUIDE[req.style][2]) if req.voiceover else n * 8
    if llm.name == "mock":
        return _template_plan(req, n), True
    system = ("You write scripts for Instagram Reels (vertical short video). Output only the requested JSON. Never invent statistics, quotes, "
              "prices or claims about real people; if you are unsure of a fact, leave it out.")
    prompt = (f"TOPIC: {req.topic}\nSTYLE: {req.style}. {STYLE_GUIDE[req.style][0]}\n"
              + (f"EXTRA DIRECTION: {req.style_notes}\n" if req.style_notes else "")
              + f"LENGTH: exactly {n} scenes, about {words} spoken words in total (about {req.duration_s} seconds).\n"
              + (f"PHOTOS: the creator supplied {n_photos} photos (indexes 0-{n_photos - 1}); set photo_index on each scene to the photo that fits it best, "
                 "using every photo at least once where possible.\n" if n_photos else "PHOTOS: none supplied; photo_index must be null.\n")
              + "Each scene: headline (max 6 words, shown on screen), narration (" + (f"about {max(words // n, 6)} words: two short spoken sentences" if req.voiceover else "one short sentence") + ", plain text, no emojis, no hashtags, no stage directions). "
                "Also give caption (the Instagram post text, 1-3 lines, may include one emoji) and 5-10 relevant hashtags without the # sign.")
    last, plan = None, None
    for attempt in range(3):
        try:
            p = prompt if plan is None else (
                f"Here is a reel script JSON:\n{plan.model_dump_json()}\n\nThe narration is too short ({_words(plan)} words; about {words} are needed). Rewrite the SAME JSON so each "
                f"narration is two short sentences totalling about {max(words // len(plan.scenes), 6)} words, adding a concrete detail or reason to each point. Keep the headlines and exactly {len(plan.scenes)} scenes.")
            plan = ReelPlan.model_validate(llm.complete_json(system, p, 4000, PLAN_SCHEMA))
        except (LLMError, ValueError) as e:
            last = e
            continue
        if not req.voiceover or _words(plan) >= 0.75 * words or attempt == 2:  # too-short drafts get one or two expansion retries
            return _clean(plan, n_photos), False
    if plan is not None:
        return _clean(plan, n_photos), False
    raise ReelError(f"could not get a valid reel script from the {llm.name} model: {last}")


def _words(plan: ReelPlan) -> int:
    return sum(len(sc.narration.split()) for sc in plan.scenes)


def _clean(plan: ReelPlan, n_photos: int) -> ReelPlan:
    for i, sc in enumerate(plan.scenes):
        sc.narration = " ".join(sc.narration.replace("#", "").split())
        sc.headline = " ".join(sc.headline.split())[:60]
        sc.photo_index = sc.photo_index if (sc.photo_index is not None and 0 <= sc.photo_index < n_photos) else (i % n_photos if n_photos else None)
    plan.hashtags = [re.sub(r"[^\w]", "", h) for h in plan.hashtags if re.sub(r"[^\w]", "", h)][:30]
    return plan


def _template_plan(req: ReelRequest, n: int) -> ReelPlan:
    t = req.topic.rstrip(".!? ")
    beats = [("Stop scrolling", f"Here is something worth knowing about {t}."), ("The idea", f"{t} is easier to grasp than most people think."),
             ("Why it matters", "Once you see it clearly, the details start to click."), ("Try this", "Pick one small step today and actually do it."),
             ("Keep going", "Small steps repeated beat big plans never started."), ("Remember", f"That is {t} in a nutshell."),
             ("Your turn", "Follow for more, and save this for later.")]
    scenes = [ReelScene(headline=b[0], narration=b[1]) for b in (beats[:n - 1] + beats[-1:] if n < len(beats) else beats + beats[1:n - len(beats) + 1])][:n]
    tag = re.sub(r"[^\w]", "", t.title().replace(" ", ""))[:30]
    return ReelPlan(title=t[:100], caption=f"{t}. Save this for later.", hashtags=[tag, "reels", req.style], scenes=scenes)


# ---------------------------------------------------------------- photos
def ingest_photo(data: bytes, dest: Path) -> Path:
    """Validate with Pillow, honour EXIF rotation, re-encode as sRGB JPEG. Raises ReelError for anything that is not a real image."""
    if len(data) > MAX_PHOTO_BYTES:
        raise ReelError(f"photo larger than {MAX_PHOTO_BYTES // 1_000_000} MB")
    try:
        import io
        im = Image.open(io.BytesIO(data))
        im.load()
        im = ImageOps.exif_transpose(im).convert("RGB")
    except Exception as e:  # noqa: BLE001 - Pillow raises many types for corrupt input
        raise ReelError("file is not a readable image (use JPEG, PNG or WebP)") from e
    if min(im.size) < 200:
        raise ReelError("photo is too small (minimum 200 px on the short side)")
    im.thumbnail((3000, 3000))
    im.save(dest, "JPEG", quality=92)
    return dest


def word_cues(cues: list[subtitles.Cue], max_words: int = 4) -> list[subtitles.Cue]:
    """Re-cut sentence cues into short on-screen chunks (reel style), timed proportionally to character count inside each sentence."""
    out = []
    for c in cues:
        words = c.text.split()
        k = max(1, -(-len(words) // max_words))
        size = -(-len(words) // k)
        chunks = [" ".join(words[i:i + size]) for i in range(0, len(words), size)]
        total = sum(len(x) for x in chunks) or 1
        t = c.start
        for x in chunks:
            d = (c.end - c.start) * len(x) / total
            out.append(subtitles.Cue(t, t + d, x))
            t += d
    return out


# ---------------------------------------------------------------- render
def _ffmpeg(cmd: list[str], what: str, timeout: int = 900):
    r = run(cmd, timeout=timeout)
    if r.returncode != 0:
        raise ReelError(f"{what} failed: {r.stderr[-500:]}")


def _silence(seconds: float, rate: int = 48000) -> bytes:
    return b"\x00" * (int(seconds * rate) * 2)


def render_reel(req: ReelRequest, plan: ReelPlan, photos: list[Path], out_dir: Path, on_progress: Callable[[str, float], None] = lambda s, p: None,
                voice=None) -> dict:
    """Plan in, finished reel out. `voice` defaults to the configured TTS; if it is unavailable the reel is rendered without narration
    (music + captions only) and `warnings` says so. Raises ReelError on a hard failure."""
    out_dir.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []
    work = Path(tempfile.mkdtemp(prefix="work_", dir=out_dir))
    try:
        if req.voiceover and voice is None:
            try:
                voice = voice_mod.get_voice()
            except voice_mod.VoiceUnavailable as e:
                warnings.append(f"no narration: {e}")
        if not req.voiceover:
            voice = None

        # 1. narration + timing per scene
        on_progress("narration", 0.05)
        scenes, t0 = [], 0.0
        pcm, rate = [], 48000
        for i, sc in enumerate(plan.scenes):
            if voice:
                wav = work / f"n{i}.wav"
                timing = narration.synth_with_timing(voice, sc.narration, wav)
                with wave.open(str(wav)) as w:
                    rate = w.getframerate()
                    data = w.readframes(w.getnframes())
                adur = len(data) / (2 * rate)
                cues = [subtitles.Cue(t0 + c["start"], t0 + c["end"], c["text"]) for c in timing]
                pcm += [data, _silence(TAIL_S, rate)]
            else:
                adur = max(2.5, len(sc.narration.split()) / STYLE_GUIDE[req.style][2])
                cues = subtitles.scene_cues(sc.narration, t0, adur)
            dur = adur + TAIL_S
            scenes.append({"scene": sc, "start": t0, "dur": dur, "cues": cues})
            t0 += dur
            on_progress("narration", 0.05 + 0.25 * (i + 1) / len(plan.scenes))
        total = t0
        if total > 90.5:
            warnings.append(f"reel is {total:.0f}s; Instagram Reels cap at 90s - lower duration_s or shorten the script")

        # 2. frames: animated scenes streamed into ffmpeg
        music_style = req.music if req.music != "auto" else STYLE_GUIDE[req.style][1]
        theme = reel_fx.THEMES[req.style]
        fx_scenes = []
        for i, s in enumerate(scenes):
            sc: ReelScene = s["scene"]
            pp = photos[sc.photo_index] if photos and sc.photo_index is not None and sc.photo_index < len(photos) else None
            chunks = []
            for c in (word_cues(s["cues"]) if req.captions else []):
                ws = c.text.split()
                tot = sum(len(w) for w in ws) or 1
                t, row = c.start, []
                for w in ws:
                    row.append((w, t, t + (c.end - c.start) * len(w) / tot))
                    t = row[-1][2]
                chunks.append(row)
            fx_scenes.append(reel_fx.SceneFx(s["start"], s["dur"], sc.headline, chunks, reel_fx.prep_photo(pp, theme) if pp else None,
                                             ("in", "out", "left", "right")[i % 4]))
        canvas = reel_fx.ReelCanvas(fx_scenes, req.style, total, reel_music.bpm(music_style) if music_style != "none" else None)
        silent = work / "video.mp4"
        nframes = int(total * FPS) + 1
        with open(work / "ffmpeg.err", "w+") as err:
            proc = popen_stdin(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                                "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p", str(silent)], err)
            try:
                for n in range(nframes):
                    proc.stdin.write(canvas.frame(n).tobytes())
                    if n % 15 == 0:
                        on_progress("visuals", 0.3 + 0.55 * n / nframes)
                proc.stdin.close()
                proc.wait(timeout=300)
            except (BrokenPipeError, OSError):
                proc.kill()
            finally:
                if proc.poll() is None:
                    proc.kill()
            if proc.returncode != 0:
                err.seek(0)
                raise ReelError(f"frame encode failed: {err.read()[-500:]}")

        # 3. audio mix
        on_progress("mix", 0.85)
        cmd = ["ffmpeg", "-y", "-i", str(silent)]
        fc, vo = [], bool(voice)
        if vo:
            narr = work / "narration.wav"
            with wave.open(str(narr), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(rate)
                w.writeframes(b"".join(pcm))
            cmd += ["-i", str(narr)]
        if music_style != "none":
            loop = reel_music.track(music_style, get_storage().path("reels", "_music", "x").parent)
            cmd += ["-stream_loop", "-1", "-i", str(loop)]
            mi = 2 if vo else 1
            fade = f"afade=t=in:d=1,afade=t=out:st={max(total - 1.5, 0):.2f}:d=1.5"
            if vo:
                fc += [f"[{mi}:a]volume=0.55,{fade}[m]", "[1:a]asplit=2[v][sc]",
                       "[m][sc]sidechaincompress=threshold=0.04:ratio=10:attack=15:release=350[md]",
                       "[v][md]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95[a]"]
            else:
                fc += [f"[{mi}:a]volume=0.9,{fade},atrim=0:{total:.3f}[a]"]
        elif vo:
            fc += ["[1:a]anull[a]"]
        else:
            cmd += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
            fc += ["[1:a]anull[a]"]
        video = out_dir / "reel.mp4"
        cmd += ["-filter_complex", ";".join(fc), "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
                "-t", f"{total:.3f}", "-movflags", "+faststart", str(video)]
        _ffmpeg(cmd, "final mix")

        # 4. verify + extras
        info = media.probe(video)
        v = next((s for s in info["streams"] if s.get("codec_type") == "video"), None)
        if not v or (v["width"], v["height"]) != (W, H) or not media.has_stream(info, "audio"):
            raise ReelError("verification failed: output is not a 1080x1920 video with an audio track")
        dur = float(info["format"]["duration"])
        if abs(dur - total) > 0.6:
            raise ReelError(f"verification failed: duration {dur:.2f}s differs from planned {total:.2f}s")
        cover = out_dir / "cover.jpg"
        _ffmpeg(["ffmpeg", "-y", "-ss", "0.8", "-i", str(video), "-frames:v", "1", "-q:v", "3", str(cover)], "cover frame", 60)
        cues_all = [c for s in scenes for c in s["cues"]]
        (out_dir / "subtitles.srt").write_text(subtitles.to_srt(cues_all))
        tags = " ".join(f"#{h}" for h in plan.hashtags)
        (out_dir / "caption.txt").write_text(f"{plan.caption}\n\n{tags}\n")
        on_progress("done", 1.0)
        return {"video": video.name, "cover": cover.name, "duration": round(dur, 2), "voiceover": vo, "music": music_style, "warnings": warnings,
                "photos_used": sum(1 for s in scenes if photos and s["scene"].photo_index is not None), "sha256": media.sha256_file(video)}
    finally:
        shutil.rmtree(work, ignore_errors=True)


# ---------------------------------------------------------------- jobs (file-backed)
def reel_dir(rid: str) -> Path:
    if not _ID.match(rid):
        raise ReelError("invalid reel id")
    return get_storage().path("reels", rid, "x").parent


def _write_status(d: Path, **kw):
    p = d / "status.json"
    cur = json.loads(p.read_text()) if p.exists() else {}
    cur.update(kw)
    tmp = d / "status.tmp"
    tmp.write_text(json.dumps(cur))
    tmp.replace(p)


def get_status(rid: str) -> dict | None:
    p = reel_dir(rid) / "status.json"
    return json.loads(p.read_text()) if p.exists() else None


def list_reels(limit: int = 50) -> list[dict]:
    root = get_storage().path("reels", "x").parent
    items = [json.loads(p.read_text()) for p in root.glob("*/status.json")]
    return sorted(items, key=lambda s: s.get("created", ""), reverse=True)[:limit]


def create_job(req: ReelRequest, photo_blobs: list[bytes], user_id: int | None = None) -> str:
    """Validates and stores photos, writes the initial status. Raises ReelError on bad input. Does not start the work."""
    from datetime import datetime, timezone
    if len(photo_blobs) > MAX_PHOTOS:
        raise ReelError(f"at most {MAX_PHOTOS} photos")
    rid = uuid.uuid4().hex[:12]
    d = reel_dir(rid)
    (d / "photos").mkdir(parents=True, exist_ok=True)
    try:
        for i, b in enumerate(photo_blobs):
            ingest_photo(b, d / "photos" / f"p{i:02d}.jpg")
    except ReelError as e:
        shutil.rmtree(d, ignore_errors=True)
        raise ReelError(f"photo {i + 1}: {e}") from e
    _write_status(d, id=rid, status="queued", stage="queued", progress=0.0, created=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                  request=req.model_dump(), photos=len(photo_blobs), user_id=user_id)
    return rid


def run_job(rid: str) -> None:
    """Executes a queued job to completion; never raises (failure is recorded in status.json)."""
    d = reel_dir(rid)
    try:
        st = get_status(rid) or {}
        req = ReelRequest.model_validate(st["request"])
        photos = sorted((d / "photos").glob("p*.jpg"))
        _write_status(d, status="running", stage="script", progress=0.02)
        plan, simulated = plan_reel(req, len(photos))
        _write_status(d, plan=plan.model_dump(), simulated=simulated, progress=0.04)
        res = render_reel(req, plan, photos, d, on_progress=lambda s, p: _write_status(d, stage=s, progress=round(p, 3)))
        _write_status(d, status="done", stage="done", progress=1.0, result=res)
    except Exception as e:  # noqa: BLE001 - the job thread must always leave a readable final state
        _write_status(d, status="error", error=f"{type(e).__name__}: {e}"[:600])
