"""All ORM models. One file keeps relationships and the status enum in one place."""
import enum
from datetime import datetime, timezone

from sqlalchemy import (JSON, Boolean, DateTime, Enum, Float, ForeignKey, Integer,
                        String, Text, UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


def now() -> datetime:
    return datetime.now(timezone.utc)


class LessonStatus(str, enum.Enum):
    TOPIC_PENDING = "TOPIC_PENDING"
    RESEARCHING = "RESEARCHING"
    SCRIPT_GENERATED = "SCRIPT_GENERATED"
    TECHNICAL_REVIEW = "TECHNICAL_REVIEW"
    SCRIPT_APPROVED = "SCRIPT_APPROVED"
    ASSETS_GENERATING = "ASSETS_GENERATING"
    ASSETS_READY = "ASSETS_READY"
    RENDERING = "RENDERING"
    QUALITY_CHECK = "QUALITY_CHECK"
    APPROVAL_PENDING = "APPROVAL_PENDING"
    APPROVED = "APPROVED"
    SCHEDULED = "SCHEDULED"
    PUBLISHED = "PUBLISHED"
    FAILED = "FAILED"


# Ordered happy path; used for resume-from-last-successful-stage.
STATUS_ORDER = [s for s in LessonStatus if s != LessonStatus.FAILED]


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class User(Base, TimestampMixin):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32), default="admin")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Course(Base, TimestampMixin):
    __tablename__ = "courses"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    language: Mapped[str] = mapped_column(String(32), default="English")
    difficulty: Mapped[str] = mapped_column(String(32), default="Intermediate")
    target_audience: Mapped[str] = mapped_column(String(255), default="")
    domain: Mapped[str] = mapped_column(String(48), default="general")
    videos_per_week: Mapped[int] = mapped_column(Integer, default=3)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=8)
    learning_objectives: Mapped[list] = mapped_column(JSON, default=list)
    prerequisites: Mapped[list] = mapped_column(JSON, default=list)
    modules: Mapped[list["Module"]] = relationship(back_populates="course", cascade="all,delete-orphan", order_by="Module.position")


class Module(Base, TimestampMixin):
    __tablename__ = "modules"
    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    course: Mapped[Course] = relationship(back_populates="modules")
    lessons: Mapped[list["Lesson"]] = relationship(back_populates="module", cascade="all,delete-orphan", order_by="Lesson.position")


