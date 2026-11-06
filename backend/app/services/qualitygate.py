"""Pre-render quality gate (Feature E). Blocking, not advisory: run_assets refuses to start TTS, run_render refuses to render
and publishing refuses to upload unless the latest stored gate result for the CURRENT script and storyboard versions passed.

Two stages: "script" (content, sources, claims, technical review; evaluated before human approval) and
"pre_tts" (adds human approval, storyboard length/placeholders/repetition)."""
import re
from datetime import timezone

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import (Approval, Lesson, QualityGateResult, ResearchSource, ReviewFinding, TechnicalClaim)
from app.schemas.content import StoryboardData
from app.services import claims as claims_mod, generation, lengthplan, research, techreview

MIN_DEMO_WORDS, MIN_DEFENSE_WORDS, MIN_SUMMARY_WORDS = 40, 30, 15
_PLACEHOLDER = re.compile(r"\b(?:lorem ipsum|todo|tbd|xxx|placeholder|your text here)\b|\[insert|<narration", re.I)


def _chk(name: str, ok: bool, detail: str = "", blocking: bool = True) -> dict:
    return {"check": name, "passed": bool(ok), "detail": detail, "blocking": blocking}


def _strings(v):
    if isinstance(v, str):
        yield v
    elif isinstance(v, dict):
        for x in v.values():
            yield from _strings(x)
    elif isinstance(v, list):
        for x in v:
            yield from _strings(x)


def _words(s: str) -> int:
    return len(s.split())


def script_checks(db: Session, lesson: Lesson, require_approval: bool) -> tuple[list[dict], int]:
    cur = generation.latest_script(lesson)
    if not cur:
        return [_chk("script_exists", False, "no script")], 0
    sc, v, prod = cur.content, cur.version, get_settings().app_env == "production"
    c = []
    mock = cur.generated_by.startswith("mock")  # template content is exempt from DEPTH checks only (same convention as lengthplan.length_check)
    # --- completeness
    missing = [f for f in ("hook", "introduction", "learning_objectives", "technical_explanation", "practical_demonstration",
                           "defensive_recommendations", "summary", "references") if not sc.get(f) or (isinstance(sc[f], str) and not sc[f].strip())]
    c.append(_chk("required_sections_present", not missing, f"missing/empty: {missing}" if missing else "all required sections have content"))
    c.append(_chk("practical_demonstration", _words(sc.get("practical_demonstration", "")) >= MIN_DEMO_WORDS, f"{_words(sc.get('practical_demonstration', ''))} words (min {MIN_DEMO_WORDS})", not mock))
    c.append(_chk("defense_and_mitigation", _words(sc.get("defensive_recommendations", "")) >= MIN_DEFENSE_WORDS, f"{_words(sc.get('defensive_recommendations', ''))} words (min {MIN_DEFENSE_WORDS})", not mock))
    c.append(_chk("conclusion", _words(sc.get("summary", "")) >= MIN_SUMMARY_WORDS, f"{_words(sc.get('summary', ''))} words (min {MIN_SUMMARY_WORDS})", not mock))
    c.append(_chk("knowledge_check", bool(sc.get("knowledge_check")) or not lesson.knowledge_checks, "quiz present" if sc.get("knowledge_check") else "lesson configures knowledge checks but the script has none"))
    body = " ".join(_strings({k: v_ for k, v_ in sc.items() if k not in ("learning_objectives", "references", "diagrams", "unverified_claims")})).lower()
    bt = research._tokens(body)
    weak = []
    for o in sc.get("learning_objectives", []):
        ot = research._tokens(o)
        if ot and len(ot & bt) / len(ot) < 0.4:
            weak.append(o[:80])
    c.append(_chk("objectives_covered", not weak, f"objectives not reflected in the lesson body: {weak}" if weak else "every objective's key terms appear in the body", not mock))
    # --- content quality
    ph = sorted({m.group(0).lower() for s in _strings(sc) for m in [_PLACEHOLDER.search(s)] if m})
    c.append(_chk("no_placeholder_text", not ph, f"placeholder markers: {ph}" if ph else ""))
    empty = [k for k, val in sc.items() if isinstance(val, str) and not val.strip()]
    c.append(_chk("no_empty_fields", not empty, f"empty: {empty}" if empty else ""))
    seen, dup = {}, []
    for field, val in sc.items():
        if field in ("references", "diagrams", "knowledge_check", "unverified_claims"):
            continue
        for s_ in re.split(r"(?<=[.!?])\s+", "\n".join(_strings(val))):
            k = claims_mod._norm(s_)
            if len(k) >= 60:
                if k in seen:
                    dup.append(s_[:80])
                seen[k] = field
    c.append(_chk("no_repeated_paragraphs", not dup, f"repeated sentences: {dup[:3]}" if dup else ""))
    # --- references
    srcs = {s.url: s for s in db.query(ResearchSource).filter_by(lesson_id=lesson.id)}
    bad = []
    for r in sc.get("references", []):
        s = srcs.get(r["url"]) or next((x for u, x in srcs.items() if research.canonical_url(u) == research.canonical_url(r["url"])), None)
        if not r["url"].startswith("https://") or not research.host_allowed(r["url"]):
            bad.append(f"{r['url']} (not an allowed https source)")
        elif s is None:
            bad.append(f"{r['url']} (never retrieved)")
        elif not s.verified and (s.status != "offline" or prod):
            bad.append(f"{r['url']} ({s.status})")
    c.append(_chk("references_valid", not bad, f"unusable references: {bad}" if bad else f"{len(sc.get('references', []))} references retrieved"))
    # --- technical review
    run = techreview.latest_run(db, lesson.id)
    done = bool(run and run.status == "completed")
    c.append(_chk("review_completed", done, f"latest review: {run.status if run else 'never run'}"
                  + (f" ({run.error[:120]})" if run and run.error else "")))
    current = bool(run and run.script_version == v)
    c.append(_chk("review_current", done and current, f"review covers script v{run.script_version if run else '-'}; latest script is v{v}" if run else "no review"))
    sim = bool(run and run.simulated)
    c.append(_chk("review_by_real_model", not (sim and prod), "review was produced by the mock LLM (simulated) - allowed only outside production" if sim else f"reviewer: {run.reviewer_model if run else '-'}"))
    openf = db.query(ReviewFinding).filter_by(lesson_id=lesson.id, script_version=v, status="open").all()
    blocking = [f for f in openf if f.blocks_approval]
    c.append(_chk("no_unresolved_blocking_findings", not blocking,
                  "; ".join(f"#{f.id} {f.severity}: {f.problem_text[:60]}" for f in blocking) if blocking else f"{len(openf)} open non-blocking findings"))
    cl = db.query(TechnicalClaim).filter_by(lesson_id=lesson.id, script_version=v).all()
    blk = [x for x in cl if claims_mod.claim_blocks(x)]
    c.append(_chk("no_unsupported_critical_claims", not blk, "; ".join(f"#{x.id} {x.status}: {x.text[:60]}" for x in blk) if blk else f"{len(cl)} claims checked, {sum(1 for x in cl if x.status == 'supported')} supported"))
    # --- human approval (pre_tts only)
    if require_approval:
        last = db.query(Approval).filter_by(lesson_id=lesson.id, stage="script").order_by(Approval.id.desc()).first()
        ok = bool(last and last.decision == "APPROVED" and _after(last.created_at, cur.created_at))
        c.append(_chk("human_script_approval", ok, "script approved by a human reviewer" if ok else "no human approval of the latest script version"))
    return c, v


