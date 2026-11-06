"""Scan text for secrets/PII before it ends up in on-screen recordings, logs or terminal scenes."""
import re

PATTERNS = {
    "aws_access_key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "anthropic_key": re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}\b"),
    "generic_api_key": re.compile(r"(?i)\b(api[_-]?key|secret|token)\b\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{16,}"),
    "bearer_token": re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-]{20,}"),
    "jwt": re.compile(r"\beyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\b"),
    "password_assign": re.compile(r"(?i)\b(password|passwd|pwd)\b\s*[:=]\s*\S{4,}"),
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "email": re.compile(r"\b[\w.+-]+@(?!(?:[\w-]+\.)*(?:example\.(?:com|org|net)|[\w-]+\.(?:test|example|invalid|localhost))\b)[\w-]+\.[\w.-]+\b"),  # RFC 2606 example domains are fine on screen
    "github_token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
}
# Lab ranges that are fine on screen: docker bridge / lab convention / typical 192.168 home-lab. Other private IPs get flagged.
_PRIV_IP = re.compile(r"\b(?:10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(?:1[6-9]|2\d|3[01])\.\d+\.\d+)\b")
_ALLOWED_IP = re.compile(r"^(?:172\.(?:1[6-9]|2\d|3[01])\.0\.\d+|10\.99\.\d+\.\d+|192\.168\.\d+\.\d+)$")  # docker/lab convention


def scan_text(text: str) -> list[dict]:
    findings = []
    for name, rx in PATTERNS.items():
        for m in rx.finditer(text):
            findings.append({"type": name, "excerpt": mask(m.group(0))})
    for m in _PRIV_IP.finditer(text):
        if not _ALLOWED_IP.match(m.group(0)):
            findings.append({"type": "private_ip", "excerpt": m.group(0)})
    return findings


def mask(s: str) -> str:
    return s[:4] + "…" + "*" * 4 if len(s) > 8 else "****"


def redact(text: str) -> str:
    for rx in PATTERNS.values():
        text = rx.sub("[REDACTED]", text)
    return text
