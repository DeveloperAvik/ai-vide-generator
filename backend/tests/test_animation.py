"""Animation metadata schema + narration synchronisation (pure logic, no rendering)."""
import pytest
from pydantic import ValidationError

from app.schemas.animation import AnimationSpec, AnimationStep, clean_animation
from app.schemas.content import Scene, StoryboardData
from app.services import animation_sync as sync
from app.services.generation import SectionScene

TIMING = [{"text": "First, the program allocates a buffer of 64 bytes.", "start": 0.0, "end": 3.0},
          {"text": "Then user input is copied into it.", "start": 3.2, "end": 5.2}]
NARR = " ".join(t["text"] for t in TIMING)


def scene(**kw):
    base = dict(scene_id="scene_001", type="slide", duration_seconds=10, narration=NARR, visual_description="v",
                on_screen_text="T", bullets=["a", "b", "c"])
    return Scene(**{**base, **kw})


# ---- schema ----
def test_old_storyboard_without_animation_validates():
    sb = StoryboardData.model_validate({"lesson_title": "x", "scenes": [
        {"scene_id": "scene_001", "type": "slide", "duration_seconds": 5, "narration": "n", "visual_description": "v", "bullets": ["a"]},
        {"scene_id": "scene_002", "type": "summary", "duration_seconds": 5, "narration": "n", "visual_description": "v", "bullets": ["a"]}]})
    assert sb.scenes[0].animation is None


def test_unknown_field_and_code_injection_rejected():
    with pytest.raises(ValidationError):
        AnimationSpec.model_validate({"onEnter": "alert(1)"})
    with pytest.raises(ValidationError):
        AnimationSpec.model_validate({"entrance_animation": "() => evil()"})
    with pytest.raises(ValidationError):
        AnimationStep(target="bullet.0; drop()", action="show")


def test_bounds_and_single_anchor():
    with pytest.raises(ValidationError):
        AnimationSpec(animation_duration=99)
    with pytest.raises(ValidationError):
        AnimationStep(target="bullet.0", at_word=1, at_phrase="x y")
    with pytest.raises(ValidationError):
        AnimationSpec(animation_sequence=[AnimationStep(target="bullet.0"), AnimationStep(target="bullet.0")])


def test_llm_scene_drops_bad_animation_but_keeps_good():
    raw = dict(type="slide", duration_seconds=10, narration="n", visual_description="v", bullets=["a"])
    bad = SectionScene.model_validate({**raw, "animation": {"entrance_animation": "<script>"}})
    assert bad.animation is None
    good = SectionScene.model_validate({**raw, "animation": {"entrance_animation": "slide", "animation_sequence": [{"target": "bullet.0"}]}})
    assert good.animation.entrance_animation == "slide"
    assert clean_animation("garbage") is None


# ---- sync ----
def test_word_timeline_stays_inside_measured_sentences_and_is_monotonic():
    w = sync.word_timeline(NARR, TIMING, 5.2)
    assert len(w) == len(NARR.split())
    assert w[0].start == 0.0 and w[-1].end == pytest.approx(5.2, abs=0.01)
    assert all(a.end <= b.start + 1e-6 for a, b in zip(w, w[1:]))
    assert all(x.basis == "word_est" for x in w)
    first_sentence = len(TIMING[0]["text"].split())
    assert w[first_sentence - 1].end == pytest.approx(3.0, abs=0.01)  # sentence edge is the real measurement


def test_phrase_anchor_lands_on_the_spoken_word():
    s = scene(animation=AnimationSpec(narration_sync={"mode": "anchored", "lead_seconds": 0.0},
                                      animation_sequence=[AnimationStep(target="bullet.1", at_phrase="a buffer of 64 bytes")]))
    ev, warn = sync.resolve_events(s, TIMING, 5.2, 30, 200)
    e = next(x for x in ev if x.target == "bullet.1")
    words = sync.word_timeline(NARR, TIMING, 5.2)
    k = sync.find_phrase(words, "a buffer of 64 bytes")
    assert e.frame == round(words[k].start * 30) and e.basis == "word_est" and not warn


def test_missing_phrase_falls_back_with_warning():
    s = scene(animation=AnimationSpec(narration_sync={"mode": "anchored"}, animation_sequence=[AnimationStep(target="bullet.0", at_phrase="not in narration")]))
    ev, warn = sync.resolve_events(s, TIMING, 5.2, 30, 200)
    assert any("not found" in x for x in warn) and any(e.target == "bullet.0" for e in ev)


def test_no_animation_metadata_still_gets_audio_synced_reveals():
    ev, _ = sync.resolve_events(scene(), TIMING, 5.2, 30, 200)
    assert [e.target for e in ev] == ["bullet.0", "bullet.1", "bullet.2"]
    assert ev[0].frame <= ev[1].frame <= ev[2].frame
    assert ev[-1].frame < 5.2 * 30  # all revealed while the narrator is still talking


def test_no_word_timing_falls_back_to_estimated_spread():
    ev, _ = sync.resolve_events(scene(), None, 5.0, 30, 200)
    assert len(ev) == 3 and {e.basis for e in ev} == {"scene_est"}
    assert all(0 <= e.frame < 200 for e in ev)


def test_cadence_mode_ignores_audio():
    s = scene(animation=AnimationSpec(narration_sync={"mode": "none", "lead_seconds": 0.0}))
    ev, _ = sync.resolve_events(s, TIMING, 5.2, 30, 200)
    assert [e.frame for e in ev] == [0, 24, 48] and {e.basis for e in ev} == {"cadence"}


