# Motion engine

The Remotion render path draws every scene as deterministic, narration-synchronised motion graphics. The ffmpeg engine
(Pillow PNGs) is unchanged and remains the default; it ignores all animation metadata.

## Data flow

```
LLM storyboard (Scene + optional `animation`, `visualization`, `quiz_answer`)     schemas/content.py, animation.py, visualization.py
        │  strict Pydantic; invalid optional blocks are DROPPED for LLM output (SectionScene), rejected everywhere else
        ▼
voice synthesis → <scene>.wav + <scene>.timing.json (real sentence boundaries)      services/narration.py
        ▼
animation_sync.resolve_events(scene, timing, audio_s, fps, frames)                  services/animation_sync.py
        │  → [{target, action, frame, effect, duration_frames, easing, direction, basis}]   (pure function, unit-tested)
        ▼
remotion_adapter.render_long  → props JSON (events, motion, layout, visualization)  workers/remotion_adapter.py
        ▼
video-engine: MotionProvider → useReveal / useStepper → components                  video-engine/src
        ▼
ffmpeg mux (SRT) → renderer.verify (codec, 1920x1080, 30fps, A/V drift, full decode) → quality gate (unchanged)
```

## Narration synchronisation

Timing quality is recorded per event in `basis`:

| basis | meaning |
|---|---|
| `sentence` | event lands on a measured sentence boundary (each sentence is synthesised separately, so these are exact) |
| `word_est` | a word inside a measured sentence; position interpolated by character length. **Not forced alignment.** |
| `scene_est` | no `timing.json`: sentences spread over the audio duration by character count |
| `cadence` | `narration_sync.mode = "none"`: fixed 0.8 s interval from scene start |

Anchors per step: `at_word`, `at_phrase` (case/punctuation-insensitive), `at_fraction`, `at_seconds` (one at most). An anchor that
cannot be resolved (phrase absent, word index too large) falls back to automatic placement and adds a warning to
`render_manifest.json → animation_warnings`. Visuals lead the spoken word by `lead_seconds` (default 0.15 s).

A scene with **no** `animation` still gets audio-synced reveals: bullets/lines/nodes/steps are spread over sentence starts.
So lessons generated before this feature render with synced motion too.

## Safety

Animation and visualization metadata is closed enums, bounded numbers, short identifiers and hex strings. There is no field
that carries code, CSS or JSX; `extra="forbid"` rejects unknown keys. Typed visualization data is *what to teach*; the
components own all drawing and simulate the mechanics themselves (heap chunk sizes, which bytes of an overflow reach saved RBP/RET).

## Components (`video-engine/src/components`)

- typography: `AnimatedTitle`, `StaggeredText`, `KineticTypography`, `HighlightedKeywords`, `AnimatedBulletList`, `LowerThird`
- diagrams: `AnimatedFlowchart` (from `mermaid_lite.layout_payload`), `AnimatedArchitecture`, `AnimatedNetwork`, `AnimatedProcessFlow`, `AnimatedTimeline`
- code/terminal: `CodeTypingAnimation`, `SyntaxHighlightedCode`, `ActiveLineHighlighter`, `TerminalWindow` (`TerminalCommandAnimation`, `TerminalOutputAnimation`), `CursorAnimation`, `BrowserInteractionAnimation`
- security (`visualization.kind`): `buffer_overflow`, `stack_frames`, `heap`, `assembly` (+`RegisterVisualization`), `control_flow`, `packet_flow`, `lifecycle` (`ProcessExecutionAnimation`), `layout` (ELF / PE / process memory)

All motion is a pure function of the frame number (`motion/index.tsx`): `interpolate`/`spring`, no CSS transitions, no timers, so frames
render identically in any order and in headless Chrome. Fonts (Inter, JetBrains Mono) are bundled via `@fontsource` and the render waits for them.

## Try it

```
cd backend
.venv/bin/python -m app.cli.motion_samples                 # all samples -> storage/motion_samples/<name>/render/lesson.mp4
.venv/bin/python -m app.cli.motion_samples --only buffer_overflow --stills 3,9,15
.venv/bin/python -m pytest tests/test_animation.py tests/test_motion_render.py
```

## Known limits

- Word timing is estimated inside measured sentences (see above). True word alignment would need a forced aligner.
- 30 fps only. `renderer.verify` (the quality gate) requires 30 fps; 60 fps would need the gate and the adapter's `FPS` changed together.
- `transition_config.kind` is honoured; `duration_frames`/`direction` are validated but not yet applied (the overlap length is global so subtitle timing stays exact).
- Applied by the engine today: `animation_profile` (travel distance), `camera_movement`, `entrance_animation`, `animation_easing/duration/delay/direction`,
  `narration_sync`, per-step `show`/`reveal`/`hide`. **Stored and validated but not yet rendered:** `exit_animation`, `emphasis_animation`, and the
  `highlight`/`pulse`/`focus`/`step` step actions (`useEmphasis` exists but no component consumes it yet).
- Library components with no storyboard data source yet (rendered only by the QA `Gallery` composition): `StaggeredText`, `HighlightedKeywords`
  (keyword timing is not wired to narration), `AnimatedArchitecture`, `AnimatedNetwork`, `AnimatedProcessFlow`, `AnimatedTimeline`, `SyntaxHighlightedCode`.
  `RegisterVisualization` is used inside the `assembly` visualization; there is no standalone registers kind.
- Heap/stack/overflow sizes are bounded (e.g. buffer 8-256 B, 5 frames, 10 heap ops) so layouts always fit the 1920x1080 content area.
- GSAP / Framer Motion are intentionally not used (wall-clock animation libraries are non-deterministic under Remotion's parallel frame rendering).
- Visualizations are illustrative teaching models (glibc-style heap, typical x86-64 frame layout), not a debugger.
