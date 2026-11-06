"""Quick draft: topic -> script -> voice -> video with no research and no review, stamped UNREVIEWED DRAFT, never approvable or publishable."""
import pytest
from PIL import Image

from app.models import Approval, Course, Lesson, LessonStatus as S, Module, ReviewRun, ResearchSource, TechnicalClaim, VideoRender
from app.providers.llm import get_llm
from app.schemas.content import LessonScriptData
from app.services import generation, pipeline, qualitygate, visuals, youtube
from app.services.storage import get_storage
from tests.conftest import needs_ffmpeg, needs_say
from tests.helpers import ScriptedLLM, good_script


def _draft_lesson(db, minutes=5, title="Gradient Descent Explained"):
    c = Course(name=f"Quick: {title}", domain="ai_ml")
    m = Module(title="Quick video")
    l = Lesson(title=title, summary=title, estimated_minutes=minutes, draft=True)
    m.lessons.append(l)
    c.modules.append(m)
    db.add(c)
    db.commit()
    return l


# ---------------- script
def test_draft_script_never_keeps_citations_even_if_the_model_invents_them(db):
    l = _draft_lesson(db)
    llm = ScriptedLLM(lesson=good_script())  # the scripted "model" ignores the instruction and cites a source
    assert good_script()["references"]
    row = generation.generate_script(db, l, llm, sources=[ResearchSource(url="https://x", verified=True, kind="k", title="t", publisher="p", excerpt="e")])
    assert row.content["references"] == []
    assert any("DRAFT" in u for u in row.content["unverified_claims"])
    prompt = llm.calls[0][1]
    assert "QUICK DRAFT" in prompt and "https://x" not in prompt  # sources are not even offered to the model


def test_a_normal_lesson_script_is_unchanged(db):
    l = _draft_lesson(db)
    l.draft = False
    db.commit()
    row = generation.generate_script(db, l, ScriptedLLM(lesson=good_script()), sources=[])
    assert row.content["references"] == good_script()["references"]


# ---------------- frames
def test_draft_frames_carry_the_banner_and_normal_frames_do_not(tmp_path):
    from tests.helpers import good_storyboard
    sc = good_storyboard(8).scenes[0]
    a = Image.open(visuals.render_scene_png(sc, "T", tmp_path / "a.png", 1, 5, None, draft=True)).convert("RGB")
    b = Image.open(visuals.render_scene_png(sc, "T", tmp_path / "b.png", 1, 5, None)).convert("RGB")
    assert a.getpixel((8, 8)) == (185, 28, 28) and b.getpixel((8, 8)) != (185, 28, 28)
    t = Image.open(visuals.render_thumbnail("Topic", "Studio", tmp_path / "t.jpg", None, draft=True)).convert("RGB")
    assert t.getpixel((8, 8))[0] > 150 and t.getpixel((8, 8))[1] < 80


# ---------------- end to end (mock model, real TTS and ffmpeg)
@needs_ffmpeg
@needs_say
def test_draft_runs_to_a_video_without_research_or_review_and_cannot_be_approved_or_published(db):
    l = _draft_lesson(db)
    pipeline.resume(db, l, llm=get_llm("mock"))
    assert l.status == S.APPROVAL_PENDING
    # nothing the strict path produces
    assert db.query(ResearchSource).filter_by(lesson_id=l.id).count() == 0
    assert db.query(ReviewRun).filter_by(lesson_id=l.id).count() == 0 and db.query(TechnicalClaim).filter_by(lesson_id=l.id).count() == 0
    assert generation.latest_script(l).content["references"] == []
    # but a real, verified video
    r = db.query(VideoRender).filter_by(lesson_id=l.id, status="done").one()
    assert get_storage().path(r.video_path).stat().st_size > 10000 and r.duration_seconds > 5
    # every slide is stamped
    from app.models import GeneratedAsset
    for a in db.query(GeneratedAsset).filter_by(lesson_id=l.id, kind="slide"):
        assert Image.open(get_storage().path(a.path)).convert("RGB").getpixel((8, 8)) == (185, 28, 28)
    # a draft cannot be approved, not even by a human
    with pytest.raises(pipeline.StageError, match="UNREVIEWED DRAFT"):
        pipeline.decide_video(db, l, 1, "APPROVED")
    assert db.query(Approval).filter_by(lesson_id=l.id).count() == 0
    # its gate result can never satisfy the gate publishing needs
    assert qualitygate.latest_passed(db, l, "draft") and not qualitygate.latest_passed(db, l, "pre_tts")
    # and even a forced status + approval record does not make it publishable
    l.status = S.APPROVED
    db.add(Approval(lesson_id=l.id, stage="video", decision="APPROVED"))
    db.commit()
    assert not pipeline.is_approved(db, l)
    with pytest.raises(youtube.NotApproved):
        youtube.upload(db, l, {}, 0)


# ---------------- API
@pytest.fixture
def no_background(monkeypatch):
    from app.api import routes
    started = []
    monkeypatch.setattr(routes, "_bg", lambda fn, lid, **kw: started.append(lid))
    return started


def test_quick_video_creates_a_draft_lesson_and_starts_it(client, auth_headers, db, no_background):
    r = client.post("/api/quick-video", json={"topic": "How Transformers Work", "domain": "ai_ml", "minutes": 5}, headers=auth_headers)
    assert r.status_code == 202, r.text
    lid = r.json()["lesson_id"]
    l = db.get(Lesson, lid)
    assert l.draft and l.status == S.TOPIC_PENDING and l.title == "How Transformers Work" and l.estimated_minutes == 5
    assert l.module.course.domain == "ai_ml" and no_background == [lid]
    again = client.post("/api/quick-video", json={"topic": "How Transformers Work", "domain": "ai_ml"}, headers=auth_headers).json()
    assert db.get(Lesson, again["lesson_id"]).module.course.name.endswith("(2)")  # same topic twice is fine
    assert client.get("/api/lessons", headers=auth_headers).json()[0]["draft"] is True


