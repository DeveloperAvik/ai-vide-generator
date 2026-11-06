from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class LoginIn(BaseModel):
    email: str
    password: str = Field(min_length=1, max_length=256)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LessonOut(ORM):
    id: int
    module_id: int
    position: int
    title: str
    summary: str
    status: str
    retry_count: int
    last_error: str
    estimated_minutes: int
    draft: bool = False
    updated_at: datetime


class ModuleOut(ORM):
    id: int
    course_id: int
    title: str
    description: str
    position: int
    lessons: list[LessonOut] = []


class CourseOut(ORM):
    id: int
    name: str
    description: str
    difficulty: str
    language: str
    domain: str
    videos_per_week: int
    duration_minutes: int
    learning_objectives: list
    prerequisites: list
    created_at: datetime


class CourseDetail(CourseOut):
    modules: list[ModuleOut] = []


class QuickVideoIn(BaseModel):
    topic: str = Field(min_length=3, max_length=200)
    domain: str = "general"
    minutes: int = Field(5, ge=5, le=25)


class ApprovalIn(BaseModel):
    decision: str = Field(pattern="^(APPROVED|REJECTED)$")
    stage: str = Field("video", pattern="^(script|video)$")
    notes: str = Field("", max_length=2000)


class ScheduleIn(BaseModel):
    publish_at: datetime | None = None


class FindingDecisionIn(BaseModel):
    decision: str = Field(pattern="^(accept|reject|waive)$")  # accept = apply correction as a NEW script revision
    note: str = Field("", max_length=2000)
    correction: str | None = Field(None, max_length=1500)  # optional human-edited replacement text for `accept`


class ClaimDecisionIn(BaseModel):
    decision: str = Field(pattern="^(accepted|rejected)$")
    note: str = Field("", max_length=2000)
