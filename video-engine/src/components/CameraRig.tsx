import React from "react";
import { useCurrentFrame } from "remotion";
import { Camera } from "../utils/types";

/** Slow, small camera moves (at most ~4% scale / 40px pan over the whole scene) - enough to feel alive, never enough to distract. */
export const CameraRig: React.FC<{ camera: Camera; frames: number; children: React.ReactNode }> = ({ camera, frames, children }) => {
  const f = useCurrentFrame();
  const k = Math.min(1, f / Math.max(1, frames));
  const e = k * k * (3 - 2 * k); // smoothstep
  const t = camera === "push_in" ? `scale(${1 + 0.04 * e})` : camera === "pull_out" ? `scale(${1.04 - 0.04 * e})` : camera === "pan_left" ? `translateX(${-40 * e}px)` : camera === "pan_right" ? `translateX(${40 * e}px)` : "none";
  return <div style={{ position: "absolute", inset: 0, transform: t, transformOrigin: "50% 45%" }}>{children}</div>;
};
