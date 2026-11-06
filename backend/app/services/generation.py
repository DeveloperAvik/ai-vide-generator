"""LLM-backed generation: curriculum, lesson script, storyboard, YouTube metadata. All output is schema-validated;
on validation failure we retry once feeding the error back, then raise - malformed data is never saved."""
import json
import re
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel, ValidationError, model_validator
from sqlalchemy.orm import Session

from app.models import Course, Lesson, LessonScript, Module, Scene as SceneRow, Storyboard
from app.providers.llm import LLMError, LLMProvider, load_prompt
from pydantic import Field
from app.schemas.animation import clean_animation
from app.schemas.visualization import clean_visualization
from app.schemas.content import Scene, Strict
from app.services import lengthplan
from app.schemas.content import (Curriculum, CurriculumRequest, LessonScriptData, StoryboardData, YouTubeMetadata)
from app.services import domains
from app.utils.media import sha256_text

T = TypeVar("T", bound=BaseModel)


class SourceSuggestion(Strict):
    kind: str = ""
    title: str = ""
    url: str
    why_relevant: str = ""


class SourceSuggestions(Strict):
    sources: list[SourceSuggestion] = Field(default_factory=list)


def _ask(llm: LLMProvider, task: str, prompt: str, model: type[T], retries: int = 1, domain: str = "") -> T:
    system = load_prompt({"metadata": "youtube_metadata"}.get(task, task)) + domains.prompt_block(domain) + (domains.lesson_requirements(domain) if task in ("lesson", "tech_review") else "") + \
        f"\n\nJSON SCHEMA:\n{json.dumps(model.model_json_schema())}\n\nTASK: {task}"
    err = ""
    for _ in range(retries + 1):
        raw = llm.complete_json(system, prompt + (f"\n\nYour previous answer failed validation:\n{err}\nFix it." if err else ""), schema=model.model_json_schema())
        try:
            return model.model_validate(raw)
        except ValidationError as e:
            err = str(e)[:1500]
    raise LLMError(f"{task}: output failed schema validation after retry: {err[:400]}")


def generate_curriculum(db: Session, req: CurriculumRequest, llm: LLMProvider) -> Course:
    if db.query(Course).filter(Course.name == req.course_name).first():
        raise ValueError(f"Course '{req.course_name}' already exists")
    prompt = (f"TOPIC: {req.course_name}\nSUBJECT: {domains.get(req.domain).label}\nLANGUAGE: {req.language}\nDIFFICULTY: {req.difficulty}\n"
              f"AUDIENCE: {req.target_audience}\nVIDEOS_PER_WEEK: {req.videos_per_week}\nDURATION: {req.duration_minutes}")
    cur = _ask(llm, "curriculum", prompt, Curriculum, domain=req.domain)
    course = Course(name=req.course_name, description=cur.description, language=req.language, difficulty=req.difficulty,
                    target_audience=req.target_audience, domain=req.domain, videos_per_week=req.videos_per_week, duration_minutes=req.duration_minutes,
                    learning_objectives=cur.learning_objectives, prerequisites=cur.prerequisites)
    for mi, m in enumerate(cur.modules):
        mod = Module(position=mi, title=m.title, description=m.description)
        for li, l in enumerate(m.lessons):
            mod.lessons.append(Lesson(position=li, title=l.title, summary=l.summary, estimated_minutes=l.estimated_minutes,
                                      dependencies=l.dependencies, exercises=l.practical_exercises, knowledge_checks=l.knowledge_checks,
                                      category=req.domain))
        course.modules.append(mod)
    db.add(course)
    db.flush()
    return course


def latest_script(lesson: Lesson) -> LessonScript | None:
    return lesson.scripts[-1] if lesson.scripts else None


def save_script(db: Session, lesson: Lesson, data: LessonScriptData, by: str) -> LessonScript:
    content = data.model_dump()
    h = sha256_text(json.dumps(content, sort_keys=True))
    cur = latest_script(lesson)
    if cur and cur.content_hash == h:  # idempotent: identical content creates no new version
        return cur
    s = LessonScript(lesson_id=lesson.id, version=(cur.version + 1 if cur else 1), content=content, generated_by=by, content_hash=h)
    db.add(s)
    db.flush()
    db.refresh(lesson)
    return s


SCRIPT_MIN_FRACTION = 0.4  # script is an outline (sections elaborate); a 7B model cannot write the full narration in one call


