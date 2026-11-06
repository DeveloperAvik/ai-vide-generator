"""Features C+D: reviewer stage, severities, blocking, human decisions, failure modes."""
import httpx
import pytest

from app.models import ReviewFinding, ReviewRun, User
from app.providers.llm import LLMError, OllamaProvider
from app.services import generation, techreview
from tests.helpers import ScriptedLLM, finding, make_lesson, reviewer_with


def run(db, l, llm):
    return techreview.run_review(db, l, llm)


def findings(db, l):
    return db.query(ReviewFinding).filter_by(lesson_id=l.id).all()


def test_valid_json_response_is_stored(db):
    l = make_lesson(db, storyboard=False)
    s = run(db, l, reviewer_with([finding("medium")]))
    f = findings(db, l)[0]
    assert s["findings"]["medium"] == 1 and f.section == "defensive_recommendations" and f.problem_text and f.recommended_correction
    r = techreview.latest_run(db, l.id)
    assert r.status == "completed" and r.reviewer_model == "scripted:scripted-1" and not r.simulated and r.script_version == 1


@pytest.mark.parametrize("sev,blocks", [("critical", True), ("high", True), ("medium", True), ("low", False), ("info", False)])
def test_severity_decides_blocking_server_side(db, sev, blocks):
    l = make_lesson(db, storyboard=False)
    # the model lies about blocks_approval in both directions: the server ignores it
    run(db, l, reviewer_with([finding(sev, blocks_approval=not blocks)]))
    assert findings(db, l)[0].blocks_approval is blocks


def test_reviewer_with_no_findings(db):
    l = make_lesson(db, storyboard=False)
    s = run(db, l, reviewer_with([]))
    assert s["findings"] == {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0} and findings(db, l) == []


def test_invalid_json_response_fails_the_run(db):
    class Bad(ScriptedLLM):
        def complete_json(self, system, prompt, max_tokens=8000, schema=None):
            return {"findings": [{"severity": "catastrophic", "category": "x"}]}
    l = make_lesson(db, storyboard=False)
    with pytest.raises(LLMError, match="technical review failed"):
        run(db, l, Bad())
    r = techreview.latest_run(db, l.id)
    assert r.status == "failed" and "schema validation" in r.error and findings(db, l) == []


def test_malformed_json_text_fails_the_run(db):
    class Garbage(OllamaProvider):
        def complete(self, system, prompt, max_tokens=8000):
            return "I think the lesson is fine. {not json"
    l = make_lesson(db, storyboard=False)
    with pytest.raises(LLMError):
        run(db, l, Garbage("http://localhost:1", "m"))
    assert techreview.latest_run(db, l.id).status == "failed"


def test_ollama_unavailable(db, monkeypatch):
    def refuse(*a, **k):
        raise httpx.ConnectError("connection refused")
    monkeypatch.setattr(httpx, "post", refuse)
    l = make_lesson(db, storyboard=False)
    with pytest.raises(LLMError, match="unreachable"):
        run(db, l, OllamaProvider("http://localhost:11434", "qwen2.5:7b-instruct"))
    r = techreview.latest_run(db, l.id)
    assert r.status == "failed" and "unreachable" in r.error


def test_model_not_installed(db, monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: httpx.Response(404, text="model not found", request=httpx.Request("POST", "http://x")))
    l = make_lesson(db, storyboard=False)
    with pytest.raises(LLMError, match="ollama pull"):
        run(db, l, OllamaProvider("http://localhost:11434", "no-such-model"))
    assert "ollama pull no-such-model" in techreview.latest_run(db, l.id).error


def test_reviewer_timeout(db, monkeypatch):
    def slow(*a, **k):
        raise httpx.ReadTimeout("timed out")
    monkeypatch.setattr(httpx, "post", slow)
    l = make_lesson(db, storyboard=False)
    with pytest.raises(LLMError):
        run(db, l, OllamaProvider("http://localhost:11434", "m"))
    assert techreview.latest_run(db, l.id).status == "failed"


def test_failed_run_leaves_no_partial_findings_and_can_be_rerun(db):
    l = make_lesson(db, storyboard=False)
    calls = {"n": 0}

    def flaky(prompt):
        calls["n"] += 1
        if calls["n"] == 2:  # the second chunk (teaching) fails after the technical chunk already produced findings
            return LLMError("Ollama unreachable at http://localhost:11434: boom")
        return {"findings": [finding("high")]}
    with pytest.raises(LLMError):
        run(db, l, ScriptedLLM(tech_review=flaky))
    assert findings(db, l) == [] and techreview.latest_run(db, l.id).status == "failed"
    run(db, l, reviewer_with([finding("low")]))  # resume = simply run again
    assert techreview.latest_run(db, l.id).status == "completed" and len(findings(db, l)) == 1


def test_quote_not_in_script_is_discarded_and_counted(db):
    l = make_lesson(db, storyboard=False)
    summary = run(db, l, reviewer_with([finding("high", text="a sentence the script never contained")]))
    assert findings(db, l) == []  # a finding that cannot be located can be neither verified nor corrected
    assert techreview.latest_run(db, l.id).summary["refined"]["not_in_script"] == 1


def test_duplicate_review_jobs_are_prevented(db):
    l = make_lesson(db, storyboard=False)
    techreview.begin_run(db, l, "technical", 1, "m", False)
    with pytest.raises(techreview.ReviewBusy):
        techreview.begin_run(db, l, "technical", 1, "m", False)
    with pytest.raises(techreview.ReviewBusy):
        run(db, l, reviewer_with([]))


