"""Claim-to-source mapping (Feature B).

The LLM proposes claims and judges them against passages that were actually retrieved. A claim is stored as `supported`
only if the model's quoted evidence is found verbatim in the stored text of a source of THIS lesson and overlaps the
claim; otherwise it is downgraded. This is a retrieval-grounded check, not proof of technical truth."""
import hashlib
import re
from typing import Literal

from pydantic import Field
from sqlalchemy.orm import Session

from app.models import Lesson, ResearchSource, TechnicalClaim
from app.providers.llm import LLMError, LLMProvider
from app.schemas.content import Strict
from app.services import research
from app.services import domains
from app.services.generation import _ask

Category = Literal["vulnerability_mechanism", "protocol", "tool_behavior", "remediation", "impact", "statistic_or_date", "general",
                   "definition", "application", "best_practice"]
Status = Literal["supported", "partially_supported", "unsupported", "contradicted", "needs_human_review"]
CLAIM_SECTIONS = ["hook", "introduction", "technical_explanation", "practical_demonstration", "real_world_applications",
                  "defensive_recommendations", "common_mistakes", "summary"]
CRITICAL_CATEGORIES = {"remediation"}  # critical by category only in security domains; elsewhere the model must flag it (see is_critical)
SIMILAR = 0.8  # token-set similarity above which two claims count as the same statement
BLOCKING = {"unsupported", "contradicted", "needs_human_review"}  # for critical claims, unless a human accepted them
MIN_QUOTE = 30
MIN_OVERLAP = 0.3
MIN_CONFIDENCE = 0.6
MAX_PER_SECTION = 12  # schema tolerance; only the first MAX_KEPT_PER_SECTION are judged
MAX_KEPT_PER_SECTION = 5
MAX_CLAIMS = 24  # critical claims first; bounds review time on small local models


class ClaimIn(Strict):
    text: str = Field(min_length=15, max_length=600)
    category: Category = "general"
    critical: bool = False


class ClaimList(Strict):
    claims: list[ClaimIn] = Field(max_length=MAX_PER_SECTION)


class Judgement(Strict):
    verdict: Literal["supported", "partially_supported", "unsupported", "contradicted"]
    source_id: int | None = None
    evidence_quote: str = ""
    notes: str = ""
    confidence: float = Field(0.5, ge=0, le=1)


def _norm(t: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[\"'“”‘’`]", "", t)).strip().lower()


def section_text(script: dict, name: str) -> str:
    v = script.get(name, "")
    return "\n".join(v) if isinstance(v, list) else str(v)


def _windows(text: str, claim: str, size: int = 3) -> tuple[float, str]:
    sents = re.split(r"(?<=[.!?])\s+", text)
    q = research._tokens(claim)
    best, best_i = 0.0, 0
    for i in range(len(sents)):
        sc = len(q & research._tokens(" ".join(sents[i:i + size]))) / max(1, len(q))
        if sc > best:
            best, best_i = sc, i
    return best, " ".join(sents[best_i:best_i + size])[:1500]


def candidates(claim: str, sources: list[ResearchSource], k: int = 3) -> list[dict]:
    """Deterministic retrieval of the passages most similar to the claim, across all verified sources of the lesson."""
    out = []
    for s in sources:
        if not s.verified or not s.full_text:
            continue
        for head, body in research.parse_sections(s.full_text):
            sc, passage = _windows(body, claim)
            if sc >= 0.2:
                out.append({"source_id": s.id, "heading": head, "score": sc, "passage": passage})
    return sorted(out, key=lambda c: -c["score"])[:k]


_NOT_A_CLAIM = re.compile(r"^(imagine|picture this|think of|let'?s|let us|in this (lesson|video)|today|welcome|we'?ll|we will|next,|first,|finally,|remember)\b|\b(is like|are like|as if|similar to a|think of it as)\b", re.I)
_STOP = set("a an the of to in on for and or is are be it its this that with as by can should must will from at into than then".split())


def is_checkable(text: str) -> bool:
    """False for text that is not a checkable statement: questions, teaching transitions, analogies, fragments."""
    t = text.strip()
    return len(t.split()) >= 5 and not t.endswith("?") and not _NOT_A_CLAIM.search(t)


