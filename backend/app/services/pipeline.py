"""Stage orchestration with resume. Each stage records `last_good_status`; on failure the lesson is FAILED and
`resume()` continues from the last good stage. Human gates (script approval, video approval) never auto-pass."""
import json
import traceback
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import (Approval, AvatarGeneration, GeneratedAsset, Lesson, LessonStatus as S, QualityCheck,
                        ResearchSource, Thumbnail, VideoRender, VoiceGeneration, WorkflowLog, YouTubePublication, now)
from app.providers.avatar import AvatarUnavailable, get_avatar
from app.providers.llm import LLMProvider, get_llm
from app.providers.voice import VoiceUnavailable, get_voice
from app.schemas.content import Scene, StoryboardData, YouTubeMetadata
from app.security import redaction
from app.services import domains, generation, lengthplan, narration, qualitygate, renderer, research, techreview, visuals
from app.services.storage import get_storage
from app.utils import media

MAX_RETRIES = 3
GATES = {S.TECHNICAL_REVIEW, S.APPROVAL_PENDING, S.APPROVED, S.SCHEDULED, S.PUBLISHED}


class StageError(RuntimeError):
    pass


class GateStop(StageError):
    """Quality gate blocked the stage (content problem). Not a crash: no retry is consumed."""


def enforce_gate(db: Session, lesson: Lesson, stage_name: str = "pre_tts"):
    try:
        if lesson.draft:  # quick draft: structural storyboard checks only (see qualitygate.enforce_draft); never a substitute for the real gate
            return qualitygate.enforce_draft(db, lesson)
        return qualitygate.enforce(db, lesson, stage_name)
    except qualitygate.GateBlocked as e:
        raise GateStop(f"rejected before rendering - {e}") from e


def log(db: Session, lesson: Lesson | None, stage: str, msg: str, level="info", actor="system", key=""):
    db.add(WorkflowLog(lesson_id=lesson.id if lesson else None, stage=stage, level=level,
                       message=redaction.redact(msg)[:4000], actor=actor, idempotency_key=key))
    db.flush()


def set_status(db: Session, lesson: Lesson, status: S, good: bool = True):
    lesson.status = status
    if good:
        lesson.last_good_status = status.value
    db.flush()


@contextmanager
def stage(db: Session, lesson: Lesson, name: str, working: S | None = None):
    """Wrap a stage: log, mark working status, on exception mark FAILED (keeping last_good_status) and re-raise."""
    if lesson.retry_count >= MAX_RETRIES and lesson.status == S.FAILED:
        raise StageError(f"lesson {lesson.id} exceeded {MAX_RETRIES} retries; manual reset required")
    if working:
        set_status(db, lesson, working, good=False)
    log(db, lesson, name, "started")
    db.commit()  # visible at once (dashboard, delete guard) and no row lock held for the whole stage, which can take many minutes
    try:
        yield
        lesson.last_error = ""  # a stage that completes clears the error left by an earlier failed attempt
        log(db, lesson, name, "completed")
        db.commit()
    except GateStop as e:  # content problem, not a crash: stay at the last good status, do not consume a retry
        db.rollback()
        lesson = db.get(Lesson, lesson.id)
        lesson.status = S(lesson.last_good_status)
        lesson.last_error = redaction.redact(f"{name}: {e}")[:2000]
        log(db, lesson, name, str(e), level="warning")
        db.commit()
        raise
    except Exception as e:  # noqa: BLE001 - stage boundary: record everything
        db.rollback()
        lesson = db.get(Lesson, lesson.id)
        lesson.status = S.FAILED
        lesson.retry_count += 1
        lesson.last_error = redaction.redact(f"{name}: {type(e).__name__}: {e}")[:2000]
        log(db, lesson, name, f"failed: {e}\n{traceback.format_exc(limit=3)}", level="error")
        db.commit()
        raise


