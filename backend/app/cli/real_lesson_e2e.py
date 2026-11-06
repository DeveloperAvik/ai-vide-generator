"""Real end-to-end lesson with the LOCAL model only: research -> script -> storyboard (section by section) -> Piper -> render -> QC.
Usage: python -m app.cli.real_lesson_e2e "<topic>" <minutes> [resume_lesson_id [regen]]
Writes a metrics report to storage/manifests/e2e_<lessonid>.json. The script-approval gate is passed programmatically here
(test harness only, logged as such); the VIDEO approval gate is never touched."""
import json
import subprocess
import sys
import time

from app.core.config import ROOT, get_settings
from app.core.db import Base, SessionLocal, engine
from app.models import Course, Lesson, LessonStatus as S, Module, VideoRender, VoiceGeneration
from app.providers.llm import OllamaProvider
from app.schemas.content import StoryboardData
from app.services import generation, lengthplan, pipeline
from app.services.storage import get_storage
from app.utils import media


def mem() -> dict:
    """RSS of the Ollama model runner + macOS free-memory percentage at this instant."""
    ps = subprocess.run(["ps", "-axo", "rss,command"], capture_output=True, text=True).stdout
    runner = sum(int(l.split()[0]) for l in ps.splitlines() if "llama-server" in l or "ollama runner" in l) // 1024
    out = subprocess.run(["memory_pressure"], capture_output=True, text=True).stdout
    free = next((l.split(":")[1].strip() for l in out.splitlines() if "free percentage" in l), "?")
    return {"ollama_runner_mb": runner, "system_free": free}


def main(topic: str, minutes: int, resume_id: int | None = None, regen: bool = False) -> int:
    s = get_settings()
    Base.metadata.create_all(engine)
    db = SessionLocal()
    llm = OllamaProvider(s.ollama_url, s.ollama_model)
    rep: dict = {"model": s.ollama_model, "topic": topic, "requested_minutes": minutes, "stages": {}, "memory": {}}

    def timed(name, fn):
        t = time.time()
        rep["memory"][f"before_{name}"] = mem()
        try:
            fn()
            rep["stages"][name] = {"seconds": round(time.time() - t, 1), "ok": True}
        except Exception as e:  # noqa: BLE001
            rep["stages"][name] = {"seconds": round(time.time() - t, 1), "ok": False, "error": f"{type(e).__name__}: {e}"[:600]}
            raise
        finally:
            rep["memory"][f"after_{name}"] = mem()
            print(name, rep["stages"].get(name), flush=True)

    try:
        if resume_id:  # continue an interrupted run: approved script and cached valid sections are reused
            l = db.get(Lesson, resume_id)
            rep["resumed_lesson"] = True
            if l.status == S.FAILED:
                l.status = S(l.last_good_status); l.retry_count = 0; db.commit()
            sbrow = generation.latest_storyboard(db, l)
            try:
                StoryboardData.model_validate(sbrow.data)
                if regen:
                    sbrow = None
            except Exception:  # noqa: BLE001 - saved under an older schema
                sbrow = None
        else:
            c = db.query(Course).filter_by(name="Phase 2 Validation").first() or Course(name="Phase 2 Validation", description="local-model validation", language="English")
            m = Module(title=f"Run {int(time.time())}", position=len(c.modules)); c.modules.append(m)
            l = Lesson(title=topic, summary=f"Introductory lesson on {topic}", estimated_minutes=minutes, category="Phase 2 Validation"); m.lessons.append(l)
            db.add(c); db.commit()
            rep["lesson_id"] = l.id
            timed("research", lambda: pipeline.run_research(db, l, online=True))
            timed("script", lambda: pipeline.run_script(db, l, llm))
            timed("technical_review", lambda: pipeline.run_technical_review(db, l, online=True))
            pipeline.log(db, l, "script_approval", "approved by e2e test harness (not a human review)", actor="cli:real_lesson_e2e")
            pipeline.approve_script(db, l, None, "e2e harness")
            sbrow = None
        rep["lesson_id"] = l.id
        if sbrow is None:
            timed("storyboard", lambda: generation.generate_storyboard(db, l, llm) and db.commit())
        sb = generation.latest_storyboard(db, l)
        rep["narration_words"] = sum(len(x.narration.split()) for x in sb.scenes)
        rep["scenes"] = len(sb.scenes)
        timed("assets_tts", lambda: pipeline.run_assets(db, l, llm))
        rep["audio_seconds_measured"] = round(sum(v.duration_seconds for v in db.query(VoiceGeneration).filter_by(lesson_id=l.id)), 1)
        timed("render", lambda: pipeline.run_render(db, l))
        r = db.query(VideoRender).filter_by(lesson_id=l.id, status="done").order_by(VideoRender.id.desc()).first()
        video = get_storage().path(r.video_path)
        info = media.probe(video)
        v = next(x for x in info["streams"] if x["codec_type"] == "video"); a = next(x for x in info["streams"] if x["codec_type"] == "audio")
        rep["video"] = {"path": str(video), "seconds_ffprobe": round(float(info["format"]["duration"]), 1), "size_mb": round(video.stat().st_size / 1e6, 1),
                        "resolution": f"{v['width']}x{v['height']}", "fps": v["r_frame_rate"], "video_codec": v["codec_name"], "audio_codec": a["codec_name"],
                        "srt": str(get_storage().path(r.srt_path))}
        timed("quality_check", lambda: pipeline.run_quality(db, l))
        rep["final_status"] = db.get(Lesson, l.id).status.value
        rep["result"] = "PASS"
    except Exception as e:  # noqa: BLE001
        rep["result"] = f"FAIL: {type(e).__name__}: {e}"[:800]
        db.rollback()
    finally:
        rep["llm_usage"] = llm.usage
        rep["words_budget_target"] = lengthplan.target_words(minutes)
        if rep.get("lesson_id"):
            lesson = db.get(Lesson, rep["lesson_id"])
            rep["final_status"] = lesson.status.value
            rep["last_error"] = lesson.last_error
        out = ROOT / "storage" / "manifests" / f"e2e_{rep.get('lesson_id', 'x')}.json"
        out.write_text(json.dumps(rep, indent=2))
        print(json.dumps(rep, indent=2))
        db.close()
    return 0 if rep["result"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]) if len(sys.argv) > 3 else None, len(sys.argv) > 4 and sys.argv[4] == "regen"))
