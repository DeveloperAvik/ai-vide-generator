"""Regression tests for the 2026-10-31 failures of lessons 78/79: four concurrent script jobs (2 per lesson) hit one Ollama; Ollama served
them one at a time, the later requests sat in its queue and the 600 s HTTP read timeout expired on requests that had not even started.
The app then reported 'Ollama unreachable' although Ollama was up."""
import threading
import time

import httpx
import pytest

from app.api import routes
from app.providers import llm as llm_mod
from app.providers.llm import LLMError, OllamaProvider


class Resp:
    status_code = 200

    def json(self):
        return {"message": {"content": "{}"}, "prompt_eval_count": 1, "eval_count": 1}


@pytest.fixture
def no_sleep(monkeypatch):
    sleeps = []
    monkeypatch.setattr(llm_mod.time, "sleep", lambda s: sleeps.append(s))
    return sleeps


def _ollama():
    return OllamaProvider("http://localhost:11434", "m")


def test_read_timeout_is_reported_as_slow_not_unreachable_and_not_retried(monkeypatch, no_sleep):
    calls = []

    def post(url, **kw):
        calls.append(kw)
        raise httpx.ReadTimeout("timed out")
    monkeypatch.setattr(httpx, "post", post)
    with pytest.raises(LLMError) as e:
        _ollama().complete("s", "p")
    assert "reachable but gave no answer" in str(e.value) and "unreachable" not in str(e.value)
    assert len(calls) == 1 and no_sleep == []  # a 10-minute timeout is never silently repeated


def test_timeouts_are_split_and_configurable(monkeypatch):
    seen = {}
    monkeypatch.setattr(httpx, "post", lambda url, **kw: seen.update(kw) or Resp())
    p = _ollama()
    p.complete("s", "p")
    t = seen["timeout"]
    assert t.connect == 10 and t.read == 900 and p.timeout == 900
    p.timeout = 77  # get_reviewer() still overrides it per call
    p.complete("s", "p")
    assert seen["timeout"].read == 77


def test_connect_failure_is_retried_with_bounded_exponential_backoff(monkeypatch, no_sleep):
    n = []

    def post(url, **kw):
        n.append(1)
        raise httpx.ConnectError("refused")
    monkeypatch.setattr(httpx, "post", post)
    with pytest.raises(LLMError, match="unreachable.*cannot connect after 3 attempts"):
        _ollama().complete("s", "p")
    assert len(n) == 3 and len(no_sleep) == 2 and 2 <= no_sleep[0] <= 3 and 4 <= no_sleep[1] <= 5


def test_recovers_when_ollama_comes_back_during_backoff(monkeypatch, no_sleep):
    state = {"n": 0}

    def post(url, **kw):
        state["n"] += 1
        if state["n"] < 3:
            raise httpx.ConnectError("refused")
        return Resp()
    monkeypatch.setattr(httpx, "post", post)
    assert _ollama().complete("s", "p") == "{}" and state["n"] == 3


def test_only_one_ollama_generation_runs_at_a_time(monkeypatch):
    active, peak = [0], [0]
    guard = threading.Lock()

    def post(url, **kw):
        with guard:
            active[0] += 1
            peak[0] = max(peak[0], active[0])
        time.sleep(0.05)
        with guard:
            active[0] -= 1
        return Resp()
    monkeypatch.setattr(httpx, "post", post)
    ts = [threading.Thread(target=lambda: _ollama().complete("s", "p")) for _ in range(4)]  # 2 lessons x 2 jobs, as on 2026-10-31
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert peak[0] == 1


def test_queue_wait_is_bounded_and_reports_busy_without_sending(monkeypatch):
    from app.core.config import get_settings
    monkeypatch.setattr(get_settings(), "ollama_queue_wait_s", 0.1)
    sent = []
    monkeypatch.setattr(httpx, "post", lambda *a, **k: sent.append(1) or Resp())
    assert llm_mod._OLLAMA_LOCK.acquire(timeout=1)
    try:
        with pytest.raises(LLMError, match="busy"):
            _ollama().complete("s", "p")
    finally:
        llm_mod._OLLAMA_LOCK.release()
    assert sent == []


def test_lock_is_released_after_a_failure(monkeypatch, no_sleep):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: (_ for _ in ()).throw(httpx.ReadTimeout("t")))
    with pytest.raises(LLMError):
        _ollama().complete("s", "p")
    assert llm_mod._OLLAMA_LOCK.acquire(timeout=1)
    llm_mod._OLLAMA_LOCK.release()


