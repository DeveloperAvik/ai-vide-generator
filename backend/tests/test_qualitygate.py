"""Feature E: the pre-render gate."""
import pytest

from app.core.config import get_settings
from app.models import Approval, TechnicalClaim
from app.providers.llm import LLMError
from app.providers.mock_llm import MockLLM
from app.schemas.content import LessonScriptData, StoryboardData
from app.services import generation, qualitygate, techreview
from tests.helpers import ScriptedLLM, finding, good_script, good_storyboard, make_lesson, reviewer_with


def ready(db, minutes=8, script=None, storyboard=True, reviewer=None, approve=True):
    """Review done, human approval recorded directly (bypassing approve_script's own gate) so the PRE-TTS gate is tested on its own."""
    l = make_lesson(db, script=script, minutes=minutes, storyboard=storyboard)
    techreview.run_review(db, l, reviewer or reviewer_with([finding("low"), finding("info", text="Testing without written authorization")]))
    if approve:
        db.add(Approval(lesson_id=l.id, stage="script", decision="APPROVED"))
    db.commit()
    return l


def gate(db, l, stage="pre_tts"):
    r = qualitygate.evaluate(db, l, stage)
    db.commit()
    return r, {c["check"]: c for c in r.checks}


@pytest.mark.parametrize("minutes", [5, 8, 20])
def test_complete_valid_lesson_passes(db, minutes):
    l = ready(db, minutes)
    r, c = gate(db, l)
    assert r.passed, qualitygate.blocking_reasons(r)
    assert c["review_completed"]["passed"] and c["human_script_approval"]["passed"] and c["estimated_duration"]["passed"]
    assert qualitygate.latest_passed(db, l)  # stored result matches current script + storyboard versions


def test_missing_required_section(db):
    s = good_script()
    s["defensive_recommendations"] = ""
    r, c = gate(db, ready(db, script=s))
    assert not r.passed and not c["required_sections_present"]["passed"] and "defensive_recommendations" in c["required_sections_present"]["detail"]
    assert not c["defense_and_mitigation"]["passed"]


def test_missing_practical_demonstration_and_conclusion(db):
    s = good_script()
    s["practical_demonstration"], s["summary"] = "Run it.", "Done."
    r, c = gate(db, ready(db, script=s))
    assert not c["practical_demonstration"]["passed"] and not c["conclusion"]["passed"] and not r.passed


def test_objective_not_covered(db):
    s = good_script()
    s["learning_objectives"] = s["learning_objectives"] + ["Configure Kubernetes admission controllers for supply-chain provenance"]
    r, c = gate(db, ready(db, script=s))
    assert not c["objectives_covered"]["passed"] and "Kubernetes" in c["objectives_covered"]["detail"]


def test_short_lesson_is_blocked(db):
    r, c = gate(db, ready(db, 8, storyboard=good_storyboard(3)))
    assert not r.passed and not c["estimated_duration"]["passed"] and "estimated" in c["estimated_duration"]["detail"]


def test_long_lesson_is_blocked(db):
    r, c = gate(db, ready(db, 8, storyboard=good_storyboard(16)))
    assert not r.passed and not c["estimated_duration"]["passed"]


def test_placeholder_content_in_script_and_storyboard(db):
    s = good_script()
    s["hook"] = "TODO: write a real hook here before recording."
    r, c = gate(db, ready(db, script=s))
    assert not c["no_placeholder_text"]["passed"] and "todo" in c["no_placeholder_text"]["detail"]
    d = good_storyboard().model_dump()
    d["scenes"][2]["narration"] = "Lorem ipsum dolor sit amet " + d["scenes"][2]["narration"]
    r, c = gate(db, ready(db, storyboard=StoryboardData.model_validate(d)))
    assert not c["storyboard_preflight"]["passed"] and "placeholder" in c["storyboard_preflight"]["detail"]


