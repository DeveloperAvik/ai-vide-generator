"""Renders captured lab output (lab/session.json) as a typed-terminal MP4 (1920x1080, 30 fps, silent).
This is an animation of REAL captured responses - the clip is labelled as such on screen.
Usage: python lab/render_session_video.py <out.mp4> <step_index> [<step_index> ...]"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "backend"))
from PIL import Image, ImageDraw  # noqa: E402
from app.services.visuals import ACCENT, BG, FG, MUTED, W, H, _base, font  # noqa: E402

COLS = 92


def wrap(s, n=COLS):
    return [s[i:i + n] for i in range(0, len(s), n)] or [""]


def frame(lines, title, out):
    img, d = _base(title, "Recorded from a local intentionally-vulnerable lab app (127.0.0.1, fake data) - animation of real captured output")
    d.rounded_rectangle([90, 190, W - 90, 930], 18, fill="#000000", outline="#334155", width=3)
    for i, c in enumerate(("#ef4444", "#f59e0b", "#22c55e")):
        d.ellipse([120 + i * 40, 215, 144 + i * 40, 239], fill=c)
    f = font(30, mono=True)
    y = 265
    for text, color in lines[-14:]:
        d.text((125, y), text, font=f, fill=color)
        y += 45
    img.save(out)


def main():
    out, idx = Path(sys.argv[1]), [int(x) for x in sys.argv[2:]]
    session = json.loads((HERE / "session.json").read_text())
    title = "Lab: " + session[idx[0]]["title"]
    lines, states = [], []  # states: (lines snapshot, seconds)
    for i in idx:
        s = session[i]
        cmd = "$ curl 'http://127.0.0.1:8099" + s["request"].split(" ", 1)[1] + "'"
        for k in range(1, len(cmd) + 1, 4):
            states.append((lines + [(l, "#4ade80") for l in wrap(cmd[:k])[-3:]], 0.05))
        lines += [(l, "#4ade80") for l in wrap(cmd)]
        states.append((list(lines), 0.8))
        col = "#f87171" if s["status"] >= 500 else "#e2e8f0"
        lines += [(f"HTTP {s['status']}", MUTED)] + [(l, col) for l in wrap(s["body"])] + [("", FG)]
        states.append((list(lines), 4.0))
    states[-1] = (states[-1][0], 3.0)
    with tempfile.TemporaryDirectory() as td:
        listing = []
        for n, (ls, dur) in enumerate(states):
            p = Path(td) / f"{n:04d}.png"
            frame(ls, title, p)
            listing.append(f"file '{p}'\nduration {dur}\n")
        listing.append(f"file '{Path(td) / f'{len(states) - 1:04d}.png'}'\n")
        (Path(td) / "l.txt").write_text("".join(listing))
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(Path(td) / "l.txt"), "-vf", "fps=30,format=yuv420p",
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-an", str(out)], check=True)
    print("wrote", out)


if __name__ == "__main__":
    main()
