"""The n8n test fixture must satisfy the REAL validators and quality gate (the gate is never loosened for it)."""
import json
import os
from pathlib import Path

from app.models import Course, Lesson, Module
from app.schemas.content import LessonScriptData, StoryboardData
from app.services import generation, lengthplan, qualitygate

ROOT = Path(__file__).resolve().parents[2]
BUNDLE = ROOT / "lessons/sqli_fundamentals/n8n_test_bundle.json"
HARNESS = ROOT / "infrastructure/scripts/n8n_test.py"


def _load():
    b = json.loads(BUNDLE.read_text())
    return b, LessonScriptData.model_validate(b["script"]), StoryboardData.model_validate(b["storyboard"])


def test_bundle_is_labelled_as_n8n_test_and_not_a_real_lesson():
    b, _, _ = _load()
    assert b["course_name"] == "n8n Connectivity Tests" and b["lesson_title"] == "n8n Pipeline Test Lesson"
    assert "not for publication" in b["summary"]


def test_schema_duration_and_preflight():
    _, script, sb = _load()
    orig_wps = lengthplan.WPS
    requested = max(1, round(sb.total_seconds / 60))  # what import_lesson stores as estimated_minutes
    assert requested == 5 and 5 <= requested <= 25
    lo, hi = lengthplan.window(requested)
    assert lo <= lengthplan.estimate_seconds(sb) <= hi
    for wps in (2.0, 2.08, 2.45, 2.8):  # robust to the calibrated speaking rate
        lengthplan.WPS = wps
        try:
            assert lo <= lengthplan.estimate_seconds(sb) <= hi, wps
        finally:
            lengthplan.WPS = orig_wps
    assert 600 <= lengthplan.word_count(sb) <= 900
    assert lengthplan.preflight(sb, requested, "manual:import_lesson") == []


def test_storyboard_has_demo_quiz_and_closing_summary():
    _, _, sb = _load()
    types = [s.type for s in sb.scenes]
    assert {"code", "terminal"} & set(types) and "quiz" in types and "instructor" in types and "slide" in types
    assert types[-1] == "summary"
    for s in sb.scenes:
        assert s.duration_seconds > 0
        if s.type == "terminal":
            assert s.terminal_lines  # real captured lab output, not invented


def test_recordings_exist_on_disk():
    b, _, _ = _load()
    for p in b["recordings"].values():
        assert (ROOT / p).exists(), p


def test_real_quality_gate_accepts_the_storyboard_without_mock_exemptions(db):
    b, script, sb = _load()
    course = Course(name=b["course_name"], description="", language="English")
    mod = Module(title=b["module_title"], position=0)
    course.modules.append(mod)
    lesson = Lesson(title=b["lesson_title"], summary=b["summary"], position=0, estimated_minutes=max(1, round(sb.total_seconds / 60)))
    mod.lessons.append(lesson)
    db.add(course)
    db.commit()
    generation.save_script(db, lesson, script, "manual:import_lesson")
    generation.save_storyboard(db, lesson, sb)
    checks = qualitygate.storyboard_checks(db, lesson, sb, "manual:import_lesson")  # NOT "mock": length and demo are enforced
    failed = [c for c in checks if c["blocking"] and not c["passed"]]
    assert not failed, failed
    assert {c["check"] for c in checks} >= {"storyboard_preflight", "estimated_duration", "storyboard_has_demo", "storyboard_has_summary"}


def test_mock_llm_is_applied_only_to_the_test_subprocess():
    src = HARNESS.read_text()
    assert src.count('"LLM_PROVIDER": "mock"') == 1
    assert 'env={**os.environ, "LLM_PROVIDER": "mock"' in src  # a copy for one subprocess, never os.environ[...] = ...
    assert "os.environ[" not in src and "putenv" not in src
    before = dict(os.environ)
    import importlib.util
    spec = importlib.util.spec_from_file_location("n8n_harness_env_check", HARNESS)
    spec.loader.exec_module(importlib.util.module_from_spec(spec))
    assert dict(os.environ) == before  # importing the harness does not touch the process environment


def test_other_lessons_are_untouched_by_the_fixture(db):
    from app.models import Lesson as L
    before = db.query(L).count()
    _load()
    assert db.query(L).count() == before == 0  # loading/validating the fixture writes nothing


def test_unapproved_upload_is_refused_before_any_llm_call(db, client, auth_headers, monkeypatch):
    """n8n found that publish asked the LLM for metadata (minutes on a local model) before refusing an unapproved lesson."""
    from tests.helpers import make_lesson
    l = make_lesson(db)
    called = []
    monkeypatch.setattr(generation, "generate_metadata", lambda *a, **k: called.append(1) or (_ for _ in ()).throw(AssertionError("LLM called")))
    r = client.post(f"/api/lessons/{l.id}/youtube/publish", json={}, headers=auth_headers)
    assert r.status_code == 403 and "not APPROVED" in r.text
    assert not called
