"""LLM provider abstraction.

MODE A (manual Claude Pro): use `ai/prompts/*.md` by hand in claude.ai, paste JSON into the dashboard
                            (POST /api/lessons/{id}/script/import) - no API credentials involved.
MODE B (automated): LLM_PROVIDER=anthropic (needs a *developer API key*, separate from Claude Pro) or ollama.
`mock` is an offline template generator for demos/tests; it never claims to be a real model.
"""
import json
import random
import re
import threading
import time
from abc import ABC, abstractmethod
from pathlib import Path

import httpx

from app.core.config import get_settings


class LLMError(RuntimeError):
    pass


class LLMProvider(ABC):
    name = "base"

    @abstractmethod
    def complete(self, system: str, prompt: str, max_tokens: int = 8000) -> str: ...

    def complete_text(self, system: str, prompt: str, max_tokens: int = 1500) -> str:
        """Free-form prose (no JSON constraint). Small models write longer, better prose this way than inside a JSON field."""
        return self.complete(system, prompt, max_tokens)

    def complete_json(self, system: str, prompt: str, max_tokens: int = 8000, schema: dict | None = None) -> dict:
        raw = self.complete(system, prompt + "\n\nRespond with a single valid JSON object only. No prose, no code fences.", max_tokens)
        return extract_json(raw)


