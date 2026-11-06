"""VoiceProvider implementations. Nothing here fabricates audio: if a provider is unavailable it raises."""
import platform
import sys
import shutil
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path

import httpx

from app.core.config import get_settings
from app.security.subprocess_safe import run
from app.utils.media import MediaError, duration, has_stream, probe


class VoiceUnavailable(RuntimeError):
    pass


class VoiceProvider(ABC):
    name = "base"
    paid = False

    @property
    def label(self) -> str:
        """Identifies the exact voice; speaking speed is measured and stored per label."""
        return self.name

    @abstractmethod
    def available(self) -> tuple[bool, str]: ...

    @abstractmethod
    def generate_audio(self, text: str, out_wav: Path) -> Path:
        """Write a 48kHz mono PCM WAV to out_wav."""

    def get_audio_duration(self, path: Path) -> float:
        return duration(path)

    def validate_audio(self, path: Path, expected_min_s: float = 0.5) -> list[str]:
        problems = []
        if not path.exists() or path.stat().st_size < 1000:
            return ["audio file missing or too small"]
        try:
            info = probe(path)
        except MediaError as e:
            return [str(e)]
        if not has_stream(info, "audio"):
            problems.append("no audio stream")
        elif duration(path) < expected_min_s:
            problems.append("audio shorter than minimum")
        return problems


def _to_wav(src: Path, dst: Path) -> None:
    r = run(["ffmpeg", "-y", "-i", str(src), "-ar", "48000", "-ac", "1", "-c:a", "pcm_s16le", str(dst)], timeout=120)
    if r.returncode != 0:
        raise MediaError(f"ffmpeg convert failed: {r.stderr[-300:]}")


class PiperVoice(VoiceProvider):
    name = "piper"

    def __init__(self):
        s = get_settings()
        venv_bin = Path(sys.executable).parent / s.piper_binary
        self.binary = str(venv_bin) if venv_bin.exists() else s.piper_binary
        self.model = s.piper_model

    @property
    def label(self):
        return f"piper:{Path(self.model).stem}"

    def available(self):
        if not shutil.which(self.binary):
            return False, f"piper binary '{self.binary}' not found (pip install piper-tts, or set PIPER_BINARY)"
        if not self.model or not Path(self.model).exists():
            return False, "PIPER_MODEL not set or file missing (download an .onnx voice from the piper-voices repo)"
        return True, "ok"

    def generate_audio(self, text, out_wav):
        ok, why = self.available()
        if not ok:
            raise VoiceUnavailable(why)
        with tempfile.TemporaryDirectory() as td:
            raw = Path(td) / "p.wav"
            r = run([self.binary, "--model", self.model, "--output_file", str(raw)], input_text=text, timeout=300)
            if r.returncode != 0:
                raise MediaError(f"piper failed: {r.stderr[-300:]}")
            _to_wav(raw, out_wav)
        return out_wav


_KOKORO = {}  # model is 325 MB: load once per process


class KokoroVoice(VoiceProvider):
    """Kokoro-82M (Apache-2.0) via kokoro-onnx: free, local, CPU. Far more natural than Piper's medium voices."""
    name = "kokoro"

    def __init__(self):
        s = get_settings()
        self.model, self.voices, self.voice, self.speed = s.kokoro_model, s.kokoro_voices, s.kokoro_voice, s.kokoro_speed

    @property
    def label(self):
        return f"kokoro:{self.voice}:{self.speed:g}"

    def available(self):
        try:
            import kokoro_onnx  # noqa: F401
            import soundfile  # noqa: F401
        except ImportError:
            return False, "pip install kokoro-onnx soundfile"
        if not (Path(self.model).exists() and Path(self.voices).exists()):
            return False, "Kokoro model files missing (voice/models/kokoro/kokoro-v1.0.onnx, voices-v1.0.bin; see voice/README.md)"
        return True, "ok"

    def generate_audio(self, text, out_wav):
        ok, why = self.available()
        if not ok:
            raise VoiceUnavailable(why)
        import soundfile as sf
        from kokoro_onnx import Kokoro
        from app.services.pronunciation import for_speech
        k = _KOKORO.get(self.model) or _KOKORO.setdefault(self.model, Kokoro(self.model, self.voices))
        if self.voice not in k.get_voices():
            raise VoiceUnavailable(f"kokoro voice '{self.voice}' not in voice pack")
        audio, sr = k.create(for_speech(text), voice=self.voice, speed=self.speed, lang="en-gb" if self.voice.startswith("b") else "en-us")
        with tempfile.TemporaryDirectory() as td:
            raw = Path(td) / "k.wav"
            sf.write(str(raw), audio, sr)
            _to_wav(raw, out_wav)
        return out_wav