def _utc(t):
    return t.astimezone(timezone.utc) if t.tzinfo else t.replace(tzinfo=timezone.utc)  # naive = UTC (how app.models.now() stamps rows)


def _after(a, b) -> bool:
    """a >= b as instants. Rows created in this session carry UTC; rows loaded from Postgres carry the connection's zone."""
    return _utc(a) >= _utc(b)


def storyboard_checks(db: Session, lesson: Lesson, sb: StoryboardData, generated_by: str) -> list[dict]:
    c = []
    problems = lengthplan.preflight(sb, lesson.estimated_minutes, generated_by, lesson.draft)  # placeholders, empty narration, repetition, markup, unsupported claims, diagrams, length
    c.append(_chk("storyboard_preflight", not problems, "; ".join(problems[:5]) if problems else "narration, repetition, diagrams and length are acceptable"))
    est, words = lengthplan.estimate_seconds(sb), lengthplan.word_count(sb)
    mock = generated_by.startswith("mock")
    lo, hi = lengthplan.window(lesson.estimated_minutes, lesson.draft)
    c.append(_chk("estimated_duration", lo <= est <= hi or mock, f"estimated {est / 60:.1f} min ({words} words at {lengthplan.WPS:.2f} w/s); window {lo / 60:.1f}-{hi / 60:.1f} min" + (" [mock: not enforced]" if mock else "")))
    types = {s.type for s in sb.scenes}
    sbrow = generation.latest_storyboard(db, lesson)
    cur = generation.latest_script(lesson)
    fresh = not (sbrow and cur) or _after(sbrow.created_at, cur.created_at)
    c.append(_chk("storyboard_matches_script", fresh, "storyboard was built after the latest script version" if fresh else "script changed after the storyboard was built - regenerate the storyboard"))
    c.append(_chk("storyboard_has_demo", bool(types & {"code", "terminal", "browser"}), f"scene types: {sorted(types)}", blocking=not mock))
    c.append(_chk("storyboard_has_quiz", "quiz" in types or not lesson.knowledge_checks, "quiz scene present" if "quiz" in types else "lesson configures knowledge checks but no quiz scene"))
    c.append(_chk("storyboard_has_summary", "summary" in types or sb.scenes[-1].type == "instructor", "closing summary present"))
    return c


