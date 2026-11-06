"""Research layer (Feature A). Every source keeps provenance: publisher, category, retrieval date, content hash,
extracted text with section headings and a retrieval status. Nothing is invented: a page that cannot be fetched,
is too big, blocked by robots.txt or has no real content is stored with its failure status and verified=False.

Safety: https only, host allow-list, DNS resolved and checked against private/loopback/link-local/metadata ranges,
every redirect hop re-validated, request timeout, streamed response-size cap, robots.txt honoured.
Known limit: the HTTP client resolves DNS again when connecting, so a hostile DNS server could rebind between our
check and the connection; the allow-list of official hosts is the primary control and the IP check is defence in depth."""
import hashlib
import json
import ipaddress
import re
import socket
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from urllib.parse import urldefrag, urlparse
from urllib.robotparser import RobotFileParser

import httpx
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Lesson, ResearchSource, now

# host -> (publisher, category)
OFFICIAL_HOSTS = {
    "owasp.org": ("OWASP", "owasp"), "top10.owasp.org": ("OWASP", "owasp"), "cheatsheetseries.owasp.org": ("OWASP", "owasp"),
    "cwe.mitre.org": ("MITRE", "mitre_cwe"), "capec.mitre.org": ("MITRE", "mitre_capec"), "attack.mitre.org": ("MITRE", "mitre_attack"),
    "nvd.nist.gov": ("NIST", "nist"), "services.nvd.nist.gov": ("NIST", "nist"), "csrc.nist.gov": ("NIST", "nist"),
    "www.nist.gov": ("NIST", "nist"), "pages.nist.gov": ("NIST", "nist"),
    "www.cisa.gov": ("CISA", "cisa"), "cisa.gov": ("CISA", "cisa"),
    "www.cve.org": ("CVE Program", "cve"), "cve.org": ("CVE Program", "cve"),
    "datatracker.ietf.org": ("IETF", "rfc"), "www.rfc-editor.org": ("RFC Editor", "rfc"),
    "www.kernel.org": ("kernel.org", "linux_docs"), "docs.kernel.org": ("kernel.org", "linux_docs"), "man7.org": ("Linux man-pages", "linux_docs"),
    "sourceware.org": ("Sourceware", "vendor_docs"), "docs.python.org": ("Python Software Foundation", "vendor_docs"),
    "developer.mozilla.org": ("MDN / Mozilla", "vendor_docs"), "learn.microsoft.com": ("Microsoft", "vendor_docs"),
    "portswigger.net": ("PortSwigger", "vendor_docs"), "www.first.org": ("FIRST", "standards"),
    "arxiv.org": ("arXiv", "academic"), "export.arxiv.org": ("arXiv", "academic"),
    # AI / ML
    "pytorch.org": ("PyTorch", "vendor_docs"), "docs.pytorch.org": ("PyTorch", "vendor_docs"), "scikit-learn.org": ("scikit-learn", "vendor_docs"),
    "www.tensorflow.org": ("TensorFlow", "vendor_docs"), "huggingface.co": ("Hugging Face", "vendor_docs"), "developers.google.com": ("Google for Developers", "vendor_docs"), "www.ibm.com": ("IBM", "vendor_docs"),
    "numpy.org": ("NumPy", "vendor_docs"),
    "pandas.pydata.org": ("pandas", "vendor_docs"), "paperswithcode.com": ("Papers with Code", "academic"), "aclanthology.org": ("ACL Anthology", "academic"),
    "proceedings.neurips.cc": ("NeurIPS", "academic"), "openreview.net": ("OpenReview", "academic"),
    # programming / platforms
    "doc.rust-lang.org": ("Rust project", "vendor_docs"), "go.dev": ("Go project", "vendor_docs"), "nodejs.org": ("Node.js", "vendor_docs"),
    "docs.oracle.com": ("Oracle", "vendor_docs"), "kotlinlang.org": ("JetBrains", "vendor_docs"), "www.typescriptlang.org": ("Microsoft", "vendor_docs"),
    "docs.github.com": ("GitHub", "vendor_docs"), "git-scm.com": ("Git", "vendor_docs"), "www.postgresql.org": ("PostgreSQL", "vendor_docs"),
    "isocpp.org": ("ISO C++", "standards"), "en.cppreference.com": ("cppreference", "vendor_docs"), "www.w3.org": ("W3C", "standards"),
    # cloud / devops
    "docs.docker.com": ("Docker", "vendor_docs"), "kubernetes.io": ("Kubernetes", "vendor_docs"), "docs.aws.amazon.com": ("AWS", "vendor_docs"),
    "cloud.google.com": ("Google Cloud", "vendor_docs"), "www.terraform.io": ("HashiCorp", "vendor_docs"), "developer.hashicorp.com": ("HashiCorp", "vendor_docs"),
    # security: red team / exploit dev / SOC
    "www.sans.org": ("SANS", "security_community"), "www.elastic.co": ("Elastic", "vendor_docs"), "sigmahq.io": ("SigmaHQ", "security_community"),
    "docs.metasploit.com": ("Rapid7", "vendor_docs"), "www.exploit-db.com": ("OffSec Exploit-DB", "security_community"),
    "googleprojectzero.blogspot.com": ("Google Project Zero", "security_community"), "msrc.microsoft.com": ("Microsoft MSRC", "vendor_docs"),
    "www.cvedetails.com": ("CVEdetails", "security_community"), "www.us-cert.gov": ("CISA", "cisa"),
    "www.lockheedmartin.com": ("Lockheed Martin", "security_community"),
    "bloodhoundproject.org": ("BloodHound (SpecterOps)", "security_community"), "bloodhound.readthedocs.io": ("BloodHound (SpecterOps)", "security_community"),
    # github.com hosts arbitrary repos (broad trust, like exploit-db.com above) - needed to cite well-known offensive
    # security tool source (PowerSploit, Impacket, Mimikatz, etc.) that live there and nowhere more curated.
    "github.com": ("GitHub", "security_community"), "raw.githubusercontent.com": ("GitHub", "security_community"),
}
ALLOWED_HOSTS = set(OFFICIAL_HOSTS)
SEEDS = {  # stable, well-known OWASP Top 10 (2021) pages
    "injection": ("owasp_top10", "A03:2021", "https://top10.owasp.org/2021/A03_2021-Injection/"),
    "sql": [("owasp_top10", "A03:2021", "https://top10.owasp.org/2021/A03_2021-Injection/"),
            ("owasp_cheatsheet", "SQL Injection Prevention", "https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html"),
            ("cwe", "CWE-89", "https://cwe.mitre.org/data/definitions/89.html")],
    "access control": ("owasp_top10", "A01:2021", "https://top10.owasp.org/2021/A01_2021-Broken_Access_Control/"),
    "authentication": ("owasp_top10", "A07:2021", "https://top10.owasp.org/2021/A07_2021-Identification_and_Authentication_Failures/"),
    "ssrf": ("owasp_top10", "A10:2021", "https://top10.owasp.org/2021/A10_2021-Server-Side_Request_Forgery_%28SSRF%29/"),
    "xss": [("owasp_top10", "A03:2021", "https://top10.owasp.org/2021/A03_2021-Injection/"),
            ("owasp_cheatsheet", "XSS Prevention", "https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html"),
            ("cwe", "CWE-79", "https://cwe.mitre.org/data/definitions/79.html")],
    "misconfiguration": ("owasp_top10", "A05:2021", "https://top10.owasp.org/2021/A05_2021-Security_Misconfiguration/"),
    # adversary tradecraft / detection (MITRE ATT&CK pages are stable per tactic/technique id)
    "command and control": [("mitre_attack", "TA0011", "https://attack.mitre.org/tactics/TA0011/"),
                            ("mitre_attack", "T1071", "https://attack.mitre.org/techniques/T1071/"),
                            ("mitre_attack", "T1573", "https://attack.mitre.org/techniques/T1573/")],
    "c2": [("mitre_attack", "TA0011", "https://attack.mitre.org/tactics/TA0011/"), ("mitre_attack", "T1071", "https://attack.mitre.org/techniques/T1071/")],
    "credential dumping": [("mitre_attack", "T1003", "https://attack.mitre.org/techniques/T1003/"), ("mitre_attack", "TA0006", "https://attack.mitre.org/tactics/TA0006/")],
    "credential access": [("mitre_attack", "TA0006", "https://attack.mitre.org/tactics/TA0006/"), ("mitre_attack", "T1003", "https://attack.mitre.org/techniques/T1003/")],
    "mimikatz": [("mitre_attack", "S0002", "https://attack.mitre.org/software/S0002/"), ("mitre_attack", "T1003", "https://attack.mitre.org/techniques/T1003/")],
    "phishing": ("mitre_attack", "T1566", "https://attack.mitre.org/techniques/T1566/"),
    "privilege escalation": ("mitre_attack", "TA0004", "https://attack.mitre.org/tactics/TA0004/"),
    "lateral movement": ("mitre_attack", "TA0008", "https://attack.mitre.org/tactics/TA0008/"),
    "persistence": ("mitre_attack", "TA0003", "https://attack.mitre.org/tactics/TA0003/"),
    "buffer overflow": [("cwe", "CWE-121", "https://cwe.mitre.org/data/definitions/121.html"), ("cwe", "CWE-787", "https://cwe.mitre.org/data/definitions/787.html")],
    "use after free": ("cwe", "CWE-416", "https://cwe.mitre.org/data/definitions/416.html"),
    "csrf": ("cwe", "CWE-352", "https://cwe.mitre.org/data/definitions/352.html"),
    "deserialization": ("cwe", "CWE-502", "https://cwe.mitre.org/data/definitions/502.html"),
    "incident response": ("nist", "SP 800-61", "https://csrc.nist.gov/pubs/sp/800/61/r2/final"),
}
# Introductory machine learning. Every URL below was fetched live and returned real article text (checked 2026-10-31).
_ML_CORE = [("google_mlcc", "What is ML", "https://developers.google.com/machine-learning/intro-to-ml/what-is-ml"),
            ("ibm_docs", "What is machine learning", "https://www.ibm.com/think/topics/machine-learning"),
            ("ms_learn", "ML concepts", "https://learn.microsoft.com/en-us/training/modules/fundamentals-machine-learning/2-what-is-machine-learning"),
            ("sklearn_docs", "Getting started", "https://scikit-learn.org/stable/getting_started.html"),
            ("sklearn_docs", "Supervised learning", "https://scikit-learn.org/stable/supervised_learning.html")]
