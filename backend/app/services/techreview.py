"""Independent technical review (Features C and D). A separate pipeline stage and (optionally) a separate local model.
The reviewer only produces findings; it never edits the script. Corrections are applied by a human via apply_correction()
which creates a new LessonScript revision."""
import json
import re
import threading
from datetime import timedelta
from typing import Literal

from pydantic import Field, ValidationError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Lesson, ResearchSource, ReviewFinding, ReviewRun, TechnicalClaim, now
from app.providers.llm import LLMError, LLMProvider, get_reviewer
from app.schemas.content import LessonScriptData, Strict
from app.services import claims as claims_mod, generation, research
from app.services import domains
from app.services.generation import _ask

Severity = Literal["critical", "high", "medium", "low", "info"]
Category = Literal["technical_correctness", "security_accuracy", "teaching_quality", "demonstration_quality", "outdated_information", "unsupported_claim",
                   "missing_citation", "needs_qualification"]
BLOCKING_SEVERITIES = {"critical", "high", "medium"}  # medium: correct it or record a documented human acceptance
# "no retrieved source mentions this" is not "this is wrong": such findings are shown but do not block by themselves.
# Critical claims lacking evidence still block through the claims gate (claims.claim_blocks), which a human can accept.
NON_BLOCKING_CATEGORIES = {"unsupported_claim", "missing_citation"}
NEEDS_CONTRADICTION = {"technical_correctness", "security_accuracy", "outdated_information"}  # categories that assert the script is wrong
_SEV = ["info", "low", "medium", "high", "critical"]
_NO_SOURCE = ("unsupported", "not supported", "no source", "not mentioned", "does not mention", "do not mention", "not found in")
SCRIPT_FIELDS = ["title", "hook", "introduction", "learning_objectives", "technical_explanation", "practical_demonstration",
                 "real_world_applications", "defensive_recommendations", "common_mistakes", "knowledge_check", "summary"]
CHUNKS = {
    "technical": ["technical_explanation", "practical_demonstration", "real_world_applications", "defensive_recommendations", "common_mistakes"],
    "teaching": ["title", "hook", "introduction", "learning_objectives", "summary", "knowledge_check"],
}
_LOCK = threading.Lock()


class ReviewBusy(RuntimeError):
    pass


class FindingOut(Strict):
    severity: Severity
    category: Category
    section: str = ""
    problem_text: str = Field(min_length=3, max_length=600)
    explanation: str = Field(min_length=3, max_length=1500)
    evidence: str = Field("", max_length=1500)
    recommended_correction: str = Field("", max_length=1500)
    objective: str = Field("", max_length=400)  # teaching_quality: the exact learning objective this text fails to meet
    why_objective_fails: str = Field("", max_length=800)  # teaching_quality: why the current text does not meet it
    blocks_approval: bool = False  # ignored: the server derives the real value (see decide_blocking)


class ReviewOut(Strict):
    findings: list[FindingOut] = Field(max_length=25)


def begin_run(db: Session, lesson: Lesson, kind: str, script_version: int, model: str, simulated: bool) -> ReviewRun:
    """Create the run row, refusing a second concurrent run for the lesson. A `running` row older than 3x the reviewer timeout is a crash leftover."""
    with _LOCK:
        stale = now() - timedelta(seconds=3 * get_settings().reviewer_timeout_s)
        for r in db.query(ReviewRun).filter_by(lesson_id=lesson.id, status="running"):
            ts = r.updated_at if r.updated_at.tzinfo else r.updated_at.replace(tzinfo=stale.tzinfo)
            if ts < stale:
                r.status, r.error, r.finished_at = "failed", "abandoned (process died while running)", now()
            else:
                raise ReviewBusy(f"a {r.kind} review is already running for lesson {lesson.id} (run {r.id})")
        run = ReviewRun(lesson_id=lesson.id, script_version=script_version, kind=kind, reviewer_model=model, simulated=simulated)
        db.add(run)
        db.commit()
        return run


def finish_run(db: Session, run_id: int, status: str, error: str = "", summary: dict | None = None):
    if status != "completed":
        db.rollback()  # discard half-written claims/findings of a failed run
    run = db.get(ReviewRun, run_id)
    run.status, run.error, run.finished_at = status, error[:2000], now()
    if summary is not None:
        run.summary = summary
    db.commit()


def _script_text(script: dict, names: list[str]) -> str:
    return "\n\n".join(f"### {n}\n{claims_mod.section_text(script, n) if n != 'knowledge_check' else json.dumps(script.get(n), ensure_ascii=False)}" for n in names if n in script)


