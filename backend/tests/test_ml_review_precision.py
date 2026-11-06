"""Regression tests for the false-positive patterns found on lesson 69 ("What is Machine Learning?"): duplicate findings, quiz
distractors reported as errors, "no source mentions it" reported as "technically wrong", analogies and fragments extracted as claims."""
from app.models import LessonStatus as S, ReviewFinding, ReviewRun, ResearchSource, TechnicalClaim
from app.services import claims, domains, generation, research, techreview
from tests.helpers import ScriptedLLM, make_lesson, reviewer_with

SCRIPT = {
    "technical_explanation": "Machine learning algorithms learn patterns from data and then make predictions on new data. A model is trained on examples.",
    "defensive_recommendations": "Ensure that the data used complies with relevant privacy regulations and that predictions are explainable.",
    "common_mistakes": ["Overfitting the model to the training data"],
    "knowledge_check": [{"question": "Which is a real-world application of machine learning?",
                         "options": ["Predicting stock market trends", "Creating hand-drawn illustrations", "Designing physical products"], "answer_index": 0}],
}
QUOTE = "Overfitting occurs when a model memorizes the training data and fails to generalize to new data."


def _src():
    return [ResearchSource(id=1, lesson_id=1, kind="x", url="https://x", verified=True, status="ok", full_text=f"## Overfitting\n{QUOTE}")]


def _claim(text, status="unsupported", critical=False):
    return TechnicalClaim(text=text, status=status, critical=critical, section="x")


def _f(problem, cat="technical_correctness", sev="high", expl="Reason.", ev="", fix=""):
    return {"severity": sev, "category": cat, "section": "x", "problem_text": problem, "explanation": expl, "evidence": ev,
            "recommended_correction": fix, "blocks_approval": sev in techreview.BLOCKING_SEVERITIES}


# ---------------- what counts as a claim
def test_questions_analogies_transitions_and_fragments_are_not_claims():
    for t in ["What is the main goal of machine learning today?", "A model is like a student who studies for an exam.", "Imagine a world where machines learn.",
              "In this lesson we will explore the basics.", "Overfitting the model", "Let's look at an example together now."]:
        assert not claims.is_checkable(t), t
    assert claims.is_checkable("Overfitting happens when a model memorizes its training data.")


def test_quiz_correct_answer_is_a_claim_but_distractors_never_are():
    got = claims.quiz_claims(SCRIPT)
    assert len(got) == 1 and "Predicting stock market trends" in got[0]["text"] and got[0]["section"] == "knowledge_check" and not got[0]["critical"]
    assert not any("hand-drawn" in c["text"] or "physical products" in c["text"] for c in got)


def test_extraction_dedupes_repeats_keeps_every_location_and_skips_analogies():
    s = "Overfitting happens when a model memorizes its training data and fails on new data."
    script = {"hook": s + " It is a very common problem in practice for everyone.", "technical_explanation": s + " Regularization helps reduce it considerably.",
              "common_mistakes": ["Think of it as a student who only memorizes the answers to the exam."], "knowledge_check": []}
    llm = ScriptedLLM(claim_extract=lambda p: {"claims": [
        {"text": s, "category": "definition"},
        {"text": "Think of it as a student who only memorizes the answers to the exam.", "category": "general"}]})
    got = claims.extract_claims(llm, script)
    assert len(got) == 1 and got[0]["text"] == s
    assert sorted(got[0]["locations"]) == ["hook", "technical_explanation"]


def test_semantically_similar_claims_merge_and_critical_is_sticky():
    a = {"section": "hook", "text": "Overfitting means the model memorizes the training data.", "category": "definition", "critical": False}
    b = {"section": "summary", "text": "The model memorizes the training data when overfitting happens.", "category": "definition", "critical": True}
    c = {"section": "summary", "text": "Cross-validation estimates performance on unseen data.", "category": "definition", "critical": False}
    got = claims.dedupe([a, b, c])
    assert len(got) == 2 and got[0]["locations"] == ["hook", "summary"] and got[0]["critical"]


