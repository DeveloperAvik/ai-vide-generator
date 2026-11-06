"""Feature B: a claim is `supported` only when its quoted evidence really exists in a retrieved source."""
import pytest

from app.models import ResearchSource, TechnicalClaim
from app.services import claims
from app.services.claims import Judgement
from tests.helpers import PARAM_SENTENCE, SOURCE_TEXT, ScriptedLLM, make_lesson, reviewer_with

CLAIM = {"text": PARAM_SENTENCE, "category": "remediation", "critical": True, "section": "defensive_recommendations"}


def src(db, lesson):
    return db.query(ResearchSource).filter_by(lesson_id=lesson.id).one()


def resolve(db, j, cands=True, claim=CLAIM):
    l = make_lesson(db, storyboard=False)
    s = src(db, l)
    return claims.resolve(claim, j, claims.candidates(claim["text"], [s]) if cands else [], {s.id: s}), s


def test_supported_claim(db):
    s0 = src(db, make_lesson(db, storyboard=False))
    r, s = resolve(db, Judgement(verdict="supported", source_id=s0.id + 1, evidence_quote=PARAM_SENTENCE, confidence=0.8))
    assert r["status"] == "supported" and r["source_ids"] == [s.id] and r["evidence_section"] == "Primary Defenses" and not r["needs_human"]


def test_supported_requires_real_quote_not_a_paraphrase(db):
    l = make_lesson(db, storyboard=False)
    s = src(db, l)
    j = Judgement(verdict="supported", source_id=s.id, evidence_quote="Parameterized queries always make SQL injection completely impossible in every case.", confidence=0.95)
    r = claims.resolve(CLAIM, j, claims.candidates(CLAIM["text"], [s]), {s.id: s})
    assert r["status"] == "needs_human_review" and "not found" in r["reviewer_notes"] and r["source_ids"] == [] and r["needs_human"]


def test_partially_supported_claim(db):
    l = make_lesson(db, storyboard=False)
    s = src(db, l)
    c = {**CLAIM, "text": "Stored procedures are always safe from injection."}
    q = "Stored procedures can be safe only if they do not build dynamic SQL internally."
    r = claims.resolve(c, Judgement(verdict="partially_supported", source_id=s.id, evidence_quote=q, confidence=0.7), claims.candidates(c["text"], [s]), {s.id: s})
    assert r["status"] == "partially_supported" and r["needs_human"] and r["evidence_excerpt"] == q


def test_supported_but_quote_barely_related_is_downgraded(db):
    l = make_lesson(db, storyboard=False)
    s = src(db, l)
    c = {**CLAIM, "text": "Kerberos tickets expire after ten hours by default in Windows domains."}
    q = "Allow-list input validation is a secondary control and is not a substitute for parameterization."
    r = claims.resolve(c, Judgement(verdict="supported", source_id=s.id, evidence_quote=q, confidence=0.9), [{"source_id": s.id, "heading": "x", "score": 1, "passage": q}], {s.id: s})
    assert r["status"] == "partially_supported" and "downgraded" in r["reviewer_notes"]


def test_unsupported_claim_when_no_source_is_related(db):
    l = make_lesson(db, storyboard=False)
    s = src(db, l)
    c = {**CLAIM, "text": "Kerberoasting requests service tickets for accounts with a registered SPN."}
    assert claims.candidates(c["text"], [s]) == []
    r = claims.resolve(c, None, [], {s.id: s})
    assert r["status"] == "unsupported" and r["source_ids"] == [] and r["needs_human"] and "no retrieved source" in r["reviewer_notes"]


def test_model_says_unsupported(db):
    r, _ = resolve(db, Judgement(verdict="unsupported", notes="passages do not mention it"))
    assert r["status"] == "unsupported" and r["evidence_excerpt"] == ""


def test_contradicted_claim_with_quote(db):
    l = make_lesson(db, storyboard=False)
    s = src(db, l)
    c = {**CLAIM, "text": "Input validation alone is a sufficient substitute for parameterized queries."}
    q = "Allow-list input validation is a secondary control and is not a substitute for parameterization."
    r = claims.resolve(c, Judgement(verdict="contradicted", source_id=s.id, evidence_quote=q, confidence=0.9), claims.candidates(c["text"], [s]), {s.id: s})
    assert r["status"] == "contradicted" and r["evidence_excerpt"] == q


