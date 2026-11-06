"""Offline template generator. Produces schema-valid but generic content so the pipeline runs without
any model. Content is deliberately conservative: only cites OWASP/MITRE pages, never CVE IDs or scores."""
import json

from .llm import LLMProvider


class MockLLM(LLMProvider):
    name = "mock"

    def complete(self, system: str, prompt: str, max_tokens: int = 8000) -> str:
        task = system.split("TASK:")[-1].strip().split()[0] if "TASK:" in system else ""
        topic = _field(prompt, "TOPIC") or "Introduction to the Topic"
        if task == "curriculum":
            return json.dumps(_curriculum(topic, int(_field(prompt, "DURATION") or 8)))
        if task == "lesson":
            return json.dumps(_lesson(topic))
        if task == "storyboard":
            return json.dumps(_storyboard(topic, int(_field(prompt, "DURATION") or 1)))
        if task == "claim_extract":  # the mock cannot reason about claims: it reports none (reviews are flagged `simulated`)
            return json.dumps({"claims": []})
        if task == "claim_judge":  # the mock cannot read passages: it never claims support
            return json.dumps({"verdict": "unsupported", "notes": "[mock] no judgement made"})
        if task == "tech_review":
            return json.dumps({"findings": []})
        if task == "metadata":
            return json.dumps(_metadata(topic))
        raise ValueError(f"mock has no template for task '{task}'")


def _field(prompt: str, key: str) -> str:
    for line in prompt.splitlines():
        if line.startswith(f"{key}:"):
            return line.split(":", 1)[1].strip()
    return ""


def _curriculum(course: str, minutes: int) -> dict:
    mods = [
        ("Foundations", [f"Introduction to {course}", f"Core Terminology and Setup for {course}"]),
        ("Core Concepts", [f"Key Techniques in {course}", f"Common Mistakes in {course}"]),
        ("Applied Practice", [f"Worked Example: {course}", f"Putting {course} Into Practice"]),
    ]
    out, prev = [], None
    for title, lessons in mods:
        ls = []
        for lt in lessons:
            ls.append({"title": lt, "summary": f"{lt}.", "estimated_minutes": minutes,
                       "dependencies": [prev] if prev else [], "practical_exercises": [f"Apply the ideas from '{lt}' in a hands-on exercise."],
                       "knowledge_checks": [f"Explain the key idea covered in '{lt}'."]})
            prev = lt
        out.append({"title": title, "description": f"{title} for {course}.", "lessons": ls})
    return {"description": f"A structured course on {course}. [mock-generated outline - review before use]",
            "learning_objectives": [f"Explain core concepts of {course}", "Apply them in practice", "Avoid the common mistakes"],
            "prerequisites": ["Curiosity and basic computer skills"], "modules": out}


def _lesson(topic: str) -> dict:
    return {
        "title": topic,
        "hook": f"One unsanitized input can undo an entire application. Today: {topic}.",
        "introduction": f"In this lesson we study {topic}: what it is, why it happens, how to test for it in an authorized lab, and how to defend against it.",
        "learning_objectives": [f"Define {topic}", "Identify the root cause in code", "Demonstrate safely in a lab", "Apply a defensive fix"],
        "technical_explanation": "Injection happens when untrusted input is interpreted as part of a command or query. The interpreter cannot tell data from instructions, so crafted input changes the meaning of the statement. The fix is to keep data and code separate with parameterized queries.",
        "practical_demonstration": "In an isolated Docker lab running an intentionally vulnerable application, send a single quote in a search field and observe the database error, then compare with the parameterized version.",
        "diagrams": ["flowchart LR\n  A[User input] --> B[Application]\n  B --> C{Parameterized?}\n  C -- No --> D[Query altered]\n  C -- Yes --> E[Input treated as data]"],
        "real_world_applications": "Injection consistently appears in the OWASP Top 10 and is a frequent finding in bug bounty and penetration testing reports.",
        "defensive_recommendations": "Use parameterized queries, least-privilege database accounts, input validation, and a web application firewall as defense in depth.",
        "common_mistakes": ["Relying only on blacklist filtering", "Escaping manually instead of using parameters", "Testing without written authorization"],
        "knowledge_check": [{"question": "Which control best prevents injection?", "options": ["Blacklist filtering", "Parameterized queries", "Hiding error messages", "Longer passwords"], "answer_index": 1}],
        "summary": "Keep data and code separate. Parameterize, validate, and always test only with authorization.",
        "references": [{"title": "OWASP Top 10 - A03:2021 Injection", "url": "https://owasp.org/Top10/A03_2021-Injection/"},
                       {"title": "OWASP SQL Injection Prevention Cheat Sheet", "url": "https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html"}],
        "unverified_claims": ["[mock] Entire script is template output; a human must verify before publishing."],
    }


