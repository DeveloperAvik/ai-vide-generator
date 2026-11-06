#!/usr/bin/env python3
"""End-to-end n8n verification. Run from the repo root AFTER `make docker-infra-up`, creating the n8n owner account in the
browser (http://localhost:5678), and starting the local API (`make start`):   make n8n-test
Needs: docker CLI on PATH. Uses only safe demo data (a clearly named test course/lesson). Writes storage/n8n_test_report.json."""
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
_ENV_FILE = ROOT / ".env"  # created by scripts/setup.sh; absent on a fresh checkout/CI (the live n8n run then cannot authenticate)
ENV = dict(l.split("=", 1) for l in _ENV_FILE.read_text().splitlines() if "=" in l and not l.startswith("#")) if _ENV_FILE.exists() else {}
N8N, API = "http://localhost:5678", "http://localhost:8000/api"
COMPOSE = ["docker", "compose", "-f", str(ROOT / "infrastructure/docker-compose.yml"), "--env-file", str(ROOT / ".env")]
PY = str(ROOT / "backend/.venv/bin/python")
results: list[dict] = []


def rec(name, status, detail=""):
    results.append({"name": name, "status": status, "detail": str(detail)[:600]})
    print(f"[{status:^9}] {name}" + (f"  - {str(detail)[:200]}" if detail else ""), flush=True)


def sh(args, timeout=300, cwd=None, **kw):
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout, cwd=cwd or ROOT, **kw)


def dc(*args, timeout=300):
    return sh(COMPOSE + ["exec", "-T", *args], timeout=timeout)


def http(method, url, body=None, headers=None, timeout=60):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()
    except OSError as e:
        return 0, str(e)


def api_token():
    code, body = http("POST", f"{API}/auth/login", {"email": ENV["FIRST_ADMIN_EMAIL"], "password": ENV["FIRST_ADMIN_PASSWORD"]})
    return json.loads(body)["access_token"] if code == 200 else None


def wait(cond, secs, step=3):
    end = time.time() + secs
    while time.time() < end:
        v = cond()
        if v:
            return v
        time.sleep(step)
    return None


# ---------------------------------------------------------------- 1. static audit
def url_problems(workflow: dict) -> list[str]:
    """n8n expressions start with exactly one "="; "==" leaks a literal "=" into the URL and the node fails with Invalid URL."""
    out = []
    for n in workflow["nodes"]:
        u = n.get("parameters", {}).get("url")
        if isinstance(u, str) and (u.startswith("==") or not (u.startswith("={{") or u.startswith("http"))):
            out.append(f"node '{n['name']}' has a malformed url: {u[:60]}")
    return out


def static_audit():
    wfs = {}
    for f in sorted((ROOT / "automation/workflows").glob("*.json")):
        d = json.loads(f.read_text())
        wfs[f.name] = d
        names = {n["name"] for n in d["nodes"]}
        problems = []
        for src, outs in d["connections"].items():
            if src not in names:
                problems.append(f"connection from unknown node {src}")
            for lane in outs.get("main", []):
                problems += [f"connection to unknown node {t['node']}" for t in lane if t["node"] not in names]
        problems += url_problems(d)
        raw = f.read_text()
        if re.search(r"localhost|127\.0\.0\.1|host\.docker\.internal", raw):
            problems.append("hardcoded host URL (must come from $env.STUDIO_API_URL)")
        if re.search(r"sk-ant|eyJ[A-Za-z0-9_-]{20,}|password\"\s*:\s*\"[^$=]", raw):
            problems.append("possible hardcoded secret")
        if "$env.STUDIO_" not in raw and "scheduleTrigger" not in raw:
            problems.append("no env-based API reference")
        rec(f"static audit {f.name}", "FAIL" if problems else "PASS", "; ".join(problems))
    return wfs


