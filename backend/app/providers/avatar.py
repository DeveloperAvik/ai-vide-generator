"""AvatarProvider implementations. Only `static` works with no setup; others report honestly when not configured."""
import shutil
from abc import ABC, abstractmethod
from pathlib import Path

import httpx

from app.core.config import get_settings
from app.security.subprocess_safe import run
from app.utils.media import MediaError


class AvatarUnavailable(RuntimeError):
    pass


class AvatarProvider(ABC):
    name = "base"
    paid = False

    @abstractmethod
    def available(self) -> tuple[bool, str]: ...

    @abstractmethod
    def generate_avatar_video(self, portrait: Path, audio: Path, out: Path) -> str:
        """Start generation; returns a job id (synchronous providers return 'local')."""

    @abstractmethod
    def get_generation_status(self, job_id: str) -> str:
        """pending | done | failed"""

    @abstractmethod
    def download_result(self, job_id: str, out: Path) -> Path: ...


class StaticPortraitAvatar(AvatarProvider):
    """Fallback: a still image (the composed instructor slide) looped for the audio duration. This is NOT lip-sync and is labelled as such."""
    name = "static"

    def available(self):
        return True, "fallback only: a still image, NOT a talking avatar"

    def generate_avatar_video(self, portrait, audio, out):
        if not portrait.exists():
            raise AvatarUnavailable(f"portrait missing: {portrait}")
        r = run(["ffmpeg", "-y", "-loop", "1", "-framerate", "30", "-i", str(portrait), "-i", str(audio),
                 "-vf", "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,format=yuv420p",
                 "-c:v", "libx264", "-tune", "stillimage", "-c:a", "aac", "-b:a", "192k", "-shortest", str(out)], timeout=600)
        if r.returncode != 0:
            raise MediaError(f"static avatar failed: {r.stderr[-300:]}")
        return "local"

    def get_generation_status(self, job_id):
        return "done"

    def download_result(self, job_id, out):
        return out


class HeyGenAvatar(AvatarProvider):
    """Talking avatar via HeyGen's public v2 API (external, paid). Implemented from HeyGen's published API docs;
    NOT verified against a live account yet. Needs HEYGEN_API_KEY and HEYGEN_AVATAR_ID. Our narration audio drives the lip-sync."""
    name = "heygen"
    paid = True
    API = "https://api.heygen.com"
    UPLOAD = "https://upload.heygen.com/v1/asset"

    def __init__(self):
        s = get_settings()
        self.key, self.avatar_id = s.heygen_api_key, s.heygen_avatar_id

    def available(self):
        if not self.key:
            return False, "HEYGEN_API_KEY not configured"
        if not self.avatar_id:
            return False, "HEYGEN_AVATAR_ID not configured (pick one in your HeyGen dashboard)"
        return True, "configured (unverified against live API)"

    def _h(self):
        return {"X-Api-Key": self.key}

    def generate_avatar_video(self, portrait, audio, out):
        ok, why = self.available()
        if not ok:
            raise AvatarUnavailable(why)
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            mp3 = Path(td) / "a.mp3"
            r = run(["ffmpeg", "-y", "-i", str(audio), "-b:a", "128k", str(mp3)], timeout=120)
            if r.returncode != 0:
                raise MediaError(f"mp3 convert failed: {r.stderr[-200:]}")
            up = httpx.post(self.UPLOAD, content=mp3.read_bytes(), headers={**self._h(), "Content-Type": "audio/mpeg"}, timeout=120)
        if up.status_code != 200:
            raise AvatarUnavailable(f"HeyGen audio upload failed: HTTP {up.status_code}")
        asset_id = up.json()["data"]["id"]
        gen = httpx.post(f"{self.API}/v2/video/generate", headers=self._h(), timeout=60, json={
            "video_inputs": [{"character": {"type": "avatar", "avatar_id": self.avatar_id, "avatar_style": "normal"},
                              "voice": {"type": "audio", "audio_asset_id": asset_id}}],
            "dimension": {"width": 1920, "height": 1080}})
        if gen.status_code != 200 or not gen.json().get("data", {}).get("video_id"):
            raise AvatarUnavailable(f"HeyGen generate failed: HTTP {gen.status_code} {gen.text[:200]}")
        return gen.json()["data"]["video_id"]

    def _status(self, job_id):
        r = httpx.get(f"{self.API}/v1/video_status.get", params={"video_id": job_id}, headers=self._h(), timeout=30)
        if r.status_code != 200:
            raise AvatarUnavailable(f"HeyGen status HTTP {r.status_code}")
        return r.json()["data"]

    def get_generation_status(self, job_id):
        import time
        for _ in range(120):  # up to ~20 min, polled every 10 s
            d = self._status(job_id)
            if d["status"] == "completed":
                return "done"
            if d["status"] == "failed":
                return "failed"
            time.sleep(10)
        return "pending"

    def download_result(self, job_id, out):
        url = self._status(job_id).get("video_url")
        if not url:
            raise AvatarUnavailable("HeyGen reports no video_url")
        with httpx.stream("GET", url, timeout=300) as r:
            r.raise_for_status()
            with open(out, "wb") as f:
                for chunk in r.iter_bytes():
                    f.write(chunk)
        return out


class MuseTalkAvatar(AvatarProvider):
    name = "musetalk"

    def __init__(self):
        self.dir = get_settings().musetalk_dir

    def available(self):
        if not self.dir or not Path(self.dir).exists():
            return False, "MUSETALK_DIR not set (requires a CUDA GPU; not supported on Apple Silicon out of the box)"
        return True, "ok"

    def generate_avatar_video(self, portrait, audio, out):
        ok, why = self.available()
        if not ok:
            raise AvatarUnavailable(why)
        raise AvatarUnavailable("MuseTalk is installed but the inference wrapper (avatar/scripts/musetalk_run.sh) is user-supplied; see avatar/README.md")

    def get_generation_status(self, job_id):
        raise AvatarUnavailable("MuseTalk unavailable")

    def download_result(self, job_id, out):
        raise AvatarUnavailable("MuseTalk unavailable")


PROVIDERS = {"static": StaticPortraitAvatar, "heygen": HeyGenAvatar, "musetalk": MuseTalkAvatar}


def get_avatar(name: str | None = None) -> AvatarProvider:
    name = (name or get_settings().avatar_provider).lower()
    p = PROVIDERS.get(name)
    if not p:
        raise AvatarUnavailable(f"unknown avatar provider '{name}'")
    inst = p()
    ok, why = inst.available()
    if not ok:
        raise AvatarUnavailable(f"{name}: {why}")
    return inst


def avatar_status() -> list[dict]:
    return [{"name": n, "paid": c.paid, "available": (a := c().available())[0], "detail": a[1]} for n, c in PROVIDERS.items()]
