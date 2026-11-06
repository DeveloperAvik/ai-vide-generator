from app.models import Course, Lesson, LessonStatus, Module
from app.security import redaction
from app.security.paths import resolve_within, safe_name
import pytest


def test_login_and_protection(client, auth_headers):
    assert client.get("/api/courses").status_code == 401
    assert client.post("/api/auth/login", json={"email": "admin@test.local", "password": "wrong"}).status_code == 401
    assert client.get("/api/courses", headers=auth_headers).status_code == 200


def test_health_public(client):
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["database"] is True


def test_course_generation_persists_and_dedupes(client, auth_headers, db):
    body = {"course_name": "Web Application Penetration Testing", "duration_minutes": 8}
    r = client.post("/api/courses/generate", json=body, headers=auth_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert len(data["modules"]) >= 2 and data["learning_objectives"]
    assert db.query(Lesson).count() == sum(len(m["lessons"]) for m in data["modules"])
    assert all(l["status"] == "TOPIC_PENDING" for m in data["modules"] for l in m["lessons"])
    assert client.post("/api/courses/generate", json=body, headers=auth_headers).status_code == 409  # duplicate prevention


def test_input_validation(client, auth_headers):
    r = client.post("/api/courses/generate", json={"course_name": "x", "duration_minutes": 99}, headers=auth_headers)
    assert r.status_code == 422


def test_all_statuses_exist():
    expected = "TOPIC_PENDING RESEARCHING SCRIPT_GENERATED TECHNICAL_REVIEW SCRIPT_APPROVED ASSETS_GENERATING ASSETS_READY RENDERING QUALITY_CHECK APPROVAL_PENDING APPROVED SCHEDULED PUBLISHED FAILED".split()
    assert [s.value for s in LessonStatus] == expected


def test_service_token_cannot_approve(client, auth_headers):
    svc = {"Authorization": "Bearer svc-token-for-tests"}
    assert client.get("/api/lessons", headers=svc).status_code == 200
    assert client.post("/api/lessons/1/video/decision", json={"decision": "APPROVED"}, headers=svc).status_code == 403


def test_path_traversal_blocked(tmp_path):
    with pytest.raises(ValueError):
        resolve_within(tmp_path, "..", "etc", "passwd")
    assert safe_name("../../evil.mp4") == "evil.mp4"


def test_redaction_flags_secrets():
    f = redaction.scan_text("export API_KEY=abcd1234abcd1234abcd and password: hunter22 ssh 10.0.0.5 AKIAABCDEFGHIJKLMNOP")
    kinds = {x["type"] for x in f}
    assert {"generic_api_key", "password_assign", "private_ip", "aws_access_key"} <= kinds
    assert "hunter22" not in redaction.redact("password: hunter22")
    assert not redaction.scan_text("nmap 192.168.1.10 and 10.99.0.7 mail user@example.com a@lab.example.org b@x.test")
    assert any(x["type"] == "email" for x in redaction.scan_text("mail bob@gmail.com"))