SEEDS.update({
    "machine learning": _ML_CORE,
    "overfit": [("google_mlcc", "Overfitting", "https://developers.google.com/machine-learning/crash-course/overfitting/overfitting"),
                ("ibm_docs", "Overfitting", "https://www.ibm.com/think/topics/overfitting"),
                ("sklearn_docs", "Underfitting vs overfitting", "https://scikit-learn.org/stable/auto_examples/model_selection/plot_underfitting_overfitting.html")],
    "fairness": [("google_mlcc", "Fairness", "https://developers.google.com/machine-learning/crash-course/fairness/video-lecture"),
                 ("nist", "AI Risk Management Framework", "https://www.nist.gov/itl/ai-risk-management-framework")],
    "ethic": [("nist", "AI Risk Management Framework", "https://www.nist.gov/itl/ai-risk-management-framework")],
    "bias": [("nist", "AI Risk Management Framework", "https://www.nist.gov/itl/ai-risk-management-framework")],
    "scikit-learn": [("sklearn_docs", "User guide", "https://scikit-learn.org/stable/user_guide.html"),
                     ("sklearn_docs", "Toy datasets", "https://scikit-learn.org/stable/datasets/toy_dataset.html")],
    "iris": [("sklearn_docs", "Toy datasets", "https://scikit-learn.org/stable/datasets/toy_dataset.html")],
    "decision tree": [("sklearn_docs", "Decision trees", "https://scikit-learn.org/stable/modules/tree.html")],
    "cross-validation": [("sklearn_docs", "Cross-validation", "https://scikit-learn.org/stable/modules/cross_validation.html")],
    "model evaluation": [("sklearn_docs", "Metrics and scoring", "https://scikit-learn.org/stable/modules/model_evaluation.html")],
    "deep learning": [("ms_learn", "Deep learning vs machine learning", "https://learn.microsoft.com/en-us/azure/machine-learning/concept-deep-learning-vs-machine-learning")],
})
MAX_SOURCES = 12
UNVERIFIED_NOT_STORED = {"model_suggested", "arxiv"}  # guesses and search hits are only kept when the page was really retrieved
FETCH_WORKERS = 4
CVE_RE = re.compile(r"\bCVE-\d{4}-\d{4,7}\b")
CVSS_RE = re.compile(r"\bCVSS(?:\s*v?\d(?:\.\d)?)?\s*(?:score\s*)?(?:of\s*)?[:=]?\s*(\d{1,2}\.\d)\b", re.I)
TEXT_TYPES = ("text/html", "application/xhtml+xml", "text/plain")
MIN_TEXT_CHARS = 200
MAX_STORED_TEXT = 60_000
MAX_HOPS = 4
_ROBOTS: dict[str, RobotFileParser | None] = {}


