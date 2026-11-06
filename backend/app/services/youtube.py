"""YouTube Data API v3 integration. Real OAuth + resumable upload; refuses to run without credentials or approval.
Default privacy is private. Nothing is ever faked: absent credentials raise YouTubeNotConfigured."""
import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Lesson, LessonStatus as S, Thumbnail, VideoRender, YouTubePublication
from app.services import pipeline
from app.services.storage import get_storage

SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube.readonly"]


class YouTubeNotConfigured(RuntimeError):
    pass


class NotApproved(RuntimeError):
    pass


def status() -> dict:
    s = get_settings()
    secrets = bool(s.youtube_client_secrets and Path(s.youtube_client_secrets).exists())
    token = Path(s.youtube_token_file).exists()
    return {"client_secrets_configured": secrets, "authorized": token, "ready_for_oauth": secrets and not token, "ready_to_upload": secrets and token}


def auth_url() -> tuple[str, str]:
    from google_auth_oauthlib.flow import Flow
    s = get_settings()
    if not (s.youtube_client_secrets and Path(s.youtube_client_secrets).exists()):
        raise YouTubeNotConfigured("Set YOUTUBE_CLIENT_SECRETS to your OAuth client JSON (docs/YOUTUBE_SETUP.md)")
    flow = Flow.from_client_secrets_file(s.youtube_client_secrets, scopes=SCOPES, redirect_uri=s.youtube_redirect_uri)
    url, state = flow.authorization_url(access_type="offline", prompt="consent", include_granted_scopes="true")
    return url, state


def finish_auth(code: str) -> None:
    from google_auth_oauthlib.flow import Flow
    s = get_settings()
    flow = Flow.from_client_secrets_file(s.youtube_client_secrets, scopes=SCOPES, redirect_uri=s.youtube_redirect_uri)
    flow.fetch_token(code=code)
    p = Path(s.youtube_token_file)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(flow.credentials.to_json())
    p.chmod(0o600)


def _client():
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    s = get_settings()
    if not Path(s.youtube_token_file).exists():
        raise YouTubeNotConfigured("Not authorized. Complete OAuth at /api/youtube/oauth/start first.")
    creds = Credentials.from_authorized_user_file(s.youtube_token_file, SCOPES)
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def build_body(meta: dict, title_index: int, privacy: str, publish_at: datetime | None) -> dict:
    if privacy not in ("private", "unlisted", "public"):
        raise ValueError("bad privacy")
    desc = meta["description"] + "\n\nChapters:\n" + "\n".join(f"{t} {l}" for t, l in meta["chapters"]) + "\n\n" + meta["disclaimer"]
    body = {"snippet": {"title": meta["titles"][title_index][:100], "description": desc[:5000], "tags": meta["tags"][:15],
                        "categoryId": meta.get("category_id", "27"), "defaultLanguage": "en", "defaultAudioLanguage": "en"},
            "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False, "containsSyntheticMedia": True}}
    if publish_at:
        if publish_at.tzinfo is None:
            publish_at = publish_at.replace(tzinfo=timezone.utc)
        body["status"]["privacyStatus"] = "private"  # YouTube requires private + publishAt for scheduling
        body["status"]["publishAt"] = publish_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return body


def upload(db: Session, lesson: Lesson, meta: dict, title_index: int = 0, publish_at: datetime | None = None, privacy: str = "private") -> YouTubePublication:
    # Approval gate comes first and does not depend on credentials.
    if not pipeline.is_approved(db, lesson):
        raise NotApproved(f"lesson {lesson.id} is not APPROVED (status={lesson.status.value})")
    from app.services import qualitygate
    qualitygate.enforce(db, lesson, "pre_tts")  # raises GateBlocked: a lesson whose review/claims/length regressed cannot be uploaded
    dup = db.query(YouTubePublication).filter(YouTubePublication.lesson_id == lesson.id, YouTubePublication.youtube_video_id != "").first()
    if dup:
        return dup  # idempotent: never upload the same lesson twice
    st = get_storage()
    r = db.query(VideoRender).filter_by(lesson_id=lesson.id, status="done").order_by(VideoRender.id.desc()).first()
    if not r:
        raise NotApproved("no completed render")
    yt = _client()
    from googleapiclient.http import MediaFileUpload
    body = build_body(meta, title_index, privacy, publish_at)
    req = yt.videos().insert(part="snippet,status", body=body, media_body=MediaFileUpload(str(st.path(r.video_path)), chunksize=8 * 1024 * 1024, resumable=True))
    resp = None
    while resp is None:
        _, resp = req.next_chunk()
    vid = resp["id"]
    th = db.query(Thumbnail).filter_by(lesson_id=lesson.id).order_by(Thumbnail.id.desc()).first()
    if th:
        yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(str(st.path(th.path)))).execute()
    pub = YouTubePublication(lesson_id=lesson.id, render_id=r.id, youtube_video_id=vid, privacy=body["status"]["privacyStatus"],
                             publish_at=publish_at, metadata_json=body, status="scheduled" if publish_at else "uploaded")
    db.add(pub)
    pipeline.set_status(db, lesson, S.SCHEDULED if publish_at else S.APPROVED)
    pipeline.log(db, lesson, "youtube_upload", f"uploaded video {vid} as {pub.privacy}")
    db.commit()
    return pub


def collect_analytics(db: Session) -> int:
    from app.models import Analytics
    pubs = db.query(YouTubePublication).filter(YouTubePublication.youtube_video_id != "").all()
    if not pubs:
        return 0
    yt = _client()
    n = 0
    for i in range(0, len(pubs), 50):
        batch = pubs[i:i + 50]
        resp = yt.videos().list(part="statistics", id=",".join(p.youtube_video_id for p in batch)).execute()
        stats = {it["id"]: it["statistics"] for it in resp.get("items", [])}
        for p in batch:
            st_ = stats.get(p.youtube_video_id)
            if st_:
                db.add(Analytics(publication_id=p.id, views=int(st_.get("viewCount", 0)), likes=int(st_.get("likeCount", 0)),
                                 comments=int(st_.get("commentCount", 0))))
                n += 1
    db.commit()
    return n
