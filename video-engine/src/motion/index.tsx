import React, { createContext, useContext, useMemo } from "react";
import { Easing as RE, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { AnimEvent, Direction, Easing, Profile, SceneProps } from "../utils/types";

/** All motion is a pure function of the frame number (no CSS transitions, no wall-clock timers), so frames render
 *  identically in any order and on any machine. */
export const easedProgress = (name: Easing, frame: number, start: number, dur: number, fps: number): number => {
  const f = frame - start;
  if (f <= 0) return 0;
  if (name.startsWith("spring")) {
    const config = name === "spring_soft" ? { damping: 200, stiffness: 80 } : name === "spring_snappy" ? { damping: 20, stiffness: 220, mass: 0.6 } : { damping: 200 };
    return spring({ frame: f, fps, config, durationInFrames: dur });
  }
  const t = Math.min(1, f / dur);
  const fn = name === "linear" ? (x: number) => x : name === "ease_in" ? RE.in(RE.cubic) : name === "ease_out" ? RE.out(RE.cubic) : RE.inOut(RE.cubic);
  return fn(t);
};

interface Ctx { events?: Map<string, AnimEvent[]>; profile: Profile }
const MotionCtx = createContext<Ctx>({ profile: "standard" });

export const MotionProvider: React.FC<{ scene: SceneProps; children: React.ReactNode }> = ({ scene, children }) => {
  const value = useMemo<Ctx>(() => {
    if (!scene.events) return { profile: scene.motion?.profile ?? "standard" };
    const m = new Map<string, AnimEvent[]>();
    for (const e of scene.events) m.set(e.target, [...(m.get(e.target) ?? []), e]);
    return { events: m, profile: scene.motion?.profile ?? "standard" };
  }, [scene]);
  return <MotionCtx.Provider value={value}>{children}</MotionCtx.Provider>;
};

const TRAVEL: Record<Profile, number> = { minimal: 0, standard: 36, expressive: 64 };
export const travel = (p: Profile) => TRAVEL[p];

const offset = (d: Direction, px: number, remaining: number) => {
  const v = px * remaining;
  return d === "up" ? `translateY(${v}px)` : d === "down" ? `translateY(${-v}px)` : d === "left" ? `translateX(${v}px)` : d === "right" ? `translateX(${-v}px)` : "none";
};

export interface Reveal { p: number; shown: boolean; start: number | null; style: React.CSSProperties; events: AnimEvent[] }

/** Progress (0..1) of a target's entrance, driven by its sync event. A target with no event is fully visible when the scene
 *  carries no events at all (old lessons / Studio preview), and stays hidden only if events exist but none address it. */
export const useReveal = (target: string, opts: { effect?: string; direction?: Direction } = {}): Reveal => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { events, profile } = useContext(MotionCtx);
  const list = events?.get(target) ?? [];
  const show = list.find((e) => e.action === "show" || e.action === "reveal");
  let p = 1, start: number | null = null, effect = opts.effect ?? "fade", direction = opts.direction ?? "up";
  if (events && show) {
    start = show.frame;
    p = Math.min(1, easedProgress(show.easing, frame, show.frame, show.duration_frames, fps));
    effect = show.effect ?? effect; direction = show.direction;
  }
  const hide = list.find((e) => e.action === "hide");
  if (hide && frame >= hide.frame) p = Math.max(0, 1 - easedProgress(hide.easing, frame, hide.frame, hide.duration_frames, fps));
  const rem = 1 - p;
  const style: React.CSSProperties = { opacity: Math.max(0, Math.min(1, p)) };
  const dist = travel(profile);
  if (effect === "slide") style.transform = offset(direction, dist, rem);
  else if (effect === "scale") style.transform = `scale(${0.94 + 0.06 * Math.min(1, p)})`;
  else if (effect === "wipe") style.clipPath = `inset(0 ${rem * 100}% 0 0)`;
  return { p, shown: p > 0.001, start, style, events: list };
};

/** frame at which a target was emphasised ("highlight"/"pulse"/"focus"), progress 0..1 while it is active, else 0 */
export const useEmphasis = (target: string): number => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { events } = useContext(MotionCtx);
  const e = events?.get(target)?.find((x) => x.action === "highlight" || x.action === "pulse" || x.action === "focus");
  return e ? Math.min(1, easedProgress("ease_out", frame, e.frame, Math.max(6, e.duration_frames), fps)) : 0;
};

/** index of the most recently revealed target among `${prefix}.0..n-1` (-1 if none yet) */
export const useActiveIndex = (prefix: string, n: number): number => {
  const frame = useCurrentFrame();
  const { events } = useContext(MotionCtx);
  if (!events) return n - 1;
  let active = -1;
  for (let i = 0; i < n; i++) {
    const s = events.get(`${prefix}.${i}`)?.find((e) => e.action === "show" || e.action === "reveal");
    if (s && frame >= s.frame) active = i;
  }
  return active;
};

export const useProfile = () => useContext(MotionCtx).profile;
export const useHasEvents = () => !!useContext(MotionCtx).events;
export const useStartFrame = (target: string): number | null => useContext(MotionCtx).events?.get(target)?.find((e) => e.action === "show" || e.action === "reveal")?.frame ?? null;

/** scene-local start frames of `${prefix}.0..n-1` (null where none); one context read instead of n hooks */
export const useStarts = (prefix: string, n: number): (number | null)[] => {
  const { events } = useContext(MotionCtx);
  return Array.from({ length: n }, (_, i) => events?.get(`${prefix}.${i}`)?.find((e) => e.action === "show" || e.action === "reveal")?.frame ?? null);
};

/** start frame of each named target (null = never scripted) */
export const useStartsOf = (targets: string[]): (number | null)[] => {
  const { events } = useContext(MotionCtx);
  return targets.map((t) => events?.get(t)?.find((e) => e.action === "show" || e.action === "reveal")?.frame ?? null);
};

/** Step-driven visualizations: `sp(i)` is how far step i has progressed (0..1, spring) and `active` the latest started step.
 *  Without events (old props / Studio preview) every step counts as done, so a static frame shows the final state. */
export const useStepper = (n: number) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const starts = useStarts("step", n);
  const active = useActiveIndex("step", n);
  const sp = (i: number, dur = 18) => (starts[i] === null ? (active >= i ? 1 : 0) : Math.min(1, easedProgress("spring", frame, starts[i] as number, dur, fps)));
  return { frame, fps, active, sp, starts };
};