def test_remediation_is_critical_only_in_security_domains():
    c = claims.ClaimIn(text="Ensure that the data used complies with regulations.", category="remediation")
    assert claims.is_critical(c, "cybersecurity") and claims.is_critical(c, "red_team")
    assert not claims.is_critical(c, "ai_ml") and not claims.is_critical(c, "general")
    assert claims.is_critical(claims.ClaimIn(text="Never deploy this model to a medical device unreviewed.", category="best_practice", critical=True), "ai_ml")


def test_quiz_answers_that_only_point_at_other_options_are_not_claims():
    for ans in ("Both A and B", "None of the above.", "All of the above", "Neither"):
        q = {"knowledge_check": [{"question": "Which is a risk?", "options": ["Overfitting", "Underfitting", ans], "answer_index": 2}]}
        assert claims.quiz_claims(q) == [], ans


# ---------------- reviewer precision (lesson 69 patterns)
def test_quiz_distractors_are_not_reported_as_errors():
    kept, st = techreview.refine([_f("Creating hand-drawn illustrations", "teaching_quality", "medium", "unsupported and irrelevant"),
                                  _f("Designing physical products", "unsupported_claim", "medium")], SCRIPT, _src(), [])
    assert kept == [] and st["quiz_distractor"] == 2


def test_a_distractor_that_is_actually_also_correct_is_still_reported():
    kept, _ = techreview.refine([_f("Designing physical products", "teaching_quality", "medium", "This option is also correct, so the question is ambiguous.")], SCRIPT, _src(), [])
    assert len(kept) == 1


def test_absence_of_evidence_is_not_technical_incorrectness():
    kept, st = techreview.refine([_f("Overfitting the model to the training data", "technical_correctness", "high", "The claim is unsupported.", ev="unsupported")],
                                 SCRIPT, _src(), [])
    assert kept[0]["category"] == "unsupported_claim" and kept[0]["severity"] == "medium" and not kept[0]["blocks_approval"] and st["reclassified_unsupported"] == 1


def test_a_real_contradiction_with_a_source_quote_stays_technical_and_blocks():
    kept, _ = techreview.refine([_f("Overfitting the model to the training data", "technical_correctness", "high", "Contradicts the source.", ev=QUOTE)], SCRIPT, _src(), [])
    assert kept[0]["category"] == "technical_correctness" and kept[0]["blocks_approval"] and kept[0]["severity"] == "high"


def test_a_made_up_quote_is_not_source_evidence():
    kept, _ = techreview.refine([_f("Overfitting the model to the training data", "technical_correctness", "high", "Contradicts the source.",
                                    ev="The source clearly states that overfitting never happens in practice.")], SCRIPT, _src(), [])
    assert kept[0]["category"] == "unsupported_claim"


def test_findings_that_only_repeat_a_tracked_claim_are_dropped():
    weak = [_claim("Ensure that the data used complies with relevant privacy regulations", "unsupported", critical=True)]
    kept, st = techreview.refine([_f("Ensure that the data used complies with relevant privacy regulations", "teaching_quality", "high", "The claim is unsupported and overly prescriptive.")],
                                 SCRIPT, _src(), weak)
    assert kept == [] and st["duplicate_of_claim"] == 1


def test_the_same_text_reported_twice_is_kept_once_at_the_higher_severity():
    kept, st = techreview.refine([_f("predictions are explainable", "teaching_quality", "medium", "Too prescriptive.", ev="x"),
                                  _f("predictions are explainable", "needs_qualification", "high", "Needs a condition.")], SCRIPT, _src(), [])
    assert len(kept) == 1 and kept[0]["severity"] == "high" and st["duplicate"] == 1


def test_finding_with_text_not_in_the_script_is_discarded():
    f = techreview.FindingOut(severity="high", category="teaching_quality", problem_text="We use the scikit-learn library to train a model", explanation="vague")
    assert techreview.normalize(f, SCRIPT) is None
    ok = techreview.FindingOut(severity="high", category="teaching_quality", problem_text="Overfitting the model to the training data", explanation="vague")
    assert techreview.normalize(ok, SCRIPT)["section"] == "common_mistakes"