def extract_json(raw: str) -> dict:
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(raw[start:end + 1])
            except json.JSONDecodeError as e:
                raise LLMError(f"LLM returned malformed JSON: {e}") from e
        raise LLMError("LLM returned no JSON object")


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, api_key: str, model: str):
        if not api_key:
            raise LLMError("ANTHROPIC_API_KEY not set. A Claude Pro subscription is NOT an API key; create one at console.anthropic.com.")
        self.key, self.model = api_key, model

    def complete(self, system: str, prompt: str, max_tokens: int = 8000) -> str:
        r = httpx.post("https://api.anthropic.com/v1/messages", timeout=180,
                       headers={"x-api-key": self.key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                       json={"model": self.model, "max_tokens": max_tokens, "system": system,
                             "messages": [{"role": "user", "content": prompt}]})
        if r.status_code != 200:
            raise LLMError(f"Anthropic API error {r.status_code}: {r.text[:300]}")
        return "".join(b.get("text", "") for b in r.json()["content"])


    def complete_json(self, system, prompt, max_tokens=8000, schema=None):
        """Forced tool call: the API returns arguments already parsed as JSON conforming to `schema`."""
        if not schema:
            return super().complete_json(system, prompt, max_tokens)
        r = httpx.post("https://api.anthropic.com/v1/messages", timeout=300,
                       headers={"x-api-key": self.key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                       json={"model": self.model, "max_tokens": max_tokens, "system": system,
                             "tools": [{"name": "emit", "description": "Return the result object.", "input_schema": schema}],
                             "tool_choice": {"type": "tool", "name": "emit"},
                             "messages": [{"role": "user", "content": prompt}]})
        if r.status_code != 200:
            raise LLMError(f"Anthropic API error {r.status_code}: {r.text[:300]}")
        for b in r.json().get("content", []):
            if b.get("type") == "tool_use" and isinstance(b.get("input"), dict):
                return b["input"]
        raise LLMError("Anthropic returned no tool_use block")


# One local model serves one request at a time. Without this lock, concurrent stages (or two jobs on one lesson) all POST at once, the
# later ones wait inside Ollama's queue, and their HTTP read timeout expires while they were never even started.
_OLLAMA_LOCK = threading.Lock()


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(self, url: str, model: str):
        s = get_settings()
        self.url, self.model = url.rstrip("/"), model
        self.timeout = s.ollama_timeout_s
        self.usage = {"calls": 0, "prompt_tokens": 0, "output_tokens": 0}

    schema: dict | None = None
    usage = {"calls": 0, "prompt_tokens": 0, "output_tokens": 0}  # replaced per instance in __init__

    def complete_json(self, system, prompt, max_tokens=8000, schema=None):
        self.schema = schema  # Ollama supports a JSON schema in `format`
        try:
            return super().complete_json(system, prompt, max_tokens)
        finally:
            self.schema = None

    plain = False

    def complete_text(self, system: str, prompt: str, max_tokens: int = 1500) -> str:
        self.plain = True
        try:
            return self.complete(system, prompt, max_tokens)
        finally:
            self.plain = False

    def _post(self, payload: dict) -> httpx.Response:
        s = get_settings()
        timeout = httpx.Timeout(self.timeout, connect=s.ollama_connect_timeout_s)
        for attempt in range(s.ollama_connect_retries + 1):
            try:
                return httpx.post(f"{self.url}/api/chat", timeout=timeout, json=payload)
            except (httpx.ConnectError, httpx.ConnectTimeout, httpx.RemoteProtocolError) as e:  # nothing was sent, or the server dropped us before any reply (Ollama restarting/unloading): safe to retry, bounded
                if attempt < s.ollama_connect_retries:
                    time.sleep(2 ** (attempt + 1) + random.uniform(0, 1))
                    continue
                raise LLMError(f"Ollama unreachable at {self.url}: cannot connect after {attempt + 1} attempts ({e})") from e
            except httpx.TimeoutException as e:  # connected, request sent, no answer in time: Ollama IS reachable
                raise LLMError(f"Ollama at {self.url} is reachable but gave no answer within {self.timeout} s "
                               f"({type(e).__name__}): the model is loading, busy or too slow for this prompt") from e
            except httpx.HTTPError as e:
                raise LLMError(f"Ollama unreachable at {self.url}: {e}") from e
        raise AssertionError("unreachable")  # pragma: no cover

    def complete(self, system: str, prompt: str, max_tokens: int = 8000) -> str:
        wait = get_settings().ollama_queue_wait_s
        if not _OLLAMA_LOCK.acquire(timeout=wait):
            raise LLMError(f"Ollama is busy: another generation in this process held the model for more than {wait} s; this request was not sent")
        try:
            for attempt in range(3):  # "token repeat limit reached" = the model looped; resampling with a repeat penalty normally clears it
                r = self._post({
                    "model": self.model, "stream": False, **({} if self.plain else {"format": self.schema or "json"}),
                    "options": {"num_predict": max_tokens, "num_ctx": 8192, "temperature": 0.4 + 0.2 * attempt,
                                **({"repeat_penalty": 1.1 + 0.05 * attempt} if attempt else {})}, "keep_alive": "10m",
                    "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}]})
                if not (r.status_code == 500 and "repeat limit" in r.text):
                    break
        finally:
            _OLLAMA_LOCK.release()
        if r.status_code == 404:
            raise LLMError(f"Ollama model '{self.model}' is not installed. Run: ollama pull {self.model}")
        if r.status_code != 200:
            raise LLMError(f"Ollama error {r.status_code}: {r.text[:300]}")
        body = r.json()
        if body.get("done_reason") == "length":  # hit num_predict / context: the answer is cut off, never use it
            raise LLMError(f"Ollama response truncated (hit the {max_tokens}-token limit)")
        self.usage["calls"] += 1
        self.usage["prompt_tokens"] += body.get("prompt_eval_count", 0)
        self.usage["output_tokens"] += body.get("eval_count", 0)
        return body["message"]["content"]


class FallbackProvider(LLMProvider):
    """Primary provider with automatic fallback (e.g. Anthropic -> Ollama) on LLMError."""

    def __init__(self, primary: LLMProvider, fallback: LLMProvider):
        self.primary, self.fallback = primary, fallback
        self.name = f"{primary.name}->{fallback.name}"

    def complete(self, system, prompt, max_tokens=8000):
        try:
            return self.primary.complete(system, prompt, max_tokens)
        except LLMError:
            return self.fallback.complete(system, prompt, max_tokens)

    def complete_json(self, system, prompt, max_tokens=8000, schema=None):
        try:
            return self.primary.complete_json(system, prompt, max_tokens, schema)
        except LLMError:
            self.name = self.fallback.name
            return self.fallback.complete_json(system, prompt, max_tokens, schema)


def load_prompt(name: str) -> str:
    return (get_settings().ai_dir / "prompts" / f"{name}.md").read_text()


def _build(p: str) -> LLMProvider:
    s = get_settings()
    p = p.lower()
    if p == "anthropic":
        return AnthropicProvider(s.anthropic_api_key, s.anthropic_model)
    if p == "ollama":
        return OllamaProvider(s.ollama_url, s.ollama_model)
    if p == "mock":
        if s.app_env == "production":
            raise LLMError("mock LLM is disabled when APP_ENV=production; configure anthropic or ollama (Settings -> AI providers)")
        from .mock_llm import MockLLM
        return MockLLM()
    raise LLMError(f"Unknown LLM provider '{p}'. Use mock | ollama | anthropic.")


def get_llm(provider: str | None = None) -> LLMProvider:
    s = get_settings()
    primary = _build(provider or s.llm_provider)
    fb = s.llm_fallback_provider
    if fb and not provider and fb != s.llm_provider:
        try:
            return FallbackProvider(primary, _build(fb))
        except LLMError:
            return primary
    return primary


def get_reviewer() -> LLMProvider:
    """LLM for the independent technical review. REVIEWER_MODEL (Ollama) picks a different local model than the writer;
    empty = the writer's provider/model, which then reviews sequentially after generation. Never downloads a model."""
    s = get_settings()
    if s.reviewer_model and s.llm_provider.lower() == "ollama":
        r = OllamaProvider(s.ollama_url, s.reviewer_model)
        r.timeout = s.reviewer_timeout_s
        return r
    llm = get_llm()
    if isinstance(llm, OllamaProvider):
        llm.timeout = s.reviewer_timeout_s
    return llm
