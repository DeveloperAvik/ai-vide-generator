"""End-to-end motion engine checks through the REAL Remotion adapter and the ffmpeg renderer.
Slow (one ~1-2 min Remotion render shared by all assertions); skipped when node/Remotion is not installed."""
import os
import subprocess
import wave
from pathlib import Path

import pytest
from PIL import Image, ImageChops, ImageStat

from app.core.config import get_settings
from app.schemas.content import StoryboardData
from app.services import renderer, visuals
from app.workers import remotion_adapter

FB = "flowchart LR\nA[In] --> B[Out]"


def sc(i, type_, text, secs=4, **kw):
    return {"scene_id": f"scene_{i:03d}", "type": type_, "duration_seconds": 3, "narration": f"Scene {i}. This is the first sentence. Here is a second one. And a third to finish.", "visual_description": text, "on_screen_text": text, **kw}


def viz(i, v):
    return sc(i, "diagram", v["kind"], mermaid=FB, visualization=v)


SCENES = [
    sc(1, "instructor", "Intro"),
    sc(2, "slide", "Slide", bullets=["one", "two", "three"], animation={"camera_movement": "push_in", "narration_sync": {"mode": "anchored"}, "animation_sequence": [{"target": "bullet.1", "at_phrase": "second one"}]}),
    sc(3, "quiz", "Quiz", bullets=["a", "b", "c", "d"], quiz_answer=2),
    sc(4, "summary", "Summary", bullets=["x", "y"]),
    sc(5, "diagram", "Flow", mermaid="flowchart LR\nA[One] --> B[Two]\nB --> C[Three]"),
    sc(6, "code", "Code", language="c", code="int main() {\n  char b[8];\n  gets(b);\n  return 0;\n}"),
    sc(7, "terminal", "Terminal", terminal_lines=["$ whoami", "root", "$ ./crash AAAA", "Segmentation fault (core dumped)"]),
    sc(8, "browser", "Browser", terminal_lines=["http://lab.local/login", "Username field", "Password field", "[Submit] button"]),
    viz(9, {"kind": "buffer_overflow", "buffer_size": 32, "input_length": 48, "stack_canary": True}),
    viz(10, {"kind": "stack_frames", "frames": [{"function": "main", "locals": [{"name": "x", "size": 4}]}, {"function": "f", "locals": [{"name": "buf", "size": 16}]}]}),
    viz(11, {"kind": "heap", "ops": [{"op": "malloc", "chunk": "A", "size": 24}, {"op": "free", "chunk": "A"}, {"op": "malloc", "chunk": "B", "size": 24}]}),
    viz(12, {"kind": "assembly", "registers": ["rax", "rip"], "instructions": [{"addr": "0x1000", "text": "mov rax, 0x1"}, {"addr": "0x1007", "text": "inc rax"}], "steps": [{"line": 0, "set": [{"reg": "rax", "value": "0x1"}]}, {"line": 1, "set": [{"reg": "rax", "value": "0x2"}]}]}),
    viz(13, {"kind": "control_flow", "blocks": [{"id": "a", "lines": ["cmp rax, 1"]}, {"id": "b", "lines": ["ret"]}, {"id": "c", "lines": ["jmp a"]}], "edges": [{"a": "a", "b": "b", "label": "eq"}, {"a": "a", "b": "c"}, {"a": "c", "b": "a"}], "path": ["a", "c", "a", "b"]}),
    viz(14, {"kind": "packet_flow", "nodes": [{"id": "c", "label": "Client"}, {"id": "s", "label": "Server"}], "packets": [{"src": "c", "dst": "s", "label": "SYN"}, {"src": "s", "dst": "c", "label": "SYN-ACK"}]}),
    viz(15, {"kind": "lifecycle", "stages": [{"label": "Load", "detail": "loader maps it"}, {"label": "Run", "detail": "entry point executes"}]}),
    viz(16, {"kind": "layout", "format": "pe", "regions": [{"name": "DOS header"}, {"name": ".text", "flags": "R-X", "note": "code"}]}),
]


def remotion_ready() -> tuple[bool, str]:
    """Remotion installed AND its Chrome Headless Shell present. Rendering needs that browser, which Remotion downloads on first
    use (network, slow, can hang offline), so a fresh checkout skips these tests. Opt in: REMOTION_RENDER_TESTS=1 pytest tests/test_motion_render.py"""
    ok, why = remotion_adapter.available()
    if not ok:
        return False, f"Remotion unavailable: {why}"
    chrome = get_settings().video_engine_dir / "node_modules" / ".remotion" / "chrome-headless-shell"
    have = chrome.is_dir() and any(p.is_file() and p.name.startswith("chrome-headless-shell") and not p.suffix and os.access(p, os.X_OK) for p in chrome.rglob("*"))
    if not (have or os.environ.get("REMOTION_RENDER_TESTS") == "1"):
        return False, "Chrome Headless Shell not downloaded yet; set REMOTION_RENDER_TESTS=1 to download it and run this slow test"
    return True, "ok"


def silent_wav(path: Path, secs: float):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(48000)
        w.writeframes(b"\x00\x00" * int(48000 * secs))


def frame(video: Path, t: float, out: Path) -> Image.Image:
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.2f}", "-i", str(video), "-frames:v", "1", str(out)], check=True)
    return Image.open(out).convert("RGB")


