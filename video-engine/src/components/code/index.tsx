import React from "react";
import { useCurrentFrame, useVideoConfig } from "remotion";
import { easedProgress, useActiveIndex, useStarts } from "../../motion";
import { SYN, T } from "../../utils/theme";
import { clipTokens, highlight } from "./highlight";

export const CursorAnimation: React.FC<{ visible?: boolean; blink?: number; color?: string; width?: number; height?: number }> =
  ({ visible = true, blink = 16, color = T.cyan, width = 14, height = 30 }) => {
    const frame = useCurrentFrame();
    const on = visible && Math.floor(frame / blink) % 2 === 0;
    return <span style={{ display: "inline-block", width, height, marginLeft: 2, verticalAlign: "text-bottom", background: on ? color : "transparent" }} />;
  };

const Line: React.FC<{ text: string; lang: string; chars?: number; flag?: string }> = ({ text, lang, chars, flag }) => {
  const toks = highlight(text, lang);
  const shown = chars === undefined ? toks : clipTokens(toks, chars);
  return <>{shown.map((t, i) => <span key={i} style={{ color: flag === "danger" && t.k === "plain" ? "#fca5a5" : SYN[t.k] }}>{t.t}</span>)}{text === "" ? " " : null}</>;
};

export const SyntaxHighlightedCode: React.FC<{ code: string; language?: string | null; size?: number }> = ({ code, language, size = 30 }) => (
  <div style={{ fontFamily: T.mono, fontSize: size, lineHeight: 1.5, whiteSpace: "pre" }}>
    {code.split("\n").map((l, i) => <div key={i}><Line text={l} lang={language ?? ""} /></div>)}
  </div>
);

/** A bar that glides from the previously active line to the new one (spring), marking where the narrator is */
export const ActiveLineHighlighter: React.FC<{ index: number; prevIndex: number; changedAt: number; lineHeight: number; top?: number; left?: number; right?: number }> =
  ({ index, prevIndex, changedAt, lineHeight, top = 0, left = 0, right = 0 }) => {
    const frame = useCurrentFrame(); const { fps } = useVideoConfig();
    if (index < 0) return null;
    const p = Math.min(1, easedProgress("spring", frame, changedAt, 14, fps));
    const y = (prevIndex < 0 ? index : prevIndex + (index - prevIndex) * p) * lineHeight;
    return <div style={{ position: "absolute", left, right, top: top + y, height: lineHeight, background: "rgba(59,130,246,0.16)", borderLeft: `4px solid ${T.accent}`, opacity: prevIndex < 0 ? p : 1 }} />;
  };

/** Code appears line by line, each line typed at `cps` characters/second when its narration event fires.
 *  Lines flagged by `dangerPattern` (default: the lab marker VULNERABLE) are tinted. Register/memory commentary may be added with `sidebar`. */
