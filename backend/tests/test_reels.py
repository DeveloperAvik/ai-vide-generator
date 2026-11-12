import io
import time

import pytest
from PIL import Image

from app.schemas.reel import ReelRequest
from app.services import reel_music, reels, subtitles
from tests.conftest import needs_ffmpeg


def _jpg(w=800, h=600, color=(200, 80, 40)) -> bytes:
    b = io.BytesIO()
    Image.new("RGB", (w, h), color).save(b, "JPEG")
    return b.getvalue()


def test_request_validation():
    with pytest.raises(ValueError):
        ReelRequest(topic="ok topic", style="bogus")
    with pytest.raises(ValueError):
        ReelRequest(topic="ok topic", duration_s=200)
    assert ReelRequest(topic="  lofi   study  ", style="LoFi").topic == "lofi study"


def test_scene_count_covers_photos():
    assert reels.scene_count(30, 0) == 6
    assert reels.scene_count(15, 9) == 9
    assert reels.scene_count(90, 0) == 12


def test_mock_plan_is_flagged_simulated():
    plan, simulated = reels.plan_reel(ReelRequest(topic="how rockets work", style="educational", duration_s=30), 2)
    assert simulated and len(plan.scenes) == 6
    assert all(0 <= (s.photo_index or 0) < 2 for s in plan.scenes)


def test_word_cues_cover_sentence_exactly():
    out = reels.word_cues([subtitles.Cue(1.0, 4.0, "one two three four five six seven")])
    assert out[0].start == 1.0 and abs(out[-1].end - 4.0) < 1e-6 and all(len(c.text.split()) <= 4 for c in out)


def test_ingest_rejects_garbage_and_tiny(tmp_path):
    with pytest.raises(reels.ReelError):
        reels.ingest_photo(b"not an image", tmp_path / "a.jpg")
    with pytest.raises(reels.ReelError):
        reels.ingest_photo(_jpg(50, 50), tmp_path / "b.jpg")
    reels.ingest_photo(_jpg(), tmp_path / "ok.jpg")


def test_reel_id_blocks_traversal():
    with pytest.raises(reels.ReelError):
        reels.reel_dir("../../etc")


@needs_ffmpeg
def test_music_loop_generates(tmp_path):
    p = reel_music.synthesize("lofi", 2, tmp_path / "m.wav")
    from app.utils import media
    assert 5 < media.duration(p) < 7


class _FakeVoice:
    """Silent 'speech' of 0.4 s per word: exercises the narration path without needing a TTS model."""
    name, paid, label = "fake", False, "fake"

    def generate_audio(self, text, out_wav):
        import wave
        with wave.open(str(out_wav), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(48000)
            w.writeframes(b"\x00\x00" * int(48000 * 0.4 * len(text.split())))
        return out_wav


@needs_ffmpeg
@pytest.mark.parametrize("photos", [0, 2])
def test_render_end_to_end(tmp_path, photos):
    req = ReelRequest(topic="why the sky is blue", style="lofi", duration_s=10)
    plan, _ = reels.plan_reel(req, photos)
    plan.scenes = plan.scenes[:3]
    paths = []
    for i in range(photos):
        paths.append(reels.ingest_photo(_jpg(color=(40 * i + 60, 100, 160)), tmp_path / f"p{i}.jpg"))
    res = reels.render_reel(req, plan, paths, tmp_path / "out", voice=_FakeVoice())
    assert res["voiceover"] and res["music"] == "lofi" and res["duration"] > 4
    assert (tmp_path / "out" / "reel.mp4").stat().st_size > 10_000
    assert (tmp_path / "out" / "caption.txt").read_text().count("#") >= 2


@needs_ffmpeg
def test_api_flow_and_no_voice_fallback(client, auth_headers, monkeypatch):
    from app.providers import voice as vm
    monkeypatch.setattr(vm, "get_voice", lambda *a, **k: (_ for _ in ()).throw(vm.VoiceUnavailable("none installed")))
    assert client.post("/api/reels", data={"topic": "x"}).status_code == 401
    r = client.post("/api/reels", headers=auth_headers, data={"topic": "3 tips for better sleep", "style": "lofi", "duration_s": 10},
                    files=[("photos", ("a.jpg", _jpg(), "image/jpeg"))])
    assert r.status_code == 202, r.text
    rid = r.json()["id"]
    for _ in range(120):
        st = client.get(f"/api/reels/{rid}", headers=auth_headers).json()
        if st["status"] in ("done", "error"):
            break
        time.sleep(1)
    assert st["status"] == "done", st
    assert st["result"]["voiceover"] is False and any("no narration" in w for w in st["result"]["warnings"])
    v = client.get(f"/api/reels/{rid}/video", headers=auth_headers)
    assert v.status_code == 200 and v.headers["content-type"] == "video/mp4"
    bad = client.post("/api/reels", headers=auth_headers, data={"topic": "bad photo"}, files=[("photos", ("a.jpg", b"nope", "image/jpeg"))])
    assert bad.status_code == 422
    assert client.get("/api/reels/zzzz", headers=auth_headers).status_code == 404