def host_allowed(url: str) -> bool:
    u = urlparse(url)
    return u.scheme == "https" and (u.hostname or "") in ALLOWED_HOSTS


def canonical_url(url: str) -> str:
    u = urlparse(urldefrag(url.strip())[0])
    return u._replace(netloc=(u.hostname or "").lower() + (f":{u.port}" if u.port else "")).geturl()


def is_public_ip(ip: str) -> bool:
    a = ipaddress.ip_address(ip)
    return not (a.is_private or a.is_loopback or a.is_link_local or a.is_multicast or a.is_reserved or a.is_unspecified
                or (a.version == 4 and ip.startswith("169.254.")))  # incl. cloud metadata 169.254.169.254


def _resolve(host: str) -> list[str]:
    return sorted({ai[4][0] for ai in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)})


def check_destination(url: str) -> str | None:
    """None if the URL may be fetched, else a short reason. Literal IPs are never allowed."""
    u = urlparse(url)
    if u.scheme != "https":
        return "only https URLs are fetched"
    host = u.hostname or ""
    try:
        ipaddress.ip_address(host)
        return "IP-literal hosts are not allowed"
    except ValueError:
        pass
    if host not in ALLOWED_HOSTS:
        return "host not in research allow-list"
    try:
        ips = _resolve(host)
    except OSError:
        return "DNS resolution failed"
    if not ips or not all(is_public_ip(i) for i in ips):
        return "host resolves to a non-public address"
    return None


