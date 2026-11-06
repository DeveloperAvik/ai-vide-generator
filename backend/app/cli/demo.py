"""Local demo: python -m app.cli.demo
Runs the real pipeline end to end with the offline mock LLM and a local TTS (Piper if configured, else macOS say).
The human gates are auto-passed ONLY here, recorded in the audit log as actor 'demo-cli'."""
import argparse
import shutil
import sys
from pathlib import Path

from app.core.config import ROOT, get_settings
from app.core.db import Base, SessionLocal, engine
from app.models import Course, LessonStatus as S, Module, Lesson
from app.providers.llm import get_llm
from app.providers.voice import VoiceUnavailable, get_voice
from app.schemas.content import CurriculumRequest
from app.services import generation, pipeline
from app.services.storage import get_storage


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", choices=["ffmpeg", "remotion"], default=get_settings().render_engine)
    ap.add_argument("--fresh", action="store_true", help="delete the demo course (and its files) first")
    ap.add_argument("--online", action="store_true", help="fetch research sources over the network")
    a = ap.parse_args()
    get_settings().render_engine = a.engine
    Base.metadata.create_all(engine)  # demo convenience; production uses `alembic upgrade head`
    try:
        v = get_voice()
    except VoiceUnavailable as e:
        sys.exit(f"DEMO CANNOT RUN: no local voice provider available ({e}). Install Piper: see voice/README.md")
    print(f"voice provider: {v.name} | llm: mock | render engine: {a.engine}")
    db = SessionLocal()
    try:
        course = db.query(Course).filter_by(name="Demo: Web Application Penetration Testing").first()
        if course and a.fresh:
            for m in course.modules:
                for l in m.lessons:
                    shutil.rmtree(get_storage().path("lessons", str(l.id)), ignore_errors=True)
            db.delete(course)
            db.commit()
            course = None
        if not course:
            course = generation.generate_curriculum(db, CurriculumRequest(course_name="Demo: Web Application Penetration Testing"), get_llm("mock"))
            db.commit()
        lesson = next(l for m in course.modules for l in m.lessons if l.title == "SQL Injection Fundamentals")
        print(f"lesson {lesson.id}: {lesson.title} [{lesson.status.value}]")
        if lesson.status == S.FAILED or lesson.status.value in ("TOPIC_PENDING", "RESEARCHING", "SCRIPT_GENERATED"):
            pipeline.resume(db, lesson, llm=get_llm("mock"), online=a.online)
        print("->", lesson.status.value)
        if lesson.status == S.TECHNICAL_REVIEW:
            pipeline.log(db, lesson, "demo", "auto-approving script (demo mode only)", actor="demo-cli")
            pipeline.approve_script(db, lesson, None, "demo auto-approval")
        if lesson.status in (S.SCRIPT_APPROVED, S.ASSETS_READY, S.QUALITY_CHECK):
            pipeline.resume(db, lesson, llm=get_llm("mock"))
        print("->", lesson.status.value)
        if lesson.status == S.APPROVAL_PENDING:
            pipeline.log(db, lesson, "demo", "auto-approving video (demo mode only)", actor="demo-cli")
            pipeline.decide_video(db, lesson, None, "APPROVED", "demo")
        st = get_storage()
        from app.models import VideoRender, Thumbnail
        r = db.query(VideoRender).filter_by(lesson_id=lesson.id, status="done").order_by(VideoRender.id.desc()).first()
        t = db.query(Thumbnail).filter_by(lesson_id=lesson.id).order_by(Thumbnail.id.desc()).first()
        out = ROOT / "storage" / "demo"
        out.mkdir(parents=True, exist_ok=True)
        for src, name in ((r.video_path, "demo_lesson.mp4"), (r.srt_path, "demo_subtitles.srt"), (t.path, "demo_thumbnail.jpg"), (r.manifest_path, "render_manifest.json")):
            shutil.copy(st.path(src), out / name)
        print(f"\nDEMO COMPLETE [{lesson.status.value}] {r.duration_seconds:.1f}s {r.engine}\n  {out}/demo_lesson.mp4\n  {out}/demo_subtitles.srt\n  {out}/demo_thumbnail.jpg")
    finally:
        db.close()


if __name__ == "__main__":
    main()
