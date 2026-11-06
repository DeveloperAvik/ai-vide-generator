#!/usr/bin/env python3
"""Generates the importable n8n workflow JSON files in ./workflows. Re-run after editing: python3 generate_workflows.py
No secrets are embedded: the backend URL and service token come from n8n environment variables
(STUDIO_API_URL, STUDIO_SERVICE_TOKEN, optional NOTIFY_WEBHOOK_URL)."""
import json
import uuid
from pathlib import Path

OUT = Path(__file__).parent / "workflows"
OUT.mkdir(exist_ok=True)
API = "{{ $env.STUDIO_API_URL }}"  # no leading "=": call sites write f"={API}/..." (a second "=" makes n8n reject the URL)
HDRS = {"parameters": [{"name": "Authorization", "value": "=Bearer {{ $env.STUDIO_SERVICE_TOKEN }}"},
                        {"name": "Idempotency-Key", "value": "={{ $workflow.name }}-{{ $execution.id }}"}]}


def nid(name):  # stable ids so re-generation doesn't churn diffs
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, name))


def node(name, type_, params, pos, version=1, **extra):
    return {"id": nid(name), "name": name, "type": type_, "typeVersion": version, "position": pos, "parameters": params, **extra}


def webhook(path):
    return node("Webhook", "n8n-nodes-base.webhook", {"httpMethod": "POST", "path": path, "responseMode": "responseNode", "options": {}}, [0, 0], 2,
                webhookId=nid(path))


def http(name, method, url, pos, body=None, on_error=True):
    p = {"method": method, "url": url, "sendHeaders": True, "headerParameters": HDRS, "options": {"timeout": 120000}}
    if body is not None:
        p.update({"sendBody": True, "specifyBody": "json", "jsonBody": body})
    extra = {"retryOnFail": True, "maxTries": 3, "waitBetweenTries": 5000}
    if on_error:
        extra["onError"] = "continueErrorOutput"
    return node(name, "n8n-nodes-base.httpRequest", p, pos, 4.2, **extra)


def notify(name, text_expr, pos):
    # POSTs to any Slack/Discord/ntfy-compatible webhook if NOTIFY_WEBHOOK_URL is set; otherwise skipped by the IF above it.
    return node(name, "n8n-nodes-base.httpRequest", {"method": "POST", "url": "={{ $env.NOTIFY_WEBHOOK_URL }}", "sendBody": True,
                "specifyBody": "json", "jsonBody": '={{ JSON.stringify({ text: ' + text_expr + ', content: ' + text_expr + ' }) }}'}, pos, 4.2,
                onError="continueRegularOutput")


def respond(name, body, pos, code=200):
    return node(name, "n8n-nodes-base.respondToWebhook", {"respondWith": "json", "responseBody": body, "options": {"responseCode": code}}, pos, 1.1)


def has_notify(pos):
    return node("Notify configured?", "n8n-nodes-base.if", {"conditions": {"options": {"caseSensitive": True, "typeValidation": "loose"},
                "combinator": "and", "conditions": [{"id": nid("nc"), "leftValue": "={{ $env.NOTIFY_WEBHOOK_URL }}", "rightValue": "",
                "operator": {"type": "string", "operation": "notEmpty", "singleValue": True}}]}}, pos, 2)


def log_failure(stage_name, pos):
    return http("Log failure", "POST", f"={API}/api/internal/log", pos,
                '={{ JSON.stringify({ stage: "n8n:' + stage_name + '", level: "error", lesson_id: $("Webhook").item.json.body.lesson_id ?? null, message: JSON.stringify($json).slice(0, 1500) }) }}',
                on_error=False)


def wf(name, nodes, connections):
    return {"id": nid("wf:" + name).replace("-", "")[:16], "name": name, "nodes": nodes, "connections": connections, "active": False, "settings": {"executionOrder": "v1", "saveManualExecutions": True,
            "saveDataErrorExecution": "all", "saveDataSuccessExecution": "all"}, "versionId": nid(name + "v"), "meta": {"templateCredsSetupCompleted": True}, "tags": []}


