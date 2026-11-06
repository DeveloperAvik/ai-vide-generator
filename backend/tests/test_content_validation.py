import pytest
from pydantic import ValidationError

from app.providers.llm import extract_json, LLMError
from app.providers.mock_llm import MockLLM, _storyboard, _lesson, _curriculum
from app.schemas.content import Curriculum, LessonScriptData, StoryboardData, YouTubeMetadata


def test_mock_outputs_validate():
    Curriculum.model_validate(_curriculum("X", 8))
    LessonScriptData.model_validate(_lesson("SQLi"))
    sb = StoryboardData.model_validate(_storyboard("SQLi", 1))
    assert {s.type for s in sb.scenes} >= {"instructor", "slide", "diagram", "code", "terminal", "quiz", "summary"}


def test_malformed_storyboard_rejected():
    good = _storyboard("T", 1)
    for mutate in (lambda d: d["scenes"][0].update(type="hologram"), lambda d: d["scenes"][1].update(scene_id=d["scenes"][0]["scene_id"]),
                   lambda d: d["scenes"][0].update(duration_seconds=-1), lambda d: d["scenes"][0].update(extra="x"),
                   lambda d: d["scenes"][0].update(narration="")):
        bad = __import__("copy").deepcopy(good)
        mutate(bad)
        with pytest.raises(ValidationError):
            StoryboardData.model_validate(bad)


def test_curriculum_unknown_dependency_rejected():
    c = _curriculum("X", 8)
    c["modules"][0]["lessons"][0]["dependencies"] = ["Does Not Exist"]
    with pytest.raises(ValidationError):
        Curriculum.model_validate(c)


def test_quiz_answer_index_checked():
    s = _lesson("T")
    s["knowledge_check"][0]["answer_index"] = 9
    with pytest.raises(ValidationError):
        LessonScriptData.model_validate(s)


def test_extract_json_variants():
    assert extract_json('```json\n{"a":1}\n```') == {"a": 1}
    assert extract_json('Sure! {"a": 2} done') == {"a": 2}
    with pytest.raises(LLMError):
        extract_json("no json here")


def test_anthropic_requires_real_key():
    from app.providers.llm import AnthropicProvider
    with pytest.raises(LLMError, match="Claude Pro"):
        AnthropicProvider("", "m")


def test_metadata_chapters_from_real_timings(db):
    from app.models import Lesson
    from app.services.generation import generate_metadata
    sb = StoryboardData.model_validate(_storyboard("T", 1))
    md = generate_metadata(Lesson(title="SQL Injection"), sb, MockLLM())
    assert md.chapters[0][0] == "0:00" and len(md.chapters) == len(sb.scenes) and len(md.titles) == 3
    assert "authorized" in md.disclaimer.lower() or "permission" in md.disclaimer.lower()
