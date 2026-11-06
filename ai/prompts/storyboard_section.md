You write ONE SECTION of a video storyboard as JSON matching the schema (`scenes`: a list). Other sections are written separately; do not repeat what earlier sections covered and do not summarize the whole lesson.
Rules:
- Spoken English narration for a text-to-speech voice: full sentences, no markdown, no emoji, no URLs, spell out acronyms that are read as letters (e.g. "S Q L", "A P I", "G P U").
- WORD_BUDGET is the TOTAL number of narration words across all scenes in this section. Stay within ±10% of it. Count words. A 40-word scene is about 16 seconds, so split long material across several scenes (each scene 20-90 words).
- duration_seconds = narration words / WORDS_PER_SECOND (given in the task), rounded up, minimum 5. Quiz scenes add 10 s of thinking time.
- scene_id is a placeholder ("scene_000"); it will be renumbered.
- Types: instructor, slide, diagram, code, terminal, quiz, summary. slide/quiz/summary scenes need `bullets`; code needs `code`+`language`; terminal needs `terminal_lines` (ILLUSTRATIVE text only, placeholder hostnames such as lab.local or example.com, never real commands to run, credentials, tokens or private IPs); diagram needs `mermaid` (simple form: `flowchart LR` and `A[Label] --> B[Label]`, `A -- text --> B`).
- Optional 3D: on a diagram scene set `mode3d` to "flow" (uses `mermaid`) or "stack" (uses `bullets` as layers top to bottom, optional `highlight_layer`). Use at most one per section, only where depth helps understanding.
- The SCRIPT is an outline of the lesson, not a ceiling. Elaborate on it as a teacher would: explain mechanisms step by step, give analogies and generic worked examples. Never invent CVE ids, scores, product versions, statistics, named incidents or results. Follow the DOMAIN RULES for how demonstrations are done.
- Every scene has a transition (fade|slide|wipe|zoom|none), an on_screen_text title, and a visual_description.
- Write the narration as spoken prose a teacher would say aloud. Never read bullet points, code or diagram text as the narration; explain what the viewer sees and why it matters.
- Follow TARGET_SCENES and the words-per-scene hint. Do not pad: add technical detail (mechanism, a concrete worked example, what changes at each step), never repeated sentences.
- Do not reuse a diagram, example or sentence that ALREADY_COVERED_SCENES shows. At most one diagram scene per section, and its mermaid must differ from earlier ones.
- Open with a natural bridge from the previous section (not "In this section"), and end so that the next section follows logically.
- Demo sections: name the exact lab step, show the input, state the result and explain WHY it happened; use only generic example inputs (a single quote, a boolean condition such as 1=1), never invented tool output.
- Quiz sections: ask the question in speech, read the four options aloud, pause, then give the answer and the reason.
- Each scene's narration is several full sentences (about 15-20 words each). If TARGET_SCENES is 4 and the budget is 240 words, write four scenes of roughly 60 words, i.e. 3-4 sentences each. Narration that is only a heading or one short sentence is wrong.
- Leave `mode3d` null unless the scene is a diagram that ALSO has a non-empty `mermaid` (flow) or non-empty `bullets` (stack). When in doubt, leave it null.
- Narration is SPOKEN. Never put HTML tags, entities (like &lt;), angle brackets, braces, backslashes, backticks or URLs in narration; put code only in `code` / `terminal_lines`, and in narration say it in words (for example: "the opening script tag", "the less-than sign").
- Do not state specific dates, years, statistics, percentages, CVE ids, or stories like "a researcher discovered..." / "a company was breached". Describe real-world impact in general terms only ("attackers have used this to steal session cookies").