def script_words(data: LessonScriptData) -> int:
    """Words of prose in the script (references/URLs and diagram code excluded)."""
    skip = {"references", "diagrams", "unverified_claims"}

    def walk(v) -> int:
        if isinstance(v, str):
            return len(v.split())
        if isinstance(v, dict):
            return sum(walk(x) for k, x in v.items() if k not in skip)
        if isinstance(v, list):
            return sum(walk(x) for x in v)
        return 0
    return walk(data.model_dump())


def generate_script(db: Session, lesson: Lesson, llm: LLMProvider, sources: list) -> LessonScript:
    primary = [x for x in sources if x.verified and x.kind not in ("arxiv", "model_suggested")]
    if len(primary) >= 3:  # search hits only mention the topic; with curated documentation available they are not offered for citation
        sources = primary
    if lesson.draft:
        sources = []  # quick draft: nothing was researched, so nothing may be cited
    src = "\n".join(f"- {s.title or s.kind} ({s.publisher}) {s.url} :: {s.excerpt[:300]}" for s in sources if s.verified) or "(none verified - put every claim you cannot support in unverified_claims)"
    prompt = (f"TOPIC: {lesson.title}\nSUMMARY: {lesson.summary}\nDURATION: {lesson.estimated_minutes}\n"
              f"NARRATION_WORD_TARGET: {lengthplan.target_words(lesson.estimated_minutes)} (the script must contain enough technical depth, examples and defensive detail to support this much narration)\n"
              f"VERIFIED SOURCES:\n{src}"
              + ("\nQUICK DRAFT: no sources are available. Leave `references` empty. State only well-established facts and keep claims general; "
                 "anything you are not sure of goes into `unverified_claims`." if lesson.draft else ""))
    data = _ask(llm, "lesson", prompt, LessonScriptData, domain=domains.of_lesson(lesson).key)
    if not llm.name.startswith("mock"):  # a thin script starves every storyboard section, so check depth here
        need = int(SCRIPT_MIN_FRACTION * lengthplan.target_words(lesson.estimated_minutes))
        for _ in range(SCRIPT_MAX_CORRECTIONS):
            have = script_words(data)
            if have >= need:
                break
            nxt = _ask(llm, "lesson", prompt + f"\n\nPREVIOUS SCRIPT (only {have} words of prose; at least {int(need * 1.25)} are required):\n{data.model_dump_json()}\n\n"
                       "Return the same JSON with every prose field substantially expanded: add mechanisms, worked examples and defensive detail to each section "
                       "(no filler, no repetition). Keep every field and all references.", LessonScriptData)
            if script_words(nxt) > have:  # never let a worse retry replace a longer draft
                data = nxt
        if script_words(data) < need:
            raise LLMError(f"script has {script_words(data)} words of prose but a {lesson.estimated_minutes}-minute lesson needs at least {need}")
    if lesson.draft:  # a model that ignores the instruction must not leave invented citations in a script nobody has checked
        data = data.model_copy(update={"references": [], "unverified_claims": [*data.unverified_claims, "DRAFT: this script was not fact-checked against any source."]})
    return save_script(db, lesson, data, llm.name)


class SectionScene(Scene):
    scene_id: str = "scene_000"  # placeholder; renumbered when sections are stitched

    @model_validator(mode="after")
    def check_payload(self):
        """Like Scene, except missing bullets / diagrams are repaired afterwards by _ensure_bullets (derived from the narration)."""
        for typ, field in (("code", self.code), ("terminal", self.terminal_lines)):
            if self.type == typ and not (field and (not isinstance(field, str) or field.strip())):
                raise ValueError(f"{typ} scene needs non-empty payload")
        return self

    @model_validator(mode="before")
    @classmethod
    def drop_unusable_3d(cls, v):
        """`mode3d` is an optional visual flag that small models set without its prerequisites; dropping it loses no content.
        The same goes for `animation`: an invalid motion block is discarded, the scene keeps its profile defaults."""
        if isinstance(v, dict) and v.get("animation") is not None:
            v = {**v, "animation": clean_animation(v["animation"])}
        if isinstance(v, dict) and v.get("visualization") is not None:
            v = {**v, "visualization": clean_visualization(v["visualization"]) if v.get("type") == "diagram" else None}
        if isinstance(v, dict) and v.get("quiz_answer") is not None and not (v.get("type") == "quiz" and isinstance(v["quiz_answer"], int) and 0 <= v["quiz_answer"] < len(v.get("bullets") or [])):
            v = {**v, "quiz_answer": None}
        if isinstance(v, dict) and v.get("mode3d"):
            ok = bool(v.get("mermaid")) if v["mode3d"] == "flow" else len(v.get("bullets") or []) >= 2
            if not ok:
                v = {**v, "mode3d": None, "highlight_layer": None}
        return v


