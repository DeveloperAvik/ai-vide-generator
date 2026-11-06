import httpx
import pytest

from app.services import research


def test_research_redirect_to_disallowed_host_blocked(monkeypatch):
    calls = []

    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        calls.append(str(request.url))
        return httpx.Response(302, headers={"location": "https://169.254.169.254/latest/meta-data"})

    monkeypatch.setattr(research, "_client", lambda: httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False))
    monkeypatch.setattr(research, "_resolve", lambda h: ["93.184.216.34"])
    research._ROBOTS.clear()
    ok, why = research.fetch_excerpt("https://owasp.org/Top10/")
    assert not ok and ("allow-list" in why or "IP-literal" in why) and calls == ["https://owasp.org/Top10/"]


def test_non_https_and_foreign_hosts_rejected():
    assert not research.host_allowed("http://owasp.org/x")
    assert not research.host_allowed("https://evil.example/x")
    assert not research.host_allowed("javascript:alert(1)")


def test_ai_config_admin_only_and_masks_key(client, auth_headers):
    svc = {"Authorization": "Bearer svc-token-for-tests"}
    assert client.get("/api/system/ai-config", headers=svc).status_code == 403
    r = client.put("/api/system/ai-config", json={"anthropic_api_key": "sk-ant-secretsecretsecret1234", "llm_provider": "mock"}, headers=auth_headers)
    assert r.status_code == 200 and "secret" not in r.text and r.json()["anthropic_key_set"] is True
    from app.core.config import RUNTIME_FILE
    assert oct(RUNTIME_FILE.stat().st_mode)[-3:] == "600"
    RUNTIME_FILE.unlink()
    from app.core.config import get_settings
    get_settings.cache_clear()


def test_production_refuses_mock_and_say(monkeypatch):
    from app.core.config import get_settings
    from app.providers.llm import LLMError, get_llm
    from app.providers.voice import VoiceUnavailable, get_voice
    monkeypatch.setenv("APP_ENV", "production")
    get_settings.cache_clear()
    try:
        with pytest.raises(LLMError, match="production"):
            get_llm("mock")
        with pytest.raises(VoiceUnavailable):
            get_voice("macos_say")
    finally:
        monkeypatch.delenv("APP_ENV")
        get_settings.cache_clear()


def test_security_headers_and_login_unknown_user(client):
    r = client.get("/api/health")
    assert r.headers["x-content-type-options"] == "nosniff" and r.headers["x-frame-options"] == "DENY"
    assert client.post("/api/auth/login", json={"email": "nobody@x.y", "password": "whatever"}).status_code == 401


def test_recording_upload_rejects_non_media_and_bad_ext(client, auth_headers, db):
    from app.models import Course, Lesson, Module
    c = Course(name="UP"); m = Module(title="m"); l = Lesson(title="l"); m.lessons.append(l); c.modules.append(m); db.add(c); db.commit()
    bad_ext = client.post(f"/api/lessons/{l.id}/recordings/scene_001", files={"file": ("x.sh", b"#!/bin/sh\nrm -rf /", "text/plain")}, headers=auth_headers)
    assert bad_ext.status_code == 415
    fake = client.post(f"/api/lessons/{l.id}/recordings/scene_001", files={"file": ("x.mp4", b"not a video", "video/mp4")}, headers=auth_headers)
    assert fake.status_code == 422
    traversal = client.post(f"/api/lessons/{l.id}/recordings/..%2Fetc", files={"file": ("x.mp4", b"x", "video/mp4")}, headers=auth_headers)
    assert traversal.status_code in (404, 422)
