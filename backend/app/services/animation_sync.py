"""Narration -> animation synchronisation. Turns a scene's declarative `AnimationSpec` plus the audio timing into a flat,
frame-numbered event list that the Remotion components consume. All timing decisions live here (pure functions, no I/O),
so React only plays events and there is exactly one fallback implementation.

Timing quality, best to worst (reported per event in `basis`):
  sentence  - the event lands on a real sentence boundary (narration.synth_with_timing measures them per sentence)
  word_est  - a word inside a measured sentence; its position is interpolated by character length (NOT forced alignment)
  scene_est - no timing.json for this scene: sentences are spread over the audio duration by character count
  cadence   - narration_sync.mode == "none": fixed interval from scene start"""
import re
from dataclasses import asdict, dataclass

from app.schemas.animation import AnimationSpec, AnimationStep
from app.services import mermaid_lite, subtitles

CADENCE_S = 0.8
MAX_TARGETS = 80
_TOKEN = re.compile(r"[a-z0-9]+")


@dataclass
class Word:
    index: int
    text: str
    start: float
    end: float
    basis: str  # word_est | scene_est


@dataclass
class Event:
    target: str
    action: str
    frame: int
    effect: str | None
    duration_frames: int
    easing: str
    direction: str
    basis: str


def _norm(s: str) -> list[str]:
    return _TOKEN.findall(s.lower())


def sentence_windows(narration: str, timing: list[dict] | None, audio_s: float) -> tuple[list[tuple[float, float]], str]:
    """(start, end) of every spoken sentence, and whether they are measured ('sentence') or estimated ('scene_est')."""
    if timing:
        return [(float(c["start"]), float(c["end"])) for c in timing], "sentence"
    cues = subtitles.scene_cues(narration, 0.0, audio_s)
    return [(c.start, c.end) for c in cues], "scene_est"


def word_timeline(narration: str, timing: list[dict] | None, audio_s: float) -> list[Word]:
    """Word start/end seconds. Inside each sentence window words share the time by length (+1 char of breath each),
    and a trailing comma/period adds a small pause weight. Sentence edges are real when `timing` is present."""
    if timing:
        sents = [(c["text"], float(c["start"]), float(c["end"])) for c in timing]
        basis = "word_est"
    else:
        sents = [(c.text, c.start, c.end) for c in subtitles.scene_cues(narration, 0.0, audio_s)]
        basis = "scene_est"
    words: list[Word] = []
    for text, a, b in sents:
        toks = text.split()
        if not toks:
            continue
        weights = [len(t) + 1 + (2 if t[-1] in ",;:" else 0) for t in toks]
        total, t = sum(weights), a
        for tok, w in zip(toks, weights):
            d = (b - a) * w / total
            words.append(Word(len(words), tok, round(t, 3), round(t + d, 3), basis))
            t += d
    return words


def find_phrase(words: list[Word], phrase: str) -> int | None:
    """Index of the first word of the first occurrence of `phrase` (case/punctuation-insensitive), else None."""
    want = _norm(phrase)
    if not want:
        return None
    toks = [(w.index, _norm(w.text)) for w in words]
    flat = [(i, t) for i, ts in toks for t in ts]
    for k in range(len(flat) - len(want) + 1):
        if [t for _, t in flat[k:k + len(want)]] == want:
            return flat[k][0]
    return None


def auto_targets(scene) -> list[str]:
    """The scene's own revealable content, in reading order. Target ids are positional so a plain scene needs no metadata."""
    t = scene.type
    if t == "diagram" and scene.visualization is not None:  # technical visualization: one reveal per teaching step
        return [f"step.{i}" for i in range(min(scene.visualization.step_count, MAX_TARGETS))]
    if t == "diagram" and scene.mode3d == "stack":
        return [f"layer.{i}" for i in range(min(len(scene.bullets or []), MAX_TARGETS))]
    if t == "diagram" and scene.mermaid and not scene.mode3d:
        try:
            return [f"node.{n}" for n in mermaid_lite.parse(scene.mermaid).nodes][:MAX_TARGETS]
        except ValueError:
            return []
    if t in ("slide", "summary", "quiz"):
        return [f"bullet.{i}" for i in range(min(len(scene.bullets or []), MAX_TARGETS))]
    if t in ("terminal", "browser"):
        return [f"line.{i}" for i in range(min(len(scene.terminal_lines or []), MAX_TARGETS))]
    if t == "code" and scene.code:
        return [f"line.{i}" for i in range(min(len(scene.code.split("\n")), MAX_TARGETS))]
    return []