@pytest.fixture(scope="module")
def rendered(tmp_path_factory):
    ok, why = remotion_ready()
    if not ok:
        pytest.skip(why)
    d = tmp_path_factory.mktemp("motion")
    sb = StoryboardData.model_validate({"lesson_title": "Motion test", "scenes": SCENES})
    audio = {}
    for s in sb.scenes:  # NO timing.json on purpose: exercises the estimated-timing fallback for every scene
        audio[s.scene_id] = d / f"{s.scene_id}.wav"
        silent_wav(audio[s.scene_id], 4.0)
    res = remotion_adapter.render_long(storyboard=sb, assets_dir=d, scene_audio=audio, scene_video={}, out_dir=d / "r", portrait=None, music=None)
    return sb, res, d


def test_remotion_output_passes_the_standard_verification(rendered):
    _, res, _ = rendered
    v = res["verification"]  # renderer.verify already ran inside render_long (codec, 1920x1080, 30fps, A/V drift, full decode)
    assert v["ok"] and v["resolution"] == "1920x1080" and v["fps"] == 30


def test_audio_video_sync_and_duration(rendered):
    sb, res, d = rendered
    n = len(sb.scenes)
    expect = n * round((4.0 + 0.4) * 30) / 30 - (n - 1) * remotion_adapter.TRANSITION_FRAMES / 30  # scene = audio + 0.4s, minus transition overlaps
    assert res["duration"] == pytest.approx(expect, abs=0.2)
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,duration", "-of", "csv=p=0", str(res["video"])], capture_output=True, text=True).stdout
    dur = {ln.split(",")[0]: float(ln.split(",")[1]) for ln in probe.split() if "," in ln and ln.split(",")[1] != "N/A"}
    assert abs(dur["video"] - dur["audio"]) < 0.25  # the subtitle track legitimately ends at the last cue


def test_every_scene_renders_content_and_animates(rendered):
    """Per scene: the frame is not blank, and the end of the scene differs from the start (something moved/revealed)."""
    sb, res, d = rendered
    scene_s = (4.4 * 30 - remotion_adapter.TRANSITION_FRAMES) / 30
    bad = []
    for i, s in enumerate(sb.scenes):
        t0 = i * scene_s
        a, b = frame(res["video"], t0 + 0.15, d / f"a{i}.png"), frame(res["video"], t0 + 3.2, d / f"b{i}.png")
        busy = ImageStat.Stat(b.convert("L")).stddev[0]
        moved = sum(ImageStat.Stat(ImageChops.difference(a, b)).mean)
        if busy < 8 or moved < 0.5:
            bad.append((s.scene_id, s.type, round(busy, 1), round(moved, 2)))
    assert not bad, f"blank or static scenes: {bad}"


def test_manifest_records_sync_basis_and_no_warnings(rendered):
    import json
    _, res, _ = rendered
    m = json.loads(res["manifest"].read_text())
    assert m["engine"] == "remotion" and m["animation_warnings"] == []


def test_ffmpeg_renderer_still_handles_animated_and_visualization_scenes(tmp_path):
    """Compatibility: animation/visualization metadata must be ignored (not break) by the ffmpeg engine; the mermaid fallback is drawn."""
    sb = StoryboardData.model_validate({"lesson_title": "FF", "scenes": [SCENES[1], SCENES[8]]})
    pngs, audio = {}, {}
    for i, s in enumerate(sb.scenes, 1):
        pngs[s.scene_id] = visuals.render_scene_png(s, "FF", tmp_path / f"{s.scene_id}.png", i, 2)
        audio[s.scene_id] = tmp_path / f"{s.scene_id}.wav"
        silent_wav(audio[s.scene_id], 2.0)
    res = renderer.render_long(storyboard=sb, scene_pngs=pngs, scene_audio=audio, scene_video={}, out_dir=tmp_path / "out")
    assert res["verification"]["ok"]


def test_old_storyboard_without_animation_fields_renders_in_remotion(tmp_path):
    ok, why = remotion_ready()
    if not ok:
        pytest.skip(why)
    raw = [{k: v for k, v in s.items() if k not in ("animation", "visualization", "quiz_answer")} for s in SCENES[:2]]  # exactly the pre-upgrade shape
    sb = StoryboardData.model_validate({"lesson_title": "Old", "scenes": raw})
    audio = {}
    for s in sb.scenes:
        audio[s.scene_id] = tmp_path / f"{s.scene_id}.wav"
        silent_wav(audio[s.scene_id], 2.0)
    res = remotion_adapter.render_long(storyboard=sb, assets_dir=tmp_path, scene_audio=audio, scene_video={}, out_dir=tmp_path / "r", portrait=None, music=None)
    assert res["verification"]["ok"]


def test_gallery_components_not_driven_by_scenes_render(tmp_path):
    """StaggeredText, HighlightedKeywords, KineticTypography, LowerThird, AnimatedArchitecture/Network/ProcessFlow/Timeline and
    SyntaxHighlightedCode have no storyboard data source yet; the QA `Gallery` composition renders each so they are still exercised."""
    ok, why = remotion_ready()
    if not ok:
        pytest.skip(why)
    eng = remotion_adapter.get_settings().video_engine_dir
    props, pub = tmp_path / "p.json", tmp_path / "pub"
    props.write_text("{}"), pub.mkdir()
    secs = [50, 110, 170, 230, 290]  # last frame area of each 60-frame section
    r = subprocess.run(["node", "scripts/still.mjs", str(props), str(pub), str(tmp_path / "g"), *map(str, secs)], cwd=eng, env={**__import__("os").environ, "COMP": "Gallery"}, capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stderr[-500:]
    for f in secs:
        img = Image.open(tmp_path / "g" / f"frame_{f:05d}.png").convert("L")
        assert img.size == (1920, 1080) and ImageStat.Stat(img).stddev[0] > 8, f"gallery frame {f} is blank"