def test_review_run_reports_what_it_refined(db):
    l = make_lesson(db)
    bad = _f("no single control is sufficient on its own", "technical_correctness", "high", "unsupported", ev="")
    llm = ScriptedLLM(tech_review=lambda p: {"findings": [bad, _f("this text is not in the script at all", "teaching_quality", "high")]} if "CHUNK: technical" in p else {"findings": []})
    summary = techreview.run_review(db, l, llm)
    assert summary["refined"]["not_in_script"] == 1 and summary["refined"]["reclassified_unsupported"] == 1
    row = db.query(ReviewFinding).filter_by(lesson_id=l.id).one()
    assert row.category == "unsupported_claim" and not row.blocks_approval


# ---------------- corrections
def test_applying_a_clause_correction_does_not_end_the_sentence_early(db):
    from tests.helpers import good_script
    l = make_lesson(db, script={**good_script(), "defensive_recommendations": "Ensure that the data used is anonymized and that the model's predictions are explainable."}, storyboard=False)
    run = techreview.begin_run(db, l, "technical", 1, "scripted:x", False)
    f = ReviewFinding(run_id=run.id, lesson_id=l.id, script_version=1, severity="high", category="technical_correctness", problem_text="the data used is anonymized",
                      recommended_correction="the data used complies with relevant privacy regulations.")
    db.add(f)
    db.flush()
    techreview.apply_correction(db, l, f, user_id=1)
    # the lesson-69 bug: this used to produce "...regulations. and that the model's predictions..."
    assert generation.latest_script(l).content["defensive_recommendations"] == \
        "Ensure that the data used complies with relevant privacy regulations and that the model's predictions are explainable."


# ---------------- sources
def test_every_curated_seed_is_https_and_on_the_allow_list():
    for key, seed in research.SEEDS.items():
        for kind, ident, url in (seed if isinstance(seed, list) else [seed]):
            assert research.host_allowed(url), (key, url)


def test_ml_lesson_gets_beginner_sources_not_arxiv_papers():
    urls = [u for _k, _i, u in research.seed_urls("what is machine learning? a model overfitting the training data, evaluated with scikit-learn")]
    assert any("developers.google.com/machine-learning/intro-to-ml/what-is-ml" in u for u in urls)
    assert any("scikit-learn.org" in u for u in urls) and any("overfitting" in u for u in urls)
    assert not any("arxiv" in u for u in urls)


def test_short_seed_keys_match_whole_words_only():
    assert research.seed_urls("how attackers use c2 channels") and not research.seed_urls("the abc2x build of this thing")


def test_guessed_or_searched_urls_that_do_not_load_are_not_stored(db, monkeypatch):
    l = make_lesson(db, source=False)
    ok = {"status": "ok", "verified": True, "excerpt": "e", "full_text": "t" * 300, "title": "T", "publisher": "p", "category": "c", "published_at": "", "section": "", "content_hash": "h"}
    bad = {**ok, "status": "http_error", "verified": False, "full_text": "", "excerpt": "HTTP 404"}
    monkeypatch.setattr(research, "fetch_source", lambda url, q="": ok if "good" in url else bad)
    got = research.collect(db, l, [("model_suggested", "guess", "https://scikit-learn.org/stable/good"), ("model_suggested", "guess", "https://scikit-learn.org/stable/nope"),
                                   ("arxiv", "1", "https://arxiv.org/abs/nope"), ("user_supplied", "", "https://docs.python.org/nope")])
    urls = {s.url for s in got}
    assert "https://scikit-learn.org/stable/good" in urls and "https://scikit-learn.org/stable/nope" not in urls and "https://arxiv.org/abs/nope" not in urls
    assert "https://docs.python.org/nope" in urls  # a URL the user supplied is shown even if it failed, so they can see why


# ---------------- blocking policy calibration (server-side) ----------------
OBJ_COVERED = "Understand data, features, labels and models"
OBJ_MISSING = "Explain gradient descent optimization of the loss function"
POLICY_SCRIPT = {**SCRIPT, "learning_objectives": [OBJ_COVERED, OBJ_MISSING],
                 "technical_explanation": "A model learns from data. Each example has features and a label. The model maps features to labels. " + SCRIPT["technical_explanation"]}