class SectionOut(Strict):
    scenes: list[SectionScene] = Field(min_length=1, max_length=12)


MAX_CORRECTIONS = 2
SCRIPT_MAX_CORRECTIONS = 4  # a local model usually undershoots by a little each pass; the longest draft is kept
SECTION_MIN_SLACK_WORDS = 15  # tiny sections get an absolute allowance as well
QUICK_SECTION_TOLERANCE = 0.25  # quick draft: a section this close to its budget is used as written, without expand/trim rewrites
SECTION_HARD_TOLERANCE = 0.45  # after corrections, a section further than this from budget fails the whole generation


def _section_prompt(lesson: Lesson, script: dict, name: str, guide: str, budget: int, covered: list[str], feedback: str = "") -> str:
    return (f"TOPIC: {lesson.title}\nSECTION: {name}\nSECTION_GUIDE: {guide}\nWORD_BUDGET: {budget}\nWORDS_PER_SECOND: {lengthplan.WPS}\nTARGET_SCENES: {lengthplan.scene_count(budget)} (about {budget // lengthplan.scene_count(budget)} narration words each)\n"
            f"ALREADY_COVERED_SCENES: {json.dumps(covered)}\nSCRIPT:\n{json.dumps(script)}" + (f"\n\n{feedback}" if feedback else ""))


def _ensure_bullets(llm: LLMProvider, scenes: list) -> list:
    """slide/quiz/summary scenes need bullets. If the model left them out, derive them FROM the scene's own narration."""
    from app.services import mermaid_lite
    out = []
    for sc in scenes:
        if sc.type == "diagram" and not (sc.mermaid or "").strip():
            raw = llm.complete_text("You draw simple flow diagrams as text. Output ONLY the diagram, no commentary, no code fences.",
                                    f"NARRATION: {sc.narration}\n\nWrite a Mermaid diagram of what the narration describes. First line `flowchart LR`, then 3 to 6 lines like "
                                    "`A[Short label] --> B[Short label]` or `A -- text --> B`. Labels at most 4 words.", 300)
            code = re.sub(r"```(?:mermaid)?", "", raw).strip()
            try:
                mermaid_lite.parse(code)
                sc = sc.model_copy(update={"mermaid": code})
            except Exception:  # noqa: BLE001 - not a diagram we can draw: honest fallback is a bulleted slide, not an empty diagram
                sc = sc.model_copy(update={"type": "slide", "mode3d": None})
        if sc.type in ("slide", "quiz", "summary") and not sc.bullets:
            ask = ("4 answer options (one per line, without letters), exactly as read aloud in the narration" if sc.type == "quiz"
                   else "3 to 5 short slide bullet points (max 10 words each, one per line) summarizing the narration")
            raw = llm.complete_text("You turn narration into slide text. Output ONLY the lines, no numbering, no markdown, no commentary.",
                                    f"NARRATION: {sc.narration}\n\nWrite {ask}.", 300)
            lines = [re.sub(r"^[\-\*\d\.\)\s]+", "", x).strip() for x in raw.splitlines()]
            lines = [x for x in lines if x][:6]
            if len(lines) < 2:
                raise LLMError(f"could not derive bullets for a {sc.type} scene")
            sc = sc.model_copy(update={"bullets": lines})
        out.append(sc)
    return out


_MARKUP_RE = lengthplan._MARKUP


def _dedupe_diagrams(llm: LLMProvider, prior: list, scenes: list) -> list:
    """A diagram identical to an earlier one is redrawn from this scene's own narration; if it still collides or cannot be drawn
    the scene becomes a bulleted slide (bullets derived from its narration by _ensure_bullets)."""
    from app.services import mermaid_lite
    seen = {(x.mermaid or "").strip() for x in prior if x.mermaid}
    out = []
    for sc in scenes:
        m = (sc.mermaid or "").strip()
        if sc.type == "diagram" and m in seen:
            raw = llm.complete_text("You draw simple flow diagrams as text. Output ONLY the diagram, no commentary, no code fences.",
                                    f"NARRATION: {sc.narration}\n\nWrite a Mermaid diagram of what THIS narration describes. It must differ from: {m}\n"
                                    "First line `flowchart LR`, then 3 to 6 lines like `A[Short label] --> B[Short label]`. Labels at most 4 words.", 300)
            code = re.sub(r"```(?:mermaid)?", "", raw).strip()
            try:
                mermaid_lite.parse(code)
                ok = code not in seen
            except ValueError:
                ok = False
            sc = sc.model_copy(update={"mermaid": code, "mode3d": sc.mode3d if ok else None} if ok else {"type": "slide", "mermaid": None, "mode3d": None, "bullets": None})
            m = (sc.mermaid or "").strip()
        if m:
            seen.add(m)
        out.append(sc)
    return out


