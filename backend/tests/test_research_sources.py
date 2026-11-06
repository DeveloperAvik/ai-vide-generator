"""Feature A: source retrieval, provenance, SSRF controls, limits."""
import httpx
import pytest

from app.core.config import get_settings
from app.models import Lesson, ResearchSource
from app.services import research
from tests.helpers import make_lesson

URL = "https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html"
PAGE = ("<html><head><title>SQL Injection Prevention - OWASP Cheat Sheet Series</title>"
        '<meta property="article:modified_time" content="2024-05-01T10:00:00Z"></head><body><nav>menu menu menu</nav>'
        "<h1>Introduction</h1><p>" + "SQL injection occurs when untrusted data is sent to an interpreter as part of a query. " * 4 + "</p>"
        "<h2>Primary Defenses</h2><p>" + "Use parameterized queries so that the database can always distinguish code from data. " * 3 + "</p>"
        "<script>evil()</script></body></html>")


@pytest.fixture
def net(monkeypatch):
    """Route all research HTTP through a handler; DNS resolves to a public address unless a test overrides _resolve."""
    state = {"calls": [], "handler": lambda req: httpx.Response(200, headers={"content-type": "text/html"}, text=PAGE)}

    def handler(req):
        state["calls"].append(str(req.url))
        if req.url.path == "/robots.txt":
            return state.get("robots", httpx.Response(404))
        return state["handler"](req)
    monkeypatch.setattr(research, "_client", lambda: httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False))
    monkeypatch.setattr(research, "_resolve", lambda h: ["93.184.216.34"])
    research._ROBOTS.clear()
    return state


def test_valid_official_source_keeps_provenance(net):
    r = research.fetch_source(URL, "sql injection parameterized queries")
    assert r["verified"] and r["status"] == "ok"
    assert r["publisher"] == "OWASP" and r["category"] == "owasp"
    assert r["title"].startswith("SQL Injection Prevention")
    assert r["published_at"].startswith("2024-05-01")
    assert len(r["content_hash"]) == 64 and "menu menu" not in r["full_text"] and "evil()" not in r["full_text"]
    assert r["section"] and "## Primary Defenses" in r["full_text"]


@pytest.mark.parametrize("url,why", [("http://owasp.org/x", "https"), ("https://evil.example/x", "allow-list"), ("javascript:alert(1)", "https"),
                                     ("https://127.0.0.1/x", "IP-literal"), ("https://169.254.169.254/latest/meta-data", "IP-literal"), ("https://[::1]/x", "IP-literal")])
def test_invalid_urls_are_never_fetched(net, url, why):
    r = research.fetch(url)
    assert r.status == "blocked_host" and why in r.detail and net["calls"] == []


def test_host_resolving_to_private_address_is_blocked(net, monkeypatch):
    monkeypatch.setattr(research, "_resolve", lambda h: ["10.0.0.5"])
    r = research.fetch(URL)
    assert r.status == "blocked_host" and "non-public" in r.detail and net["calls"] == []


def test_redirect_to_private_ip_is_blocked_and_never_requested(net):
    net["handler"] = lambda req: httpx.Response(302, headers={"location": "https://169.254.169.254/latest/meta-data"})
    r = research.fetch(URL)
    assert r.status == "blocked_redirect" and not any("169.254" in c for c in net["calls"])


def test_redirect_to_allowed_host_that_resolves_private_is_blocked(net, monkeypatch):
    net["handler"] = lambda req: httpx.Response(302, headers={"location": "https://owasp.org/rebound"})
    monkeypatch.setattr(research, "_resolve", lambda h: ["93.184.216.34"] if h == "cheatsheetseries.owasp.org" else ["192.168.1.9"])
    r = research.fetch(URL)
    assert r.status == "blocked_redirect" and "non-public" in r.detail and not any("owasp.org/rebound" in c for c in net["calls"])


def test_redirect_to_allowed_public_host_is_followed(net):
    def h(req):
        return httpx.Response(302, headers={"location": "https://owasp.org/moved"}) if req.url.host != "owasp.org" else httpx.Response(200, headers={"content-type": "text/html"}, text=PAGE)
    net["handler"] = h
    assert research.fetch(URL).status == "ok"