def test_contradicted_without_a_real_quote_is_not_trusted(db):
    l = make_lesson(db, storyboard=False)
    s = src(db, l)
    r = claims.resolve(CLAIM, Judgement(verdict="contradicted", source_id=s.id, evidence_quote="made up text that is not on the page at all, thirty chars", confidence=0.9),
                       claims.candidates(CLAIM["text"], [s]), {s.id: s})
    assert r["status"] == "needs_human_review"


def test_invalid_source_reference(db):
    l = make_lesson(db, storyboard=False)
    s = src(db, l)
    r = claims.resolve(CLAIM, Judgement(verdict="supported", source_id=9999, evidence_quote=PARAM_SENTENCE, confidence=0.9), claims.candidates(CLAIM["text"], [s]), {s.id: s})
    assert r["status"] == "needs_human_review" and "invalid source id" in r["reviewer_notes"]
    r = claims.resolve(CLAIM, Judgement(verdict="supported", source_id=None, evidence_quote=PARAM_SENTENCE), claims.candidates(CLAIM["text"], [s]), {s.id: s})
    assert r["status"] == "needs_human_review"


def test_source_from_another_lesson_cannot_support_a_claim(db):
    a, b = make_lesson(db, storyboard=False), make_lesson(db, storyboard=False)
    sa = src(db, a)
    sb = src(db, b)
    # judge cites lesson B's source while verifying lesson A: A's source map does not contain it
    r = claims.resolve(CLAIM, Judgement(verdict="supported", source_id=sb.id, evidence_quote=PARAM_SENTENCE, confidence=0.9), claims.candidates(CLAIM["text"], [sa]), {sa.id: sa})
    assert r["status"] == "needs_human_review"


def test_confidence_is_capped_and_low_confidence_needs_human(db):
    l = make_lesson(db, storyboard=False)
    s = src(db, l)
    r = claims.resolve(CLAIM, Judgement(verdict="supported", source_id=s.id, evidence_quote=PARAM_SENTENCE, confidence=1.0), claims.candidates(CLAIM["text"], [s]), {s.id: s})
    assert r["confidence"] == 0.9
    r = claims.resolve(CLAIM, Judgement(verdict="supported", source_id=s.id, evidence_quote=PARAM_SENTENCE, confidence=0.3), claims.candidates(CLAIM["text"], [s]), {s.id: s})
    assert r["status"] == "supported" and r["needs_human"]


def test_verify_claims_end_to_end_with_scripted_model(db):
    l = make_lesson(db, storyboard=False)
    rows = claims.verify_claims(db, l, 1, l.scripts[-1].content, run_id=None, llm=reviewer_with())
    db.commit()
    assert rows and all(isinstance(r, TechnicalClaim) for r in rows)
    r = rows[0]
    assert r.status == "supported" and r.critical and r.category == "remediation" and r.source_ids == [src(db, l).id]
    assert not claims.claim_blocks(r)


def test_verify_claims_marks_hallucinated_evidence_for_review(db):
    l = make_lesson(db, storyboard=False)
    rows = claims.verify_claims(db, l, 1, l.scripts[-1].content, None, reviewer_with(claim_quote="This sentence does not appear in any source document at all."))
    assert rows[0].status == "needs_human_review" and claims.claim_blocks(rows[0])  # critical + not supported -> blocks


def test_claim_blocking_rules(db):
    c = TechnicalClaim(lesson_id=1, script_version=1, text="t", status="unsupported", critical=False)
    assert not claims.claim_blocks(c)  # non-critical unsupported: warning only
    c.critical = True
    assert claims.claim_blocks(c)
    c.human_decision = "accepted"
    assert not claims.claim_blocks(c)
    c2 = TechnicalClaim(lesson_id=1, script_version=1, text="t", status="contradicted", critical=False)
    assert claims.claim_blocks(c2)  # contradicted blocks even when not critical
    assert not claims.claim_blocks(TechnicalClaim(lesson_id=1, script_version=1, text="t", status="supported", critical=True))


def test_extracted_claims_must_come_from_the_section(db):
    l = make_lesson(db, storyboard=False)
    invented = ScriptedLLM(claim_extract={"claims": [{"text": "Quantum computers broke RSA in 2019 according to researchers.", "category": "statistic_or_date"},
                                                     {"text": PARAM_SENTENCE, "category": "remediation"}]})
    got = claims.extract_claims(invented, l.scripts[-1].content)
    assert {c["text"] for c in got if c["section"] != "knowledge_check"} == {PARAM_SENTENCE}  # the invented one is discarded; the real one is de-duplicated across sections