def evaluate(db: Session, lesson: Lesson, stage: str, sb_row=None) -> QualityGateResult:
    """Run and STORE a gate result. stage: "script" | "pre_tts"."""
    checks, ver = script_checks(db, lesson, require_approval=(stage == "pre_tts"))
    sbv = None
    if stage == "pre_tts":
        sb_row = sb_row or generation.latest_storyboard(db, lesson)
        if sb_row is None:
            checks.append(_chk("storyboard_exists", False, "no storyboard"))
        else:
            sbv = sb_row.version
            cur = generation.latest_script(lesson)
            checks += storyboard_checks(db, lesson, StoryboardData.model_validate(sb_row.data), cur.generated_by if cur else "")
    passed = all(x["passed"] for x in checks if x["blocking"])
    res = QualityGateResult(lesson_id=lesson.id, stage=stage, script_version=ver, storyboard_version=sbv, passed=passed, checks=checks)
    db.add(res)
    db.flush()
    return res


class GateBlocked(RuntimeError):
    """Raised when the gate fails. The pipeline treats it as 'stopped, fix the content', not as a crash (no retry is consumed)."""


def enforce(db: Session, lesson: Lesson, stage: str = "pre_tts") -> QualityGateResult:
    """Evaluate, STORE (committed even though the caller will raise) and raise GateBlocked if any blocking check fails."""
    res = evaluate(db, lesson, stage)
    db.commit()
    if not res.passed:
        raise GateBlocked("quality gate blocked: " + "; ".join(blocking_reasons(res))[:1500])
    return res


def enforce_draft(db: Session, lesson: Lesson) -> QualityGateResult:
    """Gate for a quick draft: ONLY the storyboard checks (length, repetition, placeholders, diagrams, quiz/summary present). Nothing about sources,
    review or approval, because a draft has none. The result is stored under stage 'draft', which can never satisfy the 'pre_tts' gate that
    publishing requires."""
    sb_row = generation.latest_storyboard(db, lesson)
    cur = generation.latest_script(lesson)
    if sb_row is None:
        checks = [_chk("storyboard_exists", False, "no storyboard")]
    else:
        checks = storyboard_checks(db, lesson, StoryboardData.model_validate(sb_row.data), cur.generated_by if cur else "")
    res = QualityGateResult(lesson_id=lesson.id, stage="draft", script_version=cur.version if cur else 0, storyboard_version=sb_row.version if sb_row else None,
                            passed=all(x["passed"] for x in checks if x["blocking"]), checks=checks)
    db.add(res)
    db.commit()
    if not res.passed:
        raise GateBlocked("draft blocked: " + "; ".join(blocking_reasons(res))[:1500])
    return res


def latest_passed(db: Session, lesson: Lesson, stage: str = "pre_tts") -> bool:
    """True only if the newest stored gate result of `stage` passed for the current script AND storyboard versions."""
    r = db.query(QualityGateResult).filter_by(lesson_id=lesson.id, stage=stage).order_by(QualityGateResult.id.desc()).first()
    cur, sb = generation.latest_script(lesson), generation.latest_storyboard(db, lesson)
    return bool(r and r.passed and cur and r.script_version == cur.version and sb and r.storyboard_version == sb.version)


def blocking_reasons(res: QualityGateResult) -> list[str]:
    return [f"{x['check']}: {x['detail']}" for x in res.checks if x["blocking"] and not x["passed"]]


def review_state(db: Session, lesson: Lesson) -> dict:
    """Dashboard status: pending | running | failed | human_review_required | passed | approved_for_rendering (+ blocked flag, reasons)."""
    run = techreview.latest_run(db, lesson.id)
    if db.query(techreview.ReviewRun).filter_by(lesson_id=lesson.id, status="running").first():
        return {"state": "running", "blocked": True, "reasons": ["review in progress"]}
    if run is None:
        return {"state": "pending", "blocked": True, "reasons": ["technical review has not run"]}
    if run.status == "failed":
        return {"state": "failed", "blocked": True, "reasons": [run.error[:300] or "review failed"]}
    checks, _ = script_checks(db, lesson, require_approval=True)
    reasons = [f"{x['check']}: {x['detail']}" for x in checks if x["blocking"] and not x["passed"]]
    human = [x for x in checks if x["check"] in ("no_unresolved_blocking_findings", "no_unsupported_critical_claims") and not x["passed"]]
    if not reasons:
        return {"state": "approved_for_rendering", "blocked": False, "reasons": []}
    if human:
        return {"state": "human_review_required", "blocked": True, "reasons": reasons}
    only_approval = [x for x in checks if x["blocking"] and not x["passed"]]
    if len(only_approval) == 1 and only_approval[0]["check"] == "human_script_approval":
        return {"state": "passed", "blocked": True, "reasons": reasons}  # review is clean, waiting for the human approval click
    return {"state": "failed", "blocked": True, "reasons": reasons}