def _client() -> httpx.Client:
    s = get_settings()
    return httpx.Client(timeout=s.research_timeout_s, follow_redirects=False, headers={"User-Agent": s.research_user_agent})


def _robots_ok(client: httpx.Client, url: str) -> bool:
    u = urlparse(url)
    key = f"{u.scheme}://{u.netloc}"
    if key not in _ROBOTS:
        rp = None
        try:
            r = client.get(f"{key}/robots.txt")
            if r.status_code == 200 and len(r.content) < 500_000:
                rp = RobotFileParser()
                rp.parse(r.text.splitlines())
        except httpx.HTTPError:
            rp = None  # robots.txt unreachable: no restriction is declared
        _ROBOTS[key] = rp
    rp = _ROBOTS[key]
    return rp is None or rp.can_fetch(get_settings().research_user_agent, url)


class FetchResult:
    def __init__(self, status: str, url: str, detail: str = "", http_status: int = 0, body: str = "", headers: dict | None = None):
        self.status, self.url, self.detail, self.http_status, self.body, self.headers = status, url, detail, http_status, body, headers or {}


def fetch(url: str) -> FetchResult:
    """Fetch with every safety control. Statuses: ok | blocked_host | blocked_redirect | blocked_robots | timeout | http_error |
    too_large | unsupported_content | fetch_error."""
    limit = get_settings().research_max_bytes
    why = check_destination(url)
    if why:
        return FetchResult("blocked_host", url, why)
    try:
        with _client() as c:
            if not _robots_ok(c, url):
                return FetchResult("blocked_robots", url, "disallowed by robots.txt")
            for _hop in range(MAX_HOPS + 1):
                with c.stream("GET", url) as r:
                    if r.status_code in (301, 302, 303, 307, 308) and r.headers.get("location"):
                        url = str(httpx.URL(url).join(r.headers["location"]))
                        why = check_destination(url)  # EVERY hop is re-validated (allow-list + DNS + private ranges)
                        if why:
                            return FetchResult("blocked_redirect", url, f"redirect target rejected: {why}")
                        continue
                    if r.status_code != 200:
                        return FetchResult("http_error", url, f"HTTP {r.status_code}", r.status_code)
                    ctype = r.headers.get("content-type", "").split(";")[0].strip().lower()
                    if ctype not in TEXT_TYPES:
                        return FetchResult("unsupported_content", url, f"content-type '{ctype}' is not text/html", 200)
                    declared = r.headers.get("content-length")
                    if declared and declared.isdigit() and int(declared) > limit:
                        return FetchResult("too_large", url, f"declared size {declared} > {limit} bytes", 200)
                    buf = bytearray()
                    for chunk in r.iter_bytes():
                        buf += chunk
                        if len(buf) > limit:
                            return FetchResult("too_large", url, f"response exceeded {limit} bytes", 200)
                    return FetchResult("ok", url, "", 200, buf.decode(r.encoding or "utf-8", errors="replace"), dict(r.headers))
            return FetchResult("blocked_redirect", url, "too many redirects")
    except httpx.TimeoutException:
        return FetchResult("timeout", url, "request timed out")
    except httpx.HTTPError as e:
        return FetchResult("fetch_error", url, f"fetch failed: {type(e).__name__}")