# ---------------- stages ----------------
def run_research(db: Session, lesson: Lesson, extra_urls=None, online=True):
    with stage(db, lesson, "research", S.RESEARCHING):
        extra = list(extra_urls or [])
        if online and not research.seed_urls(research._topic_text(lesson)):  # no curated pages for this topic: search APIs + model suggestions (kept only if they load)
            dom = domains.of_lesson(lesson).key
            extra += research.discover_urls(lesson.title, dom) + research.suggest_urls(get_llm(), lesson, dom)
        research.collect(db, lesson, extra, online)
        set_status(db, lesson, S.RESEARCHING)


def run_script(db: Session, lesson: Lesson, llm: LLMProvider | None = None):
    with stage(db, lesson, "script"):
        srcs = db.query(ResearchSource).filter_by(lesson_id=lesson.id).all()
        generation.generate_script(db, lesson, llm or get_llm(), srcs)
        set_status(db, lesson, S.SCRIPT_GENERATED)


def run_technical_review(db: Session, lesson: Lesson, online=True, reviewer: LLMProvider | None = None):
    """Source collection -> regex validation -> claim mapping -> independent LLM review -> script-level gate (stored). Safe to rerun."""
    with stage(db, lesson, "technical_review"):
        script = generation.latest_script(lesson)
        research.collect(db, lesson, [r["url"] for r in script.content.get("references", [])], online)  # fetch every cited URL
        srcs = db.query(ResearchSource).filter_by(lesson_id=lesson.id).all()
        report = research.technical_validation(script.content, srcs, online)
        report["stage"] = "technical"
        db.add(QualityCheck(lesson_id=lesson.id, passed=report["passed"], report=report))
        db.commit()  # keep sources even if the (slow, fallible) LLM review below fails; it can be resumed
        try:
            summary = techreview.run_review(db, lesson, reviewer)
        except techreview.ReviewBusy as e:
            raise GateStop(str(e)) from e  # duplicate job: refuse without marking the lesson FAILED
        gate = qualitygate.evaluate(db, lesson, "script")
        log(db, lesson, "technical_review", f"review completed: {summary}; script gate {'passed' if gate.passed else 'BLOCKED: ' + '; '.join(qualitygate.blocking_reasons(gate))[:600]}")
        set_status(db, lesson, S.TECHNICAL_REVIEW)


def approve_script(db: Session, lesson: Lesson, user_id: int | None, notes="", decision="APPROVED"):
    if lesson.status != S.TECHNICAL_REVIEW:
        raise StageError("script can only be approved from TECHNICAL_REVIEW")
    qc = db.query(QualityCheck).filter_by(lesson_id=lesson.id).order_by(QualityCheck.id.desc()).first()
    if decision == "APPROVED" and qc and not qc.passed:
        raise StageError("technical validation has errors; fix the script or sources first")
    if decision == "APPROVED":
        gate = qualitygate.evaluate(db, lesson, "script")
        db.commit()
        if not gate.passed:
            raise StageError("script cannot be approved - quality gate blocked: " + "; ".join(qualitygate.blocking_reasons(gate))[:1500])
    db.add(Approval(lesson_id=lesson.id, stage="script", decision=decision, reviewer_id=user_id, notes=notes))
    if decision == "APPROVED":
        set_status(db, lesson, S.SCRIPT_APPROVED)
    else:
        set_status(db, lesson, S.RESEARCHING)
    log(db, lesson, "script_approval", decision, actor=f"user:{user_id}")
    db.commit()


def _scene_text(sc: Scene) -> str:
    return "\n".join([sc.narration, sc.on_screen_text, sc.code or "", "\n".join(sc.terminal_lines or [])])


