"""Builds bundle.json for the SQL injection lesson (human/Claude-authored; imported via `python -m app.cli.import_lesson`)."""
import json
from pathlib import Path

DIAGRAM = ("flowchart LR\n  A[User input] --> B[Application builds query]\n  B -- Concatenation --> C[Input parsed as SQL]\n"
           "  B -- Parameters --> D[Input stays data]\n  C --> E[Query meaning changed]")
VULN = '# VULNERABLE: string concatenation\nsql = "SELECT name, price FROM products WHERE name LIKE \'%" + q + "%\'"\nrows = db.execute(sql).fetchall()'
SAFE = '# SAFE: bound parameter\nsql = "SELECT name, price FROM products WHERE name LIKE ?"\nrows = db.execute(sql, ("%" + q + "%",)).fetchall()'

N = [
 ("instructor", "SQL Injection Fundamentals", "A single apostrophe in a search box is sometimes all it takes to expose an entire database. Today we look at SQL injection: why it happens, how to test for it safely in a lab, and how to fix it for good.", {}),
 ("slide", "Learning Objectives", "By the end of this lesson, you will be able to explain the root cause of SQL injection, recognize vulnerable code, demonstrate the issue against an intentionally vulnerable application on your own machine, and apply the correct defense. Everything you see today runs on localhost, against a lab application written for this lesson, with fake data. Only ever test systems you own, or have written permission to test.",
  {"bullets": ["Explain the root cause", "Recognize vulnerable code", "Demonstrate safely in a lab", "Apply the correct defense"]}),
 ("slide", "The Root Cause", "SQL injection is a failure to separate code from data. The application builds a query as a string, and pastes user input into the middle of it. The database receives one string, and has no way to know which part the developer wrote and which part the user supplied. If the input contains SQL syntax, such as a quote, that syntax is parsed as part of the query. Injection has been in the OWASP Top 10 for many years, and sits third in the twenty twenty-one edition. The weakness is catalogued as C W E eighty-nine.",
  {"bullets": ["Query built as a string", "User input pasted into the middle", "Database cannot tell code from data", "OWASP Top 10: A03 Injection · CWE-89"]}),
 ("diagram", "Where Input Goes", "Here is the data flow. User input travels to the application. If the query is built by string concatenation, the input becomes part of the SQL text, and can change the meaning of the query. If the application uses a parameterized query, the structure is sent first and the values travel separately, so the input can only ever be data.", {"mermaid": DIAGRAM}),
 ("code", "Vulnerable Code", "This is the lab application's search handler. Look at the query. The search term is concatenated directly into the SQL string, between the percent signs of a LIKE clause. Nothing stops the user from closing that string literal themselves.", {"code": VULN, "language": "python"}),
 ("terminal", "Lab: Probing the Parameter", "Now the lab. First, a normal search for laptop returns two products, as expected. Next, I send a single apostrophe. The server answers with a five hundred error, and the message comes straight from the database engine: unrecognized token. That tells us our input reached the SQL parser and broke the syntax. It is a strong signal, though not proof of exploitability by itself, and it is also information a production application should never reveal to users.", {"recording_asset": "lab_a.mp4"}),
 ("terminal", "Lab: Changing the Query", "Now we close the string ourselves. The payload ends the pattern with a percent sign and a quote, adds an always true condition, and uses two dashes to comment out the rest of the query. Every product is returned, even though none matches that name. The same idea against the login endpoint: a username of admin followed by a quote and a comment removes the password check entirely, and the application logs us in as admin. Notice that the payload depends on context. My first attempt, copied from habit, returned nothing, because of how the input sat inside the LIKE pattern. Understanding the query structure matters more than memorizing strings.", {"recording_asset": "lab_b.mp4"}),
 ("terminal", "Lab: The Fixed Endpoint", "Now the same payload against the fixed endpoint, which uses a bound parameter. The result is empty. The database searched for a product whose name literally contains that text, and found none. The input stayed data.", {"recording_asset": "lab_c.mp4"}),
 ("code", "The Fix: Parameters", "Here is the fix. The query text contains a placeholder, and the value is passed separately to the database driver. The driver and the database keep structure and data apart, so no input can change the shape of the query.", {"code": SAFE, "language": "python"}),
 ("slide", "Defense in Depth", "Parameterized queries are the primary defense. They apply to O R Ms as well, and to stored procedures, provided the procedure itself does not build dynamic SQL from strings. Then add layers around that. Run the application's database account with least privilege, so a flaw cannot read unrelated tables or change the schema. Validate input against an allow list where the format is known, such as numeric identifiers. Return generic error messages to users and log the details on the server. A web application firewall can reduce noise, but treat it as a speed bump, not a fix.",
  {"bullets": ["Parameterized queries first", "Least-privilege database account", "Allow-list validation", "Generic errors for users, details in logs"]}),
 ("slide", "Common Mistakes", "Three mistakes come up again and again. First, blacklist filtering, such as removing quotes or the word select. Attackers route around filters with encodings and alternate syntax. Second, manual escaping, which is fragile and differs between databases. Third, parameterizing the values but still concatenating identifiers, like table or column names taken from user input. For those, use a fixed allow list of permitted names. And one testing mistake: running tools against systems you are not authorized to test. Scope and written permission come first.",
  {"bullets": ["Blacklist filtering", "Manual escaping", "Concatenated identifiers", "Testing without authorization"]}),
 ("slide", "In the Real World", "When you find an injection issue in a penetration test or a bug bounty program, the useful report contains the root cause, the affected parameter, a safe proof of concept, and the recommended fix. It does not contain a data dump. Proving that the query can be changed is enough, and extracting real user data is usually out of scope and can break the rules of the program.",
  {"bullets": ["Root cause + affected parameter", "Safe proof of concept", "Recommended fix", "No unnecessary data extraction"]}),
 ("quiz", "Knowledge Check", "Quick check. Your application must let users search products by name. Which is the best protection against SQL injection? A, blacklist filtering. B, parameterized queries. C, hiding error messages. Or D, longer passwords. Pause the video and decide. The answer is B, parameterized queries. Hiding errors helps, but it does not remove the flaw.",
  {"bullets": ["A) Blacklist filtering", "B) Parameterized queries", "C) Hiding error messages", "D) Longer passwords"], "_min": 24}),
 ("summary", "Summary", "To summarize. SQL injection happens when user input is concatenated into a query. You can confirm it safely in a lab by observing errors and changed results. The fix is parameterized queries, backed by least privilege, allow list validation, and quiet error handling. Practice only on intentionally vulnerable applications that you control, like the one in this lesson.",
  {"bullets": ["Concatenation is the root cause", "Parameterize every query", "Layer: least privilege, validation, quiet errors", "Practice only in authorized labs"]}),
 ("instructor", "Thanks for Watching", "Thanks for watching. The lab app, the captured output and the lesson sources are in the project repository, so you can reproduce everything on your own machine.", {}),
]

