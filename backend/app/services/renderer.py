"""FFmpeg render engine (fallback / no-browser path). The Remotion engine (video-engine/) is the full-featured
path with real transitions; both consume the same storyboard + asset manifest and produce the same outputs."""
import json
import shutil
import tempfile
from pathlib import Path
from typing import Callable

from PIL import Image, ImageDraw

from app.schemas.content import Scene, StoryboardData
from app.security.subprocess_safe import run
from app.services import narration, subtitles, visuals
from app.utils import media


class RenderCancelled(RuntimeError):
    pass


class RenderError(RuntimeError):
    pass


def _caption(img_path: Path, text: str, out: Path) -> Path:
    img = Image.open(img_path).convert("RGB")
    d = ImageDraw.Draw(img, "RGBA")
    f = visuals.font(40, bold=True)
    lines = visuals.wrap(d, text, f, 1560)
    assert len(lines) <= 3, "caption too long; split cues shorter"
    h = 56 * len(lines) + 30
    y0 = 1000 - h
    d.rounded_rectangle([160, y0, 1760, y0 + h], 16, fill=(0, 0, 0, 170))
    for i, ln in enumerate(lines):
        d.text((960, y0 + 15 + i * 56 + 28), ln, font=f, fill="white", anchor="mm")
    img.save(out)
    return out


def _caption_overlay(text: str, out: Path) -> Path:
    img = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f = visuals.font(40, bold=True)
    lines = visuals.wrap(d, text, f, 1560)
    h = 56 * len(lines) + 30
    y0 = 1000 - h
    d.rounded_rectangle([160, y0, 1760, y0 + h], 16, fill=(0, 0, 0, 170))
    for i, ln in enumerate(lines):
        d.text((960, y0 + 15 + i * 56 + 28), ln, font=f, fill="white", anchor="mm")
    img.save(out)
    return out


def render_long(*, storyboard: StoryboardData, scene_pngs: dict[str, Path], scene_audio: dict[str, Path],
                scene_video: dict[str, Path], out_dir: Path, music: Path | None = None,
                on_progress: Callable[[float], None] = lambda p: None,
                should_cancel: Callable[[], bool] = lambda: False, fps: int = 30) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="render_", dir=out_dir))
    try:
        clips, all_cues, t0, scene_info = [], [], 0.0, []
        n = len(storyboard.scenes)
        for i, sc in enumerate(storyboard.scenes):
            if should_cancel():
                raise RenderCancelled("cancelled by user")
            audio = scene_audio[sc.scene_id]
            adur = media.duration(audio)
            dur = max(sc.duration_seconds, adur + 0.4)  # never cut narration off
            clip = work / f"{sc.scene_id}.mp4"
            tm = narration.load_timing(scene_audio[sc.scene_id])
            cues = [subtitles.Cue(t0 + c["start"], t0 + c["end"], c["text"]) for c in tm] if tm else subtitles.scene_cues(sc.narration, t0, adur)
            all_cues += cues
            rec = scene_video.get(sc.scene_id)
            if rec:  # lab recording or avatar clip as the picture track
                _clip_from_video(rec, audio, dur, clip, fps, cues, t0, work, sc.scene_id)
            else:
                _clip_from_stills(scene_pngs[sc.scene_id], cues, t0, audio, dur, clip, work, sc.scene_id, fps)
            clips.append(clip)
            scene_info.append({"scene_id": sc.scene_id, "start": round(t0, 3), "duration": round(dur, 3), "audio_duration": round(adur, 3),
                               "transition": sc.transition, "picture": "recording" if rec else "still"})
            t0 += dur
            on_progress((i + 1) / (n + 1) * 0.9)
        lst = work / "list.txt"
        lst.write_text("".join(f"file '{c.as_posix()}'\n" for c in clips))
        srt = out_dir / "subtitles.srt"
        srt.write_text(subtitles.to_srt(all_cues))
        video = out_dir / "lesson.mp4"
        cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-i", str(srt)]
        if music:
            cmd += ["-stream_loop", "-1", "-i", str(music), "-filter_complex",
                    "[2:a]volume=0.08[m];[0:a][m]amix=inputs=2:duration=first:dropout_transition=2[a]",
                    "-map", "0:v", "-map", "[a]", "-map", "1:0"]
            cmd += ["-c:v", "copy", "-c:a", "aac", "-b:a", "192k"]
        else:
            cmd += ["-map", "0:v", "-map", "0:a", "-map", "1:0", "-c:v", "copy", "-c:a", "copy"]
        cmd += ["-c:s", "mov_text", "-metadata:s:s:0", "language=eng", "-movflags", "+faststart", str(video)]
        r = run(cmd, timeout=1800)
        if r.returncode != 0:
            raise RenderError(f"final mux failed: {r.stderr[-400:]}")
        on_progress(0.95)
        result = verify(video, expected=t0, srt=srt)
        thumb_src = work / "thumb_frame.png"
        run(["ffmpeg", "-y", "-ss", "2", "-i", str(video), "-frames:v", "1", str(thumb_src)], timeout=60)
        manifest = {"engine": "ffmpeg", "video": video.name, "subtitles": srt.name, "scenes": scene_info, "verification": result,
                    "sha256": media.sha256_file(video), "music": bool(music), "fps": fps}
        (out_dir / "render_manifest.json").write_text(json.dumps(manifest, indent=2))
        on_progress(1.0)
        return {"video": video, "srt": srt, "manifest": out_dir / "render_manifest.json", "duration": result["duration"], "sha256": manifest["sha256"], "verification": result}
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _clip_from_stills(png: Path, cues, t0, audio: Path, dur: float, out: Path, work: Path, sid: str, fps: int):
    frames = []
    for i, c in enumerate(cues):
        p = work / f"{sid}_c{i}.png"
        _caption(png, c.text, p)
        frames.append((p, c.end - c.start))
    pad = dur - sum(d for _, d in frames)
    if pad > 0.01:
        frames.append((png, pad))
    lst = work / f"{sid}_frames.txt"
    lst.write_text("".join(f"file '{p.as_posix()}'\nduration {d:.4f}\n" for p, d in frames) + f"file '{frames[-1][0].as_posix()}'\n")
    fade = min(0.35, dur / 4)
    vf = f"fps={fps},scale=1920:1080,format=yuv420p,fade=t=in:st=0:d={fade},fade=t=out:st={dur - fade:.3f}:d={fade}"
    r = run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-i", str(audio), "-vf", vf,
             "-af", f"apad=whole_dur={dur:.3f},aresample=48000", "-t", f"{dur:.3f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
             "-c:a", "aac", "-b:a", "192k", "-ac", "2", str(out)], timeout=600)
    if r.returncode != 0:
        raise RenderError(f"scene {sid} failed: {r.stderr[-400:]}")