class Lesson(Base, TimestampMixin):
    __tablename__ = "lessons"
    __table_args__ = (UniqueConstraint("module_id", "title", name="uq_lesson_module_title"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    module_id: Mapped[int] = mapped_column(ForeignKey("modules.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    title: Mapped[str] = mapped_column(String(255))
    summary: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(64), default="")
    estimated_minutes: Mapped[int] = mapped_column(Integer, default=8)
    dependencies: Mapped[list] = mapped_column(JSON, default=list)
    exercises: Mapped[list] = mapped_column(JSON, default=list)
    knowledge_checks: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[LessonStatus] = mapped_column(Enum(LessonStatus), default=LessonStatus.TOPIC_PENDING, index=True)
    last_good_status: Mapped[str] = mapped_column(String(32), default="TOPIC_PENDING")
    # quick draft: script -> voice -> video with NO source research and NO fact-check review. Stamped on every frame, can never be approved or published.
    draft: Mapped[bool] = mapped_column(Boolean, default=False)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str] = mapped_column(Text, default="")
    module: Mapped[Module] = relationship(back_populates="lessons")
    scripts: Mapped[list["LessonScript"]] = relationship(back_populates="lesson", cascade="all,delete-orphan", order_by="LessonScript.version")


class LessonScript(Base, TimestampMixin):
    """Versioned. Each regeneration/edit appends a new version (version history)."""
    __tablename__ = "lesson_scripts"
    __table_args__ = (UniqueConstraint("lesson_id", "version", name="uq_script_version"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    content: Mapped[dict] = mapped_column(JSON)
    generated_by: Mapped[str] = mapped_column(String(64), default="")
    content_hash: Mapped[str] = mapped_column(String(64), default="")
    change_note: Mapped[str] = mapped_column(Text, default="")  # why this revision exists (review fix, manual edit, ...)
    lesson: Mapped[Lesson] = relationship(back_populates="scripts")


class ResearchSource(Base, TimestampMixin):
    __tablename__ = "research_sources"
    id: Mapped[int] = mapped_column(primary_key=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(32))
    identifier: Mapped[str] = mapped_column(String(128), default="")
    url: Mapped[str] = mapped_column(String(1024))
    excerpt: Mapped[str] = mapped_column(Text, default="")
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    # provenance (Feature A). `verified` is True only when status == "ok" (content really retrieved and non-trivial).
    title: Mapped[str] = mapped_column(String(512), default="")
    publisher: Mapped[str] = mapped_column(String(128), default="")
    category: Mapped[str] = mapped_column(String(32), default="")
    published_at: Mapped[str] = mapped_column(String(64), default="")
    section: Mapped[str] = mapped_column(String(512), default="")
    content_hash: Mapped[str] = mapped_column(String(64), default="")
    status: Mapped[str] = mapped_column(String(32), default="pending")
    full_text: Mapped[str] = mapped_column(Text, default="")


class Storyboard(Base, TimestampMixin):
    __tablename__ = "storyboards"
    __table_args__ = (UniqueConstraint("lesson_id", "version", name="uq_storyboard_version"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    data: Mapped[dict] = mapped_column(JSON)
    scenes: Mapped[list["Scene"]] = relationship(back_populates="storyboard", cascade="all,delete-orphan")


class Scene(Base, TimestampMixin):
    __tablename__ = "scenes"
    id: Mapped[int] = mapped_column(primary_key=True)
    storyboard_id: Mapped[int] = mapped_column(ForeignKey("storyboards.id", ondelete="CASCADE"), index=True)
    scene_id: Mapped[str] = mapped_column(String(64))
    position: Mapped[int] = mapped_column(Integer, default=0)
    type: Mapped[str] = mapped_column(String(32))
    duration_seconds: Mapped[float] = mapped_column(Float)
    narration: Mapped[str] = mapped_column(Text)
    on_screen_text: Mapped[str] = mapped_column(Text, default="")
    transition: Mapped[str] = mapped_column(String(32), default="fade")
    storyboard: Mapped[Storyboard] = relationship(back_populates="scenes")


class GeneratedAsset(Base, TimestampMixin):
    __tablename__ = "generated_assets"
    __table_args__ = (UniqueConstraint("lesson_id", "scene_id", "kind", "content_hash", name="uq_asset_idem"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"), index=True)
    scene_id: Mapped[str] = mapped_column(String(64), default="")
    kind: Mapped[str] = mapped_column(String(32))
    path: Mapped[str] = mapped_column(String(1024))
    content_hash: Mapped[str] = mapped_column(String(64))
    meta: Mapped[dict] = mapped_column(JSON, default=dict)


class VoiceGeneration(Base, TimestampMixin):
    __tablename__ = "voice_generations"
    id: Mapped[int] = mapped_column(primary_key=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"), index=True)
    scene_id: Mapped[str] = mapped_column(String(64))
    provider: Mapped[str] = mapped_column(String(32))
    path: Mapped[str] = mapped_column(String(1024))
    duration_seconds: Mapped[float] = mapped_column(Float)
    text_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="done")


class AvatarGeneration(Base, TimestampMixin):
    __tablename__ = "avatar_generations"
    id: Mapped[int] = mapped_column(primary_key=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"), index=True)
    scene_id: Mapped[str] = mapped_column(String(64))
    provider: Mapped[str] = mapped_column(String(32))
    path: Mapped[str] = mapped_column(String(1024), default="")
    status: Mapped[str] = mapped_column(String(16), default="done")
    external_id: Mapped[str] = mapped_column(String(128), default="")


class VideoRender(Base, TimestampMixin):
    __tablename__ = "video_renders"
    id: Mapped[int] = mapped_column(primary_key=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"), index=True)
    format: Mapped[str] = mapped_column(String(16), default="long")
    engine: Mapped[str] = mapped_column(String(16), default="ffmpeg")
    status: Mapped[str] = mapped_column(String(16), default="queued")
    progress: Mapped[float] = mapped_column(Float, default=0)
    video_path: Mapped[str] = mapped_column(String(1024), default="")
    srt_path: Mapped[str] = mapped_column(String(1024), default="")
    manifest_path: Mapped[str] = mapped_column(String(1024), default="")
    duration_seconds: Mapped[float] = mapped_column(Float, default=0)
    sha256: Mapped[str] = mapped_column(String(64), default="")
    error: Mapped[str] = mapped_column(Text, default="")


class Thumbnail(Base, TimestampMixin):
    __tablename__ = "thumbnails"
    id: Mapped[int] = mapped_column(primary_key=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"), index=True)
    path: Mapped[str] = mapped_column(String(1024))
    text: Mapped[str] = mapped_column(String(255), default="")


class QualityCheck(Base, TimestampMixin):
    __tablename__ = "quality_checks"
    id: Mapped[int] = mapped_column(primary_key=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"), index=True)
    passed: Mapped[bool] = mapped_column(Boolean, default=False)
    report: Mapped[dict] = mapped_column(JSON, default=dict)


class Approval(Base, TimestampMixin):
    __tablename__ = "approvals"
    id: Mapped[int] = mapped_column(primary_key=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"), index=True)
    stage: Mapped[str] = mapped_column(String(16), default="video")  # script | video
    decision: Mapped[str] = mapped_column(String(16))  # APPROVED | REJECTED
    reviewer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")


class YouTubePublication(Base, TimestampMixin):
    __tablename__ = "youtube_publications"
    id: Mapped[int] = mapped_column(primary_key=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"), index=True)
    render_id: Mapped[int] = mapped_column(ForeignKey("video_renders.id"))
    youtube_video_id: Mapped[str] = mapped_column(String(32), default="")
    privacy: Mapped[str] = mapped_column(String(16), default="private")
    publish_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(16), default="draft")


class Analytics(Base, TimestampMixin):
    __tablename__ = "analytics"
    id: Mapped[int] = mapped_column(primary_key=True)
    publication_id: Mapped[int] = mapped_column(ForeignKey("youtube_publications.id", ondelete="CASCADE"), index=True)
    views: Mapped[int] = mapped_column(Integer, default=0)
    likes: Mapped[int] = mapped_column(Integer, default=0)
    comments: Mapped[int] = mapped_column(Integer, default=0)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class WorkflowLog(Base):
    """Execution log + audit trail (actor/action) in one append-only table."""
    __tablename__ = "workflow_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    lesson_id: Mapped[int | None] = mapped_column(ForeignKey("lessons.id", ondelete="SET NULL"), nullable=True, index=True)
    stage: Mapped[str] = mapped_column(String(48))
    level: Mapped[str] = mapped_column(String(16), default="info")
    message: Mapped[str] = mapped_column(Text, default="")
    actor: Mapped[str] = mapped_column(String(128), default="system")
    idempotency_key: Mapped[str] = mapped_column(String(128), default="", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ReviewRun(Base, TimestampMixin):
    """One execution of a review stage on one script version. At most one `running` row per lesson."""
    __tablename__ = "review_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"), index=True)
    script_version: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(24), default="technical")  # technical | claims
    reviewer_model: Mapped[str] = mapped_column(String(128), default="")
    simulated: Mapped[bool] = mapped_column(Boolean, default=False)  # True = mock LLM; never counts in production
    status: Mapped[str] = mapped_column(String(16), default="running")  # running | completed | failed
    error: Mapped[str] = mapped_column(Text, default="")
    summary: Mapped[dict] = mapped_column(JSON, default=dict)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TechnicalClaim(Base, TimestampMixin):
    __tablename__ = "technical_claims"
    id: Mapped[int] = mapped_column(primary_key=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"), index=True)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("review_runs.id", ondelete="CASCADE"), nullable=True, index=True)
    script_version: Mapped[int] = mapped_column(Integer)
    section: Mapped[str] = mapped_column(String(64), default="")
    text: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(32), default="general")
    critical: Mapped[bool] = mapped_column(Boolean, default=False)
    locations: Mapped[list] = mapped_column(JSON, default=list)  # every script section where this statement appears (after de-duplication)
    status: Mapped[str] = mapped_column(String(24), default="needs_human_review")
    source_ids: Mapped[list] = mapped_column(JSON, default=list)
    evidence_excerpt: Mapped[str] = mapped_column(Text, default="")
    evidence_section: Mapped[str] = mapped_column(String(512), default="")
    reviewer_notes: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    needs_human: Mapped[bool] = mapped_column(Boolean, default=True)
    human_decision: Mapped[str] = mapped_column(String(16), default="")  # "" | accepted | rejected
    human_note: Mapped[str] = mapped_column(Text, default="")


class ReviewFinding(Base, TimestampMixin):
    __tablename__ = "review_findings"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("review_runs.id", ondelete="CASCADE"), index=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"), index=True)
    script_version: Mapped[int] = mapped_column(Integer)
    severity: Mapped[str] = mapped_column(String(16))  # critical | high | medium | low | info
    category: Mapped[str] = mapped_column(String(32))
    section: Mapped[str] = mapped_column(String(64), default="")
    problem_text: Mapped[str] = mapped_column(Text, default="")
    explanation: Mapped[str] = mapped_column(Text, default="")
    evidence: Mapped[str] = mapped_column(Text, default="")
    recommended_correction: Mapped[str] = mapped_column(Text, default="")
    objective: Mapped[str] = mapped_column(Text, default="")  # the learning objective a teaching finding says is not met (verified against the script)
    policy_note: Mapped[str] = mapped_column(Text, default="")  # why the server decided this finding blocks or is advisory
    blocks_approval: Mapped[bool] = mapped_column(Boolean, default=False)
    # open | accepted (correction applied -> new revision) | rejected (finding dismissed with a reason) | waived (blocking finding accepted by a human)
    status: Mapped[str] = mapped_column(String(16), default="open", index=True)
    decided_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    decision_note: Mapped[str] = mapped_column(Text, default="")
    applied_version: Mapped[int | None] = mapped_column(Integer, nullable=True)


class QualityGateResult(Base, TimestampMixin):
    __tablename__ = "quality_gate_results"
    id: Mapped[int] = mapped_column(primary_key=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"), index=True)
    stage: Mapped[str] = mapped_column(String(16))  # script | pre_tts
    script_version: Mapped[int] = mapped_column(Integer)
    storyboard_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    passed: Mapped[bool] = mapped_column(Boolean, default=False)
    checks: Mapped[list] = mapped_column(JSON, default=list)
