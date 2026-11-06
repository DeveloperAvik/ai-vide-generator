"""Length planning. Video length = narration length, so we budget WORDS from the requested minutes, generate the
storyboard section by section against those budgets, correct sections that miss, and enforce the result in QC.
WPS is calibrated on a real render: 957 words -> 387 s with Piper (incl. sentence gaps, scene padding, quiz pauses) = 2.47 w/s."""
import json
import re

from app.core.config import get_settings
from app.schemas.content import StoryboardData

DEFAULT_WPS = 2.45
SCENE_OVERHEAD = 0.12  # scene padding, transitions, quiz pauses: rendered length / pure narration length - 1 (from the 6m27s render)


def active_voice_label() -> str:
    """Label of the voice that will narrate (e.g. kokoro:am_michael:1). Speed is measured per voice, never pooled across voices."""
    try:
        from app.providers.voice import get_voice
        return get_voice(None).label
    except Exception:  # noqa: BLE001 - no voice installed: planning falls back to the default constant
        return "none"


def _cal_path(label: str | None = None):
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", label or active_voice_label())
    return get_settings().manifests_root / f"voice_calibration__{safe}.json"


def _load_wps() -> float:
    """Pooled speed of the ACTIVE voice (total words / total seconds over its measured samples) minus scene overhead; falls back to the
    old constant for a voice that has never been measured. Speed depends on the text, so samples accumulate."""
    try:
        cal = json.loads(_cal_path().read_text())
        return round(float(cal["wps"]) / (1 + SCENE_OVERHEAD), 3)
    except (OSError, ValueError, KeyError):
        return DEFAULT_WPS


def record_voice_sample(source: str, words: int, seconds: float, voice: str | None = None) -> dict:
    """Add a MEASURED (words, seconds) pair for `voice` (label) and re-pool. Called after every real TTS run and by the calibration CLI."""
    voice = voice or active_voice_label()
    path = _cal_path(voice)
    try:
        cal = json.loads(path.read_text())
    except (OSError, ValueError):
        cal = {}
    samples = [x for x in cal.get("samples", []) if x["source"] != source][-19:] + [{"source": source, "words": int(words), "seconds": round(seconds, 1)}]
    cal.update(voice=voice, samples=samples, wps=round(sum(x["words"] for x in samples) / sum(x["seconds"] for x in samples), 3))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cal, indent=2))
    return cal


WPS = _load_wps()
MIN_VIDEO_S, MAX_VIDEO_S = 300, 1500  # 5-25 minutes (advanced videos up to 25)
TOLERANCE = 0.12  # +-12% of the word budget is accepted
SECTIONS: list[tuple[str, float, str]] = [
    ("hook_intro", 0.06, "Instructor scene(s): a strong hook, then why this topic matters and what will be covered."),
    ("objectives", 0.04, "One slide scene. The bullets list the learning objectives; the NARRATION must speak them in full sentences ('By the end you will be able to ...', one sentence per objective) and then state that all practice happens only in an authorized, isolated lab."),
    ("fundamentals", 0.12, "Background and fundamentals a beginner needs first: the technologies and terms involved. Slides, optionally a diagram."),
    ("technical", 0.20, "Technical explanation of the root cause and mechanism: slide and diagram scenes. Optionally use mode3d (flow from `mermaid`, or stack from `bullets`) for one key diagram."),
    ("demo", 0.24, "Practical demonstration in an authorized lab: code scenes (vulnerable vs fixed) and terminal scenes with ILLUSTRATIVE output only; explain what each step shows and why."),
    ("attack_scenarios", 0.10, "Real-world attack scenarios: how this appears in real incidents, pentests and bug bounty; impact; responsible reporting. Do not invent incidents, CVE ids or victims."),
    ("defense", 0.12, "Detection and mitigation: secure coding, configuration, monitoring and logging. Slides, optionally a diagram."),
    ("mistakes", 0.05, "Common mistakes developers, defenders and learners make; one or two slide scenes. Narrate each mistake in a sentence or two: what people do wrong, why it fails, what to do instead."),
    ("quiz", 0.04, "Knowledge-check questions: one or more quiz scenes (question + 4 options in bullets) with time to pause, then the answers explained."),
    ("conclusion", 0.03, "One summary scene (bullets; narration recaps each key point in a sentence) and a brief instructor closing scene that names a next step for the learner."),
]
# The guides above are written for security lessons (lab, vulnerable vs fixed code, attacks, bug bounty). Every other subject gets neutral ones:
# same section names, budgets and order, different instructions.
GENERIC_GUIDES = {
    "objectives": "One slide scene. The bullets list the learning objectives; the NARRATION must speak them in full sentences ('By the end you will be able to ...', one sentence per objective).",
    "demo": "A worked example or hands-on demonstration: code scenes and terminal scenes with ILLUSTRATIVE output only (never present invented results as measured); explain what each step does and why, and what the learner should see.",
    "attack_scenarios": "Real-world applications and use cases: where this is used in practice, what it is good at and what it is not. Do not invent companies, products, studies or statistics.",
    "defense": "Limitations, risks and best practices: common failure modes, how to avoid or detect them, and how to apply the technique responsibly. Slides, optionally a diagram.",
    "mistakes": "Common mistakes learners and practitioners make; one or two slide scenes. Narrate each mistake in a sentence or two: what people do wrong, why it fails, what to do instead.",
}