class _Extract(HTMLParser):
    SKIP = {"script", "style", "noscript", "nav", "header", "footer", "form", "svg"}
    HEAD = {"h1", "h2", "h3"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip, self.title, self.meta, self.sections = 0, "", {}, [["", []]]
        self._in_title, self._in_head = False, False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in self.SKIP:
            self.skip += 1
        elif tag == "title":
            self._in_title = True
        elif tag in self.HEAD:
            self._in_head = True
            self.sections.append(["", []])
        elif tag == "meta":
            k = (a.get("name") or a.get("property") or a.get("itemprop") or "").lower()
            if k and a.get("content"):
                self.meta.setdefault(k, a["content"])

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip:
            self.skip -= 1
        elif tag == "title":
            self._in_title = False
        elif tag in self.HEAD:
            self._in_head = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif self.skip:
            return
        elif self._in_head:
            self.sections[-1][0] += data
        elif data.strip():
            self.sections[-1][1].append(data.strip())


def extract(html: str, headers: dict | None = None) -> dict:
    """Returns title, published date (page metadata or Last-Modified header, '' if unknown) and `sections` [(heading, text)]."""
    p = _Extract()
    try:
        p.feed(html)
    except Exception:  # noqa: BLE001 - malformed markup: use what was parsed
        pass
    sections = [(re.sub(r"\s+", " ", h).strip(), re.sub(r"\s+", " ", " ".join(t)).strip()) for h, t in p.sections]
    sections = [x for x in sections if x[1]]
    pub = next((p.meta[k] for k in ("article:modified_time", "article:published_time", "dcterms.modified", "dcterms.date", "date", "last-modified", "datepublished") if k in p.meta), "")
    pub = pub or (headers or {}).get("last-modified", "")
    return {"title": re.sub(r"\s+", " ", p.title).strip(), "published_at": pub[:64], "sections": sections}


def _tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]{3,}", text.lower()) if w not in _STOP}


_STOP = {"the", "and", "for", "with", "that", "this", "from", "are", "can", "not", "all", "was", "but", "its", "has", "have", "how", "what", "your", "into", "than", "when", "which"}


def best_sections(sections: list[tuple[str, str]], query: str, k: int = 3) -> list[tuple[str, str]]:
    q = _tokens(query)
    scored = sorted(((len(q & _tokens(h + " " + t)) / (1 + len(t) ** 0.25), i) for i, (h, t) in enumerate(sections)), reverse=True)
    return [sections[i] for sc, i in sorted(scored[:k], key=lambda x: x[1]) if sc > 0] or sections[:1]


def sections_to_text(sections: list[tuple[str, str]]) -> str:
    out = "\n".join((f"## {h}\n" if h else "") + t for h, t in sections)
    return out[:MAX_STORED_TEXT]


def parse_sections(full_text: str) -> list[tuple[str, str]]:
    """Inverse of sections_to_text (headings are '## ' lines)."""
    out, head, buf = [], "", []
    for line in full_text.splitlines():
        if line.startswith("## "):
            if buf:
                out.append((head, " ".join(buf)))
            head, buf = line[3:].strip(), []
        else:
            buf.append(line)
    if buf:
        out.append((head, " ".join(buf)))
    return out


def fetch_source(url: str, query: str = "") -> dict:
    """Fetch + extract one source. Returns the ResearchSource field values; never raises."""
    host = urlparse(url).hostname or ""
    publisher, category = OFFICIAL_HOSTS.get(host, ("", ""))
    base = {"title": "", "publisher": publisher, "category": category, "published_at": "", "section": "", "content_hash": "",
            "full_text": "", "excerpt": "", "status": "", "verified": False, "detail": ""}
    res = fetch(url)
    base["status"], base["detail"] = res.status, res.detail
    if res.status != "ok":
        return base
    ex = extract(res.body, res.headers)
    text = sections_to_text(ex["sections"])
    base.update(title=ex["title"][:500], published_at=ex["published_at"])
    if len(text) < MIN_TEXT_CHARS or re.search(r"\b(404|not found|access denied|just a moment)\b", ex["title"], re.I):
        base["status"], base["detail"] = "empty_content", "HTTP 200 but no usable article text (error page, JS-only or blocked page)"
        return base
    pick = best_sections(ex["sections"], query)
    base.update(full_text=text, content_hash=hashlib.sha256(text.encode()).hexdigest(), section=pick[0][0][:500],
                excerpt=" ".join(t for _h, t in pick)[:2000], verified=True)
    return base