export const CodeTypingAnimation: React.FC<{ code: string; language?: string | null; size?: number; cps?: number; dangerPattern?: RegExp; maxWidth?: number; sceneFrames: number }> =
  ({ code, language, size: sizeProp, cps = 45, dangerPattern = /VULNERABLE|UNSAFE|OVERFLOW/, sceneFrames }) => {
    const frame = useCurrentFrame(); const { fps } = useVideoConfig();
    const lines = code.split("\n");
    const n = lines.length;
    const size = sizeProp ?? (n <= 8 ? 40 : n <= 12 ? 34 : 28);
    const lh = Math.round(size * 1.5);
    const starts = useStarts("line", n);
    const active = useActiveIndex("line", n);
    const lastActive = active - 1;
    // sequential start: a line never starts typing before the previous one has finished (plus a short beat)
    const eff: number[] = []; const typeF: number[] = [];
    let prevEnd = 0;
    lines.forEach((l, i) => {
      const s = Math.max(starts[i] ?? 0, prevEnd);
      const tf = Math.max(4, Math.round((l.trim().length / cps) * fps));
      eff.push(s); typeF.push(tf); prevEnd = s + tf + 3;
    });
    const budget = sceneFrames - 24; // everything must be fully typed before the scene ends
    if (prevEnd > budget && budget > 0) {
      const k = Math.max(0.2, (budget - (eff[0] ?? 0)) / Math.max(1, prevEnd - (eff[0] ?? 0)));
      prevEnd = 0;
      lines.forEach((_, i) => { typeF[i] = Math.max(2, Math.round(typeF[i] * k)); eff[i] = Math.max(starts[i] ?? 0, prevEnd); prevEnd = eff[i] + typeF[i] + 1; });
    }
    let cur = -1;
    eff.forEach((s, i) => { if (frame >= s) cur = i; });
    const changedAt = cur >= 0 ? eff[cur] : 0;
    return (
      <div style={{ position: "absolute", left: T.margin, right: T.margin, top: T.contentTop, bottom: sceneFrames ? 190 : 190, background: T.panel, border: `1px solid ${T.border}`, borderRadius: T.radius, boxShadow: T.shadow, overflow: "hidden" }}>
        <div style={{ height: 44, background: T.surface, borderBottom: `1px solid ${T.border}`, display: "flex", alignItems: "center", padding: "0 20px", gap: 10, fontFamily: T.sans, fontSize: 18, color: T.muted }}>
          {[T.danger, T.warn, T.ok].map((c) => <span key={c} style={{ width: 12, height: 12, borderRadius: 6, background: c, opacity: 0.8 }} />)}
          <span style={{ marginLeft: 12 }}>{(language ?? "code").toLowerCase()}</span>
        </div>
        <div style={{ position: "relative", padding: "24px 0", fontFamily: T.mono, fontSize: size, lineHeight: `${lh}px`, whiteSpace: "pre" }}>
          <ActiveLineHighlighter index={cur} prevIndex={cur - 1 >= 0 ? cur - 1 : -1} changedAt={changedAt} lineHeight={lh} top={24} />
          {lines.map((l, i) => {
            const chars = frame < eff[i] ? -1 : Math.min(l.length, Math.floor(((frame - eff[i]) / typeF[i]) * l.length) + 1);
            const flagged = dangerPattern.test(l);
            const typing = i === cur && chars < l.length;
            return (
              <div key={i} style={{ position: "relative", height: lh, padding: "0 28px", display: "flex", background: flagged && chars >= 0 ? "rgba(248,113,113,0.10)" : "transparent" }}>
                <span style={{ width: 56, flex: "0 0 56px", color: T.dim, userSelect: "none", opacity: chars < 0 ? 0 : 1 }}>{i + 1}</span>
                <span>{chars >= 0 ? <Line text={l} lang={language ?? ""} chars={chars >= l.length ? undefined : chars} flag={flagged ? "danger" : undefined} /> : null}{typing ? <CursorAnimation height={size} width={Math.round(size * 0.55)} /> : null}</span>
              </div>
            );
          })}
        </div>
        <span style={{ display: "none" }}>{lastActive}</span>
      </div>
    );
  };

