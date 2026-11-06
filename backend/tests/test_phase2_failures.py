"""Phase 2 failure handling: bad/short/long/truncated LLM output, missing services, duration windows, resume."""
import json
from pathlib import Path

import httpx
import pytest

from app.models import Lesson, LessonStatus as S
from app.providers.llm import LLMError, OllamaProvider
from app.providers.voice import PiperVoice, VoiceUnavailable, get_voice
from app.schemas.content import StoryboardData
from app.services import generation, lengthplan, pipeline
from tests.test_length import FakeLLM, lesson, scenes_with_words


def test_extremely_short_output_is_rejected():
    with pytest.raises(LLMError, match="hard limit"):
        generation.build_storyboard_by_sections(lesson(8), {}, FakeLLM([0.05]))


def test_extremely_long_output_is_rejected():
    with pytest.raises(LLMError, match="hard limit"):
        generation.build_storyboard_by_sections(lesson(8), {}, FakeLLM([6.0]))


def test_corrections_are_capped_per_section():
    llm = FakeLLM([0.05])  # JSON answers AND prose rewrites stay hopelessly short
    with pytest.raises(LLMError, match="hard limit"):
        generation.build_storyboard_by_sections(lesson(8), {}, llm)
    assert [c[0] for c in llm.calls] == ["hook_intro"] * (generation.MAX_CORRECTIONS + 1)  # gave up on the first section, no infinite loop


def test_prose_rewrite_rescues_a_section_the_json_answer_cannot_fill():
    class JsonShortProseOk(FakeLLM):
        def complete_text(self, system, prompt, max_tokens=1500):
            target = int(prompt.split("to about ")[1].split(" words")[0])
            self.n = getattr(self, "n", 0) + 1
            return " ".join(f"w{self.n}x{i}" for i in range(target)) + "."
    sb = generation.build_storyboard_by_sections(lesson(8), {}, JsonShortProseOk([0.4]))
    assert lengthplan.within(lengthplan.word_count(sb), lengthplan.target_words(8), 0.2)


def test_model_returning_no_scenes_is_rejected_as_missing_section():
    class Empty(FakeLLM):
        def complete_json(self, *a, **k):
            return {"scenes": []}
    with pytest.raises(LLMError, match="schema validation"):
        generation.build_storyboard_by_sections(lesson(8), {}, Empty())