def _make_distinct(llm: LLMProvider, lesson: Lesson, name: str, prior: list, out: SectionOut, rounds: int = 3) -> SectionOut:
    """Rewrite scenes of this section that repeat an earlier scene (or each other). The model is told every earlier scene it collides
    with and every phrase to avoid; a rewrite that avoids one phrase often re-introduces another, hence several rounds."""
    scenes = list(out.scenes)
    system = domains.narration_system(domains.of_lesson(lesson).key, "Output ONLY the narration text: plain sentences, no markdown, no HTML or code characters, no quotes.")
    for _ in range(rounds):
        allsc = list(prior) + scenes
        hits: dict[int, list[tuple[int, str]]] = {}
        for x, y, r in lengthplan.repetition_pairs(allsc):
            if y >= len(prior):
                hits.setdefault(y - len(prior), []).append((x, r))
        if not hits:
            break
        for i, found in hits.items():
            sc = scenes[i]
            n = len(sc.narration.split())
            earlier = " | ".join(allsc[x].narration for x, _ in found[:3])
            avoid = "; ".join(sorted({r.split('"')[1] for _, r in found if '"' in r}))
            prompt = (f"LESSON: {lesson.title}\nSECTION: {name}\nSCENE TYPE: {sc.type}; ON-SCREEN: {sc.on_screen_text}; BULLETS: {sc.bullets}\n"
                      f"EARLIER SCENES THE VIEWER HAS ALREADY HEARD (do not repeat their wording, definitions or examples): {earlier}\n"
                      f"PHRASES YOU MUST NOT USE: {avoid or 'none'}\n\nCURRENT NARRATION ({n} words): {sc.narration}\n\n"
                      f"Rewrite the current narration to about {n} words. The viewer already knows what the topic is, so do NOT define it again. "
                      f"Add NEW information about this scene's own point (a different mechanism step, example or defensive detail) in different words.")
            new = _clean_prose(llm.complete_text(system, prompt))
            if new and not _MARKUP_RE.search(new):
                scenes[i] = sc.model_copy(update={"narration": new})
    prior_all = list(prior)
    scenes = _ensure_bullets(llm, _dedupe_diagrams(llm, prior_all, scenes))
    return SectionOut(scenes=scenes)


def _clean_prose(text: str) -> str:
    t = text.strip().strip('"').strip()
    t = re.sub(r"^(narration|here is[^:\n]*|sure[^:\n]*)\s*:\s*", "", t, flags=re.I)
    return re.sub(r"[*_#`>]+", "", t).replace("\n", " ").strip()