def run_assets(db: Session, lesson: Lesson, llm: LLMProvider | None = None, recordings: dict[str, Path] | None = None,
               voice_name: str | None = None, avatar_name: str | None = None, parts: set[str] | None = None):
    """Storyboard -> sanitize check -> voice per scene -> avatar clips -> slide PNGs. Idempotent by content hash."""
    st = get_storage()
    parts = parts or {"voice", "avatar", "visuals"}
    with stage(db, lesson, "assets", S.ASSETS_GENERATING):
        sbrow = generation.latest_storyboard(db, lesson) or generation.generate_storyboard(db, lesson, llm or get_llm())
        sb = StoryboardData.model_validate(sbrow.data)
        script_ = generation.latest_script(lesson)
        if "voice" in parts:  # the gate runs BEFORE any TTS; it includes the storyboard preflight (length, placeholders, repetition)
            enforce_gate(db, lesson, "pre_tts")
        leaks = [(s.scene_id, f) for s in sb.scenes for f in redaction.scan_text(_scene_text(s))]
        if leaks:
            raise StageError(f"sensitive data detected in storyboard: {leaks[:3]}")
        voice = get_voice(voice_name)
        d = st.lesson_dir(lesson.id, "assets")
        portrait = Path(get_settings().ai_dir.parent / "avatar" / "assets" / "instructor.png")
        if not portrait.exists():
            visuals.default_portrait(portrait)
        for i, sc in enumerate(sb.scenes, 1):
            h = media.sha256_text(sc.narration + voice.name)
            wav = d / f"{sc.scene_id}.wav"
            if "voice" in parts and not (wav.exists() and db.query(VoiceGeneration).filter_by(lesson_id=lesson.id, scene_id=sc.scene_id, text_hash=h).first()):
                narration.synth_with_timing(voice, sc.narration, wav)
                problems = voice.validate_audio(wav)
                if problems:
                    raise StageError(f"{sc.scene_id} audio invalid: {problems}")
                db.query(VoiceGeneration).filter_by(lesson_id=lesson.id, scene_id=sc.scene_id).delete()
                db.add(VoiceGeneration(lesson_id=lesson.id, scene_id=sc.scene_id, provider=voice.name, path=st.rel(wav),
                                       duration_seconds=voice.get_audio_duration(wav), text_hash=h))
            png = d / f"{sc.scene_id}.png"
            if "visuals" in parts:
                visuals.render_scene_png(sc, sb.lesson_title, png, i, len(sb.scenes), portrait, brand=domains.of_lesson(lesson).studio, draft=lesson.draft)
                ah = media.sha256_file(png)
                if not db.query(GeneratedAsset).filter_by(lesson_id=lesson.id, scene_id=sc.scene_id, kind="slide", content_hash=ah).first():
                    db.add(GeneratedAsset(lesson_id=lesson.id, scene_id=sc.scene_id, kind="slide", path=st.rel(png), content_hash=ah,
                                          meta={"scene_type": sc.type}))
            if "visuals" in parts and sc.type == "diagram" and sc.mermaid:
                from app.services import mermaid_lite
                svg = d / f"{sc.scene_id}.svg"
                svg.write_text(mermaid_lite.to_svg(sc.mermaid))
            if "avatar" in parts and sc.type == "instructor":
                if not wav.exists():
                    raise StageError(f"{sc.scene_id}: avatar needs narration audio first (run voice part)")
                av = get_avatar(avatar_name)
                clip = d / f"{sc.scene_id}_avatar.mp4"
                jid = av.generate_avatar_video(png if av.name == "static" else portrait, wav, clip)  # static: the composed instructor slide, others: raw portrait
                if av.get_generation_status(jid) != "done":
                    raise StageError("avatar generation not finished")
                av.download_result(jid, clip)
                db.add(AvatarGeneration(lesson_id=lesson.id, scene_id=sc.scene_id, provider=av.name, path=st.rel(clip), external_id=jid))
        if "voice" in parts:  # measured (not estimated) narration length, before spending time on rendering
            audio_s = sum(voice.get_audio_duration(d / f"{x.scene_id}.wav") for x in sb.scenes)
            lengthplan.record_voice_sample(f"lesson:{lesson.id}", lengthplan.word_count(sb), audio_s, voice.label)  # speed is text-dependent: keep learning
            ok_a, why_a = lengthplan.audio_check(audio_s, lesson.estimated_minutes, script_.generated_by if script_ else "", lesson.draft)
            log(db, lesson, "assets", why_a, level="info" if ok_a else "error")
            if not ok_a:
                raise StageError("narration duration check failed: " + why_a)
        (d / "asset_manifest.json").write_text(json.dumps({"lesson_id": lesson.id, "storyboard_version": sbrow.version,
            "voice_provider": voice.name, "scenes": [{"scene_id": s.scene_id, "type": s.type, "narration_audio": f"{s.scene_id}.wav",
            "visual": f"{s.scene_id}.png", "duration_seconds": s.duration_seconds, "transition": s.transition} for s in sb.scenes]}, indent=2))
        complete = all((d / f"{x.scene_id}.wav").exists() and (d / f"{x.scene_id}.png").exists() and
                       (x.type != "instructor" or (d / f"{x.scene_id}_avatar.mp4").exists()) for x in sb.scenes)
        if complete:
            set_status(db, lesson, S.ASSETS_READY)
        else:
            log(db, lesson, "assets", f"parts {sorted(parts)} done; other parts still pending")