def conn(*chains):
    c = {}
    for chain in chains:
        for (a, ai), (b, _) in zip(chain, chain[1:]):
            c.setdefault(a, {}).setdefault("main", [])
            while len(c[a]["main"]) <= ai:
                c[a]["main"].append([])
            c[a]["main"][ai].append({"node": b, "type": "main", "index": 0})
    return c


def webhook_flow(filename, title, path, method, url, body, stage_name):
    """webhook -> HTTP (retry x3) -> respond | error branch -> log -> (notify) -> respond 500."""
    nodes = [webhook(path), http("Call Studio API", method, url, [260, 0], body), respond("Respond OK", "={{ JSON.stringify($json) }}", [520, -80]),
             log_failure(stage_name, [520, 120]), has_notify([760, 120]),
             notify("Notify failure", f'"[Cyber Studio] {stage_name} failed for lesson " + ($("Webhook").item.json.body.lesson_id ?? "?")', [1000, 40]),
             respond("Respond Error", '={{ JSON.stringify({ error: "stage failed", stage: "' + stage_name + '" }) }}', [1240, 120], 502)]
    c = conn([("Webhook", 0), ("Call Studio API", 0)], [("Call Studio API", 0), ("Respond OK", 0)], [("Call Studio API", 1), ("Log failure", 0), ("Notify configured?", 0)],
             [("Notify configured?", 0), ("Notify failure", 0), ("Respond Error", 0)], [("Notify configured?", 1), ("Respond Error", 0)])
    save(filename, title, nodes, c)


def save(filename, title, nodes, c):
    (OUT / filename).write_text(json.dumps(wf(title, nodes, c), indent=2))


LID = '{{ $json.body.lesson_id }}'

# 01 course generator
webhook_flow("01_course_generator.json", "01 Course Generator", "studio/course-generate", "POST", f"={API}/api/courses/generate",
             '={{ JSON.stringify({ course_name: $json.body.course_name, language: $json.body.language ?? "English", difficulty: $json.body.difficulty ?? "Intermediate", target_audience: $json.body.target_audience ?? "Cybersecurity students", videos_per_week: $json.body.videos_per_week ?? 3, duration_minutes: $json.body.duration_minutes ?? 8 }) }}',
             "course_generator")
# 02 lesson generator (script stage)
webhook_flow("02_lesson_generator.json", "02 Lesson Generator", "studio/lesson-generate", "POST", f"={API}/api/lessons/{LID}/stage/script", None, "lesson_generator")
# 03 research + verification
webhook_flow("03_research_verification.json", "03 Research Verification", "studio/research", "POST", f"={API}/api/lessons/{LID}/stage/research", None, "research")
# 04..06 asset parts
webhook_flow("04_voice_generation.json", "04 Voice Generation", "studio/voice", "POST", f"={API}/api/lessons/{LID}/stage/assets?parts=voice", None, "voice")
webhook_flow("05_avatar_generation.json", "05 Avatar Generation", "studio/avatar", "POST", f"={API}/api/lessons/{LID}/stage/assets?parts=avatar", None, "avatar")
webhook_flow("06_visual_generation.json", "06 Visual Generation", "studio/visuals", "POST", f"={API}/api/lessons/{LID}/stage/assets?parts=visuals", None, "visuals")
webhook_flow("07_video_rendering.json", "07 Video Rendering", "studio/render", "POST", f"={API}/api/lessons/{LID}/stage/render", None, "render")
webhook_flow("08_quality_control.json", "08 Quality Control", "studio/quality", "POST", f"={API}/api/lessons/{LID}/stage/quality", None, "quality")
webhook_flow("10_youtube_upload.json", "10 YouTube Upload", "studio/youtube-upload", "POST", f"={API}/api/lessons/{LID}/youtube/publish",
             '={{ JSON.stringify({ publish_at: $json.body.publish_at ?? null }) }}', "youtube_upload")