def _fit_narration(llm: LLMProvider, lesson: Lesson, name: str, guide: str, out: SectionOut, budget: int, covered: list[str]) -> SectionOut:
    """Rewrite each scene's narration as plain prose toward budget/len(scenes) words. Keeps the best of 2 tries per scene,
    never accepts empty text, and gives the model its own previous text plus the neighbouring scenes so it adds substance, not repetition."""
    per = max(15, budget // len(out.scenes))
    scenes = list(out.scenes)
    system = domains.narration_system(domains.of_lesson(lesson).key, "Output ONLY the narration text: plain sentences, no markdown, no bullet points, no headings, no quotes.")
    for i, sc in enumerate(scenes):
        cur = sc.narration
        for _ in range(2):
            n = len(cur.split())
            if lengthplan.within(n, per, 0.15):
                break
            others = " | ".join(x.narration for j, x in enumerate(scenes) if j != i)[:900]
            prompt = (f"LESSON: {lesson.title}\nSECTION: {name} ({guide})\nSCENE TYPE: {sc.type}; ON-SCREEN: {sc.on_screen_text}; "
                      f"BULLETS: {sc.bullets}; CODE: {(sc.code or '')[:300]}\nOTHER SCENES IN THIS SECTION (do not repeat them): {others}\n"
                      f"ALREADY COVERED EARLIER: {covered[-6:]}\n\nCURRENT NARRATION ({n} words): {cur}\n\n"
                      f"Rewrite this narration to about {per} words ({int(per * 0.9)}-{int(per * 1.1)}). "
                      f"{'Add a concrete mechanism, step or generic worked example; no filler.' if n < per else 'Tighten it; keep the key points.'}")
            new = _clean_prose(llm.complete_text(system, prompt))
            if new and not _MARKUP_RE.search(new) and abs(len(new.split()) - per) < abs(n - per):
                cur = new
        scenes[i] = sc.model_copy(update={"narration": cur})
    return SectionOut(scenes=scenes)


def build_storyboard_by_sections(lesson: Lesson, script: dict, llm: LLMProvider, work_dir: Path | None = None) -> StoryboardData:
    """One LLM call per section against its word budget; sections that miss by >12% are re-asked (max 2 rounds);
    the stitched result must land within +-20% of the total budget or generation fails (nothing is saved).
    Sections that met their budget are written to `work_dir` as they finish, so a failed run resumes without redoing them."""
    minutes = lesson.estimated_minutes
    lengthplan.validate_request(minutes)  # pre-generation validation
    bud = lengthplan.budgets(minutes)
    parts: dict[str, list[Scene]] = {}
    covered: list[str] = []
    key = sha256_text(json.dumps([lesson.title, script, bud, lengthplan.WPS], sort_keys=True))
    quick = bool(lesson.draft)  # quick draft: one attempt per section; narration is fitted only when a section is far outside its budget
    for name, _frac, guide in lengthplan.sections_for(domains.is_security(domains.of_lesson(lesson).key)):
        saved = work_dir / f"{name}.json" if work_dir else None
        if saved and saved.exists():
            cached = json.loads(saved.read_text())
            if cached.get("key") == key:
                try:
                    loaded = SectionOut(scenes=_ensure_bullets(llm, [SectionScene.model_validate(x) for x in cached["scenes"]]))
                    if lengthplan.claim_issues(loaded.scenes) or lengthplan.speakability_issues(loaded.scenes):
                        raise ValidationError.from_exception_data("cached", [])  # saved before these gates existed: regenerate
                    parts[name] = _make_distinct(llm, lesson, name, [x for p_ in parts.values() for x in p_], loaded).scenes
                except ValidationError:  # saved under an older, looser schema: regenerate this section
                    parts.pop(name, None)
                else:
                    covered += [s.on_screen_text or s.type for s in parts[name]]
                    continue
        feedback, best = "", None  # best = (relative error, scenes, words): the attempt closest to budget wins, not merely the last one
        for attempt in range(1 if quick else MAX_CORRECTIONS + 1):
            out = _ask(llm, "storyboard_section", _section_prompt(lesson, script, name, guide, bud[name], covered, feedback), SectionOut, retries=2, domain=domains.of_lesson(lesson).key)
            words = sum(len(s.narration.split()) for s in out.scenes)
            repeats = lengthplan.repetition_issues([n for p_ in parts.values() for n in p_] + out.scenes) + lengthplan.speakability_issues(out.scenes) + lengthplan.claim_issues(out.scenes)
            err = abs(words - bud[name]) / bud[name] + (1.0 if repeats else 0.0)
            if best is None or err < best[0]:
                best = (err, out, words)
            if lengthplan.within(words, bud[name]) and not repeats:
                break
            lo, hi = int(bud[name] * 0.9), int(bud[name] * 1.1)
            n = lengthplan.scene_count(bud[name])
            feedback = (f"Your previous answer had {words} narration words but the budget is {bud[name]} (accept {lo}-{hi}). "
                        f"Write exactly {n} scenes of about {bud[name] // n} words each. "
                        f"{'Add concrete technical detail and a worked example, not filler' if words < lo else 'Cut the least useful sentences'}; keep the same scene types.\n"
                        f"YOUR PREVIOUS ANSWER (revise it, do not start over): {json.dumps([{'type': x.type, 'narration': x.narration} for x in out.scenes])}")
            if repeats:
                feedback += f" Also fix: {'; '.join(repeats[:3])}"
        _, out, words = best
        if not lengthplan.within(words, bud[name]) and not (quick and abs(words - bud[name]) <= max(QUICK_SECTION_TOLERANCE * bud[name], SECTION_MIN_SLACK_WORDS)):  # JSON answers cannot be made to hit the budget: expand/trim scene by scene as prose
            out = _fit_narration(llm, lesson, name, guide, out, bud[name], covered)
            words = sum(len(s.narration.split()) for s in out.scenes)
        if abs(words - bud[name]) > max(SECTION_HARD_TOLERANCE * bud[name], SECTION_MIN_SLACK_WORDS):
            raise LLMError(f"section '{name}' has {words} words after {MAX_CORRECTIONS} corrections; budget {bud[name]} (hard limit +-{int(SECTION_HARD_TOLERANCE * 100)}%)")
        out = SectionOut(scenes=_ensure_bullets(llm, out.scenes))
        prior = [x for p_ in parts.values() for x in p_]
        out = _make_distinct(llm, lesson, name, prior, out)  # repair repetition now, not after 40 minutes of generation
        words = sum(len(x.narration.split()) for x in out.scenes)
        parts[name] = out.scenes
        if saved and lengthplan.within(words, bud[name]) and not lengthplan.repetition_issues(prior + out.scenes):
            work_dir.mkdir(parents=True, exist_ok=True)
            saved.write_text(json.dumps({"key": key, "words": words, "budget": bud[name], "scenes": [x.model_dump() for x in out.scenes]}))
        covered += [s.on_screen_text or s.type for s in out.scenes]
    dup = lengthplan.repetition_issues([x for p_ in parts.values() for x in p_])
    if dup:
        raise LLMError("stitched storyboard repeats itself: " + "; ".join(dup[:3]))
    flat = [s for name, _f, _g in lengthplan.SECTIONS for s in parts[name]]
    scenes = [s.model_copy(update={"scene_id": f"scene_{i:03d}"}) for i, s in enumerate(flat, 1)]
    sb = StoryboardData.model_validate({"lesson_title": lesson.title, "scenes": [s.model_dump() for s in scenes]})
    total, target = lengthplan.word_count(sb), lengthplan.target_words(minutes)
    if not lengthplan.within(total, target, 0.30 if quick else 0.20):
        raise LLMError(f"storyboard has {total} narration words (~{total / lengthplan.WPS / 60:.1f} min) but {minutes} min needs ~{target}; "
                       "the model did not reach the budget after corrections")
    return sb


def generate_storyboard(db: Session, lesson: Lesson, llm: LLMProvider) -> Storyboard:
    script = latest_script(lesson)
    if not script:
        raise ValueError("lesson has no script")
    if llm.name.startswith("mock"):  # the offline template ignores budgets (and is not publishable content)
        prompt = f"TOPIC: {lesson.title}\nDURATION: {lesson.estimated_minutes}\nSCRIPT:\n{json.dumps(script.content)}"
        return save_storyboard(db, lesson, _ask(llm, "storyboard", prompt, StoryboardData, domain=domains.of_lesson(lesson).key))
    from app.services.storage import get_storage
    return save_storyboard(db, lesson, build_storyboard_by_sections(lesson, script.content, llm, get_storage().lesson_dir(lesson.id, "sections")))


def save_storyboard(db: Session, lesson: Lesson, sb: StoryboardData) -> Storyboard:
    last = db.query(Storyboard).filter_by(lesson_id=lesson.id).order_by(Storyboard.version.desc()).first()
    row = Storyboard(lesson_id=lesson.id, version=(last.version + 1 if last else 1), data=sb.model_dump())
    for i, s in enumerate(sb.scenes):
        row.scenes.append(SceneRow(scene_id=s.scene_id, position=i, type=s.type, duration_seconds=s.duration_seconds,
                                   narration=s.narration, on_screen_text=s.on_screen_text, transition=s.transition))
    db.add(row)
    db.flush()
    return row


def latest_storyboard(db: Session, lesson: Lesson) -> Storyboard | None:
    return db.query(Storyboard).filter_by(lesson_id=lesson.id).order_by(Storyboard.version.desc()).first()


def generate_metadata(lesson: Lesson, sb: StoryboardData, llm: LLMProvider) -> YouTubeMetadata:
    t, chapters = 0.0, []
    for s in sb.scenes:
        chapters.append([f"{int(t // 60)}:{int(t % 60):02d}", (s.on_screen_text or s.type.title())[:60]])
        t += s.duration_seconds
    md = _ask(llm, "metadata", f"TOPIC: {lesson.title}\nCHAPTERS(from real scene timings): {json.dumps(chapters)}", YouTubeMetadata, domain=domains.of_lesson(lesson).key)
    md.chapters = [tuple(c) for c in chapters]  # chapters always come from real timings, never from the model
    if not md.chapters or md.chapters[0][0] != "0:00":
        raise LLMError("chapters must start at 0:00")
    return md