def _source_context(sources: list[ResearchSource], query: str) -> str:
    out = []
    for s in [x for x in sources if x.verified][:5]:
        picks = research.best_sections(research.parse_sections(s.full_text), query, k=2)
        out.append(f"[source {s.id}] {s.title or s.url} ({s.publisher})\n" + "\n".join(f"- {h}: {t[:700]}" for h, t in picks))
    return "\n\n".join(out) or "(no verified sources were retrieved)"


def _locate(script: dict, text: str) -> str | None:
    """Field name containing `text` (whitespace-insensitive), or None."""
    want = claims_mod._norm(text)
    for k, v in script.items():
        blob = claims_mod._norm(json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v)
        if want and want in blob:
            return k
    return None


# ---------------- blocking policy (server-side; the model's own blocks_approval is ignored) ----------------
# Strict: a statement that is wrong, unsafe, outdated or a bad demonstration blocks at critical/high/medium.
STRICT_CATEGORIES = {"technical_correctness", "security_accuracy", "demonstration_quality", "outdated_information"}
COVERED = 0.7  # share of an objective's key terms that must appear in the script for the script to count as already covering it
_VAGUE = re.compile(r"\b(vague|unclear|could be clearer|more detail|more specific|specificity|too broad|too simple|too brief|not engaging|lacks? (context|depth))\b", re.I)


def _objective_match(objective: str, script: dict) -> str:
    """The script's own learning objective that `objective` refers to ('' if it matches none)."""
    want = research._tokens(objective)
    if not want:
        return ""
    best, best_o = 0.0, ""
    for o in script.get("learning_objectives") or []:
        ot = research._tokens(o)
        sc = len(want & ot) / max(1, min(len(want), len(ot)))
        if sc > best:
            best, best_o = sc, o
    return best_o if best >= 0.6 else ""


def _flatten(v) -> list[str]:
    if isinstance(v, str):
        return [v]
    if isinstance(v, dict):
        return [x for e in v.values() for x in _flatten(e)]
    if isinstance(v, list):
        return [x for e in v for x in _flatten(e)]
    return []


_FILLER = set("understand learn explain define describe explore identify apply gain know recognize discuss use using core key concept concepts basic basics fundamental "
              "fundamentals overview introduction importance significance practical knowledge real world modern their its".split())


