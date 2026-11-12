"""Royalty-free background music, synthesised locally (no samples, no downloads, nothing to license).

Each track is a short seamless loop: chord progression + optional drums + vinyl crackle, written as 22.05 kHz mono WAV and
softened with an ffmpeg low-pass. The renderer loops it under the narration. Pure Python, so it runs anywhere ffmpeg does."""
import math
import random
import struct
import wave
from dataclasses import dataclass
from pathlib import Path

from app.security.subprocess_safe import run

SR = 22050


@dataclass(frozen=True)
class Track:
    bpm: int
    chords: tuple[tuple[int, ...], ...]  # MIDI notes per bar
    bass: tuple[int, ...]
    drums: str  # "lofi" | "four" | "none"
    crackle: float
    lowpass: int
    gain: float


_TRACKS = {
    "lofi": Track(75, ((65, 69, 72, 76), (64, 67, 71, 74), (62, 65, 69, 72), (60, 64, 67, 71)), (41, 40, 38, 36), "lofi", 0.05, 3200, 0.8),
    "chill": Track(68, ((57, 60, 64, 67), (53, 57, 60, 64), (60, 64, 67, 71), (55, 59, 62, 66)), (45, 41, 48, 43), "none", 0.02, 2800, 0.8),
    "upbeat": Track(112, ((60, 64, 67, 72), (67, 71, 74, 79), (69, 72, 76, 81), (65, 69, 72, 77)), (36, 43, 45, 41), "four", 0.0, 9000, 0.7),
    "cinematic": Track(84, ((57, 60, 64, 69), (53, 57, 60, 65), (48, 52, 55, 60), (55, 59, 62, 67)), (33, 29, 36, 31), "none", 0.0, 6000, 0.8),
}
MUSIC_STYLES = tuple(_TRACKS)


def bpm(style: str) -> int:
    return _TRACKS[style].bpm


def _hz(m: int) -> float:
    return 440.0 * 2 ** ((m - 69) / 12)


def _add(buf: list[float], start: int, samples) -> None:
    n = len(buf)  # wrap around so note tails fold into the loop start: the loop is seamless
    for i, v in enumerate(samples):
        buf[(start + i) % n] += v


def _tone(freq: float, dur: float, vol: float, attack=0.01, decay=2.5):
    n = int(dur * SR)
    out = []
    for i in range(n):
        t = i / SR
        env = min(1.0, t / attack) * math.exp(-decay * t)
        out.append(vol * env * (math.sin(2 * math.pi * freq * t) + 0.35 * math.sin(4 * math.pi * freq * t) * math.exp(-4 * t)
                                + 0.12 * math.sin(6 * math.pi * freq * t)))
    return out


def _kick(vol=0.55):
    return [vol * math.sin(2 * math.pi * (50 + 90 * math.exp(-28 * (i / SR))) * (i / SR)) * math.exp(-9 * (i / SR)) for i in range(int(0.28 * SR))]


def _noise_hit(rng: random.Random, dur: float, vol: float, decay: float):
    return [vol * (rng.random() * 2 - 1) * math.exp(-decay * (i / SR)) for i in range(int(dur * SR))]


def synthesize(style: str, bars: int, out_wav: Path, seed: int = 7) -> Path:
    """Write `bars` bars (the progression repeats). A bar is 4 beats."""
    tr = _TRACKS[style]
    rng = random.Random(seed)
    beat = 60.0 / tr.bpm
    bar = int(4 * beat * SR)
    buf = [0.0] * (bar * bars)
    for b in range(bars):
        s0 = b * bar
        chord, root = tr.chords[b % len(tr.chords)], tr.bass[b % len(tr.bass)]
        slow = tr.drums == "none"
        for k, m in enumerate(chord):  # chord: gently rolled
            _add(buf, s0 + int(k * 0.03 * SR), _tone(_hz(m), 4 * beat * (1.4 if slow else 1.0), 0.11, attack=0.25 if slow else 0.01, decay=0.6 if slow else 2.2))
        _add(buf, s0, _tone(_hz(root), 2 * beat, 0.22, attack=0.02, decay=1.8))
        if tr.drums == "four":
            for q in range(8):  # arpeggio on eighths keeps the track moving
                _add(buf, s0 + int(q * beat / 2 * SR), _tone(_hz(chord[q % 4] + 12), beat, 0.05, decay=6))
        for q in range(4):
            t = s0 + int(q * beat * SR)
            if tr.drums == "four":
                _add(buf, t, _kick())
                _add(buf, t + int(beat / 2 * SR), _noise_hit(rng, 0.05, 0.12, 60))
                if q % 2 == 1:
                    _add(buf, t, _noise_hit(rng, 0.14, 0.22, 25))
            elif tr.drums == "lofi":
                if q in (0, 2):
                    _add(buf, t + (int(0.4 * beat * SR) if q == 2 else 0), _kick(0.5))
                if q in (1, 3):
                    _add(buf, t, _noise_hit(rng, 0.16, 0.2, 22))
                _add(buf, t + int(beat / 2 * SR) + int(rng.uniform(0, 0.02) * SR), _noise_hit(rng, 0.03, 0.06, 90))  # lazy swung hat
    if tr.crackle:
        for i in range(len(buf)):
            if rng.random() < 0.0004:
                buf[i] += tr.crackle * (rng.random() * 2 - 1) * 3
            buf[i] += tr.crackle * 0.05 * (rng.random() * 2 - 1)
    peak = max(abs(v) for v in buf) or 1.0
    scale = tr.gain * 32767 / peak
    raw = out_wav.with_suffix(".raw.wav")
    with wave.open(str(raw), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(struct.pack(f"<{len(buf)}h", *(int(max(-32767, min(32767, v * scale))) for v in buf)))
    r = run(["ffmpeg", "-y", "-i", str(raw), "-af", f"lowpass=f={tr.lowpass},aecho=0.6:0.4:{int(beat * 750)}:0.18", "-t", f"{len(buf) / SR:.4f}", "-ar", "44100", "-ac", "2", str(out_wav)], timeout=120)
    raw.unlink(missing_ok=True)
    if r.returncode != 0:
        raise RuntimeError(f"music post-filter failed: {r.stderr[-300:]}")
    return out_wav


def track(style: str, cache_dir: Path) -> Path:
    """Cached 8-bar loop for a style (generated once, ~1-3 s)."""
    if style not in _TRACKS:
        raise ValueError(f"unknown music style '{style}'")
    cache_dir.mkdir(parents=True, exist_ok=True)
    p = cache_dir / f"{style}_v1.wav"
    if not p.exists() or p.stat().st_size < 10_000:
        tmp = cache_dir / f"{style}_v1.tmp.wav"
        synthesize(style, 8, tmp)
        tmp.replace(p)
    return p