scenes = []
for i, (typ, title, narr, extra) in enumerate(N, 1):
    words = len(narr.split())
    dur = max(extra.pop("_min", 0), round(words / 2.6 + 1, 1), 5)
    scenes.append({"scene_id": f"scene_{i:03d}", "type": typ, "duration_seconds": min(dur, 120), "narration": narr,
                   "visual_description": title, "on_screen_text": title, "asset_requirements": [], "transition": "fade" if i % 3 else "slide", **extra})

script = {
    "title": "SQL Injection Fundamentals",
    "hook": N[0][2], "introduction": N[1][2],
    "learning_objectives": ["Explain the root cause of SQL injection", "Recognize vulnerable query construction", "Demonstrate it safely against a local lab app", "Apply parameterized queries and layered defenses"],
    "technical_explanation": N[2][2] + " " + N[3][2],
    "practical_demonstration": " ".join(n[2] for n in N[5:8]),
    "diagrams": [DIAGRAM],
    "real_world_applications": N[11][2],
    "defensive_recommendations": N[9][2],
    "common_mistakes": ["Blacklist filtering", "Manual escaping instead of parameters", "Concatenating identifiers from user input", "Testing without written authorization"],
    "knowledge_check": [{"question": "Which is the best protection against SQL injection?", "options": ["Blacklist filtering", "Parameterized queries", "Hiding error messages", "Longer passwords"], "answer_index": 1}],
    "summary": N[13][2],
    "references": [
        {"title": "OWASP Top 10:2021 - A03 Injection", "url": "https://owasp.org/Top10/A03_2021-Injection/"},
        {"title": "OWASP SQL Injection Prevention Cheat Sheet", "url": "https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html"},
        {"title": "CWE-89: Improper Neutralization of Special Elements used in an SQL Command", "url": "https://cwe.mitre.org/data/definitions/89.html"}],
    "unverified_claims": [],
}
bundle = {"course_name": "Web Application Penetration Testing", "module_title": "Injection Flaws", "lesson_title": "SQL Injection Fundamentals",
          "summary": "Root cause, safe lab demonstration and defenses for SQL injection.", "script": script,
          "storyboard": {"lesson_title": "SQL Injection Fundamentals", "scenes": scenes},
          "recordings": {s["scene_id"]: f"storage/lab_clips/{s['recording_asset']}" for s in scenes if s.get("recording_asset")}}
Path(__file__).with_name("bundle.json").write_text(json.dumps(bundle, indent=2))
print(sum(len(n[2].split()) for n in N), "narration words;", len(scenes), "scenes")