// -------- terminal --------
const IMPORTANT = /(error|fail(ed|ure)?|denied|segmentation fault|sigsegv|core dumped|uid=0|root@|vulnerable|exploit(ed)?|overflow|success|shell|flag\{|0x[0-9a-f]{6,})/i;
const isCommand = (l: string) => /^(\$|#|>|\(gdb\)|msf\S*>|[\w.-]+@[\w.-]+[:~][^\n]*[$#])\s/.test(l) || /^(\$|#|>)$/.test(l);

/** a command line that types itself after its prompt */
export const TerminalCommandAnimation: React.FC<{ line: string; start: number; frames: number; showCursor?: boolean }> = ({ line, start, frames, showCursor }) => {
  const frame = useCurrentFrame();
  const m = /^(\S*\s)(.*)$/.exec(line) ?? ["", "", line];
  const n = frame < start ? -1 : Math.min(m[2].length, Math.floor(((frame - start) / frames) * m[2].length) + 1);
  if (n < 0) return null;
  return <div style={{ whiteSpace: "pre-wrap", wordBreak: "break-all" }}><span style={{ color: T.ok, fontWeight: 700 }}>{m[1]}</span><span style={{ color: T.fg }}>{m[2].slice(0, n)}</span>{showCursor ? <CursorAnimation height={30} width={16} /> : null}</div>;
};

/** an output line that fades in; important lines (errors, crashes, uid=0, addresses) get a tinted bar */
export const TerminalOutputAnimation: React.FC<{ line: string; start: number }> = ({ line, start }) => {
  const frame = useCurrentFrame(); const { fps } = useVideoConfig();
  const p = Math.min(1, easedProgress("ease_out", frame, start, 8, fps));
  if (p <= 0) return null;
  const bad = /(error|fail|denied|segmentation|sigsegv|core dumped)/i.test(line);
  const imp = IMPORTANT.test(line);
  const glow = imp ? Math.min(1, easedProgress("ease_out", frame, start + 4, 12, fps)) : 0;
  return <div style={{ opacity: p, whiteSpace: "pre-wrap", wordBreak: "break-all", color: bad ? "#fca5a5" : imp ? T.warn : "#c7d2e5", margin: "0 -14px", padding: "0 14px", borderRadius: 6, background: imp ? `rgba(${bad ? "248,113,113" : "251,191,36"},${0.12 * glow})` : "none" }}>{line || " "}</div>;
};

export const TerminalWindow: React.FC<{ lines: string[]; sceneFrames: number; size?: number; cps?: number; title?: string }> = ({ lines, sceneFrames, size: sizeProp, cps = 28, title = "lab-terminal" }) => {
  const frame = useCurrentFrame(); const { fps } = useVideoConfig();
  const n = lines.length;
  const size = sizeProp ?? (n <= 8 ? 36 : n <= 12 ? 32 : 28);
  const starts = useStarts("line", n);
  const cmdFrames = lines.map((l) => (isCommand(l) ? Math.max(8, Math.round((l.length / cps) * fps)) : 6));
  const compute = (scale: number) => {
    const eff: number[] = []; let prev = 0;
    lines.forEach((_, i) => { const s = Math.max(starts[i] ?? 0, prev); eff.push(s); prev = s + Math.max(2, Math.round(cmdFrames[i] * scale)) + (isCommand(lines[i]) ? 10 : 2); });
    return { eff, end: prev };
  };
  let scale = 1, r = compute(1);
  const budget = sceneFrames - 24;
  if (r.end > budget && budget > 0) { scale = Math.max(0.15, budget / r.end); r = compute(scale); }
  const { eff } = r;
  let lastVisible = -1;
  eff.forEach((s, i) => { if (frame >= s) lastVisible = i; });
  const visible = lines.map((_, i) => i <= lastVisible);
  const lh = Math.round(size * 1.55);
  const maxLines = Math.floor((T.contentBottom - T.contentTop - 130) / lh);
  const first = Math.max(0, lastVisible - maxLines + 1); // scroll like a real terminal once the window is full
  return (
    <div style={{ position: "absolute", left: T.margin, right: T.margin, top: T.contentTop, bottom: 190, background: "#05080f", border: `1px solid ${T.border}`, borderRadius: T.radius, boxShadow: T.shadow, overflow: "hidden" }}>
      <div style={{ height: 44, background: T.surface, borderBottom: `1px solid ${T.border}`, display: "flex", alignItems: "center", padding: "0 20px", gap: 10, fontFamily: T.sans, fontSize: 18, color: T.muted }}>
        {[T.danger, T.warn, T.ok].map((c) => <span key={c} style={{ width: 12, height: 12, borderRadius: 6, background: c, opacity: 0.8 }} />)}
        <span style={{ marginLeft: 12 }}>{title}</span>
      </div>
      <div style={{ padding: "22px 36px", fontFamily: T.mono, fontSize: size, lineHeight: `${lh}px` }}>
        {lines.map((l, i) => {
          if (!visible[i] || i < first) return null;
          const typingNow = isCommand(l) && frame < eff[i] + Math.round(cmdFrames[i] * scale);
          return isCommand(l)
            ? <TerminalCommandAnimation key={i} line={l} start={eff[i]} frames={Math.max(2, Math.round(cmdFrames[i] * scale))} showCursor={typingNow || i === lastVisible} />
            : <TerminalOutputAnimation key={i} line={l} start={eff[i]} />;
        })}
      </div>
      <div style={{ position: "absolute", left: 36, bottom: 14, fontFamily: T.sans, fontSize: 18, color: T.dim }}>Illustrative / lab demonstration - not evidence of real-world results</div>
    </div>
  );
};

// -------- browser --------
export const BrowserInteractionAnimation: React.FC<{ lines: string[]; sceneFrames: number }> = ({ lines, sceneFrames }) => {
  const frame = useCurrentFrame(); const { fps } = useVideoConfig();
  const url = lines.find((l) => /^https?:\/\//i.test(l.trim())) ?? "http://lab.local/";
  const body = lines.filter((l) => l !== url);
  const typeEnd = 30 + Math.min(40, url.length);
  const chars = Math.max(0, Math.min(url.length, Math.floor(((frame - 12) / (typeEnd - 12)) * url.length)));
  const loaded = easedProgress("ease_out", frame, typeEnd + 4, 18, fps);
  const rowStart = (i: number) => typeEnd + 22 + i * Math.max(6, Math.floor((sceneFrames - typeEnd - 80) / Math.max(1, body.length + 1)));
  const pick = (re: RegExp) => body.findIndex((l) => re.test(l));
  const targetIdx = Math.max(0, [/submit|button|\[.*\]|sign in|log in/i, /search|go\b/i, /input|field|form/i].map(pick).find((i) => i >= 0) ?? body.length - 1);
  const rowH = 70;
  const mouseT = easedProgress("ease_in_out", frame, rowStart(targetIdx) + 14, 26, fps);
  const clickAt = rowStart(targetIdx) + 40;
  const ripple = Math.min(1, Math.max(0, (frame - clickAt) / 14));
  const mx = 1500 + (360 - 1500) * mouseT, my = 420 + ((91 + targetIdx * rowH + rowH / 2) - 420) * mouseT;
  return (
    <div style={{ position: "absolute", left: T.margin, right: T.margin, top: T.contentTop, bottom: 190, background: "#0d1424", border: `1px solid ${T.border}`, borderRadius: T.radius, boxShadow: T.shadow, overflow: "hidden" }}>
      <div style={{ height: 64, background: T.surface, display: "flex", alignItems: "center", padding: "0 20px", gap: 16, borderBottom: `1px solid ${T.border}` }}>
        {[T.danger, T.warn, T.ok].map((c) => <span key={c} style={{ width: 12, height: 12, borderRadius: 6, background: c, opacity: 0.8 }} />)}
        <div style={{ flex: 1, marginLeft: 12, height: 38, borderRadius: 19, background: "#0a0f1c", border: `1px solid ${T.border}`, display: "flex", alignItems: "center", padding: "0 20px", fontFamily: T.mono, fontSize: 22, color: T.muted }}>
          {url.slice(0, chars)}{chars < url.length ? <CursorAnimation height={22} width={10} /> : null}
        </div>
      </div>
      <div style={{ height: 3, background: T.border }}><div style={{ height: 3, width: `${loaded * 100}%`, background: T.accent }} /></div>
      <div style={{ position: "relative", padding: "24px 40px", fontFamily: T.sans, fontSize: 30, color: T.fg }}>
        {body.map((l, i) => {
          const p = Math.min(1, easedProgress("ease_out", frame, rowStart(i), 10, fps));
          const hot = i === targetIdx && frame > clickAt - 12;
          return <div key={i} style={{ height: rowH, display: "flex", alignItems: "center", opacity: p, transform: `translateY(${(1 - p) * 12}px)`, padding: "0 20px", borderRadius: 10, background: hot ? "rgba(59,130,246,0.18)" : "transparent", border: hot ? `1px solid ${T.accent}` : "1px solid transparent" }}>{l}</div>;
        })}
      </div>
      <svg width="40" height="40" viewBox="0 0 24 24" style={{ position: "absolute", left: mx, top: my, opacity: loaded > 0.5 ? 1 : 0 }}><path d="M5 3l14 8-6 1.6L9.8 19z" fill="#fff" stroke="#0a0f1c" strokeWidth="1.2" /></svg>
      {ripple > 0 && ripple < 1 ? <div style={{ position: "absolute", left: mx - 6, top: my - 6, width: 12 + ripple * 60, height: 12 + ripple * 60, marginLeft: -(ripple * 30), marginTop: -(ripple * 30), borderRadius: "50%", border: `3px solid ${T.cyan}`, opacity: 1 - ripple }} /> : null}
    </div>
  );
};
