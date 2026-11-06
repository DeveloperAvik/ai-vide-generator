from pathlib import Path

from app.models import (Course, GeneratedAsset, Lesson, LessonScript, LessonStatus as S, ResearchSource, Storyboard, Thumbnail, VideoRender,
                        WorkflowLog, YouTubePublication)
from app.providers.llm import LLMProvider
from app.services import domains, generation
from app.services.storage import get_storage
from tests.helpers import make_lesson


def _render(db, lesson, status="done", published=False):
    st = get_storage()
    d = st.lesson_dir(lesson.id, f"render_{lesson.id}")
    for n in ("v.mp4", "s.srt", "m.json"):
        (d / n).write_bytes(b"x")
    r = VideoRender(lesson_id=lesson.id, status=status, video_path=st.rel(d / "v.mp4"), srt_path=st.rel(d / "s.srt"), manifest_path=st.rel(d / "m.json"))
    db.add(r)
    db.flush()
    if published:
        db.add(YouTubePublication(lesson_id=lesson.id, render_id=r.id, youtube_video_id="abc123", status="published"))
    db.commit()
    return r


def test_delete_lesson_removes_rows_and_files(client, auth_headers, db):
    l = make_lesson(db)
    lid = l.id
    r = _render(db, l)
    db.add(GeneratedAsset(lesson_id=lid, scene_id="s", kind="png", path="x", content_hash="h"))
    db.add(Thumbnail(lesson_id=lid, path="t.jpg"))
    db.add(WorkflowLog(lesson_id=lid, stage="x", message="m"))
    db.commit()
    root = get_storage().path("lessons", str(lid))
    assert root.exists()
    resp = client.delete(f"/api/lessons/{lid}", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    db.expire_all()
    assert db.get(Lesson, lid) is None and not root.exists()
    for model in (LessonScript, Storyboard, ResearchSource, VideoRender, GeneratedAsset, Thumbnail):
        assert db.query(model).filter_by(lesson_id=lid).count() == 0, model
    kept = db.query(WorkflowLog).filter(WorkflowLog.lesson_id.is_(None)).all()  # audit trail survives, detached
    assert any("lesson.delete" in w.message for w in kept)
    assert client.delete(f"/api/lessons/{lid}", headers=auth_headers).status_code == 404


def test_delete_lesson_needs_auth(client, db):
    l = make_lesson(db)
    assert client.delete(f"/api/lessons/{l.id}").status_code in (401, 403)


def test_delete_blocked_while_working_and_force_overrides(client, auth_headers, db):
    l = make_lesson(db)
    l.status = S.RENDERING
    db.add(WorkflowLog(lesson_id=l.id, stage="render", message="started"))
    db.commit()
    assert client.delete(f"/api/lessons/{l.id}", headers=auth_headers).status_code == 409
    assert db.get(Lesson, l.id) is not None
    assert client.delete(f"/api/lessons/{l.id}?force=true", headers=auth_headers).status_code == 200


def test_published_lesson_requires_force(client, auth_headers, db):
    l = make_lesson(db)
    _render(db, l, published=True)
    r = client.delete(f"/api/lessons/{l.id}", headers=auth_headers)
    assert r.status_code == 409 and "YouTube" in r.json()["detail"]
    assert client.delete(f"/api/lessons/{l.id}?force=true", headers=auth_headers).status_code == 200


def test_delete_render_removes_files_and_resets_lesson(client, auth_headers, db):
    l = make_lesson(db)
    l.status = S.APPROVAL_PENDING
    r = _render(db, l)
    paths = [get_storage().path(*Path(p).parts) for p in (r.video_path, r.srt_path, r.manifest_path)]
    rid = r.id
    assert client.delete(f"/api/renders/{rid}", headers=auth_headers).status_code == 200
    db.expire_all()
    assert db.get(VideoRender, rid) is None and not any(p.exists() for p in paths)
    assert db.get(Lesson, l.id).status == S.ASSETS_READY  # can be re-rendered


def test_delete_running_render_refused(client, auth_headers, db):
    l = make_lesson(db)
    r = _render(db, l, status="running")
    assert client.delete(f"/api/renders/{r.id}", headers=auth_headers).status_code == 409


def test_delete_course_removes_everything(client, auth_headers, db):
    l = make_lesson(db)
    cid = l.module.course_id
    lid = l.id
    assert client.delete(f"/api/courses/{cid}", headers=auth_headers).status_code == 200
    db.expire_all()
    assert db.get(Course, cid) is None and db.get(Lesson, lid) is None
    assert client.delete(f"/api/courses/{cid}", headers=auth_headers).status_code == 404


def test_course_delete_is_all_or_nothing(client, auth_headers, db):
    l = make_lesson(db)
    l.status = S.ASSETS_GENERATING
    db.add(WorkflowLog(lesson_id=l.id, stage="assets", message="started"))
    db.commit()
    cid = l.module.course_id
    assert client.delete(f"/api/courses/{cid}", headers=auth_headers).status_code == 409
    assert db.get(Course, cid) is not None


# ---------------- domains
def test_domains_listed_and_course_stores_domain(client, auth_headers, db):
    keys = {d["key"] for d in client.get("/api/domains", headers=auth_headers).json()}
    assert {"cybersecurity", "red_team", "exploit_dev", "soc", "ai_ml", "programming", "general"} <= keys
    r = client.post("/api/courses/generate", json={"course_name": "Intro to Transformers", "domain": "ai_ml"}, headers=auth_headers)
    assert r.status_code == 200 and r.json()["domain"] == "ai_ml"
    assert all(l.category == "ai_ml" for l in db.query(Lesson))


def test_unknown_domain_falls_back_to_general():
    assert domains.get("nonsense").key == "general" and domains.get(None).key == "general"


class _Capture(LLMProvider):
    name = "capture"

    def __init__(self):
        self.systems = []

    def complete(self, system, prompt, max_tokens=8000):
        self.systems.append(system)
        raise RuntimeError("stop")


def test_domain_rules_reach_the_system_prompt(db):
    llm = _Capture()
    from app.schemas.content import CurriculumRequest, Curriculum
    for dom, needle in (("ai_ml", "machine-learning"), ("red_team", "weaponized"), ("programming", "runnable")):
        try:
            generation.generate_curriculum(db, CurriculumRequest(course_name=f"Course {dom}", domain=dom), llm)
        except Exception:
            pass
        assert needle in llm.systems[-1], dom
    assert "cybersecurity" not in llm.systems[0].lower().replace("subject domain", "")  # base prompt is topic-neutral


def test_idle_researching_lesson_can_be_deleted_without_force(client, auth_headers, db):
    """RESEARCHING is where a lesson waits after research finished or after its script was rejected: nothing is running."""
    l = make_lesson(db)
    l.status = S.RESEARCHING
    db.add_all([WorkflowLog(lesson_id=l.id, stage="research", message="started"), WorkflowLog(lesson_id=l.id, stage="research", message="completed"),
                WorkflowLog(lesson_id=l.id, stage="script_approval", message="REJECTED")])
    db.commit()
    assert client.delete(f"/api/lessons/{l.id}", headers=auth_headers).status_code == 200


def test_a_stage_that_started_long_ago_is_a_crash_leftover_not_a_running_job(client, auth_headers, db):
    from datetime import datetime, timedelta, timezone
    l = make_lesson(db)
    l.status = S.RESEARCHING
    db.add(WorkflowLog(lesson_id=l.id, stage="research", message="started", created_at=datetime.now(timezone.utc) - timedelta(hours=3)))
    db.commit()
    assert client.delete(f"/api/lessons/{l.id}", headers=auth_headers).status_code == 200
