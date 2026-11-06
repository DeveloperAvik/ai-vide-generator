import re
from pathlib import Path

_SAFE = re.compile(r"[^A-Za-z0-9._-]")


def safe_name(name: str) -> str:
    """Strip directories and unsafe characters from a user-supplied filename."""
    base = Path(name.replace("\\", "/")).name
    base = _SAFE.sub("_", base).lstrip(".")
    if not base:
        raise ValueError("invalid filename")
    return base[:120]


def resolve_within(root: Path, *parts: str) -> Path:
    """Join and ensure the result stays inside root (blocks ../ and symlink escapes)."""
    root = root.resolve()
    p = root.joinpath(*parts).resolve()
    if p != root and root not in p.parents:
        raise ValueError("path traversal blocked")
    return p