def fetch_excerpt(url: str, timeout: float = 15) -> tuple[bool, str]:
    """Back-compat wrapper: (ok, excerpt-or-reason)."""
    r = fetch_source(url)
    return (True, ((r["title"] + " - ") if r["title"] else "") + r["excerpt"][:600]) if r["verified"] else (False, r["detail"] or r["status"])


def lookup_cve(cve_id: str) -> dict | None:
    """Real NVD API 2.0 query. Returns None if NVD doesn't know it or is unreachable (never guesses)."""
    if not CVE_RE.fullmatch(cve_id):
        return None
    try:
        r = httpx.get("https://services.nvd.nist.gov/rest/json/cves/2.0", params={"cveId": cve_id}, timeout=20)
        if r.status_code != 200:
            return None
        vulns = r.json().get("vulnerabilities", [])
    except (httpx.HTTPError, ValueError):
        return None
    if not vulns:
        return None
    c = vulns[0]["cve"]
    desc = next((d["value"] for d in c.get("descriptions", []) if d["lang"] == "en"), "")
    return {"id": c["id"], "description": desc, "metrics": c.get("metrics", {}), "url": f"https://nvd.nist.gov/vuln/detail/{c['id']}"}


def _json_get(url: str, params: dict) -> str:
    """Small allow-listed GET used by source discovery (search APIs). Returns '' on any failure; never raises."""
    if check_destination(url):
        return ""
    try:
        with httpx.Client(timeout=get_settings().research_timeout_s, headers={"User-Agent": get_settings().research_user_agent}) as c:
            r = c.get(url, params=params)
            return r.text if r.status_code == 200 and len(r.content) < 1_000_000 else ""
    except httpx.HTTPError:
        return ""


def discover_urls(topic: str, domain: str = "") -> list[tuple[str, str, str]]:
    """Find extra candidate pages for a topic from free public search APIs (currently arXiv, for AI/ML topics).
    Returns (kind, identifier, https url) triples. Everything returned is still fetched, allow-list checked and verified by collect()."""
    out: list[tuple[str, str, str]] = []
    q = re.sub(r"\b(introduction to|intro to|all about|fundamentals of|basics of)\b", "", topic, flags=re.I)
    q = re.sub(r"\([^)]*\)", "", q).strip()[:120] or topic[:120]
    if domain == "ai_ml":
        body = _json_get("https://export.arxiv.org/api/query", {"search_query": f"all:{q}", "max_results": 3, "sortBy": "relevance"})
        for m in re.finditer(r"<id>https?://arxiv\.org/abs/([^<\s]+)</id>", body):
            out.append(("arxiv", m.group(1), f"https://arxiv.org/abs/{m.group(1)}"))
    return out


def suggest_urls(llm, lesson: Lesson, domain: str) -> list[tuple[str, str, str]]:
    """Ask the model for authoritative pages (prompt: ai/prompts/research.md). Only allow-listed https URLs are kept, and each is
    fetched and verified later, so a hallucinated URL ends up as an unverified source rather than as evidence. Never raises."""
    if llm is None or llm.name.startswith("mock"):
        return []
    try:
        from app.services import generation
        res = generation._ask(llm, "research", f"TOPIC: {lesson.title}\nSUMMARY: {lesson.summary}", generation.SourceSuggestions, domain=domain)
    except Exception:  # noqa: BLE001 - research must still succeed with seeds/search alone
        return []
    return [(x.kind[:32] or "model_suggested", x.title[:100], x.url) for x in res.sources if host_allowed(x.url)]


def _topic_text(lesson: Lesson) -> str:
    """Title, summary and the prose of the latest script (when there is one), lower-cased: what the lesson is actually about."""
    parts = [lesson.title, lesson.summary]
    sc = lesson.scripts[-1].content if getattr(lesson, "scripts", None) else {}
    for k in ("title", "introduction", "technical_explanation", "practical_demonstration", "real_world_applications", "common_mistakes", "defensive_recommendations"):
        v = sc.get(k, "")
        parts.append(" ".join(v) if isinstance(v, list) else str(v))
    return " ".join(parts).lower()