def _storyboard(topic: str, scale: int) -> dict:
    n = [0]

    def sc(type_, dur, narr, vis, text, **kw):
        n[0] += 1
        d = {"scene_id": f"scene_{n[0]:03d}", "type": type_, "duration_seconds": dur, "narration": narr,
             "visual_description": vis, "on_screen_text": text, "asset_requirements": [], "transition": "fade"}
        d.update(kw)
        return d

    scenes = [
        sc("instructor", 8, f"Welcome. Today we are looking at {topic}, one of the most important topics in web security.", "Instructor portrait with lower-third title", topic),
        sc("slide", 8, "By the end of this lesson you will define the problem, spot it in code, and apply the right fix.", "Learning objectives slide", "Learning Objectives",
           bullets=["Define the vulnerability", "Spot the root cause", "Demonstrate in a lab", "Apply the defense"]),
        sc("diagram", 9, "Here is the flow. Untrusted input reaches the application. If the query is not parameterized, the input changes its meaning.", "Mermaid flow", "How it happens",
           mermaid="flowchart LR\n  A[User input] --> B[Application]\n  B --> C{Parameterized?}\n  C -- No --> D[Query altered]\n  C -- Yes --> E[Input treated as data]"),
        sc("code", 9, "This vulnerable code concatenates user input straight into the SQL string. The safe version passes it as a bound parameter.", "Code comparison", "Vulnerable vs safe", language="python",
           code='# VULNERABLE\nq = "SELECT * FROM users WHERE name = \'" + name + "\'"\n\n# SAFE\ncur.execute("SELECT * FROM users WHERE name = %s", (name,))'),
        sc("terminal", 8, "In an isolated lab with an intentionally vulnerable app, a single quote produces a database error, which signals unsafe query construction.", "Lab terminal walk-through (illustrative)", "Authorized lab only",
           terminal_lines=["$ curl 'http://lab.local:8080/search?q=test'", "200 OK - 3 results", "$ curl \"http://lab.local:8080/search?q=test'\"", "500 - database syntax error (illustrative output)"]),
        sc("quiz", 8, "Quick check. Which control best prevents injection? Pause and think about it.", "Quiz card", "Which control best prevents injection?",
           bullets=["A) Blacklist filtering", "B) Parameterized queries", "C) Hiding error messages", "D) Longer passwords"]),
        sc("summary", 8, "To recap: keep data and code separate, use parameterized queries, and only test systems you are authorized to test.", "Summary slide", "Summary",
           bullets=["Parameterize queries", "Least-privilege DB accounts", "Test only with authorization"]),
    ]
    k = max(1, scale)
    for s in scenes:
        s["duration_seconds"] = float(s["duration_seconds"]) * 1
    return {"lesson_title": topic, "scenes": scenes}


def _metadata(topic: str) -> dict:
    return {"titles": [f"{topic}: Explained for Students", f"{topic} - Root Cause and Defense", f"Understanding {topic} (Authorized Lab Demo)"],
            "description": f"{topic} explained with diagrams, code, and a lab walkthrough.\n\nAll demonstrations use intentionally vulnerable, isolated lab environments.",
            "chapters": [["0:00", "Introduction"]], "tags": ["tutorial", "education", "explained"],
            "thumbnail_text": topic[:38], "thumbnail_layout": "Dark gradient, large title left, instructor portrait right, accent bar",
            "category_id": "27",
            "disclaimer": "Educational content. Only test systems you own or have written permission to test."}