def test_abandoned_running_row_does_not_block_forever(db):
    from datetime import timedelta
    from app.models import now
    l = make_lesson(db, storyboard=False)
    r = techreview.begin_run(db, l, "technical", 1, "m", False)
    r.updated_at = now() - timedelta(days=1)
    db.commit()
    run(db, l, reviewer_with([]))
    assert db.get(ReviewRun, r.id).status == "failed" and techreview.latest_run(db, l.id).status == "completed"


def test_accept_applies_correction_as_new_revision_and_keeps_history(db):
    l = make_lesson(db, storyboard=False)
    run(db, l, reviewer_with([finding("high", text="no single control is sufficient on its own", fix="no single control is sufficient on its own, so layers are required")]))
    f = findings(db, l)[0]
    before = generation.latest_script(l).content["defensive_recommendations"]
    v = techreview.apply_correction(db, l, f, user_id=1)
    db.commit()
    db.refresh(l)
    assert v == 2 and f.status == "accepted" and f.applied_version == 2
    assert [s.version for s in l.scripts] == [1, 2]
    assert l.scripts[0].content["defensive_recommendations"] == before  # original preserved
    assert "so layers are required" in l.scripts[1].content["defensive_recommendations"] and "finding" in l.scripts[1].change_note


def test_accept_with_human_edited_correction(db):
    l = make_lesson(db, storyboard=False)
    run(db, l, reviewer_with([finding("medium")]))
    f = findings(db, l)[0]
    techreview.apply_correction(db, l, f, 1, correction="no control is sufficient alone")
    assert "no control is sufficient alone" in generation.latest_script(l).content["defensive_recommendations"]


def test_accept_refused_when_text_not_found_or_stale(db):
    l = make_lesson(db, storyboard=False)
    run(db, l, reviewer_with([finding("medium")]))
    f = findings(db, l)[0]
    f.problem_text = "a sentence the script never contained"  # e.g. the script was edited after the finding was recorded
    with pytest.raises(techreview.DecisionError, match="not found verbatim"):
        techreview.apply_correction(db, l, f, 1)
    f2 = ReviewFinding(run_id=f.run_id, lesson_id=l.id, script_version=0, severity="low", category="x", problem_text="p", recommended_correction="c")
    with pytest.raises(techreview.DecisionError, match="rerun the review"):
        techreview.apply_correction(db, l, f2, 1)


def test_waiver_rules(db):
    l = make_lesson(db, storyboard=False)
    run(db, l, reviewer_with([finding("high"), finding("medium", text="Allow-list input validation as a secondary control")]))
    hi, med = sorted(findings(db, l), key=lambda f: f.severity)
    reviewer = User(id=2, email="r@x", password_hash="", role="reviewer")
    admin = User(id=1, email="a@x", password_hash="", role="admin")
    with pytest.raises(techreview.DecisionError, match="note"):
        techreview.decide(db, med, reviewer, "waive", "short")
    with pytest.raises(techreview.DecisionError, match="admin"):
        techreview.decide(db, hi, reviewer, "waive", "I accept this risk for the demo")
    techreview.decide(db, hi, admin, "waive", "Accepted by the course owner after manual check")
    techreview.decide(db, med, reviewer, "reject", "The wording is already qualified in the previous sentence")
    assert hi.status == "waived" and med.status == "rejected" and hi.decided_by == 1


def test_human_decisions_survive_a_rerun_on_same_script_version(db):
    l = make_lesson(db, storyboard=False)
    llm = reviewer_with([finding("medium")])
    run(db, l, llm)
    f = findings(db, l)[0]
    techreview.decide(db, f, User(id=2, email="r", password_hash="", role="reviewer"), "reject", "reviewed by a human, wording is fine")
    db.commit()
    run(db, l, llm)
    new = [x for x in findings(db, l) if x.run_id != f.run_id]
    assert new and new[0].status == "rejected"


def test_rerun_reviews_the_updated_script(db):
    l = make_lesson(db, storyboard=False)
    llm = reviewer_with([])
    run(db, l, llm)
    s = generation.latest_script(l).content
    s["summary"] = "REVISED SUMMARY MARKER keeps data and code separate with parameterized queries and written authorization in an isolated lab."
    from app.schemas.content import LessonScriptData
    generation.save_script(db, l, LessonScriptData.model_validate(s), "manual:x")
    db.refresh(l)
    llm.calls.clear()
    run(db, l, llm)
    assert any("REVISED SUMMARY MARKER" in p for t, p in llm.calls if t == "tech_review")
    assert techreview.latest_run(db, l.id).script_version == 2


def test_reviewer_model_is_configurable_and_never_downloaded(monkeypatch):
    from app.core.config import get_settings
    from app.providers import llm as llm_mod
    s = get_settings()
    monkeypatch.setattr(s, "llm_provider", "ollama")
    monkeypatch.setattr(s, "reviewer_model", "qwen2.5:14b-instruct")
    r = llm_mod.get_reviewer()
    assert isinstance(r, OllamaProvider) and r.model == "qwen2.5:14b-instruct" and r.timeout == s.reviewer_timeout_s
    monkeypatch.setattr(s, "reviewer_model", "")
    assert llm_mod.get_reviewer().model == s.ollama_model  # same model, sequential
