"""Shared test setup: take a lesson (script + storyboard already saved) through review and human approval the legitimate way."""
from app.models import LessonStatus as S
from app.services import pipeline


def approve_for_assets(db, lesson, reviewer=None):
    """Technical review (offline sources) -> human script approval. Leaves the lesson at SCRIPT_APPROVED."""
    pipeline.run_technical_review(db, lesson, online=False, reviewer=reviewer)
    pipeline.approve_script(db, lesson, None)
    db.refresh(lesson)
    assert lesson.status == S.SCRIPT_APPROVED


# ---------------------------------------------------------------- fixtures for the review / claims / gate tests
import itertools
import json

from app.models import Course, Lesson, Module, ResearchSource
from app.providers.llm import LLMError, LLMProvider
from app.schemas.content import LessonScriptData, StoryboardData
from app.services import generation, lengthplan

_uid = itertools.count(1)
PARAM_SENTENCE = "Parameterized queries ensure that an attacker cannot change the intent of a query, even if SQL commands are inserted by an attacker."
SOURCE_TEXT = ("## Overview\nInjection flaws occur when untrusted data is sent to an interpreter as part of a command or query. "
               "The attacker's hostile data can trick the interpreter into executing unintended commands or accessing data without authorization. "
               "A web application is vulnerable when user supplied data is not validated, filtered, or sanitized by the application.\n"
               f"## Primary Defenses\n{PARAM_SENTENCE} Stored procedures can be safe only if they do not build dynamic SQL internally. "
               "Allow-list input validation is a secondary control and is not a substitute for parameterization.")
SOURCE_URL = "https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html"


def good_script() -> dict:
    return {
        "title": "SQL Injection Fundamentals",
        "hook": "A single quote typed into a search box can expose a whole database, and the cause is almost always one design mistake.",
        "introduction": "In this lesson we study SQL injection: what it is, why it happens, how to test for it in an authorized isolated lab, and how to defend against it with parameterized queries and least privilege.",
        "learning_objectives": ["Define SQL injection and its root cause", "Demonstrate a injection safely in an isolated lab", "Apply parameterized queries as the primary defense"],
        "technical_explanation": ("SQL injection happens when untrusted input is concatenated into a query string so the database cannot tell data from instructions. "
                                  "The root cause is mixing code and data in one string, while the impact depends on database privileges and the data stored. "
                                  "Injection is therefore a vulnerability class, whereas data theft is one possible impact of exploiting it."),
        "practical_demonstration": ("In an isolated lab running an intentionally vulnerable application bound to localhost, send a single quote in the search field and observe the database error. "
                                    "Then submit a crafted condition and compare the rows returned with a normal search. Expected result: the vulnerable version returns extra rows and the fixed version treats the text as a literal. "
                                    "Finally rerun both requests against the parameterized version to verify the fix."),
        "diagrams": ["flowchart LR\n  A[User input] --> B[Application]\n  B --> C{Parameterized?}\n  C -- No --> D[Query altered]\n  C -- Yes --> E[Input treated as data]"],
        "real_world_applications": "Injection appears in the OWASP Top 10 and is a regular finding in authorized penetration tests, which is why reviewers look for it in every data access layer.",
        "defensive_recommendations": (f"{PARAM_SENTENCE} Combine this with least-privilege database accounts, allow-list input validation as a secondary control, "
                                      "and monitoring of database errors, because no single control is sufficient on its own."),
        "common_mistakes": ["Relying only on blacklist filtering", "Escaping manually instead of using parameters", "Testing without written authorization"],
        "knowledge_check": [{"question": "Which control is primary?", "options": ["Blacklist", "Parameterized queries", "Hiding errors", "Long passwords"], "answer_index": 1}],
        "summary": "Keep data and code separate with parameterized queries, add layered controls, and always test only with written authorization in an isolated lab.",
        "references": [{"title": "OWASP SQL Injection Prevention Cheat Sheet", "url": SOURCE_URL}],
        "unverified_claims": [],
    }