def _clip_from_video(src: Path, audio: Path, dur: float, out: Path, fps: int, cues=(), t0: float = 0.0, work: Path | None = None, sid: str = "s"):
    """Recording as picture track: holds the last frame if shorter than the narration, burns timed captions via overlay."""
    base = f"fps={fps},scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,format=yuv420p,tpad=stop_mode=clone:stop_duration=300"
    cmd = ["ffmpeg", "-y", "-i", str(src), "-i", str(audio)]
    chain, last = [f"[0:v]{base}[v0]"], "v0"
    for k, c in enumerate(cues):
        png = _caption_overlay(c.text, work / f"{sid}_cap{k}.png")
        cmd += ["-i", str(png)]
        chain.append(f"[{last}][{k + 2}:v]overlay=enable='between(t,{c.start - t0:.3f},{c.end - t0:.3f})'[v{k + 1}]")
        last = f"v{k + 1}"
    fade = min(0.35, dur / 4)
    chain.append(f"[{last}]fade=t=in:st=0:d={fade},fade=t=out:st={dur - fade:.3f}:d={fade},format=yuv420p[vout]")
    cmd += ["-filter_complex", ";".join(chain), "-map", "[vout]", "-map", "1:a", "-af", f"apad=whole_dur={dur:.3f},aresample=48000",
            "-t", f"{dur:.3f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-b:a", "192k", "-ac", "2", str(out)]
    r = run(cmd, timeout=900)
    if r.returncode != 0:
        raise RenderError(f"recording clip failed: {r.stderr[-400:]}")


def verify(video: Path, expected: float, srt: Path | None = None, size=(1920, 1080), tol: float = 1.0) -> dict:
    """Integrity, duration, codec, and A/V sync checks via ffprobe. Raises RenderError on failure."""
    info = media.probe(video)
    v = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
    a = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    problems = []
    if not v or not a:
        problems.append("missing video or audio stream")
    else:
        if v["codec_name"] != "h264":
            problems.append(f"video codec {v['codec_name']} != h264")
        if a["codec_name"] != "aac":
            problems.append(f"audio codec {a['codec_name']} != aac")
        if (v["width"], v["height"]) != size:
            problems.append(f"resolution {v['width']}x{v['height']} != {size[0]}x{size[1]}")
        num, den = map(int, v["r_frame_rate"].split("/"))
        if abs(num / den - 30) > 0.5:
            problems.append(f"fps {num / den:.2f} != 30")
        vd, ad = float(v.get("duration", 0)), float(a.get("duration", 0))
        if abs(vd - ad) > 0.25:
            problems.append(f"A/V drift: video {vd:.2f}s vs audio {ad:.2f}s")
    dur = float(info["format"]["duration"])
    if abs(dur - expected) > tol:
        problems.append(f"duration {dur:.2f}s differs from expected {expected:.2f}s")
    # decode the whole file to catch corruption
    r = run(["ffmpeg", "-v", "error", "-i", str(video), "-f", "null", "-"], timeout=900)
    if r.returncode != 0 or r.stderr.strip():
        problems.append(f"decode errors: {r.stderr.strip()[:200]}")
    if srt is not None and (not srt.exists() or srt.stat().st_size == 0):
        problems.append("SRT missing")
    if problems:
        raise RenderError("; ".join(problems))
    return {"duration": dur, "video_codec": "h264", "audio_codec": "aac", "resolution": f"{size[0]}x{size[1]}", "fps": 30, "ok": True}