# ---------------------------------------------------------------- main
def main():
    wfs = static_audit()

    code, _ = http("GET", f"{N8N}/healthz")
    rec("n8n /healthz on 127.0.0.1:5678", "PASS" if code == 200 else "FAIL", f"HTTP {code}")
    if code != 200:
        return finish("n8n not reachable - run `make docker-infra-up` first")
    code, body = http("GET", f"{N8N}/rest/settings")
    try:
        needs_owner = json.loads(body)["data"]["userManagement"]["showSetupOnFirstLoad"]
    except (ValueError, KeyError):
        needs_owner = None
    rec("n8n owner account", "FAIL" if needs_owner else ("PASS" if needs_owner is False else "UNKNOWN"),
        "open http://localhost:5678 and create the owner account first" if needs_owner else "")
    if needs_owner:
        return finish("create the owner account, then rerun")

    ps = sh(COMPOSE + ["ps", "--format", "json"]).stdout
    states = {}
    for line in ps.splitlines():
        try:
            c = json.loads(line)
            states[c["Service"]] = f'{c["State"]}/{c.get("Health") or "-"}'
        except (ValueError, KeyError):
            pass
    rec("containers (postgres, n8n only)", "PASS" if set(states) == {"postgres", "n8n"} and all(v.startswith("running") for v in states.values()) else "FAIL", states)
    pg = dc("postgres", "psql", "-U", "studio", "-d", "n8n", "-tAc", "select count(*) from information_schema.tables where table_schema='public'")
    rec("n8n stores data in postgres:5432 (db n8n)", "PASS" if pg.returncode == 0 and int(pg.stdout.strip() or 0) > 5 else "FAIL", pg.stdout.strip() or pg.stderr[-200:])

    # local API reachable from inside the container via host.docker.internal
    probe = dc("n8n", "sh", "-c", 'wget -qO- "$STUDIO_API_URL/api/health"')
    rec("n8n container -> local FastAPI (host.docker.internal:8000)", "PASS" if '"status":"ok"' in probe.stdout else "FAIL", probe.stdout or probe.stderr[-300:])
    tok_probe = dc("n8n", "sh", "-c", 'wget -qO- --header "Authorization: Bearer $STUDIO_SERVICE_TOKEN" "$STUDIO_API_URL/api/lessons" | head -c 80')
    rec("service token accepted by API", "PASS" if tok_probe.stdout.startswith("[") else "FAIL", tok_probe.stdout or tok_probe.stderr[-200:])

    # import
    imp = sh(["bash", "infrastructure/scripts/import_workflows.sh"], timeout=300)
    ok_imp = imp.returncode == 0
    rec("import 13 workflows", "PASS" if ok_imp else "FAIL", (imp.stdout + imp.stderr)[-400:])
    lst = dc("n8n", "n8n", "list:workflow").stdout
    ids = {}
    for line in lst.splitlines():
        if "|" in line:
            wid, name = line.split("|", 1)
            ids[name.strip()] = wid.strip()
    missing = [d["name"] for d in wfs.values() if d["name"] not in ids]
    rec("all 13 present in n8n", "PASS" if not missing else "FAIL", missing or f"{len(ids)} listed")

    # activate webhook workflows
    for fname, d in wfs.items():
        if any(n["type"].endswith("webhook") for n in d["nodes"]) and d["name"] in ids:
            out = dc("n8n", "n8n", "update:workflow", f"--id={ids[d['name']]}", "--active=true")
            if out.returncode != 0:
                out = dc("n8n", "n8n", "publish:workflow", f"--id={ids[d['name']]}")
            rec(f"activate {fname}", "PASS" if out.returncode == 0 else "FAIL", (out.stdout + out.stderr)[-200:])
    sh(COMPOSE + ["restart", "n8n"])
    wait(lambda: http("GET", f"{N8N}/healthz")[0] == 200, 90, 3)
    # /healthz passes before webhooks are registered. A GET on a POST-only production webhook answers 404 "Did you mean to make
    # a POST request?" when it IS registered (and never runs the workflow); an unregistered path says "is not registered".
    paths = sorted({n["parameters"]["path"] for d in wfs.values() for n in d["nodes"] if n["type"].endswith("webhook") and "path" in n["parameters"]})
    pending = set(paths)

    def all_registered():
        pending.intersection_update({p for p in pending if "Did you mean" not in http("GET", f"{N8N}/webhook/{p}")[1]})
        return not pending

    wait(all_registered, 120, 3)
    rec("webhooks registered after restart", "PASS" if not pending else "FAIL", f"{len(paths) - len(pending)}/{len(paths)} registered" + (f"; missing {sorted(pending)}" if pending else ""))

    # report the ACTUAL activation state from n8n's database (the CLI exit code alone does not prove it)
    act = sh(COMPOSE + ["exec", "-T", "postgres", "sh", "-c", 'psql -U "${POSTGRES_USER:-postgres}" -d n8n -Atc "select name||\'|\'||active from workflow_entity order by name"']).stdout
    for line in filter(None, act.splitlines()):
        nm, _, on = line.rpartition("|")
        scheduled = any(d["name"] == nm and not any(n["type"].endswith("webhook") for n in d["nodes"]) for d in wfs.values())
        if scheduled:  # 11/12/13 would upload / collect / retry real lessons on a timer, so the harness never switches them on
            rec(f"n8n active state: {nm}", "PASS" if on not in ("t", "true") else "FAIL", f"scheduled workflow, intentionally left inactive (active={on})")
        else:
            rec(f"n8n active state: {nm}", "PASS" if on in ("t", "true") else "FAIL", f"active={on}")

    # functional tests
    tok = api_token()
    if not tok:
        return finish("could not log in to local API (is `make start` running?)")
    H = {"Authorization": f"Bearer {tok}"}
    hook = lambda path, body: http("POST", f"{N8N}/webhook/studio/{path}", body, timeout=120)  # noqa: E731
    logs = lambda lid: json.loads(http("GET", f"{API}/logs?lesson_id={lid}", headers=H)[1])  # noqa: E731
    status = lambda lid: json.loads(http("GET", f"{API}/lessons/{lid}", headers=H)[1])["lesson"]["status"]  # noqa: E731

    imp = sh([PY, "-m", "app.cli.import_lesson", str(ROOT / "lessons/sqli_fundamentals/n8n_test_bundle.json"), "--approve-script", "--stop-after-approval", "--fresh", "--offline"], cwd=ROOT / "backend", timeout=300,
            env={**os.environ, "LLM_PROVIDER": "mock", "LLM_FALLBACK_PROVIDER": ""})  # test lesson only: real-model review takes ~15 min; gates still run
    m = re.search(r"lesson id (\d+)", imp.stdout)
    if not m:
        rec("create test lesson (SCRIPT_APPROVED)", "FAIL", imp.stdout[-300:] + imp.stderr[-300:])
        return finish("cannot create test lesson")
    lid = int(m.group(1))
    rec("create test lesson (SCRIPT_APPROVED)", "PASS", f"lesson {lid} 'n8n Pipeline Test Lesson'")

    def stage_wf(label, path, expect_status, wait_log=None, timeout=900):
        def count(level_or_msg):
            return sum(1 for x in logs(lid) if x["stage"] == wait_log and (x["message"] == "completed" if level_or_msg == "ok" else x["level"] == "error"))
        ok0, err0 = count("ok"), count("err")
        code, body = hook(path, {"lesson_id": lid})
        if code != 200:
            return rec(f"workflow {label}", "FAIL", f"webhook HTTP {code}: {body[:200]}")
        if wait_log:
            done = wait(lambda: count("ok") > ok0 or count("err") > err0, timeout)
            if not done:
                return rec(f"workflow {label}", "FAIL", f"stage did not finish in {timeout} s")
        st = status(lid)
        rec(f"workflow {label}", "PASS" if st == expect_status else "FAIL", f"lesson status {st} (expected {expect_status})")

    # order matters: the avatar part composes on the slide PNG made by the visuals part and needs the narration audio from voice
    # (the voice stage is slow on CPU TTS; kokoro took ~8 min for 5 min of audio on this machine)
    stage_wf("04_voice_generation", "voice", "ASSETS_GENERATING", "assets")
    stage_wf("06_visual_generation", "visuals", "ASSETS_GENERATING", "assets")
    stage_wf("05_avatar_generation", "avatar", "ASSETS_READY", "assets")
    stage_wf("07_video_rendering", "render", "QUALITY_CHECK", "render")
    stage_wf("08_quality_control", "quality", "APPROVAL_PENDING", "quality_check")

    # error branch + duplicate prevention: render again on a finished lesson must be refused (409 -> workflow 502 + log entry)
    pre = status(lid)
    if pre != "APPROVAL_PENDING":  # a 409 from an unfinished pipeline is not evidence of duplicate prevention
        rec("duplicate prevention + error branch (07 re-run)", "FAIL", f"precondition not met: lesson is {pre}, not APPROVAL_PENDING (render never completed)")
    code, body = hook("render", {"lesson_id": lid})
    logged = any(x["stage"] == "n8n:render" and x["level"] == "error" for x in logs(lid))
    if pre == "APPROVAL_PENDING":
        rec("duplicate prevention + error branch (07 re-run)", "PASS" if code == 502 and logged else "FAIL", f"HTTP {code}, failure logged by workflow: {logged}")
    code, body = hook("youtube-upload", {"lesson_id": lid})
    rec("workflow 10_youtube_upload blocks unapproved lesson", "PASS" if code == 502 else "FAIL", f"HTTP {code} (API must refuse: lesson not human-approved)")
    # (a successful upload needs your Google OAuth client; not testable here)

    llm = json.loads(http("GET", f"{API}/health")[1] or "{}").get("llm_provider")
    if llm != "mock":
        # 01/02/03 drive the API's configured LLM; a real local model needs 15+ min, far beyond a webhook timeout.
        for n in ("01_course_generator", "03_research_verification", "02_lesson_generator"):
            rec(f"workflow {n}", "SKIPPED", f"API LLM provider is '{llm}', not 'mock'; this check needs the mock provider (not run, not counted as passed)")
    else:
        cname = f"n8n Webhook Test Course {int(time.time())}"
        code, body = hook("course-generate", {"course_name": cname, "duration_minutes": 8})
        rec("workflow 01_course_generator", "PASS" if code == 200 and cname in http("GET", f"{API}/courses", headers=H)[1] else "FAIL", f"HTTP {code}")
        cl = [c for c in json.loads(http("GET", f"{API}/courses", headers=H)[1]) if c["name"] == cname]
        if cl:
            det = json.loads(http("GET", f"{API}/courses/{cl[0]['id']}", headers=H)[1])
            tl = det["modules"][0]["lessons"][0]["id"]
            code, _ = hook("research", {"lesson_id": tl})
            ok = code == 200 and wait(lambda: status(tl) == "RESEARCHING", 90)
            rec("workflow 03_research_verification", "PASS" if ok else "FAIL", f"HTTP {code}, lesson {tl} status {status(tl)}")
            code, _ = hook("lesson-generate", {"lesson_id": tl})
            ok = code == 200 and wait(lambda: status(tl) == "SCRIPT_GENERATED", 90)
            rec("workflow 02_lesson_generator", "PASS" if ok else "FAIL", f"HTTP {code}, lesson {tl} status {status(tl)} (mock LLM unless configured)")

    # scheduled workflows 09/11/12/13 start from a schedule trigger. `n8n execute` only runs workflows that contain an
    # "Execute Workflow Trigger" node ("Missing node to start execution"), so they cannot be executed from the CLI at all. They are
    # reported as SKIPPED (never PASS), and the read-only API calls they make are verified separately with the service token.
    for num in ("09", "11", "12", "13"):
        rec(f"workflow {num} (scheduled) executed once", "SKIPPED",
            "not executed: schedule-triggered workflows cannot be started by `n8n execute`; the API call they make is checked below")
    svc = {"Authorization": f"Bearer {ENV['SERVICE_TOKEN']}"}
    for num, label, method, path, ok_codes in (
            ("09", "approval queue", "GET", "/approvals/queue", (200,)),
            ("11", "APPROVED lessons list", "GET", "/lessons?status=APPROVED", (200,)),
            ("13", "FAILED lessons list (read-only; retry is not called)", "GET", "/lessons?status=FAILED", (200,)),
            ("12", "analytics collect (no published videos yet)", "POST", "/analytics/collect", (200,))):
        code, body = http(method, f"{API}{path}", {} if method == "POST" else None, headers=svc)
        if code in ok_codes:
            st = "PASS"
            why = ("answers 200 with nothing to collect; real analytics need YouTube OAuth and published videos and are NOT verified"
                   if num == "12" else "API call used by the workflow answers correctly")
        else:
            st, why = "FAIL", f"unexpected HTTP {code}: {body[:120]}"
        rec(f"API call behind workflow {num}: {label}", st, f"{method} {path} -> HTTP {code}; {why}")
    finish()


def finish(msg=""):
    if msg:
        print("STOPPED:", msg)
    counts = {}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    out = ROOT / "storage" / "n8n_test_report.json"
    out.write_text(json.dumps({"summary": counts, "stopped": msg, "results": results}, indent=2))
    print("\nSUMMARY:", counts, "->", out)
    sys.exit(1 if counts.get("FAIL") or msg else 0)


if __name__ == "__main__":
    main()