def test_http_failure(net):
    net["handler"] = lambda req: httpx.Response(503)
    r = research.fetch_source(URL)
    assert r["status"] == "http_error" and not r["verified"] and "503" in r["detail"]


def test_timeout(net):
    def boom(req):
        raise httpx.ReadTimeout("slow", request=req)
    net["handler"] = boom
    r = research.fetch_source(URL)
    assert r["status"] == "timeout" and not r["verified"]


def test_oversized_response_streamed_cap(net, monkeypatch):
    monkeypatch.setattr(get_settings(), "research_max_bytes", 5000)
    net["handler"] = lambda req: httpx.Response(200, headers={"content-type": "text/html"}, content=b"<p>" + b"a" * 20000 + b"</p>")
    assert research.fetch_source(URL)["status"] == "too_large"


def test_oversized_declared_content_length(net, monkeypatch):
    monkeypatch.setattr(get_settings(), "research_max_bytes", 5000)
    net["handler"] = lambda req: httpx.Response(200, headers={"content-type": "text/html", "content-length": "999999"}, content=b"x")
    r = research.fetch(URL)
    assert r.status == "too_large" and "declared" in r.detail


def test_unsupported_content_type(net):
    net["handler"] = lambda req: httpx.Response(200, headers={"content-type": "application/pdf"}, content=b"%PDF-1.4")
    assert research.fetch_source(URL)["status"] == "unsupported_content"


def test_http_200_alone_is_not_enough(net):
    net["handler"] = lambda req: httpx.Response(200, headers={"content-type": "text/html"}, text="<html><title>Not Found</title><body>Sorry.</body></html>")
    r = research.fetch_source(URL)
    assert r["status"] == "empty_content" and not r["verified"]
    net["handler"] = lambda req: httpx.Response(200, headers={"content-type": "text/html"}, text="<html><title>Page</title><body>" + "word " * 100 + "</body></html>")
    assert research.fetch_source(URL)["verified"]  # non-trivial text, plain title: accepted


def test_missing_metadata_is_stored_blank_not_invented(net):
    net["handler"] = lambda req: httpx.Response(200, headers={"content-type": "text/html"}, text="<html><body><p>" + "plain article text about injection. " * 20 + "</p></body></html>")
    r = research.fetch_source(URL)
    assert r["verified"] and r["title"] == "" and r["published_at"] == ""
    net["handler"] = lambda req: httpx.Response(200, headers={"content-type": "text/html", "last-modified": "Wed, 01 May 2024 10:00:00 GMT"}, text="<p>" + "text about injection. " * 30 + "</p>")
    assert research.fetch_source(URL)["published_at"].startswith("Wed, 01 May 2024")


def test_robots_txt_disallow_is_respected(net):
    net["robots"] = httpx.Response(200, text="User-agent: *\nDisallow: /cheatsheets/\n")
    r = research.fetch(URL)
    assert r.status == "blocked_robots" and not any("Cheat_Sheet" in c for c in net["calls"])


def test_collect_stores_provenance_and_dedupes(net, db):
    l = make_lesson(db, source=False, storyboard=False)
    first = research.collect(db, l, [URL, URL + "#primary-defenses", URL])
    db.commit()
    rows = db.query(ResearchSource).filter_by(lesson_id=l.id, url=URL).all()
    assert len(rows) == 1 and rows[0].verified and rows[0].publisher == "OWASP" and rows[0].content_hash and rows[0].status == "ok"
    assert len([s for s in first if s.url.startswith(URL)]) == 1  # fragment variants and repeats are the same source
    assert research.collect(db, l, [URL]) == []  # second run adds nothing


def test_collect_failed_source_is_stored_unverified(net, db):
    net["handler"] = lambda req: httpx.Response(404)
    l = make_lesson(db, source=False, storyboard=False)
    research.collect(db, l, [URL])
    db.commit()
    s = db.query(ResearchSource).filter_by(lesson_id=l.id, url=URL).one()
    assert not s.verified and s.status == "http_error" and s.full_text == ""


def test_best_sections_picks_relevant_part():
    secs = [("Intro", "history of the web and browsers " * 5), ("Primary Defenses", "parameterized queries separate code from data " * 5)]
    assert research.best_sections(secs, "parameterized queries", k=1)[0][0] == "Primary Defenses"
    assert research.parse_sections(research.sections_to_text(secs)) == [(h, " ".join([t])) for h, t in secs]
