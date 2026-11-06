"""Real end-to-end lesson with the LOCAL model only, through the review pipeline:
research (live official pages) -> script -> claims + independent review -> gate -> [storyboard -> TTS -> render -> QC].
Usage: python -m app.cli.real_review_e2e "<topic>" <minutes> [writer_model] [reviewer_model]
It never waives or accepts findings and never approves a lesson that the gate blocks. If (and only if) the script gate passes,
the human script approval is recorded programmatically and LOGGED AS THE HARNESS, not as a person; the video approval gate is never touched.
Report: storage/manifests/e2e_review_<lesson id>.json"""
import json
import sys
import time

from app.core.config import ROOT, get_settings
from app.core.db import SessionLocal
from app.models import (Course, Lesson, Module, QualityGateResult, ResearchSource, ReviewFinding, TechnicalClaim, VideoRender, VoiceGeneration)
from app.providers.llm import OllamaProvider
from app.services import generation, lengthplan, pipeline, qualitygate, techreview
from app.services.storage import get_storage
from app.utils import media


def main(topic: str, minutes: int, writer_model: str, reviewer_model: str) -> int:
    s = get_settings()
    db = SessionLocal()
    writer = OllamaProvider(s.ollama_url, writer_model)
    reviewer = OllamaProvider(s.ollama_url, reviewer_model)
    reviewer.timeout = s.reviewer_timeout_s
    t0 = time.time()
    rep: dict = {"topic": topic, "requested_minutes": minutes, "writer_model": writer_model, "reviewer_model": reviewer_model, "stages": {}, "ran": {}}

    def timed(name, fn):
        t = time.time()
        try:
            fn()
            rep["stages"][name] = {"seconds": round(time.time() - t, 1), "ok": True}
        except Exception as e:  # noqa: BLE001
            rep["stages"][name] = {"seconds": round(time.time() - t, 1), "ok": False, "error": f"{type(e).__name__}: {e}"[:700]}
            raise
        finally:
            print(name, rep["stages"].get(name), flush=True)

    l = None
    try:
        c = db.query(Course).filter_by(name="Review Pipeline Validation").first() or Course(name="Review Pipeline Validation", description="source-backed review validation", language="English")
        m = Module(title=f"Run {int(time.time())}", position=len(c.modules)); c.modules.append(m)
        l = Lesson(title=topic, summary=f"Introductory lesson on {topic}", estimated_minutes=minutes, category="Review Validation"); m.lessons.append(l)
        db.add(c); db.commit()
        rep["lesson_id"] = l.id
        timed("research", lambda: pipeline.run_research(db, l, online=True))
        timed("script", lambda: pipeline.run_script(db, l, writer))
        try:
            timed("technical_review", lambda: pipeline.run_technical_review(db, l, online=True, reviewer=reviewer))
        finally:
            rep["ran"]["technical_review"] = techreview.latest_run(db, l.id) is not None
        db.refresh(l)
        gate = qualitygate.evaluate(db, l, "script")
        db.commit()
        rep["script_gate"] = {"passed": gate.passed, "blocking": qualitygate.blocking_reasons(gate)}
        if not gate.passed:
            rep["result"] = "STOPPED_AT_GATE: script gate blocked (as designed); needs human review in the dashboard"
            rep["ran"].update(tts=False, render=False)
            return 2
        pipeline.log(db, l, "script_approval", "approved by the e2e harness (not a human review); gate had passed", actor="cli:real_review_e2e")
        pipeline.approve_script(db, l, None, "e2e harness")
        timed("storyboard", lambda: generation.generate_storyboard(db, l, writer) and db.commit())
        pre = qualitygate.evaluate(db, l, "pre_tts")
        db.commit()
        rep["pre_tts_gate"] = {"passed": pre.passed, "blocking": qualitygate.blocking_reasons(pre), "checks": [(x["check"], x["passed"]) for x in pre.checks]}
        try:
            timed("assets_tts", lambda: pipeline.run_assets(db, l, writer))
            rep["ran"]["tts"] = True
        except pipeline.GateStop as e:
            rep["ran"].update(tts=False, render=False)
            rep["result"] = f"STOPPED_AT_PRE_TTS_GATE: {e}"[:900]
            return 2
        rep["audio_seconds_measured"] = round(sum(v.duration_seconds for v in db.query(VoiceGeneration).filter_by(lesson_id=l.id)), 1)
        timed("render", lambda: pipeline.run_render(db, l))
        rep["ran"]["render"] = True
        r = db.query(VideoRender).filter_by(lesson_id=l.id, status="done").order_by(VideoRender.id.desc()).first()
        video = get_storage().path(r.video_path)
        info = media.probe(video)
        rep["video"] = {"path": str(video), "seconds_ffprobe": round(float(info["format"]["duration"]), 1), "size_mb": round(video.stat().st_size / 1e6, 1)}
        timed("quality_check", lambda: pipeline.run_quality(db, l))
        rep["result"] = "PASS"
        return 0
    except Exception as e:  # noqa: BLE001
        db.rollback()
        rep.setdefault("result", f"FAIL: {type(e).__name__}: {e}"[:900])
        return 1
    finally:
        if l is not None:
            db.expire_all()
            rep["sources"] = [{"id": x.id, "title": x.title, "publisher": x.publisher, "category": x.category, "status": x.status, "verified": x.verified, "hash": x.content_hash[:12], "url": x.url}
                              for x in db.query(ResearchSource).filter_by(lesson_id=l.id)]
            cl = db.query(TechnicalClaim).filter_by(lesson_id=l.id).all()
            rep["claims"] = {"total": len(cl), "by_status": {k: sum(1 for c in cl if c.status == k) for k in sorted({c.status for c in cl})},
                             "unsupported_or_worse": [{"status": c.status, "critical": c.critical, "section": c.section, "text": c.text[:200], "notes": c.reviewer_notes[:200]} for c in cl if c.status != "supported"]}
            fs = db.query(ReviewFinding).filter_by(lesson_id=l.id).all()
            rep["findings"] = {"by_severity": {k: sum(1 for f in fs if f.severity == k) for k in ("critical", "high", "medium", "low", "info")},
                               "items": [{"severity": f.severity, "category": f.category, "section": f.section, "problem": f.problem_text[:200], "explanation": f.explanation[:250], "blocks": f.blocks_approval} for f in fs]}
            run = techreview.latest_run(db, l.id)
            rep["review_run"] = {"status": run.status, "model": run.reviewer_model, "simulated": run.simulated, "error": run.error[:300], "summary": run.summary} if run else None
            lesson = db.get(Lesson, l.id)
            rep["final_status"], rep["last_error"] = lesson.status.value, lesson.last_error[:500]
        rep["llm_usage"] = {"writer": writer.usage, "reviewer": reviewer.usage}
        rep["total_runtime_seconds"] = round(time.time() - t0, 1)
        out = ROOT / "storage" / "manifests" / f"e2e_review_{rep.get('lesson_id', 'x')}.json"
        out.write_text(json.dumps(rep, indent=2, default=str))
        print(json.dumps(rep, indent=2, default=str))
        db.close()


if __name__ == "__main__":
    w = sys.argv[3] if len(sys.argv) > 3 else "qwen2.5:7b-instruct"
    sys.exit(main(sys.argv[1], int(sys.argv[2]), w, sys.argv[4] if len(sys.argv) > 4 else w))
