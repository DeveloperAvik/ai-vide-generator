"""All external binaries go through here: argv lists only, no shell, timeouts, scrubbed env."""
import os
import subprocess
from pathlib import Path

_ALLOWED = {"ffmpeg", "ffprobe", "piper", "say", "afconvert", "node", "npx", "mmdc"}
_ENV_KEEP = ("PATH", "HOME", "LANG", "TMPDIR")


def run(argv: list[str], timeout: int = 600, cwd: Path | None = None, input_text: str | None = None) -> subprocess.CompletedProcess:
    if not argv or Path(argv[0]).name not in _ALLOWED:
        raise PermissionError(f"binary not allow-listed: {argv[:1]}")
    env = {k: v for k, v in os.environ.items() if k in _ENV_KEEP}
    return subprocess.run([str(a) for a in argv], capture_output=True, text=True, timeout=timeout,
                          check=False, shell=False, cwd=cwd, env=env, input=input_text)


def popen_stdin(argv: list[str], stderr_file) -> subprocess.Popen:
    """Same allow-list and scrubbed env as run(), but with a writable stdin pipe (used to stream raw video frames into ffmpeg)."""
    if not argv or Path(argv[0]).name not in _ALLOWED:
        raise PermissionError(f"binary not allow-listed: {argv[:1]}")
    env = {k: v for k, v in os.environ.items() if k in _ENV_KEEP}
    return subprocess.Popen([str(a) for a in argv], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=stderr_file, shell=False, env=env)
