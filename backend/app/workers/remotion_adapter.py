"""Runs the Remotion engine (video-engine/) as an isolated Node subprocess. Separate from the API process;
the only inputs are a props JSON and a public dir of assets. Falls back to nothing silently: errors surface."""
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Callable

from app.core.config import get_settings
from app.schemas.content import StoryboardData
from app.services import animation_sync, mermaid_lite, narration, renderer, subtitles
from app.utils import media

TRANSITION_FRAMES = 15
FPS = 30


class RemotionUnavailable(RuntimeError):
    pass


def available() -> tuple[bool, str]:
    eng = get_settings().video_engine_dir
    if not shutil.which("node"):
        return False, "node not found"
    if not (eng / "node_modules" / "@remotion" / "renderer").exists():
        return False, "run `npm install` in video-engine/"
    return True, "ok"


def render_long(*, storyboard: StoryboardData, assets_dir: Path, scene_audio: dict[str, Path], scene_video: dict[str, Path],
                out_dir: Path, portrait: Path | None, music: Path | None, on_progress: Callable[[float], None] = lambda p: None,
                should_cancel: Callable[[], bool] = lambda: False, brand: str = "Teaching Studio") -> dict:
    ok, why = available()
    if not ok:
        raise RemotionUnavailable(why)
    eng = get_settings().video_engine_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    pub = Path(tempfile.mkdtemp(prefix="pub_", dir=out_dir))
    try:
        scenes, cues, t, anim_warnings = [], [], 0.0, []
        for i, sc in enumerate(storyboard.scenes):
            adur = media.duration(scene_audio[sc.scene_id])
            frames = round(max(sc.duration_seconds, adur + 0.4) * FPS)
            shutil.copy(scene_audio[sc.scene_id], pub / f"{sc.scene_id}.wav")
            entry = {"scene_id": sc.scene_id, "type": sc.type, "narration": sc.narration, "on_screen_text": sc.on_screen_text,
                     "transition": sc.transition, "code": sc.code, "language": sc.language, "terminal_lines": sc.terminal_lines,
                     "bullets": sc.bullets, "brand": brand, "audio": f"{sc.scene_id}.wav", "frames": frames}
            tm = narration.load_timing(scene_audio[sc.scene_id])
            evs, warns = animation_sync.resolve_events(sc, tm, adur, FPS, frames)  # narration -> frame-numbered events (see animation_sync)
            anim_warnings += warns
            spec = sc.animation
            entry["events"] = animation_sync.events_payload(evs)
            entry["motion"] = {"profile": spec.animation_profile if spec else "standard", "camera": spec.camera_movement if spec else "none",
                               "exit": spec.exit_animation if spec else "none", "emphasis": spec.emphasis_animation if spec else "none"}
            entry["quiz_answer"] = sc.quiz_answer
            if sc.visualization is not None:
                entry["visualization"] = sc.visualization.model_dump()
            if spec and spec.transition_config:  # kind only: the overlap length is global so cue timing stays exact
                entry["transition"] = spec.transition_config.kind
            if sc.type == "diagram" and sc.mermaid:
                (pub / f"{sc.scene_id}.svg").write_text(mermaid_lite.to_svg(sc.mermaid))
                entry["svg"] = f"{sc.scene_id}.svg"
                if not sc.mode3d:
                    entry["layout"] = mermaid_lite.layout_payload(sc.mermaid)
            if sc.mode3d:
                entry["mode3d"], entry["highlight_layer"] = sc.mode3d, sc.highlight_layer
                if sc.mode3d == "flow":
                    entry["graph3d"] = mermaid_lite.graph_3d(sc.mermaid)
            rec = scene_video.get(sc.scene_id)
            if rec:
                shutil.copy(rec, pub / f"{sc.scene_id}_rec{rec.suffix}")
                entry["recording"] = f"{sc.scene_id}_rec{rec.suffix}"
            if portrait and sc.type == "instructor" and not rec:
                shutil.copy(portrait, pub / "portrait.png")
                entry["portrait"] = "portrait.png"
            scenes.append(entry)
            cues += [subtitles.Cue(t + c["start"], t + c["end"], c["text"]) for c in tm] if tm else subtitles.scene_cues(sc.narration, t, adur)
            t += frames / FPS - TRANSITION_FRAMES / FPS
        total = sum(s["frames"] for s in scenes) - (len(scenes) - 1) * TRANSITION_FRAMES
        props = {"title": storyboard.lesson_title, "fps": FPS, "transitionFrames": TRANSITION_FRAMES, "scenes": scenes,
                 "cues": [{"start": c.start, "end": c.end, "text": c.text} for c in cues], "music": None}
        if music:
            shutil.copy(music, pub / "music.mp3")
            props["music"] = "music.mp3"
        pf = out_dir / "remotion_props.json"
        pf.write_text(json.dumps(props))
        raw = out_dir / "remotion_raw.mp4"
        proc = subprocess.Popen(["node", "scripts/render.mjs", str(pf), str(raw), str(pub), "Lesson"], cwd=eng, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False)
        err = ""
        for line in proc.stdout:  # type: ignore[union-attr]
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if ev.get("event") == "progress":
                on_progress(min(0.9, ev["value"] * 0.9))
            if should_cancel():
                proc.terminate()
                proc.wait(timeout=30)
                raise renderer.RenderCancelled("cancelled by user")
            if ev.get("event") == "error":
                err = ev.get("message", "")
        proc.wait()
        if proc.returncode != 0 or not raw.exists():
            raise renderer.RenderError(f"remotion failed: {err or proc.stderr.read()[-400:]}")
        srt = out_dir / "subtitles.srt"
        srt.write_text(subtitles.to_srt(cues))
        video = out_dir / "lesson.mp4"
        from app.security.subprocess_safe import run
        r = run(["ffmpeg", "-y", "-i", str(raw), "-i", str(srt), "-map", "0:v", "-map", "0:a", "-map", "1:0", "-c:v", "copy", "-c:a", "copy",
                 "-c:s", "mov_text", "-metadata:s:s:0", "language=eng", "-movflags", "+faststart", str(video)], timeout=600)
        if r.returncode != 0:
            raise renderer.RenderError(f"mux failed: {r.stderr[-300:]}")
        raw.unlink(missing_ok=True)
        ver = renderer.verify(video, expected=total / FPS, srt=srt)
        manifest = {"engine": "remotion", "video": video.name, "subtitles": srt.name, "scenes": [{"scene_id": s["scene_id"], "frames": s["frames"], "transition": s["transition"], "mode3d": s.get("mode3d")} for s in scenes],
                    "verification": ver, "sha256": media.sha256_file(video), "music": bool(music), "fps": FPS, "animation_warnings": anim_warnings}
        (out_dir / "render_manifest.json").write_text(json.dumps(manifest, indent=2))
        on_progress(1.0)
        return {"video": video, "srt": srt, "manifest": out_dir / "render_manifest.json", "duration": ver["duration"], "sha256": manifest["sha256"], "verification": ver}
    finally:
        shutil.rmtree(pub, ignore_errors=True)