def run_render(db: Session, lesson: Lesson, recordings: dict[str, Path] | None = None, music: Path | None = None, render_id: int | None = None):
    st = get_storage()
    sbrow = generation.latest_storyboard(db, lesson)
    sb = StoryboardData.model_validate(sbrow.data)
    d = st.lesson_dir(lesson.id, "assets")
    r = db.get(VideoRender, render_id) if render_id else VideoRender(lesson_id=lesson.id, engine="ffmpeg", status="running")
    db.add(r)
    r.status = "running"
    db.flush()
    out_dir = st.lesson_dir(lesson.id, f"render_{r.id}")
    with stage(db, lesson, "render", S.RENDERING):
        enforce_gate(db, lesson, "pre_tts")  # re-evaluated: a review rerun or script edit since the assets were built blocks rendering

        def prog(p):
            r.progress = p
            db.commit()

        def cancelled():
            db.refresh(r)
            return r.status == "cancelling"

        recs = dict(recordings or {})
        for sc in sb.scenes:  # instructor scenes use the avatar clip as picture track
            clip = d / f"{sc.scene_id}_avatar.mp4"
            if sc.type == "instructor" and clip.exists():
                recs.setdefault(sc.scene_id, clip)
        engine = get_settings().render_engine
        has_3d = any(sc.mode3d or sc.visualization for sc in sb.scenes)  # typed visualizations only exist in the Remotion engine
        if lesson.draft:
            engine, has_3d = "ffmpeg", False  # the draft banner is drawn into the frames; 3D scenes fall back to their flat diagram
        if has_3d and engine != "remotion":
            from app.workers import remotion_adapter as _ra
            ok3d, why3d = _ra.available()
            if not ok3d:
                raise StageError(f"storyboard has 3D/visualization scenes but the Remotion engine is unavailable: {why3d}")
            log(db, lesson, "render", "storyboard contains 3D/visualization scenes: using the Remotion engine")
            engine = "remotion"
        portrait_p = Path(get_settings().ai_dir.parent / "avatar" / "assets" / "instructor.png")
        try:
            if engine == "remotion":
                from app.workers import remotion_adapter
                r.engine = "remotion"
                res = remotion_adapter.render_long(brand=domains.of_lesson(lesson).studio, storyboard=sb, assets_dir=d, scene_audio={s.scene_id: d / f"{s.scene_id}.wav" for s in sb.scenes},
                                                   scene_video=dict(recordings or {}), out_dir=out_dir,
                                                   portrait=portrait_p, music=music, on_progress=prog, should_cancel=cancelled)
            else:
                res = renderer.render_long(storyboard=sb, scene_pngs={s.scene_id: d / f"{s.scene_id}.png" for s in sb.scenes},
                                           scene_audio={s.scene_id: d / f"{s.scene_id}.wav" for s in sb.scenes}, scene_video=recs,
                                           out_dir=out_dir, music=music, on_progress=prog, should_cancel=cancelled)
        except renderer.RenderCancelled:
            r.status = "cancelled"
            set_status(db, lesson, S.ASSETS_READY)
            db.commit()
            return r
        except Exception as e:
            r.status, r.error = "failed", str(e)[:1000]
            db.commit()
            raise
        r.video_path, r.srt_path, r.manifest_path = st.rel(res["video"]), st.rel(res["srt"]), st.rel(res["manifest"])
        r.duration_seconds, r.sha256, r.status, r.progress = res["duration"], res["sha256"], "done", 1.0
        meta_dir = out_dir
        script = generation.latest_script(lesson)
        thumb = visuals.render_thumbnail(sb.lesson_title, domains.of_lesson(lesson).studio, meta_dir / "thumbnail.jpg",
                                         Path(get_settings().ai_dir.parent / "avatar" / "assets" / "instructor.png"), draft=lesson.draft)
        db.add(Thumbnail(lesson_id=lesson.id, path=st.rel(thumb), text=sb.lesson_title))
        set_status(db, lesson, S.QUALITY_CHECK)
    return r


