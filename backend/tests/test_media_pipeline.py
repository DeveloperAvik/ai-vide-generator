"""End-to-end media tests; need ffmpeg and a local TTS (macOS say or Piper)."""
import json

import pytest

from app.models import LessonStatus as S
from app.providers.llm import get_llm
from app.providers.voice import MacSayVoice, PiperVoice, ElevenLabsVoice, VoiceUnavailable, get_voice
from app.schemas.content import CurriculumRequest, StoryboardData
from app.providers.mock_llm import _storyboard
from app.services import generation, pipeline, subtitles, visuals
from app.services.storage import get_storage
from tests.conftest import needs_ffmpeg, needs_say


def test_paid_voice_disabled_without_credentials():
    ok, why = ElevenLabsVoice().available()
    assert not ok and "not configured" in why
    with pytest.raises(VoiceUnavailable):
        ElevenLabsVoice().generate_audio("hi", __import__("pathlib").Path("/tmp/x.wav"))


def test_piper_reports_missing_not_fake():
    p = PiperVoice()
    p.binary = "definitely-not-installed"
    assert p.available()[0] is False


def test_heygen_not_faked():
    from app.providers.avatar import HeyGenAvatar, AvatarUnavailable
    with pytest.raises(AvatarUnavailable):
        HeyGenAvatar().get_generation_status("x")


def test_srt_roundtrip_and_timing():
    cues = subtitles.scene_cues("First sentence here. Second sentence follows.", 10.0, 6.0)
    assert cues[0].start == 10.0 and abs(cues[-1].end - 16.0) < 1e-6
    again = subtitles.parse_srt(subtitles.to_srt(cues))
    assert len(again) == len(cues) and again[0].text == cues[0].text
    assert subtitles.ts(3661.5) == "01:01:01,500"


def test_mermaid_svg_and_slides(tmp_path):
    from app.services import mermaid_lite
    sb = StoryboardData.model_validate(_storyboard("T", 1))
    svg = mermaid_lite.to_svg(next(s.mermaid for s in sb.scenes if s.mermaid))
    assert svg.startswith("<svg") and "Parameterized?" in svg
    with pytest.raises(ValueError):
        mermaid_lite.parse("sequenceDiagram\n A->>B: hi")
    for i, s in enumerate(sb.scenes, 1):
        out = visuals.render_scene_png(s, sb.lesson_title, tmp_path / f"{i}.png", i, len(sb.scenes))
        assert out.stat().st_size > 5000
    th = visuals.render_thumbnail("SQL Injection Fundamentals", "Studio", tmp_path / "t.jpg")
    from PIL import Image
    assert Image.open(th).size == (1280, 720)


@needs_ffmpeg
@needs_say
def test_voice_generation_and_validation(tmp_path):
    v = get_voice()
    wav = v.generate_audio("This is a short narration test for the studio.", tmp_path / "a.wav")
    assert v.validate_audio(wav) == [] and v.get_audio_duration(wav) > 1.0
    assert v.validate_audio(tmp_path / "missing.wav")


@needs_ffmpeg
@needs_say
def test_full_pipeline_gates_resume_and_upload_refusal(db):
    course = generation.generate_curriculum(db, CurriculumRequest(course_name="Pipeline Test Course"), get_llm("mock"))
    db.commit()
    lesson = course.modules[1].lessons[0]
    pipeline.resume(db, lesson, llm=get_llm("mock"), online=False)
    assert lesson.status == S.TECHNICAL_REVIEW  # stops at human gate
    pipeline.resume(db, lesson)  # gate: no-op
    assert lesson.status == S.TECHNICAL_REVIEW

    # upload must be refused before approval
    from app.services import youtube
    with pytest.raises(youtube.NotApproved):
        youtube.upload(db, lesson, {}, 0)

    pipeline.approve_script(db, lesson, None)
    # inject a failure in rendering, then resume from last good stage
    from app.services import renderer
    real = renderer.render_long
    calls = {"n": 0}

    def flaky(**kw):
        calls["n"] += 1
        if calls["n"] == 1:
            raise renderer.RenderError("simulated crash")
        return real(**kw)

    renderer.render_long = flaky
    try:
        with pytest.raises(renderer.RenderError):
            pipeline.resume(db, lesson, llm=get_llm("mock"))
        db.refresh(lesson)
        assert lesson.status == S.FAILED and lesson.last_good_status == "ASSETS_READY" and lesson.retry_count == 1
        pipeline.resume(db, lesson)  # resumes at render, NOT at assets
    finally:
        renderer.render_long = real
    assert lesson.status == S.APPROVAL_PENDING
    from app.models import VideoRender, VoiceGeneration
    r = db.query(VideoRender).filter_by(lesson_id=lesson.id, status="done").one()
    st = get_storage()
    assert st.path(r.video_path).stat().st_size > 10000 and st.path(r.srt_path).read_text().startswith("1\n")
    man = json.loads(st.path(r.manifest_path).read_text())
    assert man["verification"]["ok"] and man["verification"]["resolution"] == "1920x1080"
    assert db.query(VoiceGeneration).filter_by(lesson_id=lesson.id).count() == len(StoryboardData.model_validate(generation.latest_storyboard(db, lesson).data).scenes)

    with pytest.raises(youtube.NotApproved):
        youtube.upload(db, lesson, {}, 0)  # still not approved by a human
    pipeline.decide_video(db, lesson, None, "APPROVED")
    with pytest.raises(youtube.YouTubeNotConfigured):  # approved, but no OAuth credentials -> honest error, no fake upload
        youtube.upload(db, lesson, generation.generate_metadata(lesson, StoryboardData.model_validate(generation.latest_storyboard(db, lesson).data), get_llm("mock")).model_dump(), 0)


