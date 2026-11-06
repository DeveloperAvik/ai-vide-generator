import React from "react";
import { interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { easedProgress, useActiveIndex, useProfile, useReveal, travel } from "../../motion";
import { Direction, Easing } from "../../utils/types";
import { T } from "../../utils/theme";

/** Shared timing props: `start` is a scene-local frame, `duration` in frames. Narration sync comes from `target` (events) or an explicit `start`. */
interface Timing { start?: number; duration?: number; easing?: Easing }

export const AnimatedTitle: React.FC<{ text: string; size?: number } & Timing> = ({ text, size = 56, start = 0, duration = 18, easing = "spring" }) => {
  const frame = useCurrentFrame(); const { fps } = useVideoConfig(); const profile = useProfile();
  const p = easedProgress(easing, frame, start, duration, fps);
  const bar = easedProgress("ease_out", frame, start + 6, 20, fps);
  return (
    <div style={{ position: "absolute", left: T.margin, top: 56, right: T.margin }}>
      <div style={{ fontSize: size, fontWeight: 700, letterSpacing: -1, lineHeight: 1.1, opacity: Math.min(1, p), transform: `translateY(${(1 - Math.min(1, p)) * travel(profile) * 0.5}px)` }}>{text}</div>
      <div style={{ marginTop: 18, height: 4, width: 200 * bar, borderRadius: 2, background: `linear-gradient(90deg, ${T.accent}, ${T.cyan})` }} />
    </div>
  );
};

/** words (or characters) rise in one after another */
export const StaggeredText: React.FC<{ text: string; by?: "word" | "char"; stagger?: number; style?: React.CSSProperties; direction?: Direction } & Timing> =
  ({ text, by = "word", stagger = 3, start = 0, duration = 14, easing = "spring", style, direction = "up" }) => {
    const frame = useCurrentFrame(); const { fps } = useVideoConfig(); const profile = useProfile();
    const units = by === "word" ? text.split(" ") : Array.from(text);
    return (
      <span style={style}>
        {units.map((u, i) => {
          const p = Math.min(1, easedProgress(easing, frame, start + i * stagger, duration, fps));
          const d = (1 - p) * travel(profile) * 0.6;
          const t = direction === "up" ? `translateY(${d}px)` : direction === "down" ? `translateY(${-d}px)` : direction === "left" ? `translateX(${d}px)` : direction === "right" ? `translateX(${-d}px)` : "none";
          return <span key={i} style={{ display: "inline-block", opacity: p, transform: t, whiteSpace: "pre" }}>{u}{by === "word" && i < units.length - 1 ? " " : ""}</span>;
        })}
      </span>
    );
  };

/** large statement lines revealed one at a time with a masked slide; the last line may carry the accent colour */
export const KineticTypography: React.FC<{ lines: string[]; size?: number; accentLast?: boolean; lineGap?: number } & Timing> =
  ({ lines, size = 88, accentLast = true, lineGap = 14, start = 0, duration = 18, easing = "spring" }) => {
    const frame = useCurrentFrame(); const { fps } = useVideoConfig();
    return (
      <div style={{ fontSize: size, fontWeight: 700, lineHeight: 1.08, letterSpacing: -2 }}>
        {lines.map((l, i) => {
          const p = Math.min(1, easedProgress(easing, frame, start + i * (duration - 4), duration, fps));
          return (
            <div key={i} style={{ overflow: "hidden", paddingBottom: lineGap }}>
              <div style={{ transform: `translateY(${(1 - p) * 110}%)`, opacity: p, color: accentLast && i === lines.length - 1 ? T.cyan : T.fg }}>{l}</div>
            </div>
          );
        })}
      </div>
    );
  };

/** text with keyword spans that get a highlight sweep when the narration reaches them (`keywordStarts` are scene frames) */
export const HighlightedKeywords: React.FC<{ text: string; keywords: string[]; keywordStarts?: number[]; color?: string; style?: React.CSSProperties; startAfter?: number }> =
  ({ text, keywords, keywordStarts, color = T.accent, style, startAfter = 12 }) => {
    const frame = useCurrentFrame(); const { fps } = useVideoConfig();
    if (!keywords.length) return <span style={style}>{text}</span>;
    const esc = keywords.map((k) => k.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
    const parts = text.split(new RegExp(`(${esc.join("|")})`, "gi"));
    return (
      <span style={style}>
        {parts.map((part, i) => {
          const k = keywords.findIndex((w) => w.toLowerCase() === part.toLowerCase());
          if (k < 0) return <React.Fragment key={i}>{part}</React.Fragment>;
          const s = keywordStarts?.[k] ?? startAfter + k * 8;
          const p = easedProgress("ease_out", frame, s, 14, fps);
          return <span key={i} style={{ padding: "0 6px", margin: "0 -2px", borderRadius: 6, color: p > 0.5 ? T.fg : "inherit", fontWeight: 600,
            backgroundImage: `linear-gradient(${color}, ${color})`, backgroundRepeat: "no-repeat", backgroundSize: `${p * 100}% 100%`, backgroundPosition: "0 0", boxDecorationBreak: "clone" }}>{part}</span>;
        })}
      </span>
    );
  };

/** Bullets tied to narration events `${prefix}.i`. The newest bullet is full strength; earlier ones settle back so the eye follows the narrator. */
export const AnimatedBulletList: React.FC<{ items: string[]; prefix?: string; quiz?: boolean; keywords?: string[]; size?: number; maxWidth?: number; correct?: number | null }> =
  ({ items, prefix = "bullet", quiz, keywords = [], size = 56, maxWidth = 1560, correct = null }) => {
    const n = items.length;
    const active = useActiveIndex(prefix, n);
    const size2 = n > 5 ? Math.round(size * 0.8) : size;
    const gap = n > 5 ? 32 : 56;
    return (
      <div style={{ position: "absolute", left: T.margin, top: T.contentTop + 40, maxWidth, display: "flex", flexDirection: "column", gap }}>
        {items.map((b, i) => <Bullet key={i} i={i} text={b} prefix={prefix} quiz={quiz} keywords={keywords} size={size2} dimmed={active > i} current={active === i} correct={correct === null ? null : correct === i} />)}
      </div>
    );
  };

const Bullet: React.FC<{ i: number; text: string; prefix: string; quiz?: boolean; keywords: string[]; size: number; dimmed: boolean; current: boolean; correct: boolean | null }> =
  ({ i, text, prefix, quiz, keywords, size, dimmed, current, correct }) => {
    const r = useReveal(`${prefix}.${i}`, { effect: "slide", direction: "right" });
    const ans = useReveal("answer").p; // 0 until the answer is announced
    const fb = quiz && correct !== null ? ans : 0;
    const letter = String.fromCharCode(65 + i);
    return (
      <div style={{ ...r.style, display: "flex", alignItems: "flex-start", gap: 24, fontSize: size, lineHeight: 1.3, fontWeight: 500, color: T.fg,
        opacity: r.style.opacity === undefined ? 1 : (r.style.opacity as number) * (fb > 0 && !correct ? 1 - 0.55 * fb : dimmed && !quiz ? 0.62 : 1) }}>
        {quiz
          ? <div style={{ flex: "0 0 auto", width: 56, height: 56, borderRadius: 14, border: `2px solid ${fb > 0 && correct ? T.ok : current ? T.warn : T.border}`, background: fb > 0 && correct ? `rgba(52,211,153,${0.25 * fb})` : T.panel, color: fb > 0 && correct ? T.ok : T.warn, fontSize: 30, fontWeight: 700, display: "grid", placeItems: "center", transform: `scale(${1 + 0.12 * Math.sin(Math.PI * Math.min(1, fb)) * (correct ? 1 : 0)})` }}>{fb > 0.6 && correct ? "✓" : letter}</div>
          : <div style={{ flex: "0 0 auto", marginTop: size * 0.38, width: 14, height: 14, borderRadius: 4, background: current ? T.cyan : T.accent, transform: "rotate(45deg)" }} />}
        <div><HighlightedKeywords text={text} keywords={keywords} startAfter={(r.start ?? 0) + 10} /></div>
      </div>
    );
  };

/** name / role strip that slides in, holds, then leaves; `hold` is in frames */
export const LowerThird: React.FC<{ name: string; title?: string; hold?: number } & Timing> = ({ name, title, start = 12, hold = 90, duration = 16, easing = "spring" }) => {
  const frame = useCurrentFrame(); const { fps } = useVideoConfig();
  const inP = Math.min(1, easedProgress(easing, frame, start, duration, fps));
  const outP = easedProgress("ease_in", frame, start + duration + hold, 12, fps);
  const x = (1 - inP) * -520 + outP * -520;
  const o = interpolate(inP - outP, [0, 1], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <div style={{ position: "absolute", left: T.margin, bottom: 210, transform: `translateX(${x}px)`, opacity: o, display: "flex", boxShadow: T.shadow, borderRadius: 12, overflow: "hidden" }}>
      <div style={{ width: 8, background: `linear-gradient(${T.accent}, ${T.cyan})` }} />
      <div style={{ padding: "16px 32px", background: "rgba(17,26,46,0.94)" }}>
        <div style={{ fontSize: 34, fontWeight: 700, color: T.fg }}>{name}</div>
        {title ? <div style={{ fontSize: 24, color: T.cyan, marginTop: 2, fontWeight: 500 }}>{title}</div> : null}
      </div>
    </div>
  );
};
