import pytest

from app.models import Lesson
from app.providers.llm import LLMError, LLMProvider
from app.schemas.content import StoryboardData
from app.services import generation, lengthplan


_uid = __import__("itertools").count()


def scenes_with_words(n_words: int, count: int = 3, typ="slide"):
    """Unique filler words per scene, so synthetic scenes never look like repetition."""
    per = max(1, n_words // count)
    return [{"scene_id": "scene_000", "type": typ, "duration_seconds": 5, "narration": " ".join(f"w{next(_uid)}" for _ in range(per)) + ".", "visual_description": "v",
             "on_screen_text": "t", "bullets": ["a", "b"], "transition": "fade"} for _ in range(count)]


class FakeLLM(LLMProvider):
    """Returns scenes sized by the section budget in the prompt; `factor` simulates a model that under/over-writes."""
    name = "fake"

    def __init__(self, factors=(1.0,)):
        self.factors, self.calls = list(factors), []

    def complete(self, system, prompt, max_tokens=8000):
        raise NotImplementedError

    def complete_text(self, system, prompt, max_tokens=1500):
        """Prose rewrite: a model that cannot comply writes `factor` x the requested words."""
        target = int(prompt.split("to about ")[1].split(" words")[0])
        return " ".join(f"t{next(_uid)}" for _ in range(max(1, int(target * self.factors[0])))) + "."

    def complete_json(self, system, prompt, max_tokens=8000, schema=None):
        budget = int(prompt.split("WORD_BUDGET: ")[1].split("\n")[0])
        section = prompt.split("SECTION: ")[1].split("\n")[0]
        self.calls.append((section, "previous answer" in prompt))
        f = self.factors.pop(0) if len(self.factors) > 1 else self.factors[0]
        return {"scenes": scenes_with_words(int(budget * f))}


def lesson(minutes=8):
    return Lesson(title="SQL Injection", summary="s", estimated_minutes=minutes)


def test_budget_math():
    assert lengthplan.target_words(8) == int(8 * 60 * lengthplan.WPS)
    b = lengthplan.budgets(8)
    assert abs(sum(b.values()) - lengthplan.target_words(8)) < 40 and set(b) == {n for n, _, _ in lengthplan.SECTIONS}


def test_section_generation_hits_budget_and_renumbers():
    llm = FakeLLM([1.0])
    sb = generation.build_storyboard_by_sections(lesson(8), {"title": "x"}, llm)
    assert [c[0] for c in llm.calls] == [n for n, _, _ in lengthplan.SECTIONS]  # one call per section, no corrections
    ids = [s.scene_id for s in sb.scenes]
    assert ids == [f"scene_{i:03d}" for i in range(1, len(ids) + 1)]
    assert lengthplan.within(lengthplan.word_count(sb), lengthplan.target_words(8), 0.05)
    assert 6.4 * 60 <= lengthplan.estimate_seconds(sb) <= 9.6 * 60


def test_short_section_is_corrected_then_accepted():
    llm = FakeLLM([0.4, 1.0])  # first section answer is far too short, second try fine, rest fine
    sb = generation.build_storyboard_by_sections(lesson(8), {}, llm)
    assert llm.calls[0] == ("hook_intro", False) and llm.calls[1] == ("hook_intro", True)  # feedback was sent on the retry
    assert lengthplan.within(lengthplan.word_count(sb), lengthplan.target_words(8), 0.12)


def test_model_that_never_reaches_budget_is_rejected_not_saved(db):
    llm = FakeLLM([0.3])  # always writes 30% of the budget
    with pytest.raises(LLMError, match="budget"):
        generation.build_storyboard_by_sections(lesson(8), {}, llm)


def test_mock_provider_keeps_template_path(db):
    from app.models import Course, Module
    from app.providers.llm import get_llm
    from app.schemas.content import CurriculumRequest
    c = generation.generate_curriculum(db, CurriculumRequest(course_name="Len Course"), get_llm("mock"))
    l = c.modules[0].lessons[0]
    generation.save_script(db, l, __import__("app.schemas.content", fromlist=["LessonScriptData"]).LessonScriptData.model_validate(
        __import__("app.providers.mock_llm", fromlist=["_lesson"])._lesson("T")), "mock")
    sb = generation.generate_storyboard(db, l, get_llm("mock"))
    assert len(sb.data["scenes"]) == 7  # the fixed template, not budgeted


def test_length_check_rules():
    ok, d, blocking = lengthplan.length_check(387, 7, "manual:import")
    assert ok and blocking
    ok, d, blocking = lengthplan.length_check(58, 8, "anthropic")
    assert not ok and blocking and "Regenerate" in d
    ok, d, blocking = lengthplan.length_check(58, 8, "mock")
    assert not ok and not blocking and "not enforced" in d          # mock template exempt
    assert lengthplan.length_check(800, 12, "ollama")[0]
    assert not lengthplan.length_check(1600, 25, "ollama")[0]        # above hard 25-min cap
    assert not lengthplan.length_check(290, 5, "anthropic")[0]       # below hard 5-min floor


def test_regenerate_endpoint_requires_approved_script(client, auth_headers, db):
    from app.models import Course, Module
    c = Course(name="RG"); m = Module(title="m"); l = Lesson(title="l"); m.lessons.append(l); c.modules.append(m); db.add(c); db.commit()
    r = client.post(f"/api/lessons/{l.id}/storyboard/regenerate", headers=auth_headers)
    assert r.status_code == 409


def test_sections_are_the_ten_required_ones():
    assert [n for n, _, _ in lengthplan.SECTIONS] == ["hook_intro", "objectives", "fundamentals", "technical", "demo", "attack_scenarios",
                                                       "defense", "mistakes", "quiz", "conclusion"]
    assert 1150 <= lengthplan.target_words(8) <= 1250  # spec: ~1,150-1,200 words for 8 minutes


def test_completed_sections_are_saved_and_resumed(tmp_path):
    class Dies(FakeLLM):
        def complete_json(self, system, prompt, max_tokens=8000, schema=None):
            if "SECTION: defense" in prompt:
                raise LLMError("model crashed")
            return super().complete_json(system, prompt, max_tokens, schema)
    with pytest.raises(LLMError):
        generation.build_storyboard_by_sections(lesson(8), {}, Dies(), tmp_path)
    assert len(list(tmp_path.glob("*.json"))) == 6  # sections before `defense` survived
    llm = FakeLLM()
    sb = generation.build_storyboard_by_sections(lesson(8), {}, llm, tmp_path)
    assert [c[0] for c in llm.calls] == ["defense", "mistakes", "quiz", "conclusion"]  # only the missing ones were regenerated
    assert lengthplan.within(lengthplan.word_count(sb), lengthplan.target_words(8), 0.12)


def test_preflight_rejects_placeholder_and_short_content():
    sb = StoryboardData.model_validate({"lesson_title": "t", "scenes": [{**x, "scene_id": f"scene_{i:03d}", "narration": "TODO write this."} for i, x in enumerate(scenes_with_words(30, 2), 1)]})
    assert any("placeholder" in p for p in lengthplan.preflight(sb, 8, "ollama"))
    assert any("placeholder" in p for p in lengthplan.preflight(sb, 8, "mock"))  # mock is not exempt from placeholder check
    ok = StoryboardData.model_validate({"lesson_title": "t", "scenes": [{**x, "scene_id": f"scene_{i:03d}"} for i, x in enumerate(scenes_with_words(1194, 12), 1)]})
    assert lengthplan.preflight(ok, 8, "ollama") == []
    short = StoryboardData.model_validate({"lesson_title": "t", "scenes": [{**x, "scene_id": f"scene_{i:03d}"} for i, x in enumerate(scenes_with_words(150, 3), 1)]})
    assert any("outside" in p for p in lengthplan.preflight(short, 8, "ollama"))


def test_voice_calibration_pools_samples_and_changes_the_budget(tmp_path, monkeypatch):
    from app.core.config import get_settings
    monkeypatch.setattr(get_settings(), "manifests_root", tmp_path)
    lengthplan.record_voice_sample("a", 1000, 400)   # 2.5 w/s
    cal = lengthplan.record_voice_sample("b", 1000, 500)  # 2.0 w/s -> pooled 2000/900
    assert cal["wps"] == pytest.approx(2.222, abs=0.001)
    assert lengthplan._load_wps() == pytest.approx(2.222 / (1 + lengthplan.SCENE_OVERHEAD), abs=0.001)
    lengthplan.record_voice_sample("b", 1000, 450)   # re-recording a source replaces it, not double counts
    assert len(lengthplan.record_voice_sample("c", 100, 40)["samples"]) == 3


def test_xss_topics_get_real_seed_sources(db):
    from app.services import research
    from app.models import Course, Module
    c = Course(name="XSSseed"); m = Module(title="m"); l = Lesson(title="Cross-Site Scripting (XSS) Fundamentals", summary="x"); m.lessons.append(l); c.modules.append(m)
    db.add(c); db.commit()
    got = research.collect(db, l, online=False)
    assert {s.identifier for s in got} == {"A03:2021", "XSS Prevention", "CWE-79"} and all(not s.verified for s in got)  # offline: stored, never marked verified
