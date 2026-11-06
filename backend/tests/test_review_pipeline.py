"""Pipeline wiring: blocking findings stop TTS, rendering and publishing; revisions; resume; duplicates; API authorization."""
import pytest

from app.models import Approval, LessonStatus as S, QualityGateResult, ReviewFinding, ReviewRun
from app.providers.llm import LLMError
from app.services import generation, pipeline, qualitygate, renderer, techreview, youtube
from tests.helpers import ScriptedLLM, approve_for_assets, finding, good_script, make_lesson, reviewer_with


@pytest.fixture
def tts_calls(monkeypatch):
    calls = []
    monkeypatch.setattr("app.services.narration.synth_with_timing", lambda *a, **k: calls.append(a))
    return calls


def approved_lesson(db):
    l = make_lesson(db)
    approve_for_assets(db, l, reviewer_with([]))
    return l


def test_blocking_finding_prevents_tts(db, tts_calls):
    l = approved_lesson(db)
    techreview.run_review(db, l, reviewer_with([finding("critical")]))  # a later review run finds a critical error
    db.commit()
    with pytest.raises(pipeline.GateStop, match="no_unresolved_blocking_findings"):
        pipeline.run_assets(db, l)
    db.refresh(l)
    assert tts_calls == [] and l.status == S.SCRIPT_APPROVED and l.retry_count == 0  # stopped at the last good stage, no retry consumed
    assert "quality gate blocked" in l.last_error
    stored = db.query(QualityGateResult).filter_by(lesson_id=l.id, stage="pre_tts").order_by(QualityGateResult.id.desc()).first()
    assert stored and not stored.passed  # the blocking result is persisted even though the stage raised


def test_blocking_finding_prevents_rendering(db, monkeypatch):
    l = approved_lesson(db)
    techreview.run_review(db, l, reviewer_with([finding("high")]))
    pipeline.set_status(db, l, S.ASSETS_READY)
    db.commit()
    rendered = []
    monkeypatch.setattr(renderer, "render_long", lambda **k: rendered.append(1))
    with pytest.raises(pipeline.GateStop):
        pipeline.run_render(db, l)
    db.refresh(l)
    assert rendered == [] and l.status == S.ASSETS_READY


def test_blocking_finding_prevents_publishing(db):
    l = approved_lesson(db)
    pipeline.set_status(db, l, S.APPROVED)
    db.add(Approval(lesson_id=l.id, stage="video", decision="APPROVED"))
    db.commit()
    assert pipeline.is_approved(db, l)  # the video was approved by a human...
    techreview.run_review(db, l, reviewer_with([finding("high")]))
    db.commit()
    with pytest.raises(qualitygate.GateBlocked):  # ...but a high finding appeared afterwards: still no upload
        youtube.upload(db, l, {"titles": ["a", "b", "c"], "description": "", "tags": [], "chapters": [], "category_id": "27", "disclaimer": ""})


def test_publish_endpoint_returns_409_when_gate_blocks(db, client, auth_headers):
    l = approved_lesson(db)
    pipeline.set_status(db, l, S.APPROVED)
    db.add(Approval(lesson_id=l.id, stage="video", decision="APPROVED"))
    techreview.run_review(db, l, reviewer_with([finding("critical")]))
    db.commit()
    r = client.post(f"/api/lessons/{l.id}/youtube/publish", json={}, headers=auth_headers)
    assert r.status_code == 409 and "quality gate blocked" in r.json()["detail"]


def test_script_cannot_be_approved_with_blocking_finding_until_resolved(db):
    l = make_lesson(db)
    pipeline.run_technical_review(db, l, online=False, reviewer=reviewer_with([finding("high")]))
    db.refresh(l)
    assert l.status == S.TECHNICAL_REVIEW
    with pytest.raises(pipeline.StageError, match="no_unresolved_blocking_findings"):
        pipeline.approve_script(db, l, 1)
    f = db.query(ReviewFinding).filter_by(lesson_id=l.id).one()
    from app.models import User
    techreview.decide(db, f, User(id=1, email="a", password_hash="", role="admin"), "waive", "Accepted: wording is qualified in the video narration")
    pipeline.approve_script(db, l, 1)
    db.refresh(l)
    assert l.status == S.SCRIPT_APPROVED


def test_failed_review_can_be_resumed(db):
    l = make_lesson(db)
    pipeline.set_status(db, l, S.SCRIPT_GENERATED)
    db.commit()
    with pytest.raises(LLMError, match="technical review failed"):
        pipeline.run_technical_review(db, l, online=False, reviewer=ScriptedLLM(tech_review=LLMError("Ollama unreachable at http://localhost:11434")))
    db.refresh(l)
    assert l.status == S.FAILED and l.last_good_status == S.SCRIPT_GENERATED.value and "unreachable" in l.last_error
    assert techreview.latest_run(db, l.id).status == "failed"
    pipeline.resume(db, l, max_steps=1, online=False, reviewer=reviewer_with([]))
    db.refresh(l)
    assert l.status == S.TECHNICAL_REVIEW and techreview.latest_run(db, l.id).status == "completed" and l.last_error == ""


