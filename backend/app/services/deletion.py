"""Hard deletion of lessons, courses and renders (DB rows + files on disk).

Deleting never touches YouTube: a video that was published stays up there, so removing the local lesson requires `force`.
Deletes are refused while a job is in flight; cancel it first (or pass force for a job stuck after a crash). Rows are removed child-first through the table metadata so it
behaves the same on PostgreSQL (FK cascades) and SQLite (FKs off)."""
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.db import Base
from app.models import (Analytics, Course, Lesson, LessonStatus as S, Scene, Storyboard, VideoRender, WorkflowLog, YouTubePublication)
from app.services.storage import get_storage

BUSY_STATUSES = {S.RESEARCHING, S.ASSETS_GENERATING, S.RENDERING}
BUSY_RENDERS = {"queued", "running", "cancelling"}
AFTER_RENDER = {S.QUALITY_CHECK, S.APPROVAL_PENDING, S.APPROVED, S.SCHEDULED}


class DeleteBlocked(Exception):
    """The delete is not allowed right now (maps to HTTP 409)."""


def _published(db: Session, lesson_ids: list[int] | None = None, render_id: int | None = None) -> list[YouTubePublication]:
    q = db.query(YouTubePublication).filter(YouTubePublication.youtube_video_id != "")
    if lesson_ids is not None:
        q = q.filter(YouTubePublication.lesson_id.in_(lesson_ids))
    if render_id is not None:
        q = q.filter(YouTubePublication.render_id == render_id)
    return q.all()


def _stage_running(db: Session, lesson: Lesson) -> bool:
    """True while a pipeline stage is in progress. The status alone cannot tell: RESEARCHING is also where a lesson sits, idle, after research
    finished or after its script was rejected. A stage writes a 'started' log first and 'completed'/'failed' last, so the newest stage log decides;
    a 'started' older than an hour is a crash leftover, not a running job."""
    last = (db.query(WorkflowLog).filter(WorkflowLog.lesson_id == lesson.id, WorkflowLog.stage != "audit", WorkflowLog.level != "warning")
            .order_by(WorkflowLog.id.desc()).first())
    if lesson.status not in BUSY_STATUSES and not (last and last.message == "started"):
        return False
    if not last or last.message != "started":
        return False
    created = last.created_at if last.created_at.tzinfo else last.created_at.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - created < timedelta(hours=1)


def _check_lessons(db: Session, lessons: list[Lesson], force: bool):
    if force:
        return  # explicit override (e.g. a lesson stuck in a working status after a crash, or a published one)
    for l in lessons:
        if _stage_running(db, l) or db.query(VideoRender).filter(VideoRender.lesson_id == l.id, VideoRender.status.in_(BUSY_RENDERS)).count():
            raise DeleteBlocked(f"lesson '{l.title}' has a job in progress ({l.status.value}); wait for it to finish (or cancel the render) before deleting. "
                                "If it is stuck, retry with force=true")
    if _published(db, [l.id for l in lessons]):
        raise DeleteBlocked("a video was already published to YouTube; deleting here will NOT remove it from YouTube. Retry with force=true to delete locally anyway")


def _purge_rows(db: Session, lesson_id: int):
    pub_ids = [p.id for p in db.query(YouTubePublication.id).filter_by(lesson_id=lesson_id)]
    if pub_ids:
        db.query(Analytics).filter(Analytics.publication_id.in_(pub_ids)).delete(synchronize_session=False)
    sb_ids = [s.id for s in db.query(Storyboard.id).filter_by(lesson_id=lesson_id)]
    if sb_ids:
        db.query(Scene).filter(Scene.storyboard_id.in_(sb_ids)).delete(synchronize_session=False)
    db.query(WorkflowLog).filter_by(lesson_id=lesson_id).update({"lesson_id": None}, synchronize_session=False)  # keep the audit trail
    for t in reversed(Base.metadata.sorted_tables):  # children before parents
        if t.name in ("lessons", "workflow_logs") or "lesson_id" not in t.c:
            continue
        db.execute(t.delete().where(t.c.lesson_id == lesson_id))


def _rmtree(rel: str):
    p = get_storage().path(*Path(rel).parts)
    if p.exists():
        shutil.rmtree(p, ignore_errors=True)


def delete_lessons(db: Session, lessons: list[Lesson], force: bool = False) -> int:
    _check_lessons(db, lessons, force)
    ids = [l.id for l in lessons]
    for l in lessons:
        _purge_rows(db, l.id)
        db.expire(l)
        db.delete(l)
    db.flush()
    for i in ids:
        _rmtree(f"lessons/{int(i)}")
    return len(ids)


def delete_course(db: Session, course: Course, force: bool = False) -> int:
    lessons = [l for m in course.modules for l in m.lessons]
    n = delete_lessons(db, lessons, force)
    db.expire(course)
    db.delete(course)
    db.flush()
    return n


def delete_render(db: Session, r: VideoRender, force: bool = False) -> None:
    if r.status in BUSY_RENDERS:
        raise DeleteBlocked("render is in progress; cancel it first")
    if _published(db, render_id=r.id) and not force:
        raise DeleteBlocked("this render was published to YouTube; deleting it here will NOT remove the YouTube video. Retry with force=true")
    for p in db.query(YouTubePublication).filter_by(render_id=r.id):
        db.query(Analytics).filter_by(publication_id=p.id).delete(synchronize_session=False)
        db.delete(p)
    st = get_storage()
    for rel in (r.video_path, r.srt_path, r.manifest_path):
        if rel:
            try:
                st.path(*Path(rel).parts).unlink(missing_ok=True)
            except ValueError:  # path escaped storage root: never delete it
                pass
    lesson = db.get(Lesson, r.lesson_id)
    db.delete(r)
    db.flush()
    # a lesson that was past rendering no longer has a video: send it back so the pipeline can render again
    if lesson and lesson.status in AFTER_RENDER and not db.query(VideoRender).filter_by(lesson_id=lesson.id, status="done").count():
        lesson.status, lesson.last_good_status = S.ASSETS_READY, S.ASSETS_READY.value