def _sig(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in _STOP}


def same_statement(a: str, b: str) -> bool:
    x, y = _sig(a), _sig(b)
    return bool(x and y) and len(x & y) / min(len(x), len(y)) >= SIMILAR and len(x & y) / len(x | y) >= 0.6


def dedupe(claims: list[dict]) -> list[dict]:
    """Merge claims that state the same thing; the first keeps its wording and every script location it appears in is kept in `locations`."""
    out: list[dict] = []
    for c in claims:
        hit = next((u for u in out if same_statement(u["text"], c["text"])), None)
        if hit is None:
            out.append({**c, "locations": [c["section"]]})
            continue
        if c["section"] not in hit["locations"]:
            hit["locations"].append(c["section"])
        hit["critical"] = hit["critical"] or c["critical"]
    return out


def is_critical(c: ClaimIn, domain: str) -> bool:
    """Safety-critical claims block the gate. In security domains remediation advice is critical by category; elsewhere only when the model says so."""
    return c.critical or (c.category in CRITICAL_CATEGORIES and domains.is_security(domain))


_META_ANSWER = re.compile(r"^\s*(both|all|none|neither|any)\b|\b(of the above|a and b|a or b|a, b)\b", re.I)


def quiz_claims(script: dict) -> list[dict]:
    """The CORRECT answer of each quiz question is a statement we teach, so it is checked. Distractors are wrong on purpose and never are.
    An answer that only points at other options ("Both A and B", "None of the above") says nothing checkable on its own and is skipped."""
    out = []
    for q in script.get("knowledge_check") or []:
        try:
            ans = q["options"][q["answer_index"]]
        except (KeyError, IndexError, TypeError):
            continue
        if _META_ANSWER.search(ans):
            continue
        out.append({"section": "knowledge_check", "text": f"{q['question'].strip()} Answer: {ans.strip()}", "category": "general", "critical": False})
    return out


def extract_claims(llm: LLMProvider, script: dict, domain: str = "") -> list[dict]:
    out = []
    for name in CLAIM_SECTIONS:
        text = section_text(script, name).strip()
        if len(text.split()) < 12:
            continue
        res = _ask(llm, "claim_extract", f"SECTION: {name}\nTEXT:\n{text}", ClaimList, domain=domain)
        for c in res.claims[:MAX_KEPT_PER_SECTION]:
            tk = research._tokens(c.text)
            if not is_checkable(c.text):
                continue
            if _norm(c.text) in _norm(text) or len(tk & research._tokens(text)) >= 0.8 * len(tk):  # must come from the section, not be invented
                out.append({"section": name, "text": c.text.strip(), "category": c.category, "critical": is_critical(c, domain)})
    uniq = dedupe(out + quiz_claims(script))
    return sorted(uniq, key=lambda c: not c["critical"])[:MAX_CLAIMS]  # stable sort: critical first, document order otherwise


def resolve(claim: dict, j: Judgement | None, cands: list[dict], sources: dict[int, ResearchSource]) -> dict:
    """Turn a model judgement into a stored verdict, enforcing that the evidence is real. Pure function (unit-tested)."""
    base = {"status": "unsupported", "source_ids": [], "evidence_excerpt": "", "evidence_section": "", "reviewer_notes": "",
            "confidence": None, "needs_human": True}
    if not cands:
        base["reviewer_notes"] = "no retrieved source passage is related to this claim"
        return base
    if j is None:
        base.update(status="needs_human_review", reviewer_notes="the judge model did not return a usable verdict")
        return base
    base.update(reviewer_notes=j.notes[:600], confidence=j.confidence)
    if j.verdict == "unsupported":
        return base
    src = sources.get(j.source_id) if j.source_id is not None else None
    if src is None:
        base.update(status="needs_human_review", reviewer_notes=f"judge cited invalid source id {j.source_id}; {j.notes[:300]}")
        return base
    quote = j.evidence_quote.strip()
    if len(quote) < MIN_QUOTE or _norm(quote) not in _norm(src.full_text):
        base.update(status="needs_human_review", reviewer_notes=f"quoted evidence was not found in source {src.id}; verdict '{j.verdict}' not accepted. {j.notes[:300]}")
        return base
    heading = next((h for h, b in research.parse_sections(src.full_text) if _norm(quote) in _norm(b)), "")
    base.update(source_ids=[src.id], evidence_excerpt=quote[:600], evidence_section=heading[:500])
    status = j.verdict
    if status == "supported":
        overlap = len(research._tokens(claim["text"]) & research._tokens(quote)) / max(1, len(research._tokens(claim["text"])))
        if overlap < MIN_OVERLAP:
            status = "partially_supported"
            base["reviewer_notes"] += f" [downgraded: quote shares only {overlap:.0%} of the claim's terms]"
    base["status"] = status
    base["confidence"] = min(j.confidence, 0.9) if status == "supported" else j.confidence
    base["needs_human"] = status != "supported" or base["confidence"] < MIN_CONFIDENCE
    return base