def test_duplicate_review_job_does_not_mark_lesson_failed(db):
    l = make_lesson(db)
    pipeline.set_status(db, l, S.SCRIPT_GENERATED)
    techreview.begin_run(db, l, "technical", 1, "m", False)  # another job is running
    with pytest.raises(pipeline.GateStop, match="already running"):
        pipeline.run_technical_review(db, l, online=False, reviewer=reviewer_with([]))
    db.refresh(l)
    assert l.status == S.SCRIPT_GENERATED and l.retry_count == 0


def test_review_run_endpoint_rejects_duplicates(db, client, auth_headers):
    l = make_lesson(db)
    pipeline.set_status(db, l, S.SCRIPT_GENERATED)
    techreview.begin_run(db, l, "technical", 1, "m", False)
    db.commit()
    r = client.post(f"/api/lessons/{l.id}/review/run", headers=auth_headers)
    assert r.status_code == 409 and "already running" in r.json()["detail"]


def test_review_run_endpoint_needs_a_script_stage(db, client, auth_headers):
    l = make_lesson(db)
    pipeline.set_status(db, l, S.RENDERING)
    db.commit()
    assert client.post(f"/api/lessons/{l.id}/review/run", headers=auth_headers).status_code == 409


def test_accepting_a_finding_via_api_creates_revision_and_reopens_review(db, client, auth_headers):
    l = make_lesson(db)
    pipeline.run_technical_review(db, l, online=False, reviewer=reviewer_with([finding("high", fix="no single control is sufficient on its own, so layers are required")]))
    fid = db.query(ReviewFinding).filter_by(lesson_id=l.id).one().id
    r = client.post(f"/api/review/findings/{fid}/decision", json={"decision": "accept"}, headers=auth_headers)
    assert r.status_code == 200 and r.json()["status"] == "accepted" and r.json()["applied_version"] == 2
    revs = client.get(f"/api/lessons/{l.id}/revisions", headers=auth_headers).json()
    assert [x["version"] for x in revs] == [1, 2] and "finding" in revs[1]["change_note"]
    old = client.get(f"/api/lessons/{l.id}/revisions/1", headers=auth_headers).json()["content"]
    new = client.get(f"/api/lessons/{l.id}/revisions/2", headers=auth_headers).json()["content"]
    assert old != new and "so layers are required" in new["defensive_recommendations"]
    db.expire_all()
    assert db.get(type(l), l.id).status == S.SCRIPT_GENERATED  # script changed -> must be re-reviewed
    st = client.get(f"/api/lessons/{l.id}/review", headers=auth_headers).json()
    assert st["script_version"] == 2 and st["state"]["blocked"]  # stale review of v1 does not count
    assert client.post(f"/api/review/findings/{fid}/decision", json={"decision": "reject", "note": "second decision on same finding"}, headers=auth_headers).status_code == 409


def test_reject_and_waive_need_notes_and_admin_for_high(db, client, auth_headers):
    from app.models import User
    from app.security.auth import hash_password
    l = make_lesson(db)
    pipeline.run_technical_review(db, l, online=False, reviewer=reviewer_with([finding("high"), finding("medium", text="Allow-list input validation as a secondary control")]))
    db.add(User(email="rev@test.local", password_hash=hash_password("pw-rev-12345"), role="reviewer"))
    db.commit()
    tok = client.post("/api/auth/login", json={"email": "rev@test.local", "password": "pw-rev-12345"}).json()["access_token"]
    rev = {"Authorization": f"Bearer {tok}"}
    hi, med = [f.id for f in sorted(db.query(ReviewFinding).filter_by(lesson_id=l.id), key=lambda f: f.severity)]
    assert client.post(f"/api/review/findings/{hi}/decision", json={"decision": "waive", "note": "x"}, headers=auth_headers).status_code == 409  # note too short
    assert client.post(f"/api/review/findings/{hi}/decision", json={"decision": "waive", "note": "I accept this risk, reviewed by reviewer"}, headers=rev).status_code == 409  # high: admin only
    assert client.post(f"/api/review/findings/{hi}/decision", json={"decision": "waive", "note": "Course owner accepts: qualified in narration"}, headers=auth_headers).status_code == 200
    assert client.post(f"/api/review/findings/{med}/decision", json={"decision": "reject", "note": "Already qualified in the previous sentence"}, headers=rev).status_code == 200


