"""Measure real Piper speaking speed (words/second) on representative technical narration and store it.
Usage: python -m app.cli.calibrate_voice [bundle.json]
lengthplan reads the result, so word budgets track the actual voice instead of a hard-coded constant."""
import json
import sys
import tempfile
from pathlib import Path

from app.core.config import ROOT, get_settings
from app.providers.voice import get_voice
from app.services import narration

DEFAULT_BUNDLE = ROOT / "lessons" / "sqli_fundamentals" / "bundle.json"


def calibrate(bundle: Path = DEFAULT_BUNDLE, max_words: int = 600) -> dict:
    scenes = json.loads(bundle.read_text())["storyboard"]["scenes"]
    voice = get_voice(None)
    words = secs = 0.0
    with tempfile.TemporaryDirectory() as td:
        for i, sc in enumerate(scenes):
            n = len(sc["narration"].split())
            if not n:
                continue
            wav = Path(td) / f"{i}.wav"
            timing = narration.synth_with_timing(voice, sc["narration"], wav)
            words += n
            secs += timing[-1]["end"]  # real audio length incl. inter-sentence gaps
            if words >= max_words:
                break
    from app.services.lengthplan import record_voice_sample
    result = record_voice_sample(f"calibrate:{bundle.name}", int(words), secs, voice.label)
    return result


if __name__ == "__main__":
    print(json.dumps(calibrate(Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_BUNDLE), indent=2))
