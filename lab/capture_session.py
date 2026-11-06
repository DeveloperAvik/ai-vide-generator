"""Runs a FIXED list of requests (hard-coded here, never LLM-generated) against the local lab app and records the
real responses to lab/session.json. Only talks to 127.0.0.1:8099."""
import json
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
BASE = "http://127.0.0.1:8099"
STEPS = [
    ("Normal search", "/search?q=laptop"),
    ("Single quote breaks the query", "/search?q='"),
    ("Always-true condition returns every row", "/search?q=zzz%' OR 1=1--"),
    ("Login with a comment hides the password check", "/login?user=admin'--&pass=x"),
    ("Same input against the parameterized endpoint", "/safe/search?q=zzz%' OR 1=1--"),
]


def get(path):
    url = BASE + urllib.parse.quote(path, safe="/?=&'%")
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def main():
    srv = subprocess.Popen([sys.executable, str(HERE / "vuln_app.py")])
    try:
        for _ in range(50):
            try:
                get("/search?q=a")
                break
            except OSError:
                time.sleep(0.1)
        session = []
        for title, path in STEPS:
            code, body = get(path)
            session.append({"title": title, "request": f"GET {path}", "status": code, "body": body})
        (HERE / "session.json").write_text(json.dumps(session, indent=2))
        for s in session:
            print(s["status"], s["request"], "->", s["body"][:90])
    finally:
        srv.terminate()


if __name__ == "__main__":
    main()
