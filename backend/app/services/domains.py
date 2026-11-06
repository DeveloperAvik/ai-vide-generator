"""Subject domains. The pipeline is topic-agnostic; a domain only supplies the instructor persona, the safety rules and the
kind of evidence the AI should prefer. It is appended to the base prompt of every AI task (see generation._ask)."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Domain:
    key: str
    label: str
    persona: str
    sources: str
    rules: str = ""
    audience: str = "Learners"
    tags: tuple[str, ...] = ()
    studio: str = "Teaching Studio"
    security: bool = False  # security domains treat remediation advice as safety-critical
    must_cover: str = ""  # what a lesson in this domain must contain (shown to the script writer and the teaching reviewer)


_LAB = ("Demonstrations must happen only in authorized, isolated lab environments with intentionally vulnerable software you own. "
        "Never suggest testing public or third-party targets. Never invent CVE ids, CVSS scores or affected versions.")

DOMAINS: dict[str, Domain] = {d.key: d for d in [
    Domain("general", "General / Any topic", "an expert educator who explains any technical subject clearly",
           "official documentation, standards bodies, textbooks, peer-reviewed papers",
           "Never invent statistics, versions, dates, quotes or URLs.", "Learners", ("education", "tutorial"), "Teaching Studio"),
    Domain("cybersecurity", "Cybersecurity (general)", "a senior cybersecurity educator",
           "OWASP, MITRE ATT&CK/CWE, NVD/CVE records, vendor advisories, official project docs", _LAB + " Include defensive coverage; teach the concept, root cause, detection and fix.",
           "Cybersecurity students", ("cybersecurity", "infosec", "ethical hacking education"), "Cybersecurity Teaching Studio", security=True),
    Domain("red_team", "Red Teaming / Pentesting", "a senior red team operator and offensive-security instructor",
           "MITRE ATT&CK, OWASP, vendor advisories, public conference papers, official tool docs",
           _LAB + " Teach adversary tradecraft and methodology with a matching detection and mitigation for each technique. "
           "Do not provide weaponized, ready-to-deploy chains against real software or real organizations.",
           "Security professionals and pentesting students", ("red team", "penetration testing", "adversary emulation"), "Red Team Teaching Studio", security=True),
    Domain("exploit_dev", "Exploit Development", "a senior vulnerability researcher and exploit-development instructor",
           "CWE, vendor advisories, CPU/OS vendor manuals, public research write-ups, official toolchain docs",
           _LAB + " Teach memory-safety bug classes, root-cause analysis, mitigations (ASLR, DEP, CFI, stack canaries) and how to fix them, "
           "using purpose-built vulnerable binaries you compile yourself. Do not provide weaponized exploits for real software.",
           "Security researchers and advanced students", ("exploit development", "binary exploitation", "reverse engineering"), "Exploit Dev Teaching Studio", security=True),
    Domain("soc", "SOC / Blue Team / DFIR", "a senior SOC analyst and detection-engineering instructor",
           "MITRE ATT&CK, vendor detection docs, Sigma/YARA rule repositories, NIST guidance, official SIEM/EDR docs",
           "Use only synthetic or public sample logs and datasets. Never invent indicators, hashes, CVE ids or incident details. "
           "Show how to detect, triage, investigate and respond, with the reasoning behind each step.",
           "SOC analysts and blue team learners", ("SOC", "blue team", "threat detection", "incident response"), "Blue Team Teaching Studio", security=True),
    Domain("ai_ml", "AI / Machine Learning", "a senior machine-learning engineer and educator",
           "peer-reviewed papers, arXiv, official framework docs (PyTorch, scikit-learn, etc.), model cards",
           "Never invent benchmark numbers, paper titles, authors or results. State assumptions, data requirements and limitations. "
           "Prefer small reproducible examples and explain the maths intuitively before the code.",
           "Developers and ML learners", ("machine learning", "AI", "deep learning"), "AI Teaching Studio",
           must_cover="a clear definition of the topic; the core vocabulary the objective needs (for introductory ML: data, features, labels, model, training, inference); "
                      "one simple and accurate worked example; how it differs from the traditional approach (for ML: rules written by hand vs. rules learned from data); "
                      "limitations and risks (overfitting, data quality, bias, privacy); a conclusion that restates every learning objective."),
    Domain("programming", "Programming / Software Engineering", "a senior software engineer and programming instructor",
           "official language and library documentation, RFCs, language specifications",
           "Code shown must be correct, idiomatic and runnable; state the language version. Never invent APIs, flags or library behaviour. "
           "Explain why, not only how, and mention common pitfalls.",
           "Developers and programming students", ("programming", "coding", "software engineering"), "Programming Teaching Studio"),
    Domain("devops_cloud", "DevOps / Cloud / Infrastructure", "a senior DevOps and cloud-infrastructure engineer and instructor",
           "official cloud-provider and tool documentation, CNCF projects, RFCs, well-architected frameworks",
           "Never invent service limits, prices, flags or API behaviour. Use placeholder accounts and resources, never real credentials.",
           "Engineers and operators", ("devops", "cloud", "infrastructure"), "DevOps Teaching Studio"),
]}


def is_security(key: str | None) -> bool:
    return get(key).security


def lesson_requirements(key: str | None) -> str:
    d = get(key)
    return f"\nLESSON MUST COVER: {d.must_cover}" if d.must_cover else ""


def get(key: str | None) -> Domain:
    return DOMAINS.get(key or "", DOMAINS["general"])


def of_lesson(lesson) -> Domain:
    """Domain of a lesson via module -> course. Tolerates detached lessons (tests, CLIs)."""
    course = getattr(getattr(lesson, "module", None), "course", None)
    return get(getattr(course, "domain", None))


def prompt_block(key: str | None) -> str:
    d = get(key)
    return (f"\n\nSUBJECT DOMAIN: {d.label}\nYou are {d.persona}. Prefer these kinds of authoritative sources: {d.sources}."
            + (f"\nDOMAIN RULES: {d.rules}" if d.rules else ""))


def narration_system(key: str | None, extra: str) -> str:
    d = get(key)
    return f"You write spoken narration for a {d.label} teaching video. {extra} Never invent CVE ids, versions, statistics or named incidents."