@needs_ffmpeg
def test_verify_rejects_garbage(tmp_path):
    from app.services import renderer
    bad = tmp_path / "bad.mp4"
    bad.write_bytes(b"not a video")
    with pytest.raises(Exception):
        renderer.verify(bad, 10)


def test_retry_cap_enforced(db):
    course = generation.generate_curriculum(db, CurriculumRequest(course_name="Retry Cap Course"), get_llm("mock"))
    l = course.modules[0].lessons[0]
    l.status, l.retry_count = S.FAILED, 3
    db.commit()
    with pytest.raises(pipeline.StageError):
        pipeline.resume(db, l)


def test_youtube_body_defaults_private_and_schedule():
    from app.services import youtube
    from datetime import datetime, timezone
    meta = {"titles": ["a", "b", "c"], "description": "d", "chapters": [("0:00", "x")], "tags": ["t"], "disclaimer": "edu", "category_id": "27"}
    b = youtube.build_body(meta, 0, "private", None)
    assert b["status"]["privacyStatus"] == "private" and "publishAt" not in b["status"] and b["snippet"]["categoryId"] == "27"
    b2 = youtube.build_body(meta, 0, "public", datetime(2030, 1, 1, tzinfo=timezone.utc))
    assert b2["status"]["privacyStatus"] == "private" and b2["status"]["publishAt"] == "2030-01-01T00:00:00Z"


def test_workflows_importable_shape():
    import glob, pathlib
    root = pathlib.Path(__file__).resolve().parents[2] / "automation" / "workflows"
    files = sorted(root.glob("*.json"))
    assert len(files) == 13
    for f in files:
        d = json.loads(f.read_text())
        assert d["nodes"] and d["connections"]
        txt = f.read_text()
        assert "sk-ant" not in txt and "Bearer " in txt and "$env.STUDIO_SERVICE_TOKEN" in txt or "scheduleTrigger" in txt


def test_mermaid_semicolons_headers_and_chains():
    from app.services import mermaid_lite
    g = mermaid_lite.parse("flowchart LR; A[Input] --> B[App] --> C[Server]; C -- reflects --> A")
    assert len(g.nodes) == 3 and len(g.edges) == 3 and g.edges[2][2] == "reflects"
    assert mermaid_lite.to_svg("graph TD; X --> Y").startswith("<svg")


def test_pronunciation_only_changes_speech_text():
    from app.services.pronunciation import for_speech
    assert for_speech("XSS and SQL injection over HTTPS") == "X S S and S Q L injection over H T T P S"
    assert for_speech("The XSSY class") == "The XSSY class"  # whole tokens only
    assert for_speech("nginx and sudo") == "engine-X and sue-doo"


def test_kokoro_reports_missing_files_instead_of_faking(monkeypatch, tmp_path):
    import sys
    import types
    from app.providers.voice import KokoroVoice
    # Stub the optional packages so the "model files missing" branch is exercised even where kokoro-onnx isn't installed.
    monkeypatch.setitem(sys.modules, "kokoro_onnx", types.ModuleType("kokoro_onnx"))
    monkeypatch.setitem(sys.modules, "soundfile", types.ModuleType("soundfile"))
    v = KokoroVoice()
    v.model, v.voices = str(tmp_path / "no.onnx"), str(tmp_path / "no.bin")
    ok, why = v.available()
    assert not ok and "missing" in why
    with pytest.raises(VoiceUnavailable):
        v.generate_audio("hi", tmp_path / "a.wav")


@needs_ffmpeg
def test_kokoro_real_synthesis_if_installed(tmp_path):
    from app.providers.voice import KokoroVoice
    v = KokoroVoice()
    if not v.available()[0]:
        pytest.skip("Kokoro not installed")
    wav = v.generate_audio("Cross-site scripting runs attacker script in the victim's browser.", tmp_path / "k.wav")
    assert v.validate_audio(wav) == [] and 2.0 < v.get_audio_duration(wav) < 12.0
    assert v.label.startswith("kokoro:")


def test_thumbnail_regenerate_endpoint_uses_custom_headline(client, auth_headers, db):
    from PIL import Image
    from app.models import Course, Lesson, Module
    from app.services.storage import get_storage
    c = Course(name="C", domain="general")
    m = Module(title="M")
    m.lessons.append(Lesson(title="Original Lesson Title", summary="s", estimated_minutes=5))
    c.modules.append(m)
    db.add(c)
    db.commit()
    lid = db.query(Lesson).first().id
    r = client.post(f"/api/lessons/{lid}/thumbnail/regenerate", json={"text": "Shorter Hook"}, headers=auth_headers)
    assert r.status_code == 200 and r.json()["text"] == "Shorter Hook"
    img = client.get(f"/api/lessons/{lid}/thumbnail", headers=auth_headers)
    assert img.status_code == 200 and img.headers["content-type"] == "image/jpeg"
    r2 = client.post(f"/api/lessons/{lid}/thumbnail/regenerate", headers=auth_headers)  # no body -> falls back to the lesson title
    assert r2.json()["text"] == "Original Lesson Title"