def _auto_times(n: int, windows: list[tuple[float, float]], audio_s: float) -> list[float]:
    """Seconds at which n reveals should start: sentence starts when there are enough sentences, else an even spread."""
    if n == 0:
        return []
    first = windows[0][0] if windows else 0.0
    end = windows[-1][1] if windows else audio_s
    if len(windows) >= n:
        return [windows[(i * len(windows)) // n][0] for i in range(n)]
    span = max(end - first, 0.0)
    return [first + span * i / n for i in range(n)]


def _easing(step: AnimationStep | None, spec: AnimationSpec) -> str:
    return (step.easing if step and step.easing else spec.animation_easing)


def resolve_events(scene, timing: list[dict] | None, audio_s: float, fps: int, total_frames: int) -> tuple[list[Event], list[str]]:
    """Scene + audio timing -> (events sorted by frame, warnings). A scene with no `animation` still gets sensible
    auto-timed reveals, which is what keeps lessons generated before this feature animated and in sync."""
    spec: AnimationSpec = scene.animation or AnimationSpec()
    warnings: list[str] = []
    windows, win_basis = sentence_windows(scene.narration, timing, audio_s)
    words = word_timeline(scene.narration, timing, audio_s)
    mode = spec.narration_sync.mode
    lead = spec.narration_sync.lead_seconds
    dur_f = max(1, round(spec.animation_duration * fps))
    delay = spec.animation_delay

    def frame(sec: float) -> int:
        return max(0, min(total_frames - 1, round((sec + delay - lead) * fps)))

    events: list[Event] = []
    auto = auto_targets(scene)
    steps = list(spec.animation_sequence)
    explicit_show = {s.target for s in steps if s.action in ("show", "reveal")}
    base_effect = spec.entrance_animation

    # 1. default reveals for every content target the author did not script explicitly
    rest = [t for t in auto if t not in explicit_show]
    if mode == "none":
        times, basis = [CADENCE_S * i for i in range(len(rest))], "cadence"
    else:
        times, basis = _auto_times(len(rest), windows, audio_s), win_basis
    for tgt, sec in zip(rest, times):
        events.append(Event(tgt, "show", frame(sec), base_effect, dur_f, spec.animation_easing, spec.animation_direction, basis))

    # 2. scripted steps
    n_steps = len(steps)
    fallback = _auto_times(n_steps, windows, audio_s) if mode != "none" else [CADENCE_S * i for i in range(n_steps)]
    for i, s in enumerate(steps):
        sec, basis = fallback[i], ("cadence" if mode == "none" else win_basis)
        if mode == "anchored":
            if s.at_seconds is not None:
                sec, basis = s.at_seconds, "sentence"
            elif s.at_fraction is not None:
                a = windows[0][0] if windows else 0.0
                sec, basis = a + ((windows[-1][1] if windows else audio_s) - a) * s.at_fraction, win_basis
            elif s.at_word is not None:
                if s.at_word < len(words):
                    sec, basis = words[s.at_word].start, words[s.at_word].basis
                else:
                    warnings.append(f"{scene.scene_id}: at_word {s.at_word} beyond narration ({len(words)} words); placed automatically")
            elif s.at_phrase is not None:
                k = find_phrase(words, s.at_phrase)
                if k is None:
                    warnings.append(f"{scene.scene_id}: phrase {s.at_phrase!r} not found in narration; placed automatically")
                else:
                    sec, basis = words[k].start, words[k].basis
        d = max(1, round((s.duration or spec.animation_duration) * fps))
        eff = s.effect or (spec.emphasis_animation if s.action in ("highlight", "pulse", "focus") else base_effect)
        events.append(Event(s.target, s.action, frame(sec), eff if eff != "none" else None, d, _easing(s, spec), s.direction or spec.animation_direction, basis))

    if scene.type == "quiz" and scene.quiz_answer is not None and not any(s.target == "answer" for s in steps):
        # the answer is revealed once the options have been read out: late in the narration, after the last option appears
        speech_end = windows[-1][1] if windows else audio_s
        last_opt = max((e.frame for e in events if e.target.startswith("bullet.")), default=0)
        events.append(Event("answer", "show", max(last_opt + round(1.2 * fps), frame(speech_end * 0.8)), "fade", dur_f, spec.animation_easing, "none", win_basis))
    events.sort(key=lambda e: (e.frame, e.target))
    return events, warnings


def events_payload(events: list[Event]) -> list[dict]:
    return [asdict(e) for e in events]