class MacSayVoice(VoiceProvider):
    """Local macOS system TTS. Lower quality than Piper; used as an explicit offline fallback."""
    name = "macos_say"

    def __init__(self, voice: str = "Samantha"):
        self.voice = voice

    def available(self):
        if platform.system() != "Darwin" or not shutil.which("say"):
            return False, "macOS 'say' not available on this OS"
        return True, "ok"

    def generate_audio(self, text, out_wav):
        ok, why = self.available()
        if not ok:
            raise VoiceUnavailable(why)
        with tempfile.TemporaryDirectory() as td:
            aiff = Path(td) / "s.aiff"
            r = run(["say", "-v", self.voice, "-o", str(aiff), "--", text], timeout=300)
            if r.returncode != 0:
                raise MediaError(f"say failed: {r.stderr[-300:]}")
            _to_wav(aiff, out_wav)
        return out_wav


class ElevenLabsVoice(VoiceProvider):
    name = "elevenlabs"
    paid = True

    def __init__(self):
        s = get_settings()
        self.key, self.voice_id = s.elevenlabs_api_key, s.elevenlabs_voice_id

    def available(self):
        if not (self.key and self.voice_id):
            return False, "ELEVENLABS_API_KEY / ELEVENLABS_VOICE_ID not configured"
        return True, "ok"

    def generate_audio(self, text, out_wav):
        ok, why = self.available()
        if not ok:
            raise VoiceUnavailable(why)
        r = httpx.post(f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}", timeout=120,
                       headers={"xi-api-key": self.key, "accept": "audio/mpeg"},
                       json={"text": text, "model_id": "eleven_multilingual_v2"})
        if r.status_code != 200:
            raise MediaError(f"ElevenLabs error {r.status_code}")
        with tempfile.TemporaryDirectory() as td:
            mp3 = Path(td) / "e.mp3"
            mp3.write_bytes(r.content)
            _to_wav(mp3, out_wav)
        return out_wav


PROVIDERS = {"kokoro": KokoroVoice, "piper": PiperVoice, "macos_say": MacSayVoice, "elevenlabs": ElevenLabsVoice}


def get_voice(name: str | None = None) -> VoiceProvider:
    name = (name or get_settings().voice_provider).lower()
    if name == "auto":
        order = ("kokoro", "piper") if get_settings().app_env == "production" else ("kokoro", "piper", "macos_say")  # say is dev-only
        for n in order:  # free/local only; paid is never auto-selected
            p = PROVIDERS[n]()
            if p.available()[0]:
                return p
        raise VoiceUnavailable("No production TTS available. Install Kokoro or Piper (voice/README.md) (see voice/README.md).")
    if name not in PROVIDERS:
        raise VoiceUnavailable(f"unknown voice provider '{name}'")
    if name == "macos_say" and get_settings().app_env == "production":
        raise VoiceUnavailable("macos_say is a development fallback and is disabled when APP_ENV=production")
    p = PROVIDERS[name]()
    ok, why = p.available()
    if not ok:
        raise VoiceUnavailable(f"{name}: {why}")
    return p


def voice_status() -> list[dict]:
    return [{"name": n, "paid": c.paid, "available": (a := c().available())[0], "detail": a[1]} for n, c in PROVIDERS.items()]
