import re
from dataclasses import dataclass


@dataclass
class Cue:
    start: float
    end: float
    text: str


def _split_sentences(text: str, max_chars: int = 70) -> list[str]:
    parts = re.split(r"(?<=[.!?;:])\s+", text.strip())
    out = []
    for p in parts:
        while len(p) > max_chars:
            cut = p.rfind(" ", 0, max_chars)
            cut = cut if cut > 20 else max_chars
            out.append(p[:cut].strip())
            p = p[cut:].strip()
        if p:
            out.append(p)
    return out


def scene_cues(narration: str, start: float, duration: float) -> list[Cue]:
    """Spread cues over the scene proportionally to character count (real audio duration is passed in)."""
    chunks = _split_sentences(narration)
    total = sum(len(c) for c in chunks) or 1
    cues, t = [], start
    for c in chunks:
        d = duration * len(c) / total
        cues.append(Cue(t, t + d, c))
        t += d
    return cues


def ts(sec: float) -> str:
    ms = round(sec * 1000)
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def to_srt(cues: list[Cue]) -> str:
    return "\n".join(f"{i}\n{ts(c.start)} --> {ts(c.end)}\n{c.text}\n" for i, c in enumerate(cues, 1))


def parse_srt(srt: str) -> list[Cue]:
    cues = []
    for block in re.split(r"\n\s*\n", srt.strip()):
        lines = block.strip().splitlines()
        if len(lines) < 3:
            continue
        a, b = lines[1].split(" --> ")
        cues.append(Cue(_sec(a), _sec(b), " ".join(lines[2:])))
    return cues


def _sec(t: str) -> float:
    h, m, rest = t.split(":")
    s, ms = rest.split(",")
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000