def run_quality(db: Session, lesson: Lesson, llm: LLMProvider | None = None):
    st = get_storage()
    with stage(db, lesson, "quality_check"):
        r = db.query(VideoRender).filter_by(lesson_id=lesson.id, status="done").order_by(VideoRender.id.desc()).first()
        sbrow = generation.latest_storyboard(db, lesson)
        sb = StoryboardData.model_validate(sbrow.data)
        checks = []

        def chk(name, ok, detail=""):
            checks.append({"check": name, "passed": bool(ok), "detail": detail})

        if not r:
            raise StageError("no completed render")
        video = st.path(r.video_path)
        try:
            v = renderer.verify(video, expected=r.duration_seconds, srt=st.path(r.srt_path))
            chk("media_integrity", True, f"{v['resolution']} h264/aac {v['duration']:.1f}s")
        except renderer.RenderError as e:
            chk("media_integrity", False, str(e))
        chk("sha256_matches", media.sha256_file(video) == r.sha256)
        total = sb.total_seconds
        script_ = generation.latest_script(lesson)
        len_ok, len_detail, len_blocking = lengthplan.length_check(r.duration_seconds, lesson.estimated_minutes, script_.generated_by if script_ else "", lesson.draft)
        chk("duration_matches_request", len_ok, len_detail)
        audio_total = sum(v_.duration_seconds for v_ in db.query(VoiceGeneration).filter_by(lesson_id=lesson.id).all())
        try:
            actual = float(media.probe(video)["format"]["duration"])  # ffprobe of the MP4 itself, not the renderer's own number
        except Exception as e:  # noqa: BLE001
            actual = 0.0
            chk("video_duration_probe", False, str(e))
        vid_ok, vid_detail = lengthplan.video_check(actual, audio_total, lesson.estimated_minutes, lesson.draft)
        chk("video_duration_vs_narration", vid_ok or not len_blocking, vid_detail)
        leaks = [(s.scene_id, f["type"]) for s in sb.scenes for f in redaction.scan_text(_scene_text(s))]
        chk("no_sensitive_data", not leaks, str(leaks))
        chk("thumbnail_exists", db.query(Thumbnail).filter_by(lesson_id=lesson.id).count() > 0)
        script = generation.latest_script(lesson)
        chk("has_defensive_section", bool(script and script.content.get("defensive_recommendations", "").strip()))
        chk("has_references", bool(script and script.content.get("references")) or lesson.draft, "draft: no sources were collected" if lesson.draft else "")
        measured = {v_.scene_id: v_.duration_seconds for v_ in db.query(VoiceGeneration).filter_by(lesson_id=lesson.id).all()}
        wps = [len(s.narration.split()) / measured[s.scene_id] for s in sb.scenes if measured.get(s.scene_id)]
        chk("narration_pace", bool(wps) and all(1.2 <= w <= 4.0 for w in wps), f"measured {min(wps, default=0):.1f}-{max(wps, default=0):.1f} words/s over {len(wps)}/{len(sb.scenes)} scenes")
        # length is blocking for real content; mock-template content is exempt (see lengthplan.length_check)
        blocking = [c for c in checks if c["check"] != "duration_matches_request" or len_blocking]
        passed = all(c["passed"] for c in blocking)
        db.add(QualityCheck(lesson_id=lesson.id, passed=passed, report={"stage": "final", "checks": checks, "render_id": r.id}))
        if not passed:
            raise StageError("quality check failed: " + "; ".join(c["check"] for c in blocking if not c["passed"]))
        set_status(db, lesson, S.APPROVAL_PENDING)