def test_endpoints_require_authentication_and_humans(db, client, auth_headers):
    l = make_lesson(db)
    pipeline.run_technical_review(db, l, online=False, reviewer=reviewer_with([finding("medium")]))
    fid = db.query(ReviewFinding).filter_by(lesson_id=l.id).one().id
    for method, path in [("get", f"/api/lessons/{l.id}/review"), ("get", f"/api/lessons/{l.id}/claims"), ("get", f"/api/lessons/{l.id}/gate"),
                         ("post", f"/api/lessons/{l.id}/review/run"), ("post", f"/api/review/findings/{fid}/decision")]:
        assert getattr(client, method)(path).status_code == 401, path
    svc = {"Authorization": "Bearer svc-token-for-tests"}  # n8n token: may read, may not decide
    assert client.get(f"/api/lessons/{l.id}/review", headers=svc).status_code == 200
    assert client.post(f"/api/review/findings/{fid}/decision", json={"decision": "reject", "note": "service accounts cannot decide"}, headers=svc).status_code == 403
    assert client.post("/api/review/claims/1/decision", json={"decision": "accepted", "note": "service accounts cannot decide"}, headers=svc).status_code == 403


def test_read_endpoints_expose_claims_sources_and_gate(db, client, auth_headers):
    l = make_lesson(db)
    pipeline.run_technical_review(db, l, online=False, reviewer=reviewer_with([]))
    claims = client.get(f"/api/lessons/{l.id}/claims", headers=auth_headers).json()
    assert claims and claims[0]["status"] == "supported" and claims[0]["sources"][0]["publisher"] == "OWASP" and claims[0]["evidence_excerpt"]
    sid = claims[0]["sources"][0]["id"]
    txt = client.get(f"/api/lessons/{l.id}/sources/{sid}/text", headers=auth_headers).json()
    assert any(h == "Primary Defenses" for h, _ in txt["sections"])
    assert client.get(f"/api/lessons/{l.id}/sources/99999/text", headers=auth_headers).status_code == 404
    g = client.get(f"/api/lessons/{l.id}/gate", headers=auth_headers).json()
    assert g["script"]["passed"] and g["pre_tts"] is None
    detail = client.get(f"/api/lessons/{l.id}", headers=auth_headers).json()
    assert detail["review"]["state"] in ("passed", "human_review_required", "approved_for_rendering") and detail["sources"][0]["status"] == "ok"
    ev = client.post(f"/api/lessons/{l.id}/gate/evaluate?stage=pre_tts", headers=auth_headers).json()
    assert not ev["passed"]  # no human approval yet
    assert client.post(f"/api/lessons/{l.id}/gate/evaluate?stage=bogus", headers=auth_headers).status_code == 422


def test_claim_acceptance_via_api_unblocks_gate(db, client, auth_headers):
    l = make_lesson(db)
    pipeline.run_technical_review(db, l, online=False, reviewer=reviewer_with([], claim_quote="A quote that is nowhere in the retrieved sources at all."))
    cl = client.get(f"/api/lessons/{l.id}/claims", headers=auth_headers).json()[0]
    assert cl["blocks"] and cl["status"] == "needs_human_review"
    assert client.post(f"/api/review/claims/{cl['id']}/decision", json={"decision": "accepted", "note": "x"}, headers=auth_headers).status_code == 422
    r = client.post(f"/api/review/claims/{cl['id']}/decision", json={"decision": "accepted", "note": "Verified manually against the OWASP page"}, headers=auth_headers)
    assert r.status_code == 200 and not r.json()["blocks"]


def test_rerun_after_import_uses_new_script(db, client, auth_headers):
    l = make_lesson(db)
    pipeline.run_technical_review(db, l, online=False, reviewer=reviewer_with([]))
    s = good_script()
    s["hook"] = "A brand new hook that changes the first minute of the lesson completely and honestly."
    assert client.post(f"/api/lessons/{l.id}/script/import", json=s, headers=auth_headers).status_code == 200
    db.expire_all()
    l = db.get(type(l), l.id)
    assert l.status == S.SCRIPT_GENERATED  # imported edit invalidates the review
    llm = reviewer_with([])
    pipeline.run_technical_review(db, l, online=False, reviewer=llm)
    assert any("brand new hook" in p for t, p in llm.calls if t == "tech_review")
    assert techreview.latest_run(db, l.id).script_version == 2


def test_mock_pipeline_is_labelled_simulated(db):
    l = make_lesson(db, generated_by="mock")
    pipeline.run_technical_review(db, l, online=False)  # default reviewer = configured (mock) provider
    r = techreview.latest_run(db, l.id)
    assert r.simulated and r.summary["simulated"] is True
