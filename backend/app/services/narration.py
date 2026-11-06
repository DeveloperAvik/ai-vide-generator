"""Sentence-level narration synthesis. Each cue chunk is synthesized separately, so subtitle timings are the REAL
audio boundaries (no estimation). Output: one WAV (48 kHz mono PCM) + <scene>.timing.json."""
import json
import tempfile
import wave
from pathlib import Path

from app.providers.voice import VoiceProvider
from app.services.subtitles import _split_sentences

GAP_S = 0.18  # pause between sentences


def synth_with_timing(voice: VoiceProvider, narration: str, out_wav: Path) -> list[dict]:
    chunks = _split_sentences(narration)
    timing, frames, rate, t = [], [], None, 0.0
    with tempfile.TemporaryDirectory() as td:
        for i, text in enumerate(chunks):
            p = Path(td) / f"c{i}.wav"
            voice.generate_audio(text, p)
            with wave.open(str(p)) as w:
                rate = rate or w.getframerate()
                if (w.getnchannels(), w.getsampwidth(), w.getframerate()) != (1, 2, rate):
                    raise RuntimeError("voice provider returned unexpected PCM format")
                data = w.readframes(w.getnframes())
            dur = len(data) / (2 * rate)
            timing.append({"text": text, "start": round(t, 3), "end": round(t + dur, 3)})
            frames.append(data)
            gap = int(GAP_S * rate) * 2
            if i < len(chunks) - 1:
                frames.append(b"\x00" * gap)
            t += dur + GAP_S
    with wave.open(str(out_wav), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"".join(frames))
    out_wav.with_suffix(".timing.json").write_text(json.dumps(timing))
    return timing


def load_timing(wav: Path) -> list[dict] | None:
    p = wav.with_suffix(".timing.json")
    return json.loads(p.read_text()) if p.exists() else None