def _t(sev="medium", expl="The explanation is too vague and could be clearer.", obj="", why="", fix="", problem="Machine learning algorithms learn patterns from data"):
    return {**_f(problem, "teaching_quality", sev, expl, fix=fix), "objective": obj, "why_objective_fails": why}


def _blocks(f, script=POLICY_SCRIPT, domain="ai_ml"):
    kept, _ = techreview.refine([f], script, _src(), [], domain)
    assert len(kept) == 1
    return kept[0]


def test_vague_teaching_comment_without_a_concrete_defect_is_advisory():
    for sev in ("medium", "high", "critical"):
        k = _blocks(_t(sev))
        assert not k["blocks_approval"] and "objective" in k["policy_note"], sev


def test_teaching_finding_needs_objective_reason_and_correction():
    full = dict(obj=OBJ_MISSING, why="A learner cannot say how the model improves itself.", fix="Add a paragraph explaining gradient descent step by step.")
    assert _blocks(_t("medium", **full))["blocks_approval"]
    for drop in ("obj", "why", "fix"):
        partial = {**full, drop: ""}
        assert not _blocks(_t("medium", **partial))["blocks_approval"], drop


def test_objective_that_is_not_one_of_the_scripts_objectives_is_advisory():
    k = _blocks(_t("high", obj="Teach quantum computing", why="A learner cannot follow the quantum part of this.", fix="Add a quantum computing section."))
    assert not k["blocks_approval"] and "does not name" in k["policy_note"]


def test_criticism_of_a_concept_the_script_already_contains_is_advisory():
    for sev in ("medium", "high"):
        k = _blocks(_t(sev, expl="The explanation is vague and needs more detail.", obj=OBJ_COVERED, why="Not enough detail on data, features and labels here.",
                       fix="Explain data, features and labels in more detail with an example."))
        assert not k["blocks_approval"] and "already contains" in k["policy_note"], sev


def test_a_genuinely_missing_objective_blocks_and_names_the_objective():
    k = _blocks(_t("medium", expl="Gradient descent is never explained.", obj=OBJ_MISSING, why="Nothing in the lesson says how training reduces the error.",
                   fix="Add a paragraph explaining how gradient descent reduces the loss."))
    assert k["blocks_approval"] and k["objective"] == OBJ_MISSING and "not covered" in k["policy_note"]


def test_low_and_info_teaching_feedback_never_blocks():
    for sev in ("low", "info"):
        assert not _blocks(_t(sev, obj=OBJ_MISSING, why="x" * 30, fix="y" * 30))["blocks_approval"]


def test_technical_falsehood_with_source_evidence_still_blocks_at_every_blocking_severity():
    for sev in ("critical", "high", "medium"):
        k = _blocks(_f("Overfitting the model to the training data", "technical_correctness", sev, "Contradicts the source.", ev=QUOTE))
        assert k["blocks_approval"], sev
    assert not _blocks(_f("Overfitting the model to the training data", "technical_correctness", "low", "Minor.", ev=QUOTE))["blocks_approval"]


def test_security_remediation_error_still_blocks():
    f = _f("Ensure that the data used complies with relevant privacy regulations", "security_accuracy", "high", "Wrong fix.", ev=QUOTE)
    assert _blocks(f, domain="cybersecurity")["blocks_approval"] and _blocks(f, domain="red_team")["blocks_approval"]


def test_unsupported_claims_block_only_in_security_domains():
    f = lambda: _f("Ensure that the data used complies with relevant privacy regulations", "unsupported_claim", "high", "Nothing retrieved backs this.")
    sec, ml = _blocks(f(), domain="cybersecurity"), _blocks(f(), domain="ai_ml")
    assert sec["blocks_approval"] and sec["severity"] == "high"
    assert not ml["blocks_approval"] and ml["severity"] == "medium" and ml["category"] == "unsupported_claim"  # never re-labelled as a falsehood


def test_the_models_own_blocks_approval_flag_is_ignored():
    kept, _ = techreview.refine([{**_t("critical"), "blocks_approval": True}], POLICY_SCRIPT, _src(), [], "ai_ml")
    assert not kept[0]["blocks_approval"]
    kept, _ = techreview.refine([{**_f("Overfitting the model to the training data", "technical_correctness", "critical", "Wrong.", ev=QUOTE), "blocks_approval": False}],
                                POLICY_SCRIPT, _src(), [], "ai_ml")
    assert kept[0]["blocks_approval"]