def test_empty_narration_is_blocked(db):
    d = good_storyboard().model_dump()
    d["scenes"][3]["narration"] = "   "
    r, c = gate(db, ready(db, storyboard=StoryboardData.model_validate(d)))
    assert not r.passed and "empty or placeholder narration" in c["storyboard_preflight"]["detail"]


def test_repeated_paragraphs_in_script(db):
    s = good_script()
    para = "Parameterized queries separate the code of a statement from the data supplied by the user at execution time."
    s["technical_explanation"] += " " + para
    s["defensive_recommendations"] += " " + para
    r, c = gate(db, ready(db, script=s))
    assert not c["no_repeated_paragraphs"]["passed"]


def test_broken_reference(db):
    s = good_script()
    s["references"] = [{"title": "x", "url": "https://owasp.org/Top10/never-fetched/"}]
    r, c = gate(db, ready(db, script=s))
    assert not c["references_valid"]["passed"] and "never retrieved" in c["references_valid"]["detail"]
    s["references"] = [{"title": "x", "url": "http://owasp.org/insecure"}]
    r, c = gate(db, ready(db, script=s))
    assert not c["references_valid"]["passed"] and "not an allowed https source" in c["references_valid"]["detail"]


def test_unretrievable_reference_blocks_in_production(db, monkeypatch):
    from app.models import ResearchSource
    l = ready(db)
    src = db.query(ResearchSource).filter_by(lesson_id=l.id).one()
    src.verified, src.status = False, "offline"
    db.commit()
    assert gate(db, l)[1]["references_valid"]["passed"]  # development: offline sources tolerated
    monkeypatch.setattr(get_settings(), "app_env", "production")
    assert not gate(db, l)[1]["references_valid"]["passed"]


def test_unsupported_critical_claim_blocks(db):
    l = ready(db, reviewer=reviewer_with(claim_quote="A quote that is nowhere in the retrieved source documents."))
    r, c = gate(db, l)
    assert not r.passed and not c["no_unsupported_critical_claims"]["passed"]
    db.query(TechnicalClaim).filter_by(lesson_id=l.id).first().human_decision = "accepted"
    db.commit()
    assert gate(db, l)[1]["no_unsupported_critical_claims"]["passed"]  # explicit human acceptance resolves it


@pytest.mark.parametrize("sev", ["critical", "high", "medium"])
def test_unresolved_blocking_finding(db, sev):
    l = make_lesson(db)
    techreview.run_review(db, l, reviewer_with([finding(sev)]))
    db.add(Approval(lesson_id=l.id, stage="script", decision="APPROVED"))
    db.commit()
    r, c = gate(db, l)
    assert not r.passed and not c["no_unresolved_blocking_findings"]["passed"] and sev in c["no_unresolved_blocking_findings"]["detail"]


def test_low_and_info_findings_do_not_block(db):
    r, c = gate(db, ready(db))
    assert r.passed and "2 open non-blocking" in c["no_unresolved_blocking_findings"]["detail"]


def test_review_not_completed(db):
    l = make_lesson(db)
    r, c = gate(db, l)
    assert not r.passed and not c["review_completed"]["passed"] and "never run" in c["review_completed"]["detail"]
    techreview.begin_run(db, l, "technical", 1, "m", False)
    assert not gate(db, l)[1]["review_completed"]["passed"]


def test_failed_review_blocks(db):
    l = make_lesson(db)
    with pytest.raises(LLMError):
        techreview.run_review(db, l, ScriptedLLM(tech_review=LLMError("Ollama unreachable")))
    assert not gate(db, l)[1]["review_completed"]["passed"]


def test_stale_review_after_script_edit(db):
    l = ready(db)
    s = good_script()
    s["summary"] += " Remember to document every finding for the client."
    generation.save_script(db, l, LessonScriptData.model_validate(s), "manual:x")
    db.refresh(l)
    r, c = gate(db, l)
    assert not c["review_current"]["passed"] and not c["human_script_approval"]["passed"] and not r.passed