def test_quick_video_validates_input(client, auth_headers, no_background):
    assert client.post("/api/quick-video", json={"topic": "x"}, headers=auth_headers).status_code == 422
    assert client.post("/api/quick-video", json={"topic": "Valid topic", "domain": "nope"}, headers=auth_headers).status_code == 422
    assert client.post("/api/quick-video", json={"topic": "Valid topic", "minutes": 99}, headers=auth_headers).status_code == 422
    assert client.post("/api/quick-video", json={"topic": "Valid topic"}).status_code in (401, 403)
    assert no_background == []


def test_drafts_are_kept_out_of_the_approval_queue(client, auth_headers, db):
    d = _draft_lesson(db)
    d.status = S.APPROVAL_PENDING
    n = Lesson(title="Normal", summary="s", status=S.APPROVAL_PENDING, module_id=d.module_id, position=1)
    db.add(n)
    db.commit()
    ids = [x["id"] for x in client.get("/api/approvals/queue", headers=auth_headers).json()]
    assert n.id in ids and d.id not in ids
    r = client.post(f"/api/lessons/{d.id}/video/decision", json={"decision": "APPROVED"}, headers=auth_headers)
    assert r.status_code == 409 and "DRAFT" in r.json()["detail"]


def test_make_official_clears_the_draft_flag_and_restarts_the_real_pipeline(client, auth_headers, db):
    d = _draft_lesson(db)
    d.status, d.last_good_status = S.APPROVAL_PENDING, S.APPROVAL_PENDING.value
    db.commit()
    r = client.post(f"/api/lessons/{d.id}/draft/promote", headers=auth_headers)
    assert r.status_code == 200 and r.json() == {"status": "TOPIC_PENDING", "draft": False}
    db.expire_all()
    assert not db.get(Lesson, d.id).draft and db.query(Approval).filter_by(lesson_id=d.id).count() == 0  # promotion approves nothing
    assert client.post(f"/api/lessons/{d.id}/draft/promote", headers=auth_headers).status_code == 409  # no longer a draft


def test_an_existing_lesson_can_be_turned_into_a_draft_but_not_a_finished_one(client, auth_headers, db, no_background):
    l = _draft_lesson(db)
    l.draft = False
    db.commit()
    assert client.post(f"/api/lessons/{l.id}/draft", headers=auth_headers).status_code == 202
    db.expire_all()
    assert db.get(Lesson, l.id).draft
    for status in (S.APPROVED, S.PUBLISHED, S.SCHEDULED):
        x = _draft_lesson(db, title=f"Done {status.value}")
        x.draft, x.status = False, status
        db.commit()
        assert client.post(f"/api/lessons/{x.id}/draft", headers=auth_headers).status_code == 409
    y = _draft_lesson(db, title="In review")
    y.draft, y.status = False, S.TECHNICAL_REVIEW
    db.commit()
    assert client.post(f"/api/lessons/{y.id}/draft", headers=auth_headers).status_code == 409


# ---------------- subject-aware sections, draft length window
def test_non_security_lessons_do_not_get_attack_and_lab_instructions():
    from app.services import lengthplan
    sec = {n: g for n, _f, g in lengthplan.sections_for(True)}
    ml = {n: g for n, _f, g in lengthplan.sections_for(False)}
    assert "attack" in sec["attack_scenarios"].lower() and "isolated lab" in sec["objectives"]
    joined = " ".join(ml.values()).lower()
    for word in ("attack", "pentest", "bug bounty", "vulnerable", "authorized", "isolated lab"):
        assert word not in joined, word
    assert [(n, f) for n, f, _ in lengthplan.sections_for(False)] == [(n, f) for n, f, _ in lengthplan.sections_for(True)]  # same names, shares and order


def test_security_lessons_keep_their_wording(db):
    from app.services import lengthplan
    assert lengthplan.sections_for(True) == lengthplan.SECTIONS


def test_draft_gets_a_wider_length_window_but_published_lessons_do_not():
    from app.services import lengthplan
    assert lengthplan.window(5) == (300, 360) and lengthplan.window(5, True) == (195, 405)
    assert lengthplan.length_check(240, 5, "real")[0] is False and lengthplan.length_check(240, 5, "real", draft=True)[0] is True
    assert lengthplan.audio_check(200, 5, "real")[0] is False and lengthplan.audio_check(200, 5, "real", draft=True)[0] is True
    assert lengthplan.length_check(60, 5, "real", draft=True)[0] is False  # still not unbounded


def test_stage_start_is_committed_so_progress_is_visible(db):
    """A long stage used to show nothing until it finished: 'started' and the working status were only flushed."""
    from app.core.db import SessionLocal
    l = _draft_lesson(db)
    seen = {}
    with pipeline.stage(db, l, "assets", S.ASSETS_GENERATING):
        other = SessionLocal()  # a second connection sees only committed data
        try:
            seen["status"] = other.get(Lesson, l.id).status
            seen["logs"] = [w.message for w in other.query(pipeline.WorkflowLog).filter_by(lesson_id=l.id, stage="assets")]
        finally:
            other.close()
    assert seen["status"] == S.ASSETS_GENERATING and seen["logs"] == ["started"]


def test_train_test_split_percentage_is_not_a_world_claim():
    from app.services.lengthplan import claim_issues
    from types import SimpleNamespace as N
    ok = N(narration="We use the split function to allocate 80% of the data for training and 20% for testing.")
    bad = N(narration="Studies show that 80% of projects fail.")
    assert claim_issues([ok]) == []
    assert claim_issues([bad])