def test_frames_clamped_to_scene_length_and_diagram_targets():
    s = scene(type="diagram", bullets=None, mermaid="flowchart LR\nA[User] --> B[API]\nB --> C[DB]",
              animation=AnimationSpec(narration_sync={"mode": "anchored"}, animation_sequence=[AnimationStep(target="node.C", at_seconds=500)]))
    ev, _ = sync.resolve_events(s, TIMING, 5.2, 30, 100)
    assert {e.target for e in ev} == {"node.A", "node.B", "node.C"}
    assert max(e.frame for e in ev) == 99


# ---- visualization schema ----
from app.schemas.visualization import clean_visualization  # noqa: E402

BO = {"kind": "buffer_overflow", "buffer_size": 64, "input_length": 80}


def test_visualization_valid_and_step_counts():
    s = scene(type="diagram", bullets=None, mermaid="flowchart LR\nA --> B", visualization=BO)
    assert s.visualization.step_count == 5
    ev, _ = sync.resolve_events(s, TIMING, 5.2, 30, 200)
    assert [e.target for e in ev] == [f"step.{i}" for i in range(5)]  # one reveal per teaching step, no mermaid-node targets


@pytest.mark.parametrize("bad", [
    {**BO, "buffer_size": 4}, {**BO, "original_return": "401176"}, {**BO, "fill_byte": "AB"}, {"kind": "nope"},
    {"kind": "heap", "ops": [{"op": "free", "chunk": "A"}]},
    {"kind": "heap", "ops": [{"op": "malloc", "chunk": "A", "size": 8}, {"op": "malloc", "chunk": "A", "size": 8}]},
    {"kind": "assembly", "instructions": [{"addr": "0x1", "text": "nop"}], "steps": [{"line": 3}]},
    {"kind": "assembly", "instructions": [{"addr": "0x1", "text": "nop"}], "steps": [{"line": 0, "set": [{"reg": "zzz", "value": "0x1"}]}]},
    {"kind": "control_flow", "blocks": [{"id": "a", "lines": ["x"]}, {"id": "b", "lines": ["y"]}], "edges": [{"a": "a", "b": "ghost"}], "path": ["a"]},
    {"kind": "packet_flow", "nodes": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}], "packets": [{"src": "a", "dst": "a", "label": "x"}]},
    {**BO, "js": "alert(1)"},
])
def test_visualization_rejects_bad_data(bad):
    assert clean_visualization(bad) is None
    with pytest.raises(ValidationError):
        scene(type="diagram", bullets=None, mermaid="flowchart LR\nA --> B", visualization=bad)


def test_llm_section_drops_bad_visualization_keeps_scene():
    raw = dict(type="diagram", duration_seconds=10, narration="n", visual_description="v", mermaid="flowchart LR\nA --> B")
    assert SectionScene.model_validate({**raw, "visualization": {"kind": "heap", "ops": []}}).visualization is None
    assert SectionScene.model_validate({**raw, "visualization": BO}).visualization.kind == "buffer_overflow"
    assert SectionScene.model_validate({**{**raw, "type": "slide", "bullets": ["a"]}, "visualization": BO}).visualization is None  # only diagram scenes carry one


def test_quiz_answer_validation_and_feedback_event():
    q = scene(type="quiz", bullets=["a", "b", "c"], quiz_answer=1)
    ev, _ = sync.resolve_events(q, TIMING, 5.2, 30, 400)
    ans = [e for e in ev if e.target == "answer"]
    assert len(ans) == 1 and ans[0].frame > max(e.frame for e in ev if e.target.startswith("bullet."))
    with pytest.raises(ValidationError):
        scene(type="quiz", bullets=["a", "b"], quiz_answer=5)
    with pytest.raises(ValidationError):
        scene(type="slide", quiz_answer=0)
    assert not any(e.target == "answer" for e in sync.resolve_events(scene(type="quiz", bullets=["a", "b"]), TIMING, 5.2, 30, 400)[0])  # no answer data -> no feedback invented


def test_llm_section_scene_with_empty_terminal_or_code_payload_becomes_a_slide():
    """A small model sometimes emits type=terminal/code with no payload; that must not fail the whole section."""
    from app.services.generation import SectionScene
    base = {"narration": "word " * 30, "duration_seconds": 10, "visual_description": "v", "on_screen_text": "t"}
    assert SectionScene.model_validate({**base, "type": "terminal", "terminal_lines": []}).type == "slide"
    assert SectionScene.model_validate({**base, "type": "code", "code": "  "}).type == "slide"
    assert SectionScene.model_validate({**base, "type": "terminal", "terminal_lines": ["$ id"]}).type == "terminal"


def test_semantic_repetition_flags_reworded_steps_but_not_quiz_or_summary():
    from types import SimpleNamespace as N
    from app.services import lengthplan
    a = "First contact the management or legal department and request formal authorization, then submit a detailed scope document covering systems, networks, methods and timeline."
    b = "Reach out to legal or management to obtain formal authorization, and prepare a detailed scope document describing the systems, networks, testing methods and the timeline."
    c = "Encryption keys should be rotated regularly and stored inside hardware security modules with strict audit logging enabled for every access request."
    sc = [N(type="instructor", narration=a), N(type="slide", narration=b), N(type="slide", narration=c), N(type="summary", narration="To recap: legal sign-off plus a written scope of systems, networks, methods and timeline protects everyone involved.")]
    assert lengthplan.repetition_pairs(sc) == []                      # the hard (stitch) check is unchanged
    assert [(x, y) for x, y, _ in lengthplan.repetition_pairs(sc, semantic=True)] == [(0, 1)]


def test_covered_note_carries_narration_not_just_the_scene_type():
    from types import SimpleNamespace as N
    from app.services.generation import _covered_note
    assert _covered_note(N(on_screen_text="", narration="Contact legal first. Then scope.")) == "Contact legal first."
    assert _covered_note(N(on_screen_text="Scope", narration="Define the scope. More.")) == "Scope: Define the scope."
