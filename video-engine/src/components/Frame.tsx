import React from "react";
import { useCurrentFrame, useVideoConfig } from "remotion";
import { AnimatedTitle } from "./typography";
import { T } from "../utils/theme";

/** Scene chrome: charcoal-navy ground with one very slow, low-contrast light drift (frame-driven, so it is deterministic) and a faint grid. */
export const Frame: React.FC<{ title: string; footer: string; children: React.ReactNode; hideTitle?: boolean }> = ({ title, footer, children, hideTitle }) => {
  const frame = useCurrentFrame(); const { fps } = useVideoConfig();
  const t = frame / fps;
  const dx = Math.sin(t / 6) * 60, dy = Math.cos(t / 8) * 30;
  return (
    <div style={{ position: "absolute", inset: 0, background: T.bg, fontFamily: T.sans, color: T.fg, overflow: "hidden" }}>
      <div style={{ position: "absolute", inset: -200, background: `radial-gradient(900px 600px at ${1300 + dx}px ${260 + dy}px, rgba(59,130,246,0.13), transparent 70%), radial-gradient(800px 600px at ${300 - dx}px ${980 - dy}px, rgba(34,211,238,0.06), transparent 70%)` }} />
      <div style={{ position: "absolute", inset: 0, backgroundImage: "linear-gradient(rgba(138,155,184,0.045) 1px, transparent 1px), linear-gradient(90deg, rgba(138,155,184,0.045) 1px, transparent 1px)", backgroundSize: "96px 96px" }} />
      <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: 8, background: `linear-gradient(${T.accent}, ${T.cyan})` }} />
      {hideTitle ? null : <AnimatedTitle text={title} />}
      {children}
      <div style={{ position: "absolute", left: T.margin, bottom: 36, fontSize: 20, color: T.dim, letterSpacing: 0.2 }}>{footer}</div>
    </div>
  );
};