# 09 human approval: notifies reviewers about the queue (approval itself is human-only in the dashboard; the service token is refused by the API)
nodes = [node("Every 30 min", "n8n-nodes-base.scheduleTrigger", {"rule": {"interval": [{"field": "minutes", "minutesInterval": 30}]}}, [0, 0], 1.2),
         node("Webhook", "n8n-nodes-base.webhook", {"httpMethod": "POST", "path": "studio/approval-request", "responseMode": "onReceived", "options": {}}, [0, 200], 2, webhookId=nid("appr")),
         http("Get approval queue", "GET", f"={API}/api/approvals/queue", [260, 100], None),
         node("Anything pending?", "n8n-nodes-base.if", {"conditions": {"options": {"caseSensitive": True, "typeValidation": "loose"}, "combinator": "and", "conditions": [
             {"id": nid("pend"), "leftValue": "={{ $input.all().length }}", "rightValue": 0, "operator": {"type": "number", "operation": "gt"}}]}}, [520, 100], 2),
         has_notify([760, 20]),
         notify("Notify reviewers", '"[Cyber Studio] " + $("Get approval queue").all().length + " item(s) awaiting human approval: " + ($env.STUDIO_DASHBOARD_URL ?? "") + "/approvals"', [1000, 20])]
save("09_human_approval.json", "09 Human Approval", nodes, conn([("Every 30 min", 0), ("Get approval queue", 0)], [("Webhook", 0), ("Get approval queue", 0)],
     [("Get approval queue", 0), ("Anything pending?", 0)], [("Anything pending?", 0), ("Notify configured?", 0), ("Notify reviewers", 0)]))
nodes[4]["name"] = "Notify configured?"

# 11 scheduler: Mon/Wed/Fri 09:00, upload the next APPROVED lessons privately with publishAt
nodes = [node("Mon Wed Fri 09:00", "n8n-nodes-base.scheduleTrigger", {"rule": {"interval": [{"field": "cronExpression", "expression": "0 9 * * 1,3,5"}]}}, [0, 0], 1.2),
         http("Approved lessons", "GET", f"={API}/api/lessons?status=APPROVED", [260, 0], None),
         node("Take first", "n8n-nodes-base.limit", {"maxItems": 1}, [520, 0], 1),
         http("Upload private + schedule", "POST", f"={API}/api/lessons/{{{{ $json.id }}}}/youtube/publish", [780, 0],
              '={{ JSON.stringify({ publish_at: new Date(Date.now() + 48*3600*1000).toISOString() }) }}', on_error=False)]
save("11_youtube_scheduler.json", "11 YouTube Scheduler", nodes, conn([("Mon Wed Fri 09:00", 0), ("Approved lessons", 0), ("Take first", 0), ("Upload private + schedule", 0)]))

# 12 analytics
nodes = [node("Daily 06:00", "n8n-nodes-base.scheduleTrigger", {"rule": {"interval": [{"field": "cronExpression", "expression": "0 6 * * *"}]}}, [0, 0], 1.2),
         http("Collect analytics", "POST", f"={API}/api/analytics/collect", [260, 0], '={}', on_error=False)]
save("12_analytics_collector.json", "12 Analytics Collector", nodes, conn([("Daily 06:00", 0), ("Collect analytics", 0)]))

# 13 error recovery: every 15 min retry FAILED lessons (backend enforces max retries, resumes from last good stage)
nodes = [node("Every 15 min", "n8n-nodes-base.scheduleTrigger", {"rule": {"interval": [{"field": "minutes", "minutesInterval": 15}]}}, [0, 0], 1.2),
         http("Failed lessons", "GET", f"={API}/api/lessons?status=FAILED", [260, 0], None),
         node("Under retry limit", "n8n-nodes-base.filter", {"conditions": {"options": {"caseSensitive": True, "typeValidation": "loose"}, "combinator": "and", "conditions": [
             {"id": nid("rl"), "leftValue": "={{ $json.retry_count }}", "rightValue": 3, "operator": {"type": "number", "operation": "lt"}}]}}, [520, 0], 2),
         http("Retry from last good stage", "POST", f"={API}/api/lessons/{{{{ $json.id }}}}/retry", [780, 0], None, on_error=False)]
save("13_error_recovery.json", "13 Error Recovery", nodes, conn([("Every 15 min", 0), ("Failed lessons", 0), ("Under retry limit", 0), ("Retry from last good stage", 0)]))
print("wrote", len(list(OUT.glob("*.json"))), "workflows")
