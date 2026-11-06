"""Declarative animation metadata for a Scene. Everything here is DATA: closed enums, bounded numbers and short
identifiers. The LLM never supplies JavaScript, JSX, CSS or free-form expressions; the Remotion components decide how each
enum value looks. Every field is optional so storyboards generated before this schema existed still validate and render."""
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Profile = Literal["minimal", "standard", "expressive"]
Easing = Literal["linear", "ease_in", "ease_out", "ease_in_out", "spring", "spring_soft", "spring_snappy"]
Direction = Literal["up", "down", "left", "right", "none"]
Entrance = Literal["none", "fade", "slide", "scale", "typewriter", "draw", "wipe"]
Exit = Literal["none", "fade", "slide", "scale"]
Emphasis = Literal["none", "pulse", "underline", "highlight", "outline"]
Camera = Literal["none", "push_in", "pull_out", "pan_left", "pan_right"]
Action = Literal["show", "hide", "highlight", "reveal", "focus", "step", "pulse"]
SyncMode = Literal["auto", "anchored", "none"]
TransitionKind = Literal["fade", "slide", "wipe", "none"]

# `bullet.2`, `node.api_gw`, `line.0`, `layer.1`, `field.saved_ret`: a kind and an optional id inside the scene's own payload
TARGET_RE = re.compile(r"^[a-z][a-z_]{0,23}(\.[A-Za-z0-9_\-]{1,32})?$")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NarrationSync(_Strict):
    """How animation events are tied to the spoken audio.
    auto     - the engine spreads the scene's content over the narration (sentence boundaries, else even fractions)
    anchored - each step's own anchor (at_word / at_phrase / at_fraction / at_seconds) decides; unresolved ones fall back to auto
    none     - events fire on a fixed cadence from scene start (the old behaviour)"""
    mode: SyncMode = "auto"
    lead_seconds: float = Field(0.15, ge=0, le=1.0, description="show a visual slightly BEFORE the word is spoken")


class AnimationStep(_Strict):
    target: str
    action: Action = "show"
    effect: Entrance | Emphasis | None = None
    duration: float | None = Field(None, ge=0.1, le=5.0)
    easing: Easing | None = None
    direction: Direction | None = None
    # at most one anchor; with none the step is placed by the `auto` rule
    at_word: int | None = Field(None, ge=0, le=2000)
    at_phrase: str | None = Field(None, min_length=2, max_length=80)
    at_fraction: float | None = Field(None, ge=0, le=1)
    at_seconds: float | None = Field(None, ge=0, le=600)

    @model_validator(mode="after")
    def check(self):
        if not TARGET_RE.match(self.target):
            raise ValueError(f"invalid animation target {self.target!r}")
        if sum(x is not None for x in (self.at_word, self.at_phrase, self.at_fraction, self.at_seconds)) > 1:
            raise ValueError("a step takes at most one of at_word / at_phrase / at_fraction / at_seconds")
        return self


class TransitionConfig(_Strict):
    kind: TransitionKind = "fade"
    duration_frames: int = Field(15, ge=0, le=45)
    direction: Direction = "none"


class AnimationSpec(_Strict):
    animation_profile: Profile = "standard"
    animation_sequence: list[AnimationStep] = Field(default_factory=list, max_length=40)
    animation_duration: float = Field(0.6, ge=0.1, le=5.0)
    animation_delay: float = Field(0.0, ge=0, le=10.0)
    animation_easing: Easing = "spring"
    animation_direction: Direction = "up"
    entrance_animation: Entrance = "fade"
    exit_animation: Exit = "none"
    emphasis_animation: Emphasis = "none"
    camera_movement: Camera = "none"
    narration_sync: NarrationSync = Field(default_factory=NarrationSync)
    transition_config: TransitionConfig | None = None

    @model_validator(mode="after")
    def unique_steps(self):
        seen = set()
        for s in self.animation_sequence:
            k = (s.target, s.action)
            if k in seen:
                raise ValueError(f"duplicate animation step {s.target}/{s.action}")
            seen.add(k)
        return self


def clean_animation(v):
    """For LLM output: animation metadata is decoration, so an invalid block is dropped (the scene then gets the profile
    default) instead of failing the whole section and costing an LLM retry. Returns a dict or None."""
    if v is None:
        return None
    try:
        return AnimationSpec.model_validate(v).model_dump()
    except Exception:  # noqa: BLE001 - any validation problem means "ignore the decoration"
        return None