def good_storyboard(minutes: int = 8) -> StoryboardData:
    total = lengthplan.target_words(minutes)
    plan = [("instructor", 0.08), ("slide", 0.12), ("slide", 0.15), ("code", 0.20), ("terminal", 0.15), ("slide", 0.12), ("quiz", 0.06), ("summary", 0.07), ("instructor", 0.05)]
    scenes = []
    for i, (typ, frac) in enumerate(plan, 1):
        n = int(total * frac)
        sc = {"scene_id": f"scene_{i:03d}", "type": typ, "duration_seconds": 5, "visual_description": "v", "on_screen_text": "t", "transition": "fade",
              "narration": " ".join(f"w{next(_uid)}" for _ in range(n)) + "."}
        if typ in ("slide", "quiz", "summary"):
            sc["bullets"] = ["a", "b"]
        if typ == "code":
            sc.update(code="print('lab')", language="python")
        if typ == "terminal":
            sc.update(terminal_lines=["$ curl http://127.0.0.1:5000/search?q=x"])
        scenes.append(sc)
    return StoryboardData.model_validate({"lesson_title": "SQL Injection Fundamentals", "scenes": scenes})


def make_lesson(db, script: dict | None = None, minutes: int = 8, generated_by: str = "scripted", storyboard=True, source=True) -> Lesson:
    c = Course(name=f"C{next(_uid)}")
    m = Module(title="m")
    l = Lesson(title="SQL Injection Fundamentals", summary="sql", estimated_minutes=minutes)
    m.lessons.append(l)
    c.modules.append(m)
    db.add(c)
    db.commit()
    generation.save_script(db, l, LessonScriptData.model_validate(script or good_script()), generated_by)
    if source:
        db.add(ResearchSource(lesson_id=l.id, kind="owasp_cheatsheet", url=SOURCE_URL, title="SQL Injection Prevention - OWASP Cheat Sheet Series", publisher="OWASP",
                              category="owasp", status="ok", verified=True, full_text=SOURCE_TEXT, excerpt=SOURCE_TEXT[:300], content_hash="h" * 64))
    if storyboard is True:
        generation.save_storyboard(db, l, good_storyboard(minutes))
    elif storyboard:
        generation.save_storyboard(db, l, storyboard)
    db.commit()
    return l


class ScriptedLLM(LLMProvider):
    """A local-model stand-in whose answers per task are scripted. Not a mock LLM: its name does not start with 'mock', so reviews
    produced with it are NOT flagged simulated - tests using it must say what they verify."""
    name = "scripted"
    model = "scripted-1"

    def __init__(self, **handlers):
        self.handlers, self.calls = handlers, []

    def complete(self, system, prompt, max_tokens=8000):
        raise NotImplementedError

    def complete_json(self, system, prompt, max_tokens=8000, schema=None):
        task = system.split("TASK:")[-1].strip().split()[0]
        self.calls.append((task, prompt))
        h = self.handlers.get(task)
        if h is None:
            return {"claims": []} if task == "claim_extract" else {"findings": []}
        out = h(prompt) if callable(h) else h
        if isinstance(out, Exception):
            raise out
        return out


# an exact quote from SOURCE_TEXT: a finding that says "the script is wrong" must carry real source evidence to keep that category
SOURCE_EVIDENCE = "Allow-list input validation is a secondary control and is not a substitute for parameterization."


def finding(sev="medium", text="no single control is sufficient on its own", **kw):
    return {"severity": sev, "category": "technical_correctness", "section": "defensive_recommendations", "problem_text": text,
            "explanation": "Needs qualification.", "evidence": SOURCE_EVIDENCE, "recommended_correction": kw.pop("fix", "layered controls are required"), **kw}


def reviewer_with(findings=(), claim_quote=None, claim_text=PARAM_SENTENCE, verdict="supported", source_id=None):
    """Extracts one claim (the parameterized-queries sentence) from every section that contains it, judges it with `claim_quote`."""
    def extract(prompt):
        return {"claims": [{"text": claim_text, "category": "remediation", "critical": True}]} if claim_text in prompt else {"claims": []}

    def judge(prompt):
        sid = source_id if source_id is not None else int(prompt.split("source_id=")[1].split("]")[0])
        return {"verdict": verdict, "source_id": sid, "evidence_quote": claim_quote if claim_quote is not None else PARAM_SENTENCE, "notes": "quoted", "confidence": 0.8}
    return ScriptedLLM(claim_extract=extract, claim_judge=judge, tech_review=lambda p: {"findings": list(findings)} if "CHUNK: technical" in p else {"findings": []})
