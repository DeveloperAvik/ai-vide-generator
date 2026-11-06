"""Builds n8n_test_bundle.json: a 5-minute fixture for `make n8n-test`, clearly named as an n8n connectivity test.
It is derived (read-only) from bundle.json, the finished SQL injection lesson, so the content is real, safe, localhost-lab material and
passes the real validators: 5 min request, demo (code/terminal) + quiz + closing summary scenes, estimated length inside the 5-6 min window.
Run from the repo root:  backend/.venv/bin/python lessons/sqli_fundamentals/build_n8n_test_bundle.py"""
import json
from pathlib import Path

HERE = Path(__file__).parent
src = json.loads((HERE / "bundle.json").read_text())

# keep: intro, objectives, root cause, data-flow diagram, vulnerable code, 3 lab clips, fix, quiz, summary.
# dropped: defense-in-depth, common-mistakes, real-world slides and the outro (they only add length beyond the 5-6 minute window).
DROP_TITLES = {"Defense in Depth", "Common Mistakes", "In the Real World", "Thanks for Watching"}
kept = [s for s in src["storyboard"]["scenes"] if s["visual_description"] not in DROP_TITLES]

# bundle.json predates the schema rule "terminal scene needs terminal_lines" (its footage came from recording_asset), so the
# lines are taken from the REAL captured lab output (lab/session.json) instead of being invented.
session = json.loads((HERE.parent.parent / "lab" / "session.json").read_text())
def lines(*idx):
    out = []
    for i in idx:
        e = session[i]
        out += [f"$ {e['request']}", f"{e['status']} {e['body']}"]
    return out
TERMINAL = {"lab_a.mp4": lines(0, 1), "lab_b.mp4": lines(2, 3), "lab_c.mp4": lines(4)}

scenes, recordings = [], {}
for i, s in enumerate(kept, 1):
    s = dict(s)
    old = s["scene_id"]
    s["scene_id"] = f"scene_{i:03d}"
    # the preflight rejects the word "placeholder" in narration (it flags unfinished text); reword rather than weaken the check
    s["narration"] = s["narration"].replace("a placeholder", "a parameter marker")
    s["transition"] = "fade" if i % 3 else "slide"
    if s["type"] == "terminal":
        s["terminal_lines"] = TERMINAL[s["recording_asset"]]
    if old in src["recordings"]:
        recordings[s["scene_id"]] = src["recordings"][old]
    scenes.append(s)
scenes[0]["on_screen_text"] = "n8n Pipeline Test Lesson"
scenes[0]["visual_description"] = "n8n Pipeline Test Lesson"

# Declared scene durations sum to ~305 s (=> a 5 minute request) and are proportional to narration. The estimator uses
# max(declared, words / measured words-per-second), so the estimate stays inside the 5-6 minute window for any plausible TTS rate.
TARGET_S = 305.0
total_words = sum(len(s["narration"].split()) for s in scenes)
for s in scenes:
    s["duration_seconds"] = round(TARGET_S * len(s["narration"].split()) / total_words, 1)

script = dict(src["script"])
script["title"] = "n8n Pipeline Test Lesson"
script["summary"] = scenes[-1]["narration"]
bundle = {"course_name": "n8n Connectivity Tests", "module_title": "n8n Connectivity Tests", "lesson_title": "n8n Pipeline Test Lesson",
          "summary": "n8n connectivity test fixture (not for publication): SQL injection root cause, safe localhost lab demo and fix.",
          "script": script, "storyboard": {"lesson_title": "n8n Pipeline Test Lesson", "scenes": scenes}, "recordings": recordings}
(HERE / "n8n_test_bundle.json").write_text(json.dumps(bundle, indent=2))
print(sum(len(s["narration"].split()) for s in scenes), "narration words;", len(scenes), "scenes;",
      round(sum(s["duration_seconds"] for s in scenes)), "s declared")