def sections_for(security: bool) -> list[tuple[str, float, str]]:
    """(name, share, guide) for a lesson. Names and shares are fixed; security domains keep the lab/attack/defense wording."""
    return list(SECTIONS) if security else [(n, f, GENERIC_GUIDES.get(n, g)) for n, f, g in SECTIONS]


assert abs(sum(f for _, f, _ in SECTIONS) - 1) < 1e-9


def validate_request(minutes: float) -> None:
    """Pre-generation validation: the supported range is 5-25 minutes."""
    if not MIN_VIDEO_S / 60 <= minutes <= MAX_VIDEO_S / 60:
        raise ValueError(f"requested duration {minutes} min is outside the supported {MIN_VIDEO_S // 60}-{MAX_VIDEO_S // 60} minute range")


def scene_count(budget: int) -> int:
    """Models follow 'N scenes of ~W words' far better than a single total, so the prompt carries both."""
    return max(1, round(budget / 55))


def _trigrams(text: str) -> set:
    w = [x.strip(".,;:!?\"'()").lower() for x in text.split()]
    return {tuple(w[i:i + 3]) for i in range(len(w) - 2)}


def repetition_pairs(scenes, threshold: float = 0.5) -> list[tuple[int, int, str]]:
    """(earlier index, later index, reason) for near-duplicate narration (trigram Jaccard) or a shared 7-word phrase. 0-based."""
    pairs: dict[tuple[int, int], str] = {}
    grams = [_trigrams(s.narration) for s in scenes]
    seq = []
    for s in scenes:
        w = [x.strip(".,;:!?\"'()").lower() for x in s.narration.split()]
        seq.append({tuple(w[i:i + 7]) for i in range(len(w) - 6)})
    for x in range(len(scenes)):
        for y in range(x + 1, len(scenes)):
            a, b = grams[x], grams[y]
            if len(a) >= 6 and len(b) >= 6 and len(a & b) / len(a | b) >= threshold:
                pairs[(x, y)] = "nearly the same thing"
            elif seq[x] & seq[y]:
                pairs[(x, y)] = f"both say \"{' '.join(sorted(seq[x] & seq[y])[0])}\""
    return [(x, y, r) for (x, y), r in sorted(pairs.items())]


