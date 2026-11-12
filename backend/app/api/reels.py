"""Instagram Reels endpoints: POST /api/reels (multipart: topic + options + optional photos) -> 202 {id}; poll GET /api/reels/{id}."""
import threading

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import ValidationError

from app.models import User
from app.schemas.reel import MUSIC, STYLES, ReelRequest
from app.security import auth
from app.services import reel_music, reels

router = APIRouter(prefix="/api/reels", dependencies=[Depends(auth.current_user)])
_LOCK = threading.Lock()
_ACTIVE: set[str] = set()
_MAX_ACTIVE = 2  # rendering is CPU-heavy; extra jobs are refused instead of thrashing the machine


def _spawn(rid: str):
    def job():
        try:
            reels.run_job(rid)
        finally:
            with _LOCK:
                _ACTIVE.discard(rid)
    with _LOCK:
        if len(_ACTIVE) >= _MAX_ACTIVE:
            return False
        _ACTIVE.add(rid)
    threading.Thread(target=job, daemon=True).start()
    return True


@router.get("/options")
def options():
    return {"styles": STYLES, "music": MUSIC, "music_styles": reel_music.MUSIC_STYLES, "max_photos": reels.MAX_PHOTOS, "duration_s": [10, 90]}


@router.post("", status_code=202)
async def create(topic: str = Form(...), style: str = Form("trending"), style_notes: str = Form(""), duration_s: int = Form(30),
                 voiceover: bool = Form(True), music: str = Form("auto"), captions: bool = Form(True),
                 photos: list[UploadFile] = File(default_factory=list), user: User = Depends(auth.current_user)):
    try:
        req = ReelRequest(topic=topic, style=style, style_notes=style_notes, duration_s=duration_s, voiceover=voiceover, music=music, captions=captions)
    except ValidationError as e:
        raise HTTPException(422, "; ".join(f"{'.'.join(map(str, x['loc']))}: {x['msg']}" for x in e.errors()))
    blobs = []
    for f in photos[:reels.MAX_PHOTOS + 1]:
        blobs.append(await f.read(reels.MAX_PHOTO_BYTES + 1))
    try:
        rid = reels.create_job(req, blobs, user.id)
    except reels.ReelError as e:
        raise HTTPException(422, str(e))
    if not _spawn(rid):
        reels._write_status(reels.reel_dir(rid), status="error", error="server busy: too many reels rendering, try again shortly")
        raise HTTPException(429, "too many reels are rendering right now; try again in a minute")
    return {"id": rid, "status": "queued"}


@router.get("")
def list_all():
    return [{k: s.get(k) for k in ("id", "status", "stage", "progress", "created", "error")} | {"topic": s["request"]["topic"], "style": s["request"]["style"]}
            for s in reels.list_reels()]


def _get(rid: str) -> dict:
    try:
        s = reels.get_status(rid)
    except reels.ReelError:
        s = None
    if not s:
        raise HTTPException(404, "reel not found")
    return s


@router.get("/{rid}")
def status(rid: str):
    s = _get(rid)
    s.pop("user_id", None)
    return s


def _file(rid: str, name: str, media_type: str, download: str | None = None):
    s = _get(rid)
    if s["status"] != "done":
        raise HTTPException(409, f"reel is {s['status']}")
    p = reels.reel_dir(rid) / name
    if not p.exists():
        raise HTTPException(404, "file missing")
    return FileResponse(p, media_type=media_type, filename=download)


@router.get("/{rid}/video")
def video(rid: str, download: bool = False):
    return _file(rid, "reel.mp4", "video/mp4", f"reel-{rid}.mp4" if download else None)


@router.get("/{rid}/cover")
def cover(rid: str):
    return _file(rid, "cover.jpg", "image/jpeg")


@router.get("/{rid}/caption")
def caption(rid: str):
    return _file(rid, "caption.txt", "text/plain")
