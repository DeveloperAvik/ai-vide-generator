from pydantic import BaseModel, Field, field_validator

STYLES = ("trending", "lofi", "educational", "motivational", "storytelling", "promo")
MUSIC = ("auto", "none", "lofi", "chill", "upbeat", "cinematic")


class ReelRequest(BaseModel):
    topic: str = Field(min_length=3, max_length=300)
    style: str = Field("trending", description="trending | lofi | educational | motivational | storytelling | promo")
    style_notes: str = Field("", max_length=400, description="Free-form direction, e.g. 'funny, Gen-Z slang' or 'for beginners'")
    duration_s: int = Field(30, ge=10, le=90, description="Target length. Instagram Reels allow up to 90 s.")
    voiceover: bool = True
    music: str = "auto"
    captions: bool = True

    @field_validator("style")
    @classmethod
    def _style(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in STYLES:
            raise ValueError(f"style must be one of {', '.join(STYLES)}")
        return v

    @field_validator("music")
    @classmethod
    def _music(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in MUSIC:
            raise ValueError(f"music must be one of {', '.join(MUSIC)}")
        return v

    @field_validator("topic", "style_notes")
    @classmethod
    def _strip(cls, v: str) -> str:
        return " ".join(v.split())


class ReelScene(BaseModel):
    headline: str = Field(max_length=60)  # short on-screen title
    narration: str = Field(min_length=3, max_length=400)
    photo_index: int | None = None  # which uploaded photo to show (0-based); None = automatic


class ReelPlan(BaseModel):
    title: str = Field(max_length=100)
    caption: str = Field("", max_length=2000)  # the Instagram post caption
    hashtags: list[str] = Field(default_factory=list, max_length=30)
    scenes: list[ReelScene] = Field(min_length=1, max_length=14)