def seed_urls(topic: str) -> list[tuple[str, str, str]]:
    """Curated pages whose keyword occurs in `topic` as a word (prefix match; short keys like 'c2' must match whole words)."""
    wanted = []
    for key, seed in SEEDS.items():
        pat = rf"\b{re.escape(key)}\b" if len(key) <= 3 else rf"\b{re.escape(key)}"
        if re.search(pat, topic) or (key == "xss" and "cross-site scripting" in topic):
            for sd in (seed if isinstance(seed, list) else [seed]):
                if sd not in wanted:
                    wanted.append(sd)
    return wanted


def collect(db: Session, lesson: Lesson, extra_urls: list | None = None, online: bool = True) -> list[ResearchSource]:
    """`extra_urls` items are an https URL (stored as user_supplied) or a (kind, identifier, url) triple."""
    topic = _topic_text(lesson)
    wanted = seed_urls(topic)
    for u in extra_urls or []:
        wanted.append(("user_supplied", "", u) if isinstance(u, str) else tuple(u))
    existing = {canonical_url(s.url) for s in db.query(ResearchSource).filter_by(lesson_id=lesson.id)}
    todo = []
    for kind, ident, url in wanted:
        if not url.startswith("https://") or canonical_url(url) in existing:
            continue  # never store non-https URLs (they end up in href attributes); duplicates are skipped
        existing.add(canonical_url(url))
        todo.append((kind, ident, url))
    todo = todo[:MAX_SOURCES]
    # fetch concurrently: total wait is about the slowest page (<= research_timeout_s), not the sum of all pages
    def get(item):
        return fetch_source(item[2], f"{lesson.title} {lesson.summary} {item[1]}") if online else {"status": "offline", "verified": False, "excerpt": "offline mode: not fetched"}
    with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as pool:
        fetched = list(pool.map(get, todo))
    out = []
    for (kind, ident, url), f in zip(todo, fetched):
        if online and not f["verified"] and kind in UNVERIFIED_NOT_STORED:
            continue  # a guessed or searched URL that did not really load is not a source, not even a failed one
        s = ResearchSource(lesson_id=lesson.id, kind=kind, identifier=ident, url=url, excerpt=(f.get("excerpt") or f.get("detail") or "")[:2000],
                           verified=f["verified"], status=f["status"], title=f.get("title", ""), publisher=f.get("publisher", ""),
                           category=f.get("category", ""), published_at=f.get("published_at", ""), section=f.get("section", ""),
                           content_hash=f.get("content_hash", ""), full_text=f.get("full_text", ""))
        db.add(s)
        out.append(s)
    db.flush()
    return out


def technical_validation(script: dict, sources: list[ResearchSource], online: bool = True) -> dict:
    """Validation report: references vs. recorded sources, CVE/CVSS claims, and explicit unverified claims."""
    text = " ".join(str(v) for v in script.values())
    src_urls = {s.url for s in sources}
    refs = script.get("references", [])
    issues = []
    for r in refs:
        if r["url"] not in src_urls and not host_allowed(r["url"]):
            issues.append({"severity": "error", "msg": f"reference host not on allow-list: {r['url']}"})
        elif r["url"] not in src_urls:
            issues.append({"severity": "warning", "msg": f"reference not fetched/verified: {r['url']}"})
    cves = sorted(set(CVE_RE.findall(text)))
    cve_results = {}
    for c in cves:
        info = lookup_cve(c) if online else None
        cve_results[c] = bool(info)
        if not info:
            issues.append({"severity": "error", "msg": f"{c} could not be verified in NVD - remove or verify manually"})
    if CVSS_RE.search(text) and not cves:
        issues.append({"severity": "error", "msg": "CVSS score mentioned without a verified CVE record"})
    for u in script.get("unverified_claims", []):
        issues.append({"severity": "warning", "msg": f"model flagged unverified: {u}"})
    unverified_src = [s.url for s in sources if not s.verified]
    return {"cves": cve_results, "references_checked": len(refs), "sources_verified": len(sources) - len(unverified_src),
            "sources_unverified": unverified_src, "issues": issues, "passed": not any(i["severity"] == "error" for i in issues),
            "needs_human_review": True, "generated_at": now().isoformat()}