def judge_claims(db: Session, lesson: Lesson, script: dict, llm: LLMProvider) -> list[dict]:
    """Extract and judge claims. Reads only: it can take many minutes on a local model, so it must hold no row locks and no open transaction.
    Returns plain dicts ready for store_claims()."""
    sources = db.query(ResearchSource).filter_by(lesson_id=lesson.id).all()
    for src in sources:
        db.expunge(src)  # keep their loaded text usable after the rollback below (no re-select per access)
    by_id = {x.id: x for x in sources}
    dom = domains.of_lesson(lesson).key
    db.rollback()  # end the read transaction: nothing below touches the database until the caller stores the results
    out = []
    for c in extract_claims(llm, script, domain=dom):
        cands = candidates(c["text"], sources)
        j = None
        if cands:
            passages = "\n\n".join(f"[source_id={x['source_id']}] ({by_id[x['source_id']].title or by_id[x['source_id']].url} / {x['heading']})\n{x['passage']}" for x in cands)
            try:
                j = _ask(llm, "claim_judge", f"CLAIM: {c['text']}\n\nSOURCE PASSAGES:\n{passages}", Judgement, domain=dom)
            except LLMError as e:
                if "unreachable" in str(e) or "not installed" in str(e) or "truncated" in str(e):
                    raise  # infrastructure failure: fail the run, do not record fake verdicts
        out.append({**c, **resolve(c, j, cands, by_id)})
    return out


def store_claims(db: Session, lesson: Lesson, script_version: int, run_id: int, judged: list[dict]) -> list[TechnicalClaim]:
    """Replace this script version's claims with `judged` in one short transaction. Human decisions on identical claim text survive."""
    prior = {_norm(c.text): c for c in db.query(TechnicalClaim).filter_by(lesson_id=lesson.id, script_version=script_version).all() if c.human_decision}
    db.query(TechnicalClaim).filter_by(lesson_id=lesson.id, script_version=script_version).delete()
    rows = []
    for c in judged:
        meta = {k: c[k] for k in ("status", "source_ids", "evidence_excerpt", "evidence_section", "reviewer_notes", "confidence", "needs_human")}
        row = TechnicalClaim(lesson_id=lesson.id, run_id=run_id, script_version=script_version, section=c["section"], text=c["text"],
                             category=c["category"], critical=c["critical"], locations=c["locations"], **meta)
        old = prior.get(_norm(c["text"]))
        if old:
            row.human_decision, row.human_note = old.human_decision, old.human_note
        db.add(row)
        rows.append(row)
    db.flush()
    return rows


def verify_claims(db: Session, lesson: Lesson, script_version: int, script: dict, run_id: int, llm: LLMProvider) -> list[TechnicalClaim]:
    return store_claims(db, lesson, script_version, run_id, judge_claims(db, lesson, script, llm))


def claim_blocks(c: TechnicalClaim) -> bool:
    """A claim blocks the gate when it is contradicted, or critical and not supported, unless a human accepted it."""
    if c.human_decision == "accepted":
        return False
    return c.status == "contradicted" or (c.critical and c.status in BLOCKING)


def claim_hash(text: str) -> str:
    return hashlib.sha256(_norm(text).encode()).hexdigest()[:16]