def _stem(w: str) -> str:
    for suf in ("ing", "ed", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 4:
            return w[: -len(suf)]
    return w


def _terms(text: str) -> set[str]:
    """Content words of an objective or of the lesson body: lower-cased, light stemming, generic objective verbs removed."""
    return {_stem(t) for t in research._tokens(text) if t not in _FILLER}


def _coverage(objective: str, script: dict) -> float:
    """Share of the objective's key terms found anywhere in the lesson body."""
    body = " ".join(_flatten({k: v for k, v in script.items() if k not in ("learning_objectives", "references", "diagrams", "unverified_claims")}))
    ot, bt = _terms(objective), _terms(body)
    return len(ot & bt) / len(ot) if ot else 1.0


def decide_blocking(f: dict, script: dict, security: bool) -> tuple[bool, str, str]:
    """(blocks, objective, note) for one finding. Pure function; this is the only place that decides whether a finding blocks.
    - strict categories (wrong / unsafe / outdated / demonstration): critical, high and medium block.
    - teaching_quality blocks only with a concrete defect: the finding names one of the script's own objectives, says why the text fails it and
      gives a correction, AND (medium) the objective's key terms are demonstrably missing from the script, or (high/critical) the criticism is not
      merely 'vague/needs more detail' about a concept the script already contains. Everything else is advisory.
    - unsupported_claim / missing_citation / needs_qualification: block only in security domains at high/critical; elsewhere advisory
      (critical claims are handled by the claims gate)."""
    cat, sev = f["category"], f["severity"]
    if cat in STRICT_CATEGORIES:
        return sev in BLOCKING_SEVERITIES, "", f"{cat} at {sev}: strict category"
    if cat in NON_BLOCKING_CATEGORIES or cat == "needs_qualification":
        if security and sev in ("critical", "high"):
            return True, "", f"{cat} at {sev} in a security domain"
        return False, "", f"advisory: {cat} is tracked as a claim, and is not evidence that the text is wrong"
    # teaching_quality
    if sev in ("low", "info"):
        return False, "", "advisory: low-severity teaching feedback"
    objective = _objective_match(f.get("objective", ""), script)
    if not objective:
        return False, "", "advisory: does not name one of the script's learning objectives"
    if len((f.get("why_objective_fails") or "").strip()) < 20 or len((f.get("recommended_correction") or "").strip()) < 15:
        return False, objective, "advisory: no concrete reason the objective is unmet and/or no specific correction"
    cov = _coverage(objective, script)
    if sev == "medium":
        if cov < COVERED:
            return True, objective, f"objective not covered: only {cov:.0%} of its key terms appear in the script"
        return False, objective, f"advisory: the script already contains {cov:.0%} of the objective's key terms"
    if cov >= COVERED and _VAGUE.search(f["explanation"] + " " + f.get("why_objective_fails", "")):
        return False, objective, "advisory: asks for more detail about a concept the script already contains"
    return True, objective, f"concrete {sev} teaching defect against the objective (coverage {cov:.0%})"


def normalize(f: FindingOut, script: dict) -> dict | None:
    """Server-side shaping of one model finding. None if the quoted text is not in the current script (a finding that cannot be
    located cannot be corrected or verified)."""
    where = _locate(script, f.problem_text)
    if where is None:
        return None
    sev, cat = f.severity, f.category
    return {"severity": sev, "category": cat, "section": where, "problem_text": f.problem_text, "explanation": f.explanation,
            "evidence": f.evidence, "recommended_correction": f.recommended_correction, "objective": f.objective,
            "why_objective_fails": f.why_objective_fails, "blocks_approval": sev in BLOCKING_SEVERITIES, "policy_note": ""}


def _quiz_parts(script: dict) -> tuple[list[str], list[str]]:
    """(correct answers, distractors) of the knowledge check."""
    right, wrong = [], []
    for q in script.get("knowledge_check") or []:
        try:
            for i, o in enumerate(q["options"]):
                (right if i == q["answer_index"] else wrong).append(o)
        except (KeyError, TypeError):
            continue
    return right, wrong


def _same_text(a: str, b: str) -> bool:
    x, y = claims_mod._norm(a), claims_mod._norm(b)
    return len(x) >= 10 and len(y) >= 10 and (x == y or x in y or y in x)


def _has_source_evidence(f: dict, sources: list[ResearchSource]) -> bool:
    """True when the finding's evidence is a real quote from a retrieved source (so it can contradict the script, not merely be absent)."""
    ev = claims_mod._norm(f["evidence"])
    return len(ev) >= 30 and any(ev in claims_mod._norm(s.full_text) for s in sources if s.verified)


def refine(found: list[dict], script: dict, sources: list[ResearchSource], claim_rows: list[TechnicalClaim], domain: str = "") -> tuple[list[dict], dict]:
    """Deterministic precision pass over the reviewer's findings. Returns (kept, counts of what was dropped or re-classified)."""
    stats = {"not_in_script": 0, "quiz_distractor": 0, "duplicate_of_claim": 0, "duplicate": 0, "reclassified_unsupported": 0}
    _right, distractors = _quiz_parts(script)
    weak = [c for c in claim_rows if c.status != "supported" or c.critical]
    kept: list[dict] = []
    for f in found:
        f = dict(f)
        ambiguous = any(w in (f["explanation"] + f["evidence"]).lower() for w in ("also correct", "ambigu", "more than one", "plausible", "valid answer", "could also"))
        if any(_same_text(f["problem_text"], d) for d in distractors) and not (f["category"] == "teaching_quality" and ambiguous):
            stats["quiz_distractor"] += 1  # a distractor is wrong on purpose; only "it is also a valid answer" is a real problem with it
            continue
        says_no_source = any(w in (f["explanation"] + " " + f["evidence"]).lower() for w in _NO_SOURCE)
        if (f["category"] in NEEDS_CONTRADICTION and not _has_source_evidence(f, sources)) or (f["category"] == "teaching_quality" and says_no_source):
            f["category"] = "unsupported_claim"  # absence of evidence is not evidence of error
            stats["reclassified_unsupported"] += 1
        if f["category"] in NON_BLOCKING_CATEGORIES:
            if not domains.is_security(domain):
                f["severity"] = _SEV[min(_SEV.index(f["severity"]), _SEV.index("medium"))]
            if any(claims_mod.same_statement(c.text, f["problem_text"]) or _same_text(c.text, f["problem_text"]) for c in weak):
                stats["duplicate_of_claim"] += 1  # the claim table already tracks this statement and its evidence
                continue
        dup = next((k for k in kept if _same_text(k["problem_text"], f["problem_text"])), None)
        if dup:
            stats["duplicate"] += 1
            if _SEV.index(f["severity"]) > _SEV.index(dup["severity"]):
                dup.update(severity=f["severity"])
            continue
        kept.append(f)
    for f in kept:  # decided last, on the final category and severity, and never from anything the model said about blocking
        f["blocks_approval"], obj, f["policy_note"] = decide_blocking(f, script, domains.is_security(domain))
        f["objective"] = obj
        f.pop("why_objective_fails", None)
    stats["advisory"] = sum(1 for f in kept if not f["blocks_approval"])
    stats["blocking"] = len(kept) - stats["advisory"]
    return kept, stats


def review_script(llm: LLMProvider, script: dict, sources: list[ResearchSource], claim_rows: list[TechnicalClaim], domain: str = "") -> tuple[list[dict], dict]:
    weak = [f"- ({c.status}{', CRITICAL' if c.critical else ''}) [{c.section}] {c.text}" for c in claim_rows if c.status != "supported"]
    out, dropped = [], 0
    for chunk, names in CHUNKS.items():
        body = _script_text(script, names)
        prompt = (f"CHUNK: {chunk}\nSCRIPT SECTIONS:\n{body}\n\nCLAIM STATUS (claims not supported by retrieved sources):\n" + ("\n".join(weak) or "(none)")
                  + f"\n\nSOURCE EXCERPTS:\n{_source_context(sources, body[:1500])}")
        for f in _ask(llm, "tech_review", prompt, ReviewOut, domain=domain).findings:
            n = normalize(f, script)
            if n is None:
                dropped += 1
            else:
                out.append(n)
    kept, stats = refine(out, script, sources, claim_rows, domain)
    stats["not_in_script"] = dropped
    return kept, stats


def _archive_previous_run(db: Session, lesson_id: int, version: int, run_id: int) -> None:
    """A rerun on the same script version replaces the open findings and claims. Nothing is deleted: the older findings become `superseded`
    and the replaced claims are copied into the older run's summary, so the history stays inspectable."""
    older = db.query(ReviewRun).filter(ReviewRun.lesson_id == lesson_id, ReviewRun.script_version == version, ReviewRun.id != run_id).all()
    old_claims = db.query(TechnicalClaim).filter_by(lesson_id=lesson_id, script_version=version).all()
    if older and old_claims:
        last = max(older, key=lambda r: r.id)
        last.summary = {**(last.summary or {}), "claims_snapshot": [{"text": c.text, "status": c.status, "critical": c.critical, "section": c.section,
                                                                     "locations": c.locations, "source_ids": c.source_ids} for c in old_claims]}
    db.query(ReviewFinding).filter(ReviewFinding.lesson_id == lesson_id, ReviewFinding.script_version == version, ReviewFinding.run_id != run_id,
                                   ReviewFinding.status == "open").update({"status": "superseded"}, synchronize_session=False)


def run_review(db: Session, lesson: Lesson, llm: LLMProvider | None = None) -> dict:
    """Claims + reviewer for the latest script version. Raises on infrastructure failure (the run row is marked failed)."""
    script_row = generation.latest_script(lesson)
    if not script_row:
        raise LLMError("lesson has no script to review")
    llm = llm or get_reviewer()
    model = getattr(llm, "model", llm.name)
    simulated = llm.name.startswith("mock")
    run = begin_run(db, lesson, "technical", script_row.version, f"{llm.name}:{model}", simulated)
    run_id, model_label, version, content, dom = run.id, run.reviewer_model, script_row.version, script_row.content, domains.of_lesson(lesson).key
    try:
        sources = db.query(ResearchSource).filter_by(lesson_id=lesson.id).all()
        for src in sources:
            db.expunge(src)
        # The slow part (many local-model calls, 10+ minutes) runs with NO open transaction and no row locks, so approvals, finding decisions,
        # deletes and "run next" clicks are never queued behind a review. Everything is written at the end in one short transaction.
        judged = claims_mod.judge_claims(db, lesson, content, llm)
        claim_objs = [TechnicalClaim(**{k: c[k] for k in ("section", "text", "category", "critical", "status")}) for c in judged]
        found, refined = review_script(llm, content, sources, claim_objs, domain=dom)
        db.rollback()
        _archive_previous_run(db, lesson.id, version, run_id)
        rows = claims_mod.store_claims(db, lesson, version, run_id, judged)
        prior = {(f.severity, claims_mod._norm(f.problem_text)): f for f in db.query(ReviewFinding).filter_by(lesson_id=lesson.id, script_version=version)}
        for f in found:
            row = ReviewFinding(run_id=run_id, lesson_id=lesson.id, script_version=version, **f)
            old = prior.get((f["severity"], claims_mod._norm(f["problem_text"])))
            if old and old.status in ("rejected", "waived"):  # a human decision on identical text survives a rerun
                row.status, row.decided_by, row.decision_note = old.status, old.decided_by, old.decision_note
            db.add(row)
        by_sev = {s: sum(1 for f in found if f["severity"] == s) for s in ("critical", "high", "medium", "low", "info")}
        by_claim = {}
        for c in rows:
            by_claim[c.status] = by_claim.get(c.status, 0) + 1
        db.flush()
        finish_run(db, run_id, "completed", summary={"findings": by_sev, "claims": by_claim, "claims_total": len(rows), "sources": len(sources),
                                                     "sources_verified": sum(1 for s in sources if s.verified), "model": model_label, "simulated": simulated, "refined": refined})
    except (LLMError, ValidationError, ValueError) as e:
        finish_run(db, run_id, "failed", f"{type(e).__name__}: {e}")
        raise LLMError(f"technical review failed: {e}") from e
    except Exception as e:  # noqa: BLE001
        finish_run(db, run_id, "failed", f"{type(e).__name__}: {e}")
        raise
    return db.get(ReviewRun, run_id).summary


# ---------------- human decisions ----------------
class DecisionError(ValueError):
    pass


def apply_correction(db: Session, lesson: Lesson, finding: ReviewFinding, user_id: int | None, correction: str | None = None) -> int:
    """Replace the problematic text with the (possibly human-edited) correction and save a NEW script revision. Returns the version."""
    cur = generation.latest_script(lesson)
    if finding.script_version != cur.version:
        raise DecisionError(f"finding belongs to script v{finding.script_version}; latest is v{cur.version} - rerun the review")
    fix = (correction if correction is not None else finding.recommended_correction).strip()
    if not fix:
        raise DecisionError("finding has no recommended correction; edit the script manually")
    old = finding.problem_text.strip()
    if old and old[-1] not in ".!?" and fix[-1] in ".!?":  # the quote is a clause inside a longer sentence: do not end that sentence early
        fix = fix.rstrip(".!?")
    content = json.loads(json.dumps(cur.content))
    done = False

    def sub(v):
        nonlocal done
        if isinstance(v, str):
            if not done and old in v:
                done = True
                return v.replace(old, fix, 1)
            return v
        if isinstance(v, list):
            return [sub(x) for x in v]
        if isinstance(v, dict):
            return {k: sub(x) for k, x in v.items()}
        return v
    content = sub(content)
    if not done:
        raise DecisionError("problem text was not found verbatim in the script; edit the script manually")
    try:
        data = LessonScriptData.model_validate(content)
    except ValidationError as e:
        raise DecisionError(f"corrected script no longer validates: {str(e)[:300]}") from e
    row = generation.save_script(db, lesson, data, f"review-fix:user:{user_id}")
    row.change_note = f"applied correction for finding {finding.id} ({finding.severity}/{finding.category})"
    finding.status, finding.decided_by, finding.applied_version = "accepted", user_id, row.version
    db.flush()
    return row.version


def decide(db: Session, finding: ReviewFinding, user, decision: str, note: str = "") -> None:
    """reject = dismiss the finding as wrong/irrelevant (reason required). waive = accept the risk of a blocking finding without
    changing the script (reason required; Critical/High need an admin)."""
    if decision not in ("reject", "waive"):
        raise DecisionError("decision must be reject or waive")
    if len(note.strip()) < 10:
        raise DecisionError("a decision note of at least 10 characters is required")
    if decision == "waive" and finding.severity in ("critical", "high") and user.role != "admin":
        raise DecisionError("only an admin may waive a Critical or High finding")
    finding.status = "rejected" if decision == "reject" else "waived"
    finding.decided_by, finding.decision_note = user.id, note.strip()[:2000]
    db.flush()


def latest_run(db: Session, lesson_id: int, kind: str = "technical") -> ReviewRun | None:
    return db.query(ReviewRun).filter_by(lesson_id=lesson_id, kind=kind).order_by(ReviewRun.id.desc()).first()
