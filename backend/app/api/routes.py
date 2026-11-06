import json
import shutil
import threading
from datetime import datetime, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import SessionLocal, get_db
from app.models import (Approval, Course, GeneratedAsset, Lesson, LessonScript, LessonStatus as S, Module, QualityCheck, QualityGateResult, ResearchSource,
                        ReviewFinding, ReviewRun, TechnicalClaim,
                        Thumbnail, User, VideoRender, WorkflowLog, YouTubePublication, Analytics)
from app.providers import avatar as avatar_mod, voice as voice_mod
from app.providers.llm import LLMError, get_llm
from app.schemas import api as A
from app.schemas.content import CurriculumRequest, LessonScriptData, StoryboardData
from app.security import auth, redaction
from app.security.paths import safe_name
from app.services import claims as claims_mod, deletion, domains, generation, pipeline, qualitygate, research, techreview, youtube
from app.services.storage import get_storage

router = APIRouter(prefix="/api")
protected = APIRouter(dependencies=[Depends(auth.current_user)])


def audit(db: Session, user: User, action: str, lesson_id: int | None = None):
    pipeline.log(db, db.get(Lesson, lesson_id) if lesson_id else None, "audit", action, actor=f"user:{user.id}")


# ---------- auth / health ----------
@router.post("/auth/login", response_model=A.TokenOut)
def login(body: A.LoginIn, db: Session = Depends(get_db)):
    u = db.query(User).filter(func.lower(User.email) == body.email.lower()).first()
    ok = auth.verify_password(body.password, u.password_hash if u else auth.DUMMY_HASH)  # constant work whether or not the user exists
    if not u or not ok or not u.is_active:
        raise HTTPException(401, "Invalid credentials")
    return A.TokenOut(access_token=auth.create_token(u))


@router.get("/health")
def health(db: Session = Depends(get_db)):
    import shutil as sh
    try:
        db.execute(text("select 1"))
        dbok = True
    except Exception:  # noqa: BLE001
        dbok = False
    return {"status": "ok" if dbok else "degraded", "database": dbok, "ffmpeg": bool(sh.which("ffmpeg")), "ffprobe": bool(sh.which("ffprobe")),
            "llm_provider": get_settings().llm_provider}


@protected.get("/system/providers")
def providers():
    return {"voice": voice_mod.voice_status(), "avatar": avatar_mod.avatar_status(), "youtube": youtube.status(),
            "llm": {"configured": get_settings().llm_provider, "anthropic_key_set": bool(get_settings().anthropic_api_key),
                    "note": "Claude Pro is not an API key. Manual mode: paste JSON via /lessons/{id}/script/import."}}


# ---------- AI / voice configuration ----------
class AIConfigIn(BaseModel):
    llm_provider: str | None = Field(None, pattern="^(mock|ollama|anthropic)$")
    llm_fallback_provider: str | None = Field(None, pattern="^(|ollama|anthropic)$")
    anthropic_api_key: str | None = Field(None, max_length=300)
    anthropic_model: str | None = Field(None, max_length=100)
    ollama_url: str | None = Field(None, pattern=r"^https?://[\w.\-:]+$")
    ollama_model: str | None = Field(None, max_length=100)
    voice_provider: str | None = Field(None, pattern="^(auto|kokoro|piper|macos_say|elevenlabs)$")
    piper_model: str | None = Field(None, max_length=500)


def _ai_config_view():
    s = get_settings()
    return {"app_env": s.app_env, "llm_provider": s.llm_provider, "llm_fallback_provider": s.llm_fallback_provider,
            "anthropic_model": s.anthropic_model, "anthropic_key_set": bool(s.anthropic_api_key),
            "ollama_url": s.ollama_url, "ollama_model": s.ollama_model, "voice_provider": s.voice_provider, "piper_model": s.piper_model}


@protected.get("/system/ai-config")
def ai_config(user: User = Depends(auth.require_admin)):
    return _ai_config_view()  # never returns the API key itself


@protected.put("/system/ai-config")
def set_ai_config(body: AIConfigIn, db: Session = Depends(get_db), user: User = Depends(auth.require_admin)):
    from app.core.config import save_runtime
    upd = {k: v for k, v in body.model_dump().items() if v is not None}
    if upd.get("llm_provider") == "mock" and get_settings().app_env == "production":
        raise HTTPException(422, "mock provider is disabled in production")
    save_runtime(upd)
    audit(db, user, "ai-config.update " + ",".join(k for k in upd if "key" not in k) + (" anthropic_api_key=***" if "anthropic_api_key" in upd else ""))
    db.commit()
    return _ai_config_view()


@protected.post("/system/ai-config/test")
def test_ai_config(provider: str | None = None, user: User = Depends(auth.require_admin)):
    """Makes one tiny real call to the selected provider and reports success or the exact error."""
    try:
        llm = get_llm(provider)
        out = llm.complete_json("Reply with the JSON object {\"ok\": true}.", "ping", max_tokens=50, schema={"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"]}) \
            if llm.name != "mock" else {"ok": True}
        return {"provider": llm.name, "ok": bool(out.get("ok")), "note": "mock is offline template output" if llm.name == "mock" else ""}
    except LLMError as e:
        raise HTTPException(502, str(e))