def decide_video(db: Session, lesson: Lesson, user_id: int | None, decision: str, notes: str = ""):
    if lesson.status != S.APPROVAL_PENDING:
        raise StageError("video can only be decided from APPROVAL_PENDING")
    if lesson.draft and decision == "APPROVED":
        raise StageError("this is an UNREVIEWED DRAFT: it cannot be approved. Use 'Make official' to run the full source research and review first")
    db.add(Approval(lesson_id=lesson.id, stage="video", decision=decision, reviewer_id=user_id, notes=notes))
    set_status(db, lesson, S.APPROVED if decision == "APPROVED" else S.ASSETS_READY)
    log(db, lesson, "video_approval", decision, actor=f"user:{user_id}")
    db.commit()


def is_approved(db: Session, lesson: Lesson) -> bool:
    last = db.query(Approval).filter_by(lesson_id=lesson.id, stage="video").order_by(Approval.id.desc()).first()
    return bool(last and last.decision == "APPROVED" and lesson.status in (S.APPROVED, S.SCHEDULED) and not lesson.draft)


# ---------------- resume ----------------
NEXT = {
    S.TOPIC_PENDING: run_research, S.RESEARCHING: run_script, S.SCRIPT_GENERATED: run_technical_review,
    S.SCRIPT_APPROVED: run_assets, S.ASSETS_GENERATING: run_assets, S.ASSETS_READY: run_render,
    S.RENDERING: run_render, S.QUALITY_CHECK: run_quality,
}
# Quick draft: no research and no review. Script, then assets, render and the media checks; ends at APPROVAL_PENDING, where approval is refused.
NEXT_DRAFT = {
    S.TOPIC_PENDING: run_script, S.RESEARCHING: run_script, S.SCRIPT_GENERATED: run_assets, S.SCRIPT_APPROVED: run_assets,
    S.ASSETS_GENERATING: run_assets, S.ASSETS_READY: run_render, S.RENDERING: run_render, S.QUALITY_CHECK: run_quality,
}


def start_draft(db: Session, lesson: Lesson) -> None:
    """Mark the lesson as a quick draft. Only a lesson that has not been through the real pipeline can become one."""
    if lesson.status in (S.APPROVED, S.SCHEDULED, S.PUBLISHED):
        raise StageError(f"lesson is {lesson.status.value}; a finished lesson cannot be turned into a draft")
    if lesson.status in (S.TECHNICAL_REVIEW, S.APPROVAL_PENDING) and not lesson.draft:
        raise StageError("this lesson is already in the normal review flow; finish or reject it there")
    lesson.draft = True
    log(db, lesson, "draft", "quick draft started: no source research and no fact-check review; every frame is stamped UNREVIEWED DRAFT")
    db.commit()


def promote_draft(db: Session, lesson: Lesson, user_id: int | None = None) -> None:
    """'Make official': clear the draft flag and send the lesson back to the start of the normal pipeline (research -> script -> review ->
    approval). The draft script, audio and video stay as history; nothing about the draft counts toward approval."""
    if not lesson.draft:
        raise StageError("lesson is not a draft")
    lesson.draft, lesson.retry_count, lesson.last_error = False, 0, ""
    set_status(db, lesson, S.TOPIC_PENDING)
    log(db, lesson, "draft", "promoted: the full research, review and approval flow will run", actor=f"user:{user_id}")
    db.commit()


def resume(db: Session, lesson: Lesson, max_steps: int = 10, **kw) -> Lesson:
    """Continue from last_good_status until a human gate or completion. Safe to call repeatedly."""
    if lesson.status == S.FAILED:
        if lesson.retry_count >= MAX_RETRIES:
            raise StageError(f"lesson {lesson.id} exceeded {MAX_RETRIES} retries; call reset to clear")
        lesson.status = S(lesson.last_good_status)
        db.commit()
    steps = NEXT_DRAFT if lesson.draft else NEXT
    for _ in range(max_steps):
        fn = steps.get(S(lesson.last_good_status if lesson.status == S.FAILED else lesson.status))
        if fn is None:
            break
        try:
            fn(db, lesson, **{k: v for k, v in kw.items() if k in fn.__code__.co_varnames})
        except Exception:
            db.refresh(lesson)
            raise
        db.refresh(lesson)
    return lesson
