"""Strict Pydantic schemas for LLM output. Malformed output is rejected, never repaired silently."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.animation import AnimationSpec
from app.schemas.visualization import Visualization

SceneType = Literal["instructor", "slide", "diagram", "code", "terminal", "browser", "quiz", "summary"]
Transition = Literal["fade", "slide", "wipe", "zoom", "none"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------- curriculum ----------
class CurriculumRequest(Strict):
    course_name: str = Field(min_length=3, max_length=200)
    language: str = "English"
    difficulty: Literal["Beginner", "Intermediate", "Advanced"] = "Intermediate"
    domain: str = "general"  # key in services.domains.DOMAINS
    target_audience: str = "Learners"
    videos_per_week: int = Field(3, ge=1, le=14)
    duration_minutes: int = Field(8, ge=5, le=25)


class LessonOutline(Strict):
    title: str = Field(min_length=3)
    summary: str
    estimated_minutes: int = Field(ge=1, le=30)
    dependencies: list[str] = []
    practical_exercises: list[str] = []
    knowledge_checks: list[str] = []


class ModuleOutline(Strict):
    title: str
    description: str
    lessons: list[LessonOutline] = Field(min_length=1)


class Curriculum(Strict):
    description: str
    learning_objectives: list[str] = Field(min_length=1)
    prerequisites: list[str]
    modules: list[ModuleOutline] = Field(min_length=1)

    @model_validator(mode="after")
    def deps_exist(self):
        titles = {l.title for m in self.modules for l in m.lessons}
        for m in self.modules:
            for l in m.lessons:
                missing = [d for d in l.dependencies if d not in titles]
                if missing:
                    raise ValueError(f"lesson '{l.title}' depends on unknown lessons {missing}")
        return self


# ---------- lesson script ----------
class Reference(Strict):
    title: str
    url: str


class QuizQuestion(Strict):
    question: str
    options: list[str] = Field(min_length=2)
    answer_index: int = Field(ge=0)

    @model_validator(mode="after")
    def in_range(self):
        if self.answer_index >= len(self.options):
            raise ValueError("answer_index out of range")
        return self


class LessonScriptData(Strict):
    title: str
    hook: str
    introduction: str
    learning_objectives: list[str] = Field(min_length=1)
    technical_explanation: str
    practical_demonstration: str
    diagrams: list[str] = Field(description="Mermaid sources")
    real_world_applications: str
    defensive_recommendations: str
    common_mistakes: list[str]
    knowledge_check: list[QuizQuestion] = Field(min_length=1)
    summary: str
    references: list[Reference]
    unverified_claims: list[str] = Field(default_factory=list, description="Facts needing human verification")


# ---------- storyboard ----------
class Scene(Strict):
    scene_id: str = Field(pattern=r"^scene_\d{3}$")
    type: SceneType
    duration_seconds: float = Field(ge=2, le=120)
    narration: str = Field(min_length=1)
    visual_description: str
    on_screen_text: str = ""
    asset_requirements: list[str] = []
    transition: Transition = "fade"
    # Type-specific payload. Rendering reads these; they are data, never executed.
    code: str | None = None
    language: str | None = None
    terminal_lines: list[str] | None = None
    mermaid: str | None = None
    bullets: list[str] | None = None
    recording_asset: str | None = Field(None, description="Filename of an attached lab recording")
    mode3d: Literal["flow", "stack"] | None = Field(None, description="Render this scene as a 3D explanation (Remotion engine). flow: from `mermaid`; stack: layers from `bullets`")
    highlight_layer: int | None = Field(None, ge=0, description="stack mode: index of the layer to emphasise")
    quiz_answer: int | None = Field(None, ge=0, le=7, description="quiz scenes: index into `bullets` of the correct option; enables answer feedback animation")
    visualization: Visualization | None = Field(None, description="Optional typed technical visualization (diagram scenes, Remotion engine); `mermaid` stays as the flat fallback")
    animation: AnimationSpec | None = Field(None, description="Optional declarative motion metadata (Remotion engine); absent = profile defaults")

    @model_validator(mode="after")
    def check_payload(self):
        """Every scene type must carry what its renderer needs; catching it here makes the LLM retry with the error."""
        need = {"diagram": ("mermaid", self.mermaid), "code": ("code", self.code), "terminal": ("terminal_lines", self.terminal_lines)}
        if self.type in need:
            field, value = need[self.type]
            if not value or (isinstance(value, str) and not value.strip()):
                raise ValueError(f"{self.type} scene needs non-empty `{field}`")
        if self.type in ("slide", "quiz", "summary") and not self.bullets:
            raise ValueError(f"{self.type} scene needs `bullets`")
        if self.quiz_answer is not None and (self.type != "quiz" or self.quiz_answer >= len(self.bullets or [])):
            raise ValueError("quiz_answer must index a bullet of a quiz scene")
        return self

    @model_validator(mode="after")
    def check_3d(self):
        if self.mode3d == "flow" and not self.mermaid:
            raise ValueError("mode3d=flow needs `mermaid`")
        if self.mode3d == "stack":
            if not self.bullets or len(self.bullets) < 2:
                raise ValueError("mode3d=stack needs >= 2 `bullets` (layers, top to bottom)")
            if self.highlight_layer is not None and self.highlight_layer >= len(self.bullets):
                raise ValueError("highlight_layer out of range")
        return self

    @field_validator("narration", "on_screen_text")
    @classmethod
    def no_ctrl(cls, v: str) -> str:
        if any(ord(c) < 32 and c not in "\n\t" for c in v):
            raise ValueError("control characters not allowed")
        return v


class StoryboardData(Strict):
    lesson_title: str
    scenes: list[Scene] = Field(min_length=2)

    @model_validator(mode="after")
    def unique_ordered(self):
        ids = [s.scene_id for s in self.scenes]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate scene_id")
        if ids != sorted(ids):
            raise ValueError("scenes must be ordered by scene_id")
        return self

    @property
    def total_seconds(self) -> float:
        return sum(s.duration_seconds for s in self.scenes)


class YouTubeMetadata(Strict):
    titles: list[str] = Field(min_length=3, max_length=3)
    description: str
    chapters: list[tuple[str, str]]  # (timestamp, label)
    tags: list[str]
    thumbnail_text: str = Field(max_length=40)
    thumbnail_layout: str
    category_id: str = "27"  # Education
    disclaimer: str