class PreviewIn(BaseModel):
    text: str = Field("Welcome to the lesson. Today we look at how injection flaws work and how to defend against them.", max_length=400)
    provider: str | None = Field(None, pattern="^(kokoro|piper|macos_say|elevenlabs)$")


@protected.post("/system/voice/preview")
def voice_preview(body: PreviewIn, user: User = Depends(auth.current_user)):
    import tempfile
    from pathlib import Path as P
    from fastapi.responses import Response
    try:
        v = voice_mod.get_voice(body.provider)
        with tempfile.TemporaryDirectory() as td:
            out = P(td) / "p.wav"
            v.generate_audio(body.text, out)
            data = out.read_bytes()
    except (voice_mod.VoiceUnavailable, Exception) as e:  # noqa: BLE001
        raise HTTPException(409, f"voice preview failed: {e}")
    return Response(data, media_type="audio/wav", headers={"X-Voice-Provider": v.name})


# ---------- dashboard ----------
@protected.get("/dashboard")
def dashboard(db: Session = Depends(get_db)):
    c = lambda s: db.query(Lesson).filter(Lesson.status == s).count()  # noqa: E731
    now_ = datetime.now().astimezone()
    week_start = (now_ - timedelta(days=now_.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    done = db.query(VideoRender).filter(VideoRender.status == "done").count()
    return {"courses": db.query(Course).count(), "lessons": db.query(Lesson).count(), "videos_generated": done,
            "pending_approval": c(S.APPROVAL_PENDING), "published": c(S.PUBLISHED), "failed": c(S.FAILED),
            "failed_renders": db.query(VideoRender).filter(VideoRender.status == "failed").count(),
            "weekly_target": 3, "weekly_done": db.query(VideoRender).filter(VideoRender.status == "done", VideoRender.created_at >= week_start).count()}


# ---------- courses ----------
@protected.post("/courses/generate", response_model=A.CourseDetail)
def create_course(req: CurriculumRequest, db: Session = Depends(get_db), user: User = Depends(auth.current_user)):
    try:
        course = generation.generate_curriculum(db, req, get_llm())
    except ValueError as e:
        raise HTTPException(409, str(e))
    except LLMError as e:
        raise HTTPException(502, str(e))
    audit(db, user, f"course.generate {course.name}")
    db.commit()
    return course


@protected.get("/domains")
def list_domains():
    return [{"key": d.key, "label": d.label, "audience": d.audience} for d in domains.DOMAINS.values()]


@protected.get("/courses", response_model=list[A.CourseOut])
def list_courses(db: Session = Depends(get_db)):
    return db.query(Course).order_by(Course.id.desc()).all()


@protected.get("/courses/{cid}", response_model=A.CourseDetail)
def get_course(cid: int, db: Session = Depends(get_db)):
    c = db.get(Course, cid)
    if not c:
        raise HTTPException(404)
    return c


@protected.delete("/courses/{cid}")
def delete_course(cid: int, force: bool = False, db: Session = Depends(get_db), user: User = Depends(auth.require_admin)):
    """Deletes the course with all modules, lessons, renders and files. Does not touch YouTube."""
    c = db.get(Course, cid)
    if not c:
        raise HTTPException(404)
    name = c.name
    try:
        n = deletion.delete_course(db, c, force)
    except deletion.DeleteBlocked as e:
        db.rollback()
        raise HTTPException(409, str(e))
    audit(db, user, f"course.delete {name} ({n} lessons)")
    db.commit()
    return {"deleted": cid, "lessons": n}


@protected.delete("/lessons/{lid}")
def delete_lesson(lid: int, force: bool = False, db: Session = Depends(get_db), user: User = Depends(auth.current_user)):
    """Deletes the lesson with its script, assets, renders and files. Does not touch YouTube."""
    l = _lesson(db, lid)
    title = l.title
    try:
        deletion.delete_lessons(db, [l], force)
    except deletion.DeleteBlocked as e:
        db.rollback()
        raise HTTPException(409, str(e))
    audit(db, user, f"lesson.delete {title} (#{lid})")
    db.commit()
    return {"deleted": lid}


# ---------- quick draft videos ----------
@protected.post("/quick-video", status_code=202)
def quick_video(body: A.QuickVideoIn, db: Session = Depends(get_db), user: User = Depends(auth.current_user)):
    """One topic in, one UNREVIEWED DRAFT video out: no source research, no fact-check review. Creates a one-lesson course and starts it."""
    if body.domain not in domains.DOMAINS:
        raise HTTPException(422, f"unknown subject area '{body.domain}'")
    name, n = f"Quick: {body.topic.strip()}"[:240], 1
    while db.query(Course).filter(Course.name == name).first():
        n += 1
        name = f"Quick: {body.topic.strip()}"[:230] + f" ({n})"
    d = domains.get(body.domain)
    course = Course(name=name, description="Quick draft video (not fact-checked)", language="English", difficulty="Intermediate", domain=body.domain,
                    target_audience=d.audience, videos_per_week=1, duration_minutes=body.minutes)
    lesson = Lesson(position=0, title=body.topic.strip(), summary=body.topic.strip(), estimated_minutes=body.minutes, category=body.domain, draft=True)
    mod = Module(position=0, title="Quick video")
    mod.lessons.append(lesson)
    course.modules.append(mod)
    db.add(course)
    db.flush()
    pipeline.log(db, lesson, "draft", "quick draft started: no source research and no fact-check review; every frame is stamped UNREVIEWED DRAFT")
    audit(db, user, f"quick-video {name}", lesson.id)
    db.commit()
    _bg(lambda d_, ls, **k: pipeline.resume(d_, ls), lesson.id)
    return {"course_id": course.id, "lesson_id": lesson.id, "draft": True}


@protected.post("/lessons/{lid}/draft", status_code=202)
def start_draft(lid: int, db: Session = Depends(get_db), user: User = Depends(auth.current_user)):
    l = _lesson(db, lid)
    _refuse_if_running(lid)
    try:
        pipeline.start_draft(db, l)
    except pipeline.StageError as e:
        raise HTTPException(409, str(e))
    audit(db, user, "lesson.draft", lid)
    db.commit()
    _bg(lambda d, ls, **k: pipeline.resume(d, ls), lid)
    return {"status": "draft started"}


@protected.post("/lessons/{lid}/draft/promote")
def promote_draft(lid: int, db: Session = Depends(get_db), user: User = Depends(auth.current_user)):
    """'Make official': back to the start of the normal flow (research -> script -> review -> approval). Does not approve anything."""
    l = _lesson(db, lid)
    try:
        pipeline.promote_draft(db, l, user.id)
    except pipeline.StageError as e:
        raise HTTPException(409, str(e))
    return {"status": l.status.value, "draft": False}


@protected.get("/lessons", response_model=list[A.LessonOut])
def list_lessons(status: str | None = None, db: Session = Depends(get_db)):
    q = db.query(Lesson)
    if status:
        try:
            q = q.filter(Lesson.status == S(status))
        except ValueError:
            raise HTTPException(422, "bad status")
    return q.order_by(Lesson.id).all()


def _lesson(db, lid) -> Lesson:
    l = db.get(Lesson, lid)
    if not l:
        raise HTTPException(404, "lesson not found")
    return l


def _length_info(l: Lesson, sb) -> dict | None:
    if not sb:
        return None
    from app.services import lengthplan
    data = StoryboardData.model_validate(sb.data)
    return {"requested_minutes": l.estimated_minutes, "target_words": lengthplan.target_words(l.estimated_minutes), "words": lengthplan.word_count(data),
            "estimated_minutes": round(lengthplan.estimate_seconds(data) / 60, 1)}


def _source_out(s: ResearchSource) -> dict:
    return {"id": s.id, "url": s.url, "verified": s.verified, "retrieved_at": s.retrieved_at, "excerpt": s.excerpt, "title": s.title,
            "publisher": s.publisher, "category": s.category, "published_at": s.published_at, "section": s.section,
            "content_hash": s.content_hash, "status": s.status, "kind": s.kind, "identifier": s.identifier}


@protected.get("/lessons/{lid}")
def lesson_detail(lid: int, db: Session = Depends(get_db)):
    l = _lesson(db, lid)
    sc = generation.latest_script(l)
    sb = generation.latest_storyboard(db, l)
    r = db.query(VideoRender).filter_by(lesson_id=lid).order_by(VideoRender.id.desc()).first()
    qc = db.query(QualityCheck).filter_by(lesson_id=lid).order_by(QualityCheck.id.desc()).all()
    return {"lesson": A.LessonOut.model_validate(l), "script": sc.content if sc else None, "script_version": sc.version if sc else None,
            "storyboard": sb.data if sb else None, "length": _length_info(l, sb), "render": {"id": r.id, "status": r.status, "progress": r.progress, "duration": r.duration_seconds,
            "error": r.error} if r else None, "quality": [{"passed": q.passed, "report": q.report} for q in qc],
            "sources": [_source_out(s) for s in db.query(ResearchSource).filter_by(lesson_id=lid)],
            "review": qualitygate.review_state(db, l)}


# ---------- pipeline actions ----------
_RUNNING: set[int] = set()  # lessons with a live background job in THIS process (a crash leftover can never block a retry)
_RUNNING_LOCK = threading.Lock()


def _running(lid: int) -> bool:
    with _RUNNING_LOCK:
        return lid in _RUNNING


def _refuse_if_running(lid: int):
    if _running(lid):
        raise HTTPException(409, f"lesson {lid} already has a stage running; wait for it to finish (a second job would only queue behind it)")


def _bg(fn, lid: int, **kw) -> bool:
    """Start a background job unless this lesson already has one. Returns False (and starts nothing) when one is live."""
    with _RUNNING_LOCK:
        if lid in _RUNNING:
            return False
        _RUNNING.add(lid)

    def job():
        db = SessionLocal()
        try:
            fn(db, db.get(Lesson, lid), **kw)
        except Exception as e:  # noqa: BLE001 - stage() logs its own failures; this catches what happens outside a stage (e.g. retry cap)
            try:
                db.rollback()
                pipeline.log(db, db.get(Lesson, lid), "job", f"background job failed before or outside a stage: {type(e).__name__}: {e}", level="error")
                db.commit()
            except Exception:  # noqa: BLE001 - logging must never mask the job ending
                pass
        finally:
            db.close()
            with _RUNNING_LOCK:
                _RUNNING.discard(lid)
    threading.Thread(target=job, daemon=True).start()
    return True


@protected.post("/lessons/{lid}/run")
def run_lesson(lid: int, bg: BackgroundTasks, online: bool = True, db: Session = Depends(get_db), user: User = Depends(auth.current_user)):
    """Idempotent: runs from last good stage until the next human gate."""
    l = _lesson(db, lid)
    if l.status in pipeline.GATES:
        return {"status": l.status.value, "detail": "waiting at a gate; nothing to run"}
    if _running(lid):
        return {"status": "already_running", "detail": "a stage is already running for this lesson"}
    audit(db, user, "lesson.run", lid)
    db.commit()
    _bg(lambda d, ls, **k: pipeline.resume(d, ls, online=online), lid)
    return {"status": "started"}


STAGES = {"research": pipeline.run_research, "script": pipeline.run_script, "review": pipeline.run_technical_review,
          "assets": pipeline.run_assets, "render": pipeline.run_render, "quality": pipeline.run_quality}
PREREQ = {"research": {S.TOPIC_PENDING}, "script": {S.RESEARCHING}, "review": {S.SCRIPT_GENERATED},
          "assets": {S.SCRIPT_APPROVED, S.ASSETS_GENERATING}, "render": {S.ASSETS_READY, S.RENDERING}, "quality": {S.QUALITY_CHECK}}


@protected.post("/lessons/{lid}/stage/{name}", status_code=202)
def run_stage(lid: int, name: str, parts: str = "voice,avatar,visuals", db: Session = Depends(get_db), user: User = Depends(auth.current_user)):
    """Run one pipeline stage. Idempotent + ordered: refuses stages whose prerequisite status isn't met."""
    if name not in STAGES:
        raise HTTPException(404, "unknown stage")
    l = _lesson(db, lid)
    _refuse_if_running(lid)
    cur = S(l.last_good_status) if l.status == S.FAILED else l.status
    if cur not in PREREQ[name]:
        raise HTTPException(409, f"stage '{name}' needs status in {sorted(x.value for x in PREREQ[name])}, lesson is {cur.value}")
    audit(db, user, f"stage.{name}", lid)
    db.commit()
    kw = {"parts": set(parts.split(","))} if name == "assets" else {}
    _bg(lambda d, ls, **k: (setattr(ls, "status", cur), d.commit(), STAGES[name](d, ls, **kw)), lid)
    return {"accepted": name}


@protected.post("/analytics/collect")
def collect_analytics(db: Session = Depends(get_db)):
    try:
        return {"collected": youtube.collect_analytics(db)}
    except youtube.YouTubeNotConfigured as e:
        raise HTTPException(409, str(e))


@protected.post("/lessons/{lid}/retry")
def retry(lid: int, db: Session = Depends(get_db), user: User = Depends(auth.current_user)):
    l = _lesson(db, lid)
    if l.status != S.FAILED:
        raise HTTPException(409, "lesson is not FAILED")
    _refuse_if_running(lid)
    if l.retry_count >= pipeline.MAX_RETRIES:  # otherwise the job would fail silently and the dashboard would say "retrying"
        raise HTTPException(409, f"lesson {lid} used all {pipeline.MAX_RETRIES} automatic retries; an admin must reset the retry counter first")
    audit(db, user, "lesson.retry", lid)
    db.commit()
    _bg(lambda d, ls, **k: pipeline.resume(d, ls), lid)
    return {"status": "retrying", "resume_from": l.last_good_status}


@protected.post("/lessons/{lid}/reset")
def reset_retries(lid: int, db: Session = Depends(get_db), user: User = Depends(auth.require_admin)):
    l = _lesson(db, lid)
    l.retry_count, l.last_error = 0, ""
    db.commit()
    return {"ok": True}


@protected.post("/lessons/{lid}/script/import")
def import_script(lid: int, payload: dict, db: Session = Depends(get_db), user: User = Depends(auth.current_user)):
    """MODE A: paste JSON produced manually in Claude Pro. Same strict validation as API output."""
    l = _lesson(db, lid)
    try:
        data = LessonScriptData.model_validate(payload)
    except ValidationError as e:
        raise HTTPException(422, json.loads(e.json()))
    s = generation.save_script(db, l, data, f"manual:{user.email}")
    s.change_note = s.change_note or "manual import / edit"
    if l.status in (S.TOPIC_PENDING, S.RESEARCHING, S.SCRIPT_GENERATED, S.TECHNICAL_REVIEW, S.SCRIPT_APPROVED):
        pipeline.set_status(db, l, S.SCRIPT_GENERATED)  # a changed script must be re-reviewed and re-approved
    audit(db, user, f"script.import v{s.version}", lid)
    db.commit()
    return {"version": s.version}


@protected.put("/lessons/{lid}/storyboard")
def put_storyboard(lid: int, payload: dict, db: Session = Depends(get_db), user: User = Depends(auth.current_user)):
    l = _lesson(db, lid)
    try:
        sb = StoryboardData.model_validate(payload)
    except ValidationError as e:
        raise HTTPException(422, json.loads(e.json()))
    leaks = [f for s in sb.scenes for f in redaction.scan_text(pipeline._scene_text(s))]
    if leaks:
        raise HTTPException(422, {"error": "sensitive data detected", "findings": leaks[:5]})
    row = generation.save_storyboard(db, l, sb)
    audit(db, user, f"storyboard.save v{row.version}", lid)
    db.commit()
    return {"version": row.version}


@protected.post("/lessons/{lid}/storyboard/regenerate-scene/{scene_id}")
def regenerate_scene(lid: int, scene_id: str, db: Session = Depends(get_db), user: User = Depends(auth.current_user)):
    l = _lesson(db, lid)
    sb = generation.latest_storyboard(db, l)
    if not sb or scene_id not in {s["scene_id"] for s in sb.data["scenes"]}:
        raise HTTPException(404, "scene not found")
    try:
        fresh = generation.generate_storyboard(db, l, get_llm())  # regenerate whole board, keep other scenes from previous version
    except LLMError as e:
        raise HTTPException(502, str(e))
    old = {s["scene_id"]: s for s in sb.data["scenes"]}
    merged = StoryboardData.model_validate({"lesson_title": fresh.data["lesson_title"],
        "scenes": [s if s["scene_id"] == scene_id else old.get(s["scene_id"], s) for s in fresh.data["scenes"]]})
    row = generation.save_storyboard(db, l, merged)
    audit(db, user, f"scene.regenerate {scene_id}", lid)
    db.commit()
    return {"version": row.version}


@protected.post("/lessons/{lid}/storyboard/regenerate")
def regenerate_storyboard(lid: int, db: Session = Depends(get_db), user: User = Depends(auth.current_user)):
    """Rebuild the whole storyboard against the word budget for the requested length, then re-run assets/render."""
    l = _lesson(db, lid)
    base = S(l.last_good_status) if l.status == S.FAILED else l.status
    if base not in (S.SCRIPT_APPROVED, S.ASSETS_GENERATING, S.ASSETS_READY, S.QUALITY_CHECK, S.APPROVAL_PENDING):
        raise HTTPException(409, f"storyboard can be regenerated after script approval (lesson is {base.value})")
    try:
        row = generation.generate_storyboard(db, l, get_llm())
    except LLMError as e:
        raise HTTPException(502, str(e))
    l.status, l.last_good_status, l.retry_count, l.last_error = S.SCRIPT_APPROVED, S.SCRIPT_APPROVED.value, 0, ""
    audit(db, user, f"storyboard.regenerate v{row.version}", lid)
    db.commit()
    return {"version": row.version}


@protected.post("/lessons/{lid}/script/decision")
def script_decision(lid: int, body: A.ApprovalIn, db: Session = Depends(get_db), user: User = Depends(auth.require_human)):
    try:
        pipeline.approve_script(db, _lesson(db, lid), user.id, body.notes, body.decision)
    except pipeline.StageError as e:
        raise HTTPException(409, str(e))
    return {"ok": True}


@protected.post("/lessons/{lid}/video/decision")
def video_decision(lid: int, body: A.ApprovalIn, db: Session = Depends(get_db), user: User = Depends(auth.require_human)):
    try:
        pipeline.decide_video(db, _lesson(db, lid), user.id, body.decision, body.notes)
    except pipeline.StageError as e:
        raise HTTPException(409, str(e))
    return {"ok": True}


@protected.get("/approvals/queue", response_model=list[A.LessonOut])
def approval_queue(db: Session = Depends(get_db)):
    return db.query(Lesson).filter(Lesson.status.in_([S.APPROVAL_PENDING, S.TECHNICAL_REVIEW]), Lesson.draft.is_(False)).all()  # a draft cannot be approved


# ---------- renders ----------
@protected.get("/renders")
def renders(db: Session = Depends(get_db)):
    return [{"id": r.id, "lesson_id": r.lesson_id, "status": r.status, "progress": r.progress, "duration": r.duration_seconds, "error": r.error,
             "engine": r.engine} for r in db.query(VideoRender).order_by(VideoRender.id.desc()).limit(100)]


@protected.post("/renders/{rid}/cancel")
def cancel_render(rid: int, db: Session = Depends(get_db)):
    r = db.get(VideoRender, rid)
    if not r or r.status != "running":
        raise HTTPException(409, "render not running")
    r.status = "cancelling"
    db.commit()
    return {"ok": True}


@protected.delete("/renders/{rid}")
def delete_render(rid: int, force: bool = False, db: Session = Depends(get_db), user: User = Depends(auth.current_user)):
    """Deletes one rendered video (mp4, subtitles, manifest). The lesson goes back to ASSETS_READY if this was its only finished render."""
    r = db.get(VideoRender, rid)
    if not r:
        raise HTTPException(404)
    lid = r.lesson_id
    try:
        deletion.delete_render(db, r, force)
    except deletion.DeleteBlocked as e:
        db.rollback()
        raise HTTPException(409, str(e))
    audit(db, user, f"render.delete #{rid}", lid)
    db.commit()
    return {"deleted": rid}


@protected.get("/renders/{rid}/video")
def stream_video(rid: int, db: Session = Depends(get_db)):
    r = db.get(VideoRender, rid)
    if not r or not r.video_path:
        raise HTTPException(404)
    return FileResponse(get_storage().path(r.video_path), media_type="video/mp4")


@protected.get("/renders/{rid}/subtitles")
def get_srt(rid: int, db: Session = Depends(get_db)):
    r = db.get(VideoRender, rid)
    if not r or not r.srt_path:
        raise HTTPException(404)
    return FileResponse(get_storage().path(r.srt_path), media_type="text/plain")


@protected.get("/lessons/{lid}/thumbnail")
def get_thumb(lid: int, db: Session = Depends(get_db)):
    t = db.query(Thumbnail).filter_by(lesson_id=lid).order_by(Thumbnail.id.desc()).first()
    if not t:
        raise HTTPException(404)
    return FileResponse(get_storage().path(t.path), media_type="image/jpeg")


class ThumbIn(BaseModel):
    text: str | None = Field(default=None, max_length=80)  # custom headline; defaults to the lesson title


@protected.post("/lessons/{lid}/thumbnail/regenerate")
def regenerate_thumb(lid: int, body: ThumbIn | None = None, db: Session = Depends(get_db), user: User = Depends(auth.current_user)):
    """Re-render the thumbnail (e.g. with a shorter headline) without re-rendering the video."""
    from app.services import visuals
    l = _lesson(db, lid)
    sb = generation.latest_storyboard(db, l)
    headline = ((body.text if body else None) or "").strip() or (sb.data.get("lesson_title") if sb else None) or l.title
    st = get_storage()
    out = visuals.render_thumbnail(headline, domains.of_lesson(l).studio, st.lesson_dir(lid, "thumbnail") / "thumbnail.jpg",
                                   get_settings().ai_dir.parent / "avatar" / "assets" / "instructor.png", draft=l.draft)
    db.add(Thumbnail(lesson_id=lid, path=st.rel(out), text=headline))
    audit(db, user, "lesson.thumbnail", lid)
    db.commit()
    return {"status": "ok", "text": headline}


@protected.get("/lessons/{lid}/assets")
def assets(lid: int, db: Session = Depends(get_db)):
    return [{"id": a.id, "scene_id": a.scene_id, "kind": a.kind, "path": a.path} for a in db.query(GeneratedAsset).filter_by(lesson_id=lid)]


@protected.get("/assets/{aid}/file")
def asset_file(aid: int, db: Session = Depends(get_db)):
    a = db.get(GeneratedAsset, aid)
    if not a:
        raise HTTPException(404)
    return FileResponse(get_storage().path(a.path))


ALLOWED_UPLOAD = {".mp4": "video/mp4", ".mov": "video/quicktime", ".webm": "video/webm", ".png": "image/png", ".jpg": "image/jpeg"}
MAX_UPLOAD = 500 * 1024 * 1024


@protected.post("/lessons/{lid}/recordings/{scene_id}")
async def upload_recording(lid: int, scene_id: str, file: UploadFile = File(...), db: Session = Depends(get_db), user: User = Depends(auth.current_user)):
    """Attach an OBS / terminal / browser recording to a scene. Extension, magic-bytes, size and ffprobe validated."""
    import re
    import tempfile
    from pathlib import Path
    from app.utils import media
    _lesson(db, lid)
    if not re.fullmatch(r"scene_\d{3}", scene_id):
        raise HTTPException(422, "bad scene id")
    name = safe_name(file.filename or "rec")
    ext = Path(name).suffix.lower()
    if ext not in ALLOWED_UPLOAD:
        raise HTTPException(415, f"unsupported type {ext}")
    dest = get_storage().lesson_dir(lid, "recordings") / f"{scene_id}{ext}"
    size = 0
    with open(dest, "wb") as f:
        while chunk := await file.read(1 << 20):
            size += len(chunk)
            if size > MAX_UPLOAD:
                f.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(413, "file too large")
            f.write(chunk)
    try:
        info = media.probe(dest)
        if not media.has_stream(info, "video") and ext not in (".png", ".jpg"):
            raise media.MediaError("no video stream")
    except media.MediaError as e:
        dest.unlink(missing_ok=True)
        raise HTTPException(422, f"not a valid media file: {e}")
    audit(db, user, f"recording.attach {scene_id} {name}", lid)
    db.commit()
    return {"path": get_storage().rel(dest), "warning": "Review the recording yourself for credentials/PII; automatic scanning covers text only."}


# ---------- youtube ----------
@protected.get("/youtube/status")
def yt_status():
    return youtube.status()


@protected.get("/youtube/oauth/start")
def yt_start():
    try:
        url, _ = youtube.auth_url()
    except youtube.YouTubeNotConfigured as e:
        raise HTTPException(409, str(e))
    return {"authorization_url": url}


@router.get("/youtube/oauth/callback")
def yt_callback(code: str):
    youtube.finish_auth(code)
    return RedirectResponse(get_settings().cors_origins.split(",")[0] + "/youtube?connected=1")


@protected.post("/lessons/{lid}/youtube/publish")
def yt_publish(lid: int, body: A.ScheduleIn, db: Session = Depends(get_db), user: User = Depends(auth.current_user)):
    l = _lesson(db, lid)
    if not pipeline.is_approved(db, l):  # cheap gate first: never spend an LLM call (minutes on a local model) on an unapproved lesson
        raise HTTPException(403, f"lesson {l.id} is not APPROVED (status={l.status.value})")
    sb = generation.latest_storyboard(db, l)
    meta = generation.generate_metadata(l, StoryboardData.model_validate(sb.data), get_llm()).model_dump()
    try:
        pub = youtube.upload(db, l, meta, 0, body.publish_at, "private")
    except youtube.NotApproved as e:
        raise HTTPException(403, str(e))
    except qualitygate.GateBlocked as e:
        raise HTTPException(409, str(e))
    except youtube.YouTubeNotConfigured as e:
        raise HTTPException(409, str(e))
    audit(db, user, f"youtube.upload {pub.youtube_video_id}", lid)
    db.commit()
    return {"youtube_video_id": pub.youtube_video_id, "privacy": pub.privacy, "status": pub.status}


@protected.get("/lessons/{lid}/youtube/metadata")
def yt_metadata(lid: int, db: Session = Depends(get_db)):
    l = _lesson(db, lid)
    sb = generation.latest_storyboard(db, l)
    if not sb:
        raise HTTPException(409, "no storyboard")
    return generation.generate_metadata(l, StoryboardData.model_validate(sb.data), get_llm())


@protected.get("/analytics")
def analytics(db: Session = Depends(get_db)):
    return [{"publication_id": a.publication_id, "views": a.views, "likes": a.likes, "comments": a.comments, "collected_at": a.collected_at}
            for a in db.query(Analytics).order_by(Analytics.id.desc()).limit(200)]


class LogIn(BaseModel):
    stage: str = Field(max_length=48)
    level: str = Field("info", pattern="^(info|warning|error)$")
    lesson_id: int | None = None
    message: str = Field("", max_length=4000)


@protected.post("/internal/log", status_code=201)
def internal_log(body: LogIn, db: Session = Depends(get_db), user: User = Depends(auth.current_user)):
    """Used by n8n error branches to write into the same execution log."""
    pipeline.log(db, db.get(Lesson, body.lesson_id) if body.lesson_id else None, body.stage, body.message, body.level, actor=f"user:{user.id}")
    db.commit()
    return {"ok": True}


@protected.get("/logs")
def logs(lesson_id: int | None = None, db: Session = Depends(get_db)):
    q = db.query(WorkflowLog).order_by(WorkflowLog.id.desc())
    if lesson_id:
        q = q.filter_by(lesson_id=lesson_id)
    return [{"id": x.id, "lesson_id": x.lesson_id, "stage": x.stage, "level": x.level, "message": x.message, "actor": x.actor,
             "at": x.created_at} for x in q.limit(200)]




# ---------- source verification, technical review, claims, quality gate ----------
REVIEW_FROM = {S.SCRIPT_GENERATED, S.TECHNICAL_REVIEW, S.SCRIPT_APPROVED}


def _review_busy(db, lid: int) -> bool:
    return db.query(ReviewRun).filter_by(lesson_id=lid, status="running").first() is not None


@protected.post("/lessons/{lid}/research/verify", status_code=202)
def research_verify(lid: int, db: Session = Depends(get_db), user: User = Depends(auth.current_user)):
    """Re-fetch every source cited by the latest script (SSRF-guarded, robots-aware) and store provenance."""
    l = _lesson(db, lid)
    sc = generation.latest_script(l)
    if not sc:
        raise HTTPException(409, "lesson has no script yet")
    audit(db, user, "research.verify", lid)
    db.commit()

    def job(d, ls, **k):
        urls = [r["url"] for r in sc.content.get("references", [])]
        # collect() dedupes against ANY existing row for a URL, including a stale failed/blocked one from before
        # an allow-list fix or a transient outage - drop those so this actually re-fetches them, not just new URLs.
        wanted = {research.canonical_url(u) for u in urls}
        stale = (d.query(ResearchSource).filter_by(lesson_id=ls.id, verified=False)
                 .filter(ResearchSource.url.in_(urls)).all())
        for s in stale:
            if research.canonical_url(s.url) in wanted:
                d.delete(s)
        d.flush()
        research.collect(d, ls, urls, True)
        d.commit()
    _bg(job, lid)
    return {"accepted": "research"}


@protected.post("/lessons/{lid}/review/run", status_code=202)
def review_run(lid: int, db: Session = Depends(get_db), user: User = Depends(auth.current_user)):
    """Start (or rerun, or resume after a failure) the technical review of the CURRENT script version."""
    l = _lesson(db, lid)
    base = S(l.last_good_status) if l.status == S.FAILED else l.status
    if base not in REVIEW_FROM:
        raise HTTPException(409, f"technical review needs a generated script (lesson is {base.value})")
    if _review_busy(db, lid):
        raise HTTPException(409, "a review is already running for this lesson")
    _refuse_if_running(lid)
    if l.status == S.FAILED:
        l.retry_count, l.last_error = 0, ""
    pipeline.set_status(db, l, S.SCRIPT_GENERATED)
    audit(db, user, "review.run", lid)
    db.commit()
    _bg(lambda d, ls, **k: pipeline.run_technical_review(d, ls), lid)
    return {"accepted": "review"}


def _finding_out(f: ReviewFinding) -> dict:
    return {c.name: getattr(f, c.name) for c in f.__table__.columns}


@protected.get("/lessons/{lid}/review")
def review_get(lid: int, all_versions: bool = False, db: Session = Depends(get_db)):
    l = _lesson(db, lid)
    cur = generation.latest_script(l)
    q = db.query(ReviewFinding).filter_by(lesson_id=lid)
    if not all_versions and cur:
        q = q.filter_by(script_version=cur.version)
    runs = db.query(ReviewRun).filter_by(lesson_id=lid).order_by(ReviewRun.id.desc()).limit(10).all()
    return {"state": qualitygate.review_state(db, l), "script_version": cur.version if cur else None,
            "runs": [{c.name: getattr(r, c.name) for c in r.__table__.columns} for r in runs],
            "findings": [_finding_out(f) for f in q.order_by(ReviewFinding.id)]}


@protected.get("/lessons/{lid}/claims")
def claims_get(lid: int, db: Session = Depends(get_db)):
    l = _lesson(db, lid)
    cur = generation.latest_script(l)
    srcs = {s.id: s for s in db.query(ResearchSource).filter_by(lesson_id=lid)}
    rows = db.query(TechnicalClaim).filter_by(lesson_id=lid, script_version=cur.version if cur else 0).order_by(TechnicalClaim.id).all()
    return [{**{c.name: getattr(r, c.name) for c in r.__table__.columns}, "blocks": claims_mod.claim_blocks(r),
             "sources": [_source_out(srcs[i]) for i in r.source_ids if i in srcs]} for r in rows]


@protected.get("/lessons/{lid}/sources/{sid}/text")
def source_text(lid: int, sid: int, db: Session = Depends(get_db)):
    s = db.get(ResearchSource, sid)
    if not s or s.lesson_id != lid:
        raise HTTPException(404, "source not found")
    return {**_source_out(s), "sections": research.parse_sections(s.full_text)}


@protected.post("/review/findings/{fid}/decision")
def finding_decision(fid: int, body: A.FindingDecisionIn, db: Session = Depends(get_db), user: User = Depends(auth.require_human)):
    f = db.get(ReviewFinding, fid)
    if not f:
        raise HTTPException(404, "finding not found")
    l = _lesson(db, f.lesson_id)
    if f.status != "open":
        raise HTTPException(409, f"finding is already {f.status}")
    try:
        if body.decision == "accept":
            v = techreview.apply_correction(db, l, f, user.id, body.correction)
            if l.status in (S.TECHNICAL_REVIEW, S.SCRIPT_APPROVED):
                pipeline.set_status(db, l, S.SCRIPT_GENERATED)  # the script changed: it must be reviewed again
            audit(db, user, f"finding.accept #{fid} -> script v{v}", l.id)
        else:
            techreview.decide(db, f, user, body.decision, body.note)
            audit(db, user, f"finding.{body.decision} #{fid} ({f.severity})", l.id)
    except techreview.DecisionError as e:
        db.rollback()
        raise HTTPException(409, str(e))
    db.commit()
    return _finding_out(f)


@protected.post("/review/claims/{cid}/decision")
def claim_decision(cid: int, body: A.ClaimDecisionIn, db: Session = Depends(get_db), user: User = Depends(auth.require_human)):
    c = db.get(TechnicalClaim, cid)
    if not c:
        raise HTTPException(404, "claim not found")
    if len(body.note.strip()) < 10:
        raise HTTPException(422, "a note of at least 10 characters is required")
    c.human_decision, c.human_note = body.decision, body.note.strip()
    audit(db, user, f"claim.{body.decision} #{cid}", c.lesson_id)
    db.commit()
    return {"id": c.id, "human_decision": c.human_decision, "blocks": claims_mod.claim_blocks(c)}


@protected.get("/lessons/{lid}/gate")
def gate_get(lid: int, db: Session = Depends(get_db)):
    _lesson(db, lid)
    out = {}
    for st in ("script", "pre_tts"):
        r = db.query(QualityGateResult).filter_by(lesson_id=lid, stage=st).order_by(QualityGateResult.id.desc()).first()
        out[st] = {"passed": r.passed, "script_version": r.script_version, "storyboard_version": r.storyboard_version, "checks": r.checks,
                   "created_at": r.created_at} if r else None
    return out


@protected.post("/lessons/{lid}/gate/evaluate")
def gate_evaluate(lid: int, stage: str = "pre_tts", db: Session = Depends(get_db), user: User = Depends(auth.current_user)):
    if stage not in ("script", "pre_tts"):
        raise HTTPException(422, "stage must be script or pre_tts")
    l = _lesson(db, lid)
    r = qualitygate.evaluate(db, l, stage)
    db.commit()
    return {"passed": r.passed, "checks": r.checks, "script_version": r.script_version, "storyboard_version": r.storyboard_version}


@protected.get("/lessons/{lid}/revisions")
def revisions(lid: int, db: Session = Depends(get_db)):
    _lesson(db, lid)
    rows = db.query(LessonScript).filter_by(lesson_id=lid).order_by(LessonScript.version).all()
    return [{"version": r.version, "generated_by": r.generated_by, "change_note": r.change_note, "content_hash": r.content_hash, "created_at": r.created_at} for r in rows]


@protected.get("/lessons/{lid}/revisions/{version}")
def revision(lid: int, version: int, db: Session = Depends(get_db)):
    r = db.query(LessonScript).filter_by(lesson_id=lid, version=version).first()
    if not r:
        raise HTTPException(404, "revision not found")
    return {"version": r.version, "generated_by": r.generated_by, "change_note": r.change_note, "content": r.content}


router.include_router(protected)  # must stay last: routes registered on `protected` after this line would be ignored
