# Course-Wide Assessment Strategy

## Levels of assessment

1. **Lesson knowledge checks** (5–10 items, in each lesson's README): multiple-choice, technical-reasoning ("explain why X fails when Y"), and scenario-based ("given this log/crash, what's the next step") questions, with answer keys and a one-to-two sentence explanation per answer. Formative only — not scored toward certification-style completion.
2. **Module assessments** (`modules/module-NN/assessments/`): one cumulative written assessment (15–20 items spanning the module's lessons) plus one practical lab-based task scored against a short rubric (criteria + 0–3 scale per criterion). Gate for moving to the next module in an instructor-led delivery.
3. **Capstone** (Module 12): learner picks one of three tracks (`capstone/`), each scored against `instructor/ASSESSMENT_RUBRICS.md`. The deliverable is a professional report (root cause/methodology, evidence, remediation or detection content, references) — mirroring real engagement/analysis reporting, not a raw exploit or sample hand-in.

## Grading philosophy

- Practical rubrics reward **process and reasoning** (why a technique works, what it's evidence of, what the correct defensive response is) at least as much as "did it work."
- No rubric item rewards exfiltrating more data, achieving broader unauthorized access, or building a more deployable payload than the lab requires — see `LAB_SAFETY.md`.
- Questions and rubrics are written to be gradable by a human instructor without re-running the learner's exact lab (i.e., they ask for documented evidence: screenshots of the learner's own isolated VM, decompiled snippets, log excerpts, written analysis).

## Question-bank conventions

Each lesson's knowledge check is self-contained (no answer requires content from a later lesson). Scenario questions reference fictional system/company names only (never real organizations), consistent with `ai/prompts/curriculum.md`'s "never include real-world targets" rule used elsewhere in this repository.