def repetition_issues(scenes, threshold: float = 0.5) -> list[str]:
    """Human-readable repetition findings (see repetition_pairs) plus identical diagrams."""
    issues = [f"scenes {x + 1} and {y + 1} {r}" for x, y, r in repetition_pairs(scenes, threshold)]
    seen: dict[str, int] = {}
    for i, s in enumerate(scenes, 1):
        m = (getattr(s, "mermaid", None) or "").strip()
        if m:
            if m in seen:
                issues.append(f"scenes {seen[m]} and {i} use the identical diagram")
            seen.setdefault(m, i)
    return issues


_MARKUP = re.compile(r"&(?:[a-z]+|#\d+);|</?[A-Za-z][^>\s]*|[<>{}\\|`]|\bhttps?://")


def speakability_issues(scenes) -> list[str]:
    """Narration is read by a TTS voice: HTML entities, tags, code punctuation and URLs would be spoken as symbols or garbled.
    Code belongs in `code`/`terminal_lines`; in narration, describe it in words ('the less-than script tag')."""
    out = []
    for i, sc in enumerate(scenes, 1):
        m = _MARKUP.search(sc.narration)
        if m:
            out.append(f"scene {i} narration contains {m.group(0)!r}; describe code and markup in words instead")
    return out


_CLAIM = re.compile(r"\b(?:in|since|during|back in|around)\s+(?:19|20)\d\d\b|\bCVE-\d{4}-\d+|\b\d+(?:\.\d+)?\s?(?:%|percent)"
                    r"|\b(?:a|one|the|several)\s+(?:security\s+)?(?:researchers?|companies|company|hackers?|attackers?)\s+(?:\w+\s+){0,3}?"
                    r"(?:discovered|reported|breached|exploited|found)\b|\b(?:studies|research|surveys?)\s+(?:show|shows|found|indicate)", re.I)


# "80% of the data for training" is a teaching parameter, not a statistic about the world
_PARAMETER_PCT = re.compile(r"\b\d+(?:\.\d+)?\s?(?:%|percent)\s+(?:of\s+(?:the\s+)?)?(?:\w+\s+){0,3}?(?:for|to|as|in)\s+(?:the\s+)?(?:training|testing|test|validation|train|split)\b", re.I)


def _without_parameters(text: str) -> str:
    return _PARAMETER_PCT.sub("", text)


def claim_issues(scenes) -> list[str]:
    """Specific, checkable real-world claims (dates, statistics, CVE ids, 'a researcher discovered ...') that a local model can only
    invent. Narration must stay general unless a verified source supports the claim (source-backed claims arrive with Phase 6)."""
    out = []
    for i, sc in enumerate(scenes, 1):
        m = _CLAIM.search(_without_parameters(sc.narration))
        if m:
            out.append(f"scene {i} makes an unsupported real-world claim ({m.group(0)!r}); speak generally, no dates, statistics, CVE ids or named/unnamed incidents")
    return out


def target_words(minutes: float) -> int:
    return int(minutes * 60 * WPS)


def word_count(sb: StoryboardData) -> int:
    return sum(len(s.narration.split()) for s in sb.scenes)


def estimate_seconds(sb: StoryboardData) -> float:
    """Rendered length: each scene lasts max(declared, narration + 0.4 s)."""
    return sum(max(s.duration_seconds, len(s.narration.split()) / WPS + 0.4) for s in sb.scenes)


def budgets(minutes: float) -> dict[str, int]:
    total = target_words(minutes)
    return {name: max(25, int(total * frac)) for name, frac, _ in SECTIONS}


def within(words: int, budget: int, tol: float = TOLERANCE) -> bool:
    return budget * (1 - tol) <= words <= budget * (1 + tol)


def window(requested_min: float, draft: bool = False) -> tuple[float, float]:
    """Accepted video length in seconds. Published lessons: +-20% and never under 5 minutes. A quick draft is a preview, so it gets a wider
    window (-35% / +35%, no 5-minute floor) instead of failing after twenty minutes of generation for being a little short."""
    if draft:
        return 0.65 * requested_min * 60, min(MAX_VIDEO_S, 1.35 * requested_min * 60)
    return max(MIN_VIDEO_S, 0.8 * requested_min * 60), min(MAX_VIDEO_S, 1.2 * requested_min * 60)


