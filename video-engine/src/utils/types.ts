export type SceneType = "instructor" | "slide" | "diagram" | "code" | "terminal" | "browser" | "quiz" | "summary";
/** One resolved, frame-numbered animation event (produced by backend/app/services/animation_sync.py). Frames are scene-local. */
export interface AnimEvent {
  target: string; action: "show" | "hide" | "highlight" | "reveal" | "focus" | "step" | "pulse"; frame: number;
  effect: string | null; duration_frames: number; easing: Easing; direction: Direction;
  basis: "sentence" | "word_est" | "scene_est" | "cadence";
}
export type Easing = "linear" | "ease_in" | "ease_out" | "ease_in_out" | "spring" | "spring_soft" | "spring_snappy";
export type Direction = "up" | "down" | "left" | "right" | "none";
export type Profile = "minimal" | "standard" | "expressive";
export type Camera = "none" | "push_in" | "pull_out" | "pan_left" | "pan_right";
export interface SceneMotion { profile: Profile; camera: Camera; exit: "none" | "fade" | "slide" | "scale"; emphasis: "none" | "pulse" | "underline" | "highlight" | "outline" }
export interface Layout { direction: "LR" | "TD"; nodes: { id: string; label: string; shape: string; x: number; y: number }[]; edges: { a: string; b: string; label: string }[]; w: number; h: number; bw: number; bh: number }
/** typed technical visualizations (mirror of backend/app/schemas/visualization.py) */
export type Viz =
  | { kind: "stack_frames"; arch: "x86_64" | "x86"; frames: { function: string; args: string[]; locals: { name: string; size: number; note: string }[]; return_address: string; note: string }[] }
  | { kind: "buffer_overflow"; arch: "x86_64" | "x86"; buffer_name: string; buffer_size: number; input_length: number; fill_byte: string; original_return: string; stack_canary: boolean }
  | { kind: "heap"; ops: { op: "malloc" | "free"; chunk: string; size: number | null; note: string }[] }
  | { kind: "assembly"; registers: string[]; instructions: { addr: string; text: string; comment: string }[]; steps: { line: number; set: { reg: string; value: string }[]; note: string }[] }
  | { kind: "control_flow"; blocks: { id: string; lines: string[] }[]; edges: { a: string; b: string; label: string }[]; path: string[] }
  | { kind: "packet_flow"; nodes: { id: string; label: string }[]; packets: { src: string; dst: string; label: string; detail: string }[] }
  | { kind: "lifecycle"; stages: { label: string; detail: string }[] }
  | { kind: "layout"; format: "elf" | "pe" | "process"; regions: { name: string; range: string; flags: string; note: string }[] };

export interface SceneProps {
  scene_id: string; type: SceneType; narration: string; on_screen_text: string; transition: "fade" | "slide" | "wipe" | "zoom" | "none";
  code?: string | null; language?: string | null; terminal_lines?: string[] | null; bullets?: string[] | null; brand?: string;
  /** Pre-rendered SVG file for diagram scenes (served from publicDir) */
  svg?: string | null;
  /** Laid-out flowchart (positions from mermaid_lite.layout) for the animated diagram; svg stays as the fallback */
  layout?: Layout | null;
  quiz_answer?: number | null;
  visualization?: Viz | null;
  mode3d?: "flow" | "stack" | null; highlight_layer?: number | null;
  graph3d?: { nodes: { id: string; label: string; shape: string; x: number; y: number; z: number; layer: number }[]; edges: { a: string; b: string; label: string }[] } | null;
  recording?: string | null; // mp4 filename in publicDir (lab recording or avatar clip)
  portrait?: string | null;
  audio?: string | null; // wav filename in publicDir (absent in still/preview renders)
  frames: number; // scene length in frames (>= audio length)
  /** animation: absent on lessons rendered before the motion engine; every component then falls back to fully visible */
  events?: AnimEvent[]; motion?: SceneMotion;
  /** spoken words with seconds relative to scene start (estimated inside measured sentences), used by word-level components */
  words?: { text: string; start: number; end: number }[];
}
export interface Cue { start: number; end: number; text: string } // seconds on the final timeline
export interface LessonProps { title: string; fps: number; transitionFrames: number; scenes: SceneProps[]; cues: Cue[]; music?: string | null; shorts?: boolean }
export const defaultProps: LessonProps = { title: "Preview", fps: 30, transitionFrames: 15, scenes: [], cues: [], music: null };