# ---------------------------------------------------------------- one live job per lesson
def test_second_job_for_the_same_lesson_is_not_started():
    release, ran = threading.Event(), []
    routes._RUNNING.clear()
    first = routes._bg(lambda d, ls, **k: (ran.append("first"), release.wait(5)), 999_001)
    second = routes._bg(lambda d, ls, **k: ran.append("second"), 999_001)
    other = routes._bg(lambda d, ls, **k: ran.append("other"), 999_002)  # a different lesson is not blocked here
    release.set()
    for _ in range(100):
        if not routes._running(999_001) and not routes._running(999_002):
            break
        time.sleep(0.02)
    assert (first, second, other) == (True, False, True)
    assert "second" not in ran and not routes._RUNNING
    assert routes._bg(lambda d, ls, **k: ran.append("again"), 999_001)  # allowed once the first finished
    time.sleep(0.2)


def test_run_retry_and_stage_endpoints_refuse_a_duplicate_job(db, client, auth_headers):
    from tests.helpers import make_lesson
    from app.models import LessonStatus as S
    l = make_lesson(db)
    l.status = S.FAILED
    l.last_good_status = S.RESEARCHING.value
    db.commit()
    routes._RUNNING.clear()
    routes._RUNNING.add(l.id)  # a live job exists for this lesson
    try:
        assert client.post(f"/api/lessons/{l.id}/retry", headers=auth_headers).status_code == 409
        assert client.post(f"/api/lessons/{l.id}/stage/script", headers=auth_headers).status_code == 409
        r = client.post(f"/api/lessons/{l.id}/run", headers=auth_headers)
        assert r.status_code == 200 and r.json()["status"] == "already_running"  # idempotent for the double click
    finally:
        routes._RUNNING.clear()


def test_retry_at_the_cap_is_refused_loudly_not_silently(db, client, auth_headers):
    """Lesson 78 had used 3 of 3 retries; Retry returned 'retrying' but the job died unseen and the lesson stayed FAILED."""
    from tests.helpers import make_lesson
    from app.models import LessonStatus as S
    from app.services import pipeline
    l = make_lesson(db)
    l.status, l.last_good_status, l.retry_count = S.FAILED, S.RESEARCHING.value, pipeline.MAX_RETRIES
    db.commit()
    routes._RUNNING.clear()
    r = client.post(f"/api/lessons/{l.id}/retry", headers=auth_headers)
    assert r.status_code == 409 and "reset the retry counter" in r.text
    db.refresh(l)
    assert l.status == S.FAILED and l.retry_count == pipeline.MAX_RETRIES  # nothing consumed, nothing hidden


def test_a_crashing_background_job_is_logged_not_swallowed(db):
    from tests.helpers import make_lesson
    from app.models import WorkflowLog
    l = make_lesson(db)
    routes._RUNNING.clear()

    def boom(d, ls, **k):
        raise RuntimeError("exceeded retries")
    assert routes._bg(boom, l.id)
    for _ in range(100):
        if not routes._running(l.id):
            break
        time.sleep(0.02)
    db.expire_all()
    row = db.query(WorkflowLog).filter(WorkflowLog.lesson_id == l.id, WorkflowLog.stage == "job", WorkflowLog.level == "error").first()
    assert row and "exceeded retries" in row.message


def test_repeat_limit_500_is_retried_with_a_repeat_penalty(monkeypatch):
    class Loop:
        status_code, text = 500, '{"error":"prediction aborted, token repeat limit reached"}'
    seen = []

    def post(url, **kw):
        seen.append(kw["json"]["options"])
        return Loop() if len(seen) < 3 else Resp()
    monkeypatch.setattr(httpx, "post", post)
    _ollama().complete("s", "p")
    assert len(seen) == 3 and "repeat_penalty" not in seen[0] and seen[2]["repeat_penalty"] > seen[1]["repeat_penalty"] > 1


def test_repeat_limit_gives_up_after_three_tries(monkeypatch):
    class Loop:
        status_code, text = 500, '{"error":"prediction aborted, token repeat limit reached"}'
    n = []
    monkeypatch.setattr(httpx, "post", lambda url, **kw: n.append(1) or Loop())
    with pytest.raises(LLMError, match="repeat limit"):
        _ollama().complete("s", "p")
    assert len(n) == 3


def test_restart_makes_orphaned_working_lessons_retryable(db):
    from app.core.db import SessionLocal
    from app.main import app, lifespan
    from app.models import Lesson, LessonStatus as S
    import asyncio
    from tests.helpers import make_lesson
    l, ok = make_lesson(db), make_lesson(db)
    l.status, l.last_good_status = S.ASSETS_GENERATING, S.SCRIPT_APPROVED.value
    ok.status, ok.last_good_status = S.APPROVAL_PENDING, S.APPROVAL_PENDING.value
    db.commit()

    async def boot():
        async with lifespan(app):
            pass
    asyncio.run(boot())
    db.expire_all()
    assert db.get(Lesson, l.id).status == S.FAILED and db.get(Lesson, l.id).retry_count == 0
    assert db.get(Lesson, l.id).last_good_status == S.SCRIPT_APPROVED.value
    assert db.get(Lesson, ok.id).status == S.APPROVAL_PENDING