def length_check(duration_s: float, requested_min: float, generated_by: str, draft: bool = False) -> tuple[bool, str, bool]:
    """-> (passed, detail, blocking). Mock-generated template content is exempt (it is not meant for publication)."""
    lo, hi = window(requested_min, draft)
    ok = lo <= duration_s <= hi
    detail = f"{duration_s / 60:.1f} min; required {lo / 60:.1f}-{hi / 60:.1f} min (requested {requested_min} min, hard limits 5-25)"
    if generated_by.startswith("mock"):
        return ok, detail + " [mock template: length not enforced]", False
    if not ok:
        detail += ". Regenerate the storyboard (it is built against a word budget) or edit narration."
    return ok, detail, True


PLACEHOLDER_PATTERNS = ("lorem ipsum", "todo", "tbd", "[insert", "xxx", "placeholder", "your text here", "<narration", "scene_000")


def preflight(sb: StoryboardData, requested_min: float, generated_by: str, draft: bool = False) -> list[str]:
    """Cheap blocking checks run BEFORE TTS and rendering. Returns problems (empty = ok). Mock content is never exempt from
    the placeholder check; it is exempt only from the length check."""
    problems = []
    try:
        validate_request(requested_min)
    except ValueError as e:
        problems.append(str(e))
    for sc in sb.scenes:
        low = sc.narration.lower()
        hit = [p for p in PLACEHOLDER_PATTERNS if p in low]
        if hit or not sc.narration.strip():
            problems.append(f"{sc.scene_id}: empty or placeholder narration {hit}")
    problems += repetition_issues(sb.scenes) + speakability_issues(sb.scenes) + claim_issues(sb.scenes)
    from app.services import mermaid_lite
    for sc in sb.scenes:
        if sc.type == "diagram":
            try:
                mermaid_lite.parse(sc.mermaid or "")
            except ValueError as e:
                problems.append(f"{sc.scene_id}: diagram cannot be drawn ({e})")
    if not generated_by.startswith("mock") and not problems:
        est = estimate_seconds(sb)
        lo, hi = window(requested_min, draft)
        if not lo <= est <= hi:
            problems.append(f"estimated length {est / 60:.1f} min is outside {lo / 60:.1f}-{hi / 60:.1f} min "
                            f"({word_count(sb)} words; {target_words(requested_min)} needed for {requested_min} min)")
    return problems


def audio_check(audio_s: float, requested_min: float, generated_by: str, draft: bool = False) -> tuple[bool, str]:
    """After TTS: MEASURED narration length must fit the request (video = audio + scene overhead). Mock content exempt."""
    if draft:
        lo, hi = (x / (1 + SCENE_OVERHEAD) for x in window(requested_min, True))
    else:
        lo, hi = 0.8 * requested_min * 60 / (1 + SCENE_OVERHEAD), 1.2 * requested_min * 60 / (1 + SCENE_OVERHEAD)
    ok = lo <= audio_s <= hi or generated_by.startswith("mock")
    return ok, f"measured narration {audio_s / 60:.1f} min; required {lo / 60:.1f}-{hi / 60:.1f} min for a {requested_min} min video"


def video_check(video_s: float, audio_s: float, requested_min: float, draft: bool = False) -> tuple[bool, str]:
    """After render: the ffprobe duration of the MP4 must cover all narration and sit inside the requested window."""
    ok_len, detail, _ = length_check(video_s, requested_min, "real", draft)
    ok = ok_len and video_s >= audio_s - 0.5
    return ok, f"measured video {video_s / 60:.2f} min vs narration {audio_s / 60:.2f} min; {detail}"
