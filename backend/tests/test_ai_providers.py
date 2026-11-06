import json

import httpx
import pytest

from app.providers.llm import AnthropicProvider, FallbackProvider, LLMError, OllamaProvider
from app.providers.mock_llm import _curriculum
from app.schemas.content import Curriculum, CurriculumRequest
from app.services import generation


class Resp:
    def __init__(self, code, data):
        self.status_code, self._d, self.text = code, data, json.dumps(data)

    def json(self):
        return self._d


def test_anthropic_forced_tool_call_returns_structured_json(monkeypatch):
    seen = {}

    def fake_post(url, **kw):
        seen.update(url=url, **kw)
        return Resp(200, {"content": [{"type": "tool_use", "name": "emit", "input": _curriculum("X", 8)}]})

    monkeypatch.setattr(httpx, "post", fake_post)
    schema = Curriculum.model_json_schema()
    out = AnthropicProvider("sk-ant-test", "claude-sonnet-5-5").complete_json("sys", "p", schema=schema)
    Curriculum.model_validate(out)
    body = seen["json"]
    assert seen["url"] == "https://api.anthropic.com/v1/messages" and seen["headers"]["x-api-key"] == "sk-ant-test"
    assert body["tool_choice"] == {"type": "tool", "name": "emit"} and body["tools"][0]["input_schema"] == schema
    assert body["model"] == "claude-sonnet-5-5"


def test_anthropic_error_surfaces(monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: Resp(401, {"error": "invalid x-api-key"}))
    with pytest.raises(LLMError, match="401"):
        AnthropicProvider("bad", "m").complete_json("s", "p", schema={"type": "object"})


def test_ollama_sends_schema_as_format(monkeypatch):
    seen = {}

    def fake_post(url, **kw):
        seen.update(kw)
        return Resp(200, {"message": {"content": json.dumps(_curriculum("X", 8))}})

    monkeypatch.setattr(httpx, "post", fake_post)
    schema = Curriculum.model_json_schema()
    out = OllamaProvider("http://localhost:11434", "llama3.1").complete_json("s", "p", schema=schema)
    assert seen["json"]["format"] == schema and seen["json"]["stream"] is False
    Curriculum.model_validate(out)


def test_ollama_unreachable_is_llmerror(monkeypatch):
    def boom(*a, **k):
        raise httpx.ConnectError("refused")
    monkeypatch.setattr(httpx, "post", boom)
    monkeypatch.setattr("app.providers.llm.time.sleep", lambda s: None)  # connect failures are retried with backoff; do not really wait
    with pytest.raises(LLMError, match="unreachable"):
        OllamaProvider("http://localhost:11434", "m").complete_json("s", "p")


def test_fallback_anthropic_to_ollama(monkeypatch):
    def fake_post(url, **kw):
        if "anthropic" in url:
            return Resp(529, {"error": "overloaded"})
        return Resp(200, {"message": {"content": json.dumps(_curriculum("X", 8))}})

    monkeypatch.setattr(httpx, "post", fake_post)
    llm = FallbackProvider(AnthropicProvider("k", "m"), OllamaProvider("http://localhost:11434", "m"))
    Curriculum.model_validate(llm.complete_json("s", "p", schema={"type": "object"}))
    assert llm.name == "ollama"


def test_invalid_model_output_retried_then_rejected(db, monkeypatch):
    calls = {"n": 0}

    class Bad(AnthropicProvider):
        def complete_json(self, system, prompt, max_tokens=8000, schema=None):
            calls["n"] += 1
            return {"description": "no modules"}

    with pytest.raises(LLMError, match="schema validation"):
        generation.generate_curriculum(db, CurriculumRequest(course_name="Bad Output Course"), Bad("k", "m"))
    assert calls["n"] == 2  # one retry with the validation error fed back
    from app.models import Course
    assert db.query(Course).count() == 0  # nothing malformed persisted


def test_youtube_oauth_start_with_dummy_client(tmp_path, monkeypatch, client, auth_headers):
    secrets = tmp_path / "client.json"
    secrets.write_text(json.dumps({"web": {"client_id": "x.apps.googleusercontent.com", "client_secret": "s", "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                                           "token_uri": "https://oauth2.googleapis.com/token", "redirect_uris": ["http://localhost:8000/api/youtube/oauth/callback"]}}))
    from app.core.config import get_settings
    monkeypatch.setattr(get_settings(), "youtube_client_secrets", str(secrets))
    r = client.get("/api/youtube/oauth/start", headers=auth_headers)
    assert r.status_code == 200
    url = r.json()["authorization_url"]
    assert url.startswith("https://accounts.google.com/") and "youtube.upload" in url and "access_type=offline" in url
