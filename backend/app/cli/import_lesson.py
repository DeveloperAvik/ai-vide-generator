"""Mode A import: python -m app.cli.import_lesson <bundle.json> [--approve-script] [--offline]
Takes a human/Claude-authored script + storyboard (strictly validated), runs research + technical validation,
and with --approve-script (logged as a CLI approval) continues through assets, render and quality check.
It always STOPS at APPROVAL_PENDING: final video approval and upload stay with a human."""
import argparse
import json
from pathlib import Path

from app.core.config import ROOT
from app.core.db import Base, SessionLocal, engine
from app.models import Course, Lesson, LessonStatus as S, Module
from app.schemas.content import LessonScriptData, StoryboardData
from app.services import generation, pipeline


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bundle")
    ap.add_argument("--approve-script", action="store_true")
    ap.add_argument("--stop-after-approval", action="store_true", help="leave the lesson at SCRIPT_APPROVED (n8n / API drives the rest)")
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--fresh", action="store_true", help="delete an existing copy of this lesson (and its files) first")
    a = ap.parse_args()
    b = json.loads(Path(a.bundle).read_text())
    script = LessonScriptData.model_validate(b["script"])  # reject malformed input before touching the DB
    sb = StoryboardData.model_validate(b["storyboard"])
    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        course = db.query(Course).filter_by(name=b["course_name"]).first() or Course(name=b["course_name"], description="", language="English")
        db.add(course)
        if a.fresh:
            import shutil
            from app.services.storage import get_storage
            for m_ in list(course.modules):
                for l_ in [l for l in m_.lessons if l.title == b["lesson_title"]]:
                    shutil.rmtree(get_storage().path("lessons", str(l_.id)), ignore_errors=True)
                    m_.lessons.remove(l_)
            db.commit()
        mod = next((m for m in course.modules if m.title == b["module_title"]), None)
        if not mod:
            mod = Module(title=b["module_title"], position=len(course.modules))
            course.modules.append(mod)
        lesson = next((l for l in mod.lessons if l.title == b["lesson_title"]), None)
        if not lesson:
            lesson = Lesson(title=b["lesson_title"], summary=b.get("summary", ""), position=len(mod.lessons), estimated_minutes=max(1, round(sb.total_seconds / 60)))
            mod.lessons.append(lesson)
        db.commit()
        if lesson.status == S.FAILED:
            lesson.status = S(lesson.last_good_status)
        if lesson.status in (S.TOPIC_PENDING, S.RESEARCHING, S.SCRIPT_GENERATED, S.TECHNICAL_REVIEW):
            if lesson.status == S.TOPIC_PENDING:
                pipeline.run_research(db, lesson, online=not a.offline)
            generation.save_script(db, lesson, script, "manual:import_lesson")
            generation.save_storyboard(db, lesson, sb)
            pipeline.set_status(db, lesson, S.SCRIPT_GENERATED)
            db.commit()
            pipeline.run_technical_review(db, lesson, online=not a.offline)
        print(f"lesson {lesson.id} status={lesson.status.value}")
        if lesson.status == S.TECHNICAL_REVIEW:
            from app.models import QualityCheck
            qc = db.query(QualityCheck).filter_by(lesson_id=lesson.id).order_by(QualityCheck.id.desc()).first()
            for i in qc.report["issues"]:
                print(f"  [{i['severity']}] {i['msg']}")
            print(f"  sources verified: {qc.report['sources_verified']}  validation passed: {qc.passed}")
            if a.approve_script:
                pipeline.log(db, lesson, "script_approval", "approved via CLI --approve-script (author review pending)", actor="cli:import_lesson")
                pipeline.approve_script(db, lesson, None, "CLI --approve-script")
        if a.stop_after_approval:
            print(f"final status: {lesson.status.value} (lesson id {lesson.id})")
            return
        if lesson.status in (S.SCRIPT_APPROVED, S.ASSETS_GENERATING):
            pipeline.run_assets(db, lesson)
        recs = {sid: ROOT / p for sid, p in b.get("recordings", {}).items()}
        if lesson.status in (S.ASSETS_READY, S.RENDERING):
            pipeline.run_render(db, lesson, recordings=recs)
        if lesson.status == S.QUALITY_CHECK:
            pipeline.run_quality(db, lesson)
        db.refresh(lesson)
        print(f"final status: {lesson.status.value}  (needs human video approval in the dashboard)" if lesson.status == S.APPROVAL_PENDING else f"final status: {lesson.status.value}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