def test_repeated_sections_are_rejected():
    class Parrot(FakeLLM):
        def complete_text(self, system, prompt, max_tokens=1500):
            return "Parameterized queries keep user input as data and never as executable SQL code in the database."  # rewrites repeat too
        def complete_json(self, system, prompt, max_tokens=8000, schema=None):
            budget = int(prompt.split("WORD_BUDGET: ")[1].split("\n")[0])
            text = "Parameterized queries keep user input as data and never as executable SQL code in the database."
            n = min(12, max(1, budget // len(text.split())))
            sc = scenes_with_words(10, 1)[0]
            return {"scenes": [{**sc, "narration": text + " " + " ".join(f"alpha{i}" for i in range(budget - n * len(text.split())))} for _ in range(n)]}
    with pytest.raises(LLMError, match="repeat|hard limit"):
        generation.build_storyboard_by_sections(lesson(8), {}, Parrot())


def test_repetition_detector_flags_duplicate_narration_and_diagrams():
    a = StoryboardData.model_validate({"lesson_title": "t", "scenes": [
        {**scenes_with_words(30, 1)[0], "scene_id": "scene_001", "narration": "Use parameterized queries so that input stays data and never becomes code in the query."},
        {**scenes_with_words(30, 1)[0], "scene_id": "scene_002", "narration": "Use parameterized queries so that input stays data and never becomes code in the query!"}]})
    assert lengthplan.repetition_issues(a.scenes)
    distinct = [type("S", (), {"narration": f"unique sentence number {i} about topic {i * 7} and idea {i * 13} here", "mermaid": None})() for i in range(4)]
    assert lengthplan.repetition_issues(distinct) == []


def _ollama(handler, model="qwen2.5:7b-instruct"):
    p = OllamaProvider("http://ollama.test", model)
    real = httpx.post
    httpx.post = lambda url, **kw: handler(url, kw)  # type: ignore[assignment]
    return p, lambda: setattr(httpx, "post", real)


def test_truncated_ollama_response_is_not_used():
    p, undo = _ollama(lambda u, kw: httpx.Response(200, json={"message": {"content": '{"scenes": [{"sce'}, "done_reason": "length"}))
    try:
        with pytest.raises(LLMError, match="truncated"):
            p.complete_json("s", "p")
    finally:
        undo()


def test_malformed_json_from_model_is_rejected():
    p, undo = _ollama(lambda u, kw: httpx.Response(200, json={"message": {"content": '{"scenes": [{"sce'}, "done_reason": "stop"}))
    try:
        with pytest.raises(LLMError):
            p.complete_json("s", "p")
    finally:
        undo()


def test_model_not_installed_gives_pull_instruction():
    p, undo = _ollama(lambda u, kw: httpx.Response(404, json={"error": "model not found"}), "nope:1b")
    try:
        with pytest.raises(LLMError, match="ollama pull nope:1b"):
            p.complete("s", "p")
    finally:
        undo()


def test_ollama_unavailable():
    def boom(u, kw):
        raise httpx.ConnectError("refused")
    p, undo = _ollama(boom)
    try:
        with pytest.raises(LLMError, match="unreachable"):
            p.complete("s", "p")
    finally:
        undo()


def test_piper_unavailable_raises_not_fakes(monkeypatch, tmp_path):
    v = PiperVoice()
    v.binary = "no-such-piper"
    with pytest.raises(VoiceUnavailable):
        v.generate_audio("hello", tmp_path / "a.wav")
    monkeypatch.setenv("APP_ENV", "production")
    from app.core.config import get_settings
    get_settings.cache_clear()
    try:
        monkeypatch.setattr("app.providers.voice.PiperVoice.available", lambda self: (False, "missing"))
        monkeypatch.setattr("app.providers.voice.KokoroVoice.available", lambda self: (False, "missing"))
        with pytest.raises(VoiceUnavailable):
            get_voice("auto")
    finally:
        get_settings.cache_clear()


def test_duration_windows_cover_5_to_25_minutes():
    for m in (5, 8, 12, 15, 25):
        lengthplan.validate_request(m)
        w = lengthplan.target_words(m)
        assert w == pytest.approx(m * 60 * lengthplan.WPS, abs=1)
        assert lengthplan.length_check(m * 60, m, "ollama")[0]
        assert not lengthplan.length_check(m * 60 * 0.6, m, "ollama")[0]
        assert not lengthplan.length_check(m * 60 * 1.5, m, "ollama")[0]
        # measured narration (video minus overhead) passes the audio check; half of it does not
        assert lengthplan.audio_check(m * 60 / (1 + lengthplan.SCENE_OVERHEAD), m, "ollama")[0]
        assert not lengthplan.audio_check(m * 30, m, "ollama")[0]
    for bad in (1, 4.9, 26, 60):
        with pytest.raises(ValueError):
            lengthplan.validate_request(bad)
        with pytest.raises(ValueError):
            generation.build_storyboard_by_sections(lesson(bad), {}, FakeLLM())


def test_video_check_requires_real_video_to_cover_narration():
    assert lengthplan.video_check(480, 430, 8)[0]
    assert not lengthplan.video_check(300, 430, 8)[0]   # truncated render
    assert not lengthplan.video_check(120, 110, 8)[0]   # whole thing far too short


def test_failed_audio_generation_fails_the_stage_and_keeps_resume_point(db, monkeypatch):
    from app.models import Course, Module
    from app.providers.mock_llm import _storyboard
    c = Course(name="AudioFail"); m = Module(title="m"); l = Lesson(title="l", estimated_minutes=8); m.lessons.append(l); c.modules.append(m); db.add(c); db.commit()
    sb = StoryboardData.model_validate(_storyboard("T", 1))
    from app.schemas.content import LessonScriptData
    generation.save_script(db, l, LessonScriptData.model_validate(_script()), "mock")  # mock is exempt from length, not from TTS failures
    generation.save_storyboard(db, l, sb)
    class Silent(PiperVoice):
        name = "piper"
        def available(self): return True, "ok"
        def generate_audio(self, text, out_wav):
            Path(out_wav).write_bytes(b"RIFF")  # corrupted/empty audio
            return out_wav
    monkeypatch.setattr("app.services.pipeline.get_voice", lambda name=None: Silent())
    monkeypatch.setattr("app.services.narration.synth_with_timing", lambda v, t, w: (_ for _ in ()).throw(RuntimeError("tts crashed")))
    from tests.helpers import approve_for_assets
    approve_for_assets(db, l)  # the quality gate requires review + human approval before any TTS
    with pytest.raises(RuntimeError, match="tts crashed"):
        pipeline.run_assets(db, l)
    db.refresh(l)
    assert l.status == S.FAILED and l.last_good_status == S.SCRIPT_APPROVED.value and "tts crashed" in l.last_error


def test_pipeline_rejects_short_storyboard_before_tts(db, monkeypatch):
    from app.models import Course, Module
    from app.providers.mock_llm import _storyboard
    c = Course(name="ShortPre"); m = Module(title="m"); l = Lesson(title="l", estimated_minutes=8); m.lessons.append(l); c.modules.append(m); db.add(c); db.commit()
    sb = StoryboardData.model_validate({"lesson_title": "t", "scenes": [{**x, "scene_id": f"scene_{i:03d}"} for i, x in enumerate(scenes_with_words(120, 3), 1)]})
    generation.save_storyboard(db, l, sb)
    generation.save_script(db, l, __import__("app.schemas.content", fromlist=["LessonScriptData"]).LessonScriptData.model_validate(_script()), "ollama")
    called = []
    monkeypatch.setattr("app.services.narration.synth_with_timing", lambda *a, **k: called.append(1))
    pipeline.set_status(db, l, S.SCRIPT_APPROVED); db.commit()
    with pytest.raises(pipeline.StageError, match="rejected before rendering"):
        pipeline.run_assets(db, l)
    assert called == []  # no TTS was attempted


def _script():
    from app.providers.mock_llm import _lesson
    return _lesson("t")


def test_unusable_mode3d_is_dropped_but_missing_payload_is_not_invented():
    base = {**scenes_with_words(30, 1)[0], "mode3d": "flow", "mermaid": None}
    assert generation.SectionScene.model_validate(base).mode3d is None
    with pytest.raises(Exception, match="payload"):
        generation.SectionScene.model_validate({**base, "type": "code", "mode3d": None})  # a code scene without code is rejected, never invented


def test_every_scene_type_needs_its_payload():
    from app.schemas.content import Scene
    ok = {**scenes_with_words(30, 1)[0], "scene_id": "scene_001"}
    Scene.model_validate(ok)
    for typ, field in (("code", "code"), ("terminal", "terminal_lines"), ("diagram", "mermaid")):
        with pytest.raises(Exception, match=field):
            Scene.model_validate({**ok, "type": typ})
    with pytest.raises(Exception, match="bullets"):
        Scene.model_validate({**ok, "bullets": None})


def test_missing_bullets_are_derived_from_narration_not_invented():
    class Bulleter(FakeLLM):
        def complete_text(self, system, prompt, max_tokens=1500):
            if "NARRATION:" in prompt:
                assert "Parameterized queries" in prompt  # derived from this scene's own narration
                return "- Keep input as data\n- Use parameters\n- Least privilege"
            return super().complete_text(system, prompt, max_tokens)
    sc = generation.SectionScene.model_validate({**scenes_with_words(30, 1)[0], "bullets": None, "narration": "Parameterized queries keep input as data."})
    out = generation._ensure_bullets(Bulleter(), [sc])
    assert out[0].bullets == ["Keep input as data", "Use parameters", "Least privilege"]


def test_missing_diagram_is_generated_validated_or_demoted_to_slide():
    class D(FakeLLM):
        good = True
        def complete_text(self, system, prompt, max_tokens=1500):
            if "Mermaid" in prompt:
                return "```mermaid\nflowchart LR\nA[Input] --> B[Query]\nB -- runs --> C[Database]\n```" if self.good else "not a diagram at all"
            return "- one\n- two\n- three"
    sc = generation.SectionScene.model_validate({**scenes_with_words(30, 1)[0], "type": "diagram", "mermaid": None, "bullets": None})
    d = D()
    assert generation._ensure_bullets(d, [sc])[0].mermaid.startswith("flowchart LR")
    d.good = False
    out = generation._ensure_bullets(d, [sc])[0]
    assert out.type == "slide" and out.bullets and not out.mermaid


def test_preflight_rejects_undrawable_diagram_before_tts():
    sc = [{**x, "scene_id": f"scene_{i:03d}"} for i, x in enumerate(scenes_with_words(1194, 12), 1)]
    sc[2] = {**sc[2], "type": "diagram", "mermaid": "flowchart LR\nthis is not mermaid"}
    sb = StoryboardData.model_validate({"lesson_title": "t", "scenes": sc})
    assert any("diagram cannot be drawn" in p for p in lengthplan.preflight(sb, 8, "ollama"))


def test_speakability_flags_markup_and_entities_in_narration():
    def sc(t):
        return type("S", (), {"narration": t, "mermaid": None})()
    assert lengthplan.speakability_issues([sc("We replace <script with &lt;script in the code.")])
    assert lengthplan.speakability_issues([sc("Visit https://owasp.org for more.")])
    assert lengthplan.speakability_issues([sc("Use the dollar sign, a backslash {x}.")])
    assert lengthplan.speakability_issues([sc("The browser treats the opening script tag as code, so we escape the less-than sign.")]) == []


def test_preflight_blocks_unspeakable_narration_before_tts():
    sc = [{**x, "scene_id": f"scene_{i:03d}"} for i, x in enumerate(scenes_with_words(1194, 12), 1)]
    sc[3] = {**sc[3], "narration": "Escape &lt;script&gt; before output. " + sc[3]["narration"]}
    sb = StoryboardData.model_validate({"lesson_title": "t", "scenes": sc})
    assert any("describe code and markup in words" in p for p in lengthplan.preflight(sb, 8, "ollama"))


def test_last_error_is_cleared_when_a_stage_later_succeeds(db):
    from app.models import Course, Module
    c = Course(name="LE"); m = Module(title="m"); l = Lesson(title="l", last_error="old failure"); m.lessons.append(l); c.modules.append(m); db.add(c); db.commit()
    with pipeline.stage(db, l, "noop"):
        pass
    db.refresh(l)
    assert l.last_error == ""


def test_shared_phrase_repetition_is_flagged_even_when_scenes_differ():
    mk = lambda t: type("S", (), {"narration": t, "mermaid": None})()
    a = mk("First, a quiz. What is the difference between reflected and stored XSS? Think about it for a moment before the answer arrives.")
    b = mk("Later we ask again: what is the difference between reflected and stored XSS, and where does each one execute in practice today.")
    assert lengthplan.repetition_issues([a, b])
    c = mk("Output encoding converts dangerous characters into harmless text before the browser ever sees them as markup in a page.")
    assert lengthplan.repetition_issues([a, c]) == []


def test_repeating_scene_is_rewritten_with_the_earlier_text_as_do_not_repeat():
    prompts = []

    class Fixer(FakeLLM):
        def complete_text(self, system, prompt, max_tokens=1500):
            prompts.append(prompt)
            return "A different angle: output encoding converts angle brackets into harmless text before the browser renders the page again."
    mk = lambda t: generation.SectionScene.model_validate({**scenes_with_words(30, 1)[0], "narration": t})
    same = "An attacker injects malicious scripts into a web page through user input and the browser runs them for every visitor."
    prior, cur = [mk(same)], generation.SectionOut(scenes=[mk(same + " Extra words follow here."), mk("Parameterized queries are unrelated and stay untouched by this repair.")])
    out = generation._make_distinct(Fixer(), lesson(8), "technical", prior, cur)
    assert len(prompts) == 1 and same in prompts[0] and "do not repeat" in prompts[0]
    assert out.scenes[0].narration.startswith("A different angle") and out.scenes[1].narration == cur.scenes[1].narration
    assert lengthplan.repetition_pairs(prior + list(out.scenes)) == []


def test_duplicate_diagram_is_redrawn_or_demoted():
    class D(FakeLLM):
        reply = "flowchart LR\nX[New] --> Y[Different]"
        def complete_text(self, system, prompt, max_tokens=1500):
            return "- a\n- b\n- c" if "NARRATION:" in prompt and "Mermaid" not in prompt else self.reply
    base = {**scenes_with_words(30, 1)[0], "type": "diagram", "mermaid": "flowchart LR\nA[In] --> B[Out]"}
    prior = [generation.SectionScene.model_validate(base)]
    dup = generation.SectionScene.model_validate(base)
    d = D()
    assert generation._dedupe_diagrams(d, prior, [dup])[0].mermaid.startswith("flowchart LR\nX[New]")
    d.reply = "flowchart LR\nA[In] --> B[Out]"  # model cannot produce anything different
    out = generation._ensure_bullets(d, generation._dedupe_diagrams(d, prior, [dup]))[0]
    assert out.type == "slide" and out.bullets and not out.mermaid


def test_unsupported_real_world_claims_are_flagged():
    mk = lambda t: type("S", (), {"narration": t, "mermaid": None})()
    bad = ["In 2018, a security researcher discovered a reflected XSS vulnerability in a popular application.",
           "Studies show that most sites are vulnerable.", "About 40 percent of applications are affected.", "This was tracked as CVE-2020-12345."]
    for t in bad:
        assert lengthplan.claim_issues([mk(t)]), t
    ok = "Attackers have used this technique to steal session cookies, which is why output encoding matters in every template."
    assert lengthplan.claim_issues([mk(ok)]) == []


def test_cached_section_with_a_claim_is_regenerated(tmp_path):
    llm = FakeLLM()
    generation.build_storyboard_by_sections(lesson(8), {}, llm, tmp_path)
    f = tmp_path / "defense.json"
    d = json.loads(f.read_text()); d["scenes"][0]["narration"] = "In 2019 a company was breached by this. " + d["scenes"][0]["narration"]
    f.write_text(json.dumps(d))
    llm2 = FakeLLM()
    generation.build_storyboard_by_sections(lesson(8), {}, llm2, tmp_path)
    assert [c[0] for c in llm2.calls] == ["defense"]  # only the tainted cache entry was redone
