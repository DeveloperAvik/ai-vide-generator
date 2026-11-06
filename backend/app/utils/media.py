import hashlib
import json
from pathlib import Path

from app.security.subprocess_safe import run


class MediaError(RuntimeError):
    pass


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(t: str) -> str:
    return hashlib.sha256(t.encode()).hexdigest()


def probe(path: Path) -> dict:
    r = run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)], timeout=60)
    if r.returncode != 0:
        raise MediaError(f"ffprobe failed for {path.name}: {r.stderr.strip()[:200]}")
    return json.loads(r.stdout)


def duration(path: Path) -> float:
    d = probe(path)["format"].get("duration")
    if d is None:
        raise MediaError(f"no duration in {path.name}")
    return float(d)


def has_stream(info: dict, kind: str) -> bool:
    return any(s.get("codec_type") == kind for s in info.get("streams", []))