def test_human_approval_missing(db):
    l = make_lesson(db)
    techreview.run_review(db, l, reviewer_with([]))
    db.commit()
    r, c = gate(db, l)
    assert not r.passed and not c["human_script_approval"]["passed"]
    assert c["review_completed"]["passed"] and c["no_unresolved_blocking_findings"]["passed"]


def test_rejected_approval_is_not_approval(db):
    l = make_lesson(db)
    techreview.run_review(db, l, reviewer_with([]))
    db.add(Approval(lesson_id=l.id, stage="script", decision="REJECTED"))
    db.commit()
    assert not gate(db, l)[1]["human_script_approval"]["passed"]


def test_simulated_review_allowed_in_dev_refused_in_production(db, monkeypatch):
    l = make_lesson(db)
    techreview.run_review(db, l, MockLLM())
    db.add(Approval(lesson_id=l.id, stage="script", decision="APPROVED"))
    db.commit()
    assert techreview.latest_run(db, l.id).simulated
    c = gate(db, l)[1]
    assert c["review_by_real_model"]["passed"] and "mock" in c["review_by_real_model"]["detail"]
    monkeypatch.setattr(get_settings(), "app_env", "production")
    assert not gate(db, l)[1]["review_by_real_model"]["passed"]


def test_script_stage_does_not_require_approval(db):
    l = make_lesson(db, storyboard=False)
    techreview.run_review(db, l, reviewer_with([]))
    r, c = gate(db, l, "script")
    assert r.passed and "human_script_approval" not in c and "estimated_duration" not in c


def test_storyboard_older_than_script_is_blocked(db):
    l = ready(db)
    s = good_script()
    s["summary"] += " Always document the scope before testing."
    generation.save_script(db, l, LessonScriptData.model_validate(s), "manual:x")
    db.refresh(l)
    techreview.run_review(db, l, reviewer_with([]))
    db.add(Approval(lesson_id=l.id, stage="script", decision="APPROVED"))
    db.commit()
    assert not gate(db, l)[1]["storyboard_matches_script"]["passed"]


def test_review_state_labels(db):
    l = make_lesson(db)
    assert qualitygate.review_state(db, l)["state"] == "pending"
    run = techreview.begin_run(db, l, "technical", 1, "m", False)
    assert qualitygate.review_state(db, l)["state"] == "running"
    techreview.finish_run(db, run.id, "failed", "boom")
    assert qualitygate.review_state(db, l)["state"] == "failed"
    techreview.run_review(db, l, reviewer_with([finding("high")]))
    assert qualitygate.review_state(db, l)["state"] == "human_review_required"
    l2 = make_lesson(db)
    techreview.run_review(db, l2, reviewer_with([]))
    assert qualitygate.review_state(db, l2)["state"] == "passed"  # clean review, only the human click is missing
    db.add(Approval(lesson_id=l2.id, stage="script", decision="APPROVED"))
    db.commit()
    st = qualitygate.review_state(db, l2)
    assert st["state"] == "approved_for_rendering" and not st["blocked"]


@pytest.mark.parametrize("edit", [lambda s: s.update(defensive_recommendations=""), lambda s: s.update(hook="TODO write the hook"),
                                  lambda s: s.update(practical_demonstration="Run it.")])
def test_approve_script_itself_refuses_a_failing_script(db, edit):
    from app.models import LessonStatus as S
    from app.services import pipeline
    s = good_script()
    edit(s)
    l = make_lesson(db, script=s, storyboard=False)
    pipeline.run_technical_review(db, l, online=False, reviewer=reviewer_with([]))
    db.refresh(l)
    assert l.status == S.TECHNICAL_REVIEW
    with pytest.raises(pipeline.StageError, match="quality gate blocked"):
        pipeline.approve_script(db, l, None)
    db.refresh(l)
    assert l.status == S.TECHNICAL_REVIEW and not db.query(Approval).filter_by(lesson_id=l.id).count()
