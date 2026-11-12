"""Make a reel from the command line:  python -m app.cli.reel "5 habits of great engineers" --style trending --photos a.jpg b.jpg"""
import argparse
import sys
from pathlib import Path

from app.schemas.reel import MUSIC, STYLES, ReelRequest
from app.services import reels


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Generate an Instagram Reel (1080x1920 MP4) from a topic and optional photos.")
    ap.add_argument("topic")
    ap.add_argument("--style", default="trending", choices=STYLES)
    ap.add_argument("--notes", default="", help="free-form direction, e.g. 'funny, for beginners'")
    ap.add_argument("--duration", type=int, default=30, help="target seconds (10-90)")
    ap.add_argument("--music", default="auto", choices=MUSIC)
    ap.add_argument("--no-voice", action="store_true")
    ap.add_argument("--no-captions", action="store_true")
    ap.add_argument("--photos", nargs="*", default=[], type=Path)
    a = ap.parse_args(argv)
    req = ReelRequest(topic=a.topic, style=a.style, style_notes=a.notes, duration_s=a.duration, voiceover=not a.no_voice, music=a.music, captions=not a.no_captions)
    try:
        rid = reels.create_job(req, [p.read_bytes() for p in a.photos])
    except (reels.ReelError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    reels.run_job(rid)
    st = reels.get_status(rid)
    if st["status"] != "done":
        print(f"failed: {st.get('error')}", file=sys.stderr)
        return 1
    d = reels.reel_dir(rid)
    r = st["result"]
    print(f"reel: {d / r['video']}  ({r['duration']}s, voice={r['voiceover']}, music={r['music']})\ncaption: {d / 'caption.txt'}")
    if st.get("simulated"):
        print("note: LLM_PROVIDER=mock wrote a generic template script. Set LLM_PROVIDER=anthropic or ollama for real copy.")
    for w in r["warnings"]:
        print(f"warning: {w}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