# ---------------- the gate: advisory findings do not block progression, blocking findings do
def _gate_with(db, findings):
    from tests.test_qualitygate import ready, gate
    return gate(db, ready(db, reviewer=reviewer_with(findings)))


def test_advisory_findings_do_not_block_tts_or_rendering(db):
    from tests.helpers import finding
    advisory = [finding("high", text="no single control is sufficient on its own", category="teaching_quality", explanation="This is vague and could be clearer."),
                finding("medium", text="Testing without written authorization", category="unsupported_claim", explanation="No source mentions it.")]
    r, c = _gate_with(db, advisory)
    assert r.passed, c["no_unresolved_blocking_findings"]["detail"]
    assert "2 open non-blocking" in c["no_unresolved_blocking_findings"]["detail"]


def test_a_blocking_finding_still_prevents_progression(db):
    from tests.helpers import finding
    r, c = _gate_with(db, [finding("medium")])  # technical_correctness with real source evidence
    assert not r.passed and not c["no_unresolved_blocking_findings"]["passed"]


def test_rerun_supersedes_open_findings_but_keeps_history(db):
    l = make_lesson(db)
    from tests.helpers import finding
    techreview.run_review(db, l, reviewer_with([finding("high")]))
    first = db.query(ReviewFinding).filter_by(lesson_id=l.id).one()
    techreview.run_review(db, l, reviewer_with([finding("medium")]))
    db.expire_all()
    rows = db.query(ReviewFinding).filter_by(lesson_id=l.id).order_by(ReviewFinding.id).all()
    assert [r.status for r in rows] == ["superseded", "open"] and rows[0].id == first.id and rows[0].severity == "high"
    runs = db.query(ReviewRun).filter_by(lesson_id=l.id).order_by(ReviewRun.id).all()
    assert len(runs) == 2 and runs[0].summary.get("claims_snapshot")  # the replaced claims stay inspectable on the older run
    open_blocking = [f for f in rows if f.status == "open" and f.blocks_approval]
    assert len(open_blocking) == 1  # only the newest run counts toward the gate


# ---------------- a slow review must not lock the database for the people clicking around
def test_review_holds_no_transaction_or_row_locks_while_the_model_runs(db):
    from app.core.db import SessionLocal
    from tests.helpers import finding, PARAM_SENTENCE
    l = make_lesson(db)
    techreview.run_review(db, l, reviewer_with([finding("high")]))
    lid = l.id  # read now: touching an expired ORM object inside the handler would itself open the transaction we are checking for
    before = db.query(TechnicalClaim).filter_by(lesson_id=lid).count()
    db.commit()
    assert before > 0
    seen = []

    def during(label):
        def h(prompt):
            other = SessionLocal()  # a separate session: reading through `db` would itself open the transaction we are checking for
            try:
                still_old = other.query(TechnicalClaim).filter_by(lesson_id=lid).count() == before
            finally:
                other.close()
            seen.append((label, db.in_transaction(), still_old))
            return {"claims": [{"text": PARAM_SENTENCE, "category": "remediation", "critical": True}]} if label == "extract" and PARAM_SENTENCE in prompt else (
                {"findings": []} if label == "review" else {"claims": []})
        return h

    def judge(prompt):
        sid = int(prompt.split("source_id=")[1].split("]")[0])
        seen.append(("judge", db.in_transaction(), True))
        return {"verdict": "supported", "source_id": sid, "evidence_quote": PARAM_SENTENCE, "notes": "q", "confidence": 0.8}
    llm = ScriptedLLM(claim_extract=during("extract"), claim_judge=judge, tech_review=during("review"))
    techreview.run_review(db, l, llm)
    assert seen and all(in_tx is False for _label, in_tx, _old in seen), seen  # every model call ran outside a transaction
    assert all(old for _label, _tx, old in seen), seen  # and the previous claims were still in place (nothing was deleted up front)
    assert db.query(TechnicalClaim).filter_by(lesson_id=l.id).count() > 0  # and the claims were swapped in at the end
