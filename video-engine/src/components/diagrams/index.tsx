import React from "react";
import { useCurrentFrame, useVideoConfig } from "remotion";
import { easedProgress, useReveal, useStartsOf } from "../../motion";
import { Layout } from "../../utils/types";
import { T } from "../../utils/theme";

export const wrapLabel = (text: string, width = 18): string[] => {
  const lines: string[] = []; let cur = "";
  for (const w of text.split(/\s+/)) { if ((cur + " " + w).trim().length > width && cur) { lines.push(cur); cur = w; } else cur = (cur + " " + w).trim(); }
  return cur ? [...lines, cur] : lines;
};

const clamp01 = (x: number) => Math.max(0, Math.min(1, x));

// ---------------- flowchart ----------------
const FlowNode: React.FC<{ n: Layout["nodes"][number]; bw: number; bh: number; active: boolean }> = ({ n, bw, bh, active }) => {
  const r = useReveal(`node.${n.id}`, { effect: "scale" });
  const s = 0.9 + 0.1 * clamp01(r.p);
  const stroke = n.shape === "diamond" ? T.warn : active ? T.cyan : T.accent;
  const lines = wrapLabel(n.label);
  return (
    <g opacity={clamp01(r.p)} transform={`translate(${n.x} ${n.y}) scale(${s})`} style={{ filter: active ? `drop-shadow(0 0 10px rgba(34,211,238,0.35))` : undefined }}>
      {n.shape === "diamond"
        ? <polygon points={`0,${-bh / 2 - 30} ${bw / 2 + 40},0 0,${bh / 2 + 30} ${-bw / 2 - 40},0`} fill={T.surface} stroke={stroke} strokeWidth={3} />
        : <rect x={-bw / 2} y={-bh / 2} width={bw} height={bh} rx={n.shape === "circle" ? bh / 2 : 14} fill={T.surface} stroke={stroke} strokeWidth={active ? 4 : 3} />}
      {lines.map((ln, i) => <text key={i} y={(i - (lines.length - 1) / 2) * 30 + 9} fill={T.fg} fontSize={26} fontWeight={500} textAnchor="middle" fontFamily={T.sans}>{ln}</text>)}
    </g>
  );
};

/** Nodes pop in as the narrator mentions them; each connecting arrow is DRAWN toward its target just before it appears, and the
 *  newest node plus the path that led to it is highlighted so the viewer can follow the flow. Branches reveal in narration order. */
export const AnimatedFlowchart: React.FC<{ layout: Layout }> = ({ layout }) => {
  const frame = useCurrentFrame(); const { fps } = useVideoConfig();
  const ids = layout.nodes.map((n) => n.id);
  const starts = useStartsOf(ids.map((i) => `node.${i}`));
  const start = (id: string) => starts[ids.indexOf(id)] ?? 0;
  let activeId = ids[0], best = -1;
  ids.forEach((id) => { const s = start(id); if (frame >= s && s >= best) { best = s; activeId = id; } });
  const pos = Object.fromEntries(layout.nodes.map((n) => [n.id, n]));
  const { bw, bh, direction } = layout;
  return (
    <svg viewBox={`0 0 ${layout.w} ${layout.h}`} width={layout.w} height={layout.h} style={{ position: "absolute", left: (1920 - layout.w) / 2, top: T.contentTop }}>
      {layout.edges.map((e, i) => {
        const A = pos[e.a], B = pos[e.b];
        if (!A || !B) return null;
        const lr = direction === "LR";
        const x1 = lr ? A.x + bw / 2 : A.x, y1 = lr ? A.y : A.y + bh / 2, x2 = lr ? B.x - bw / 2 : B.x, y2 = lr ? B.y : B.y - bh / 2;
        const es = Math.max(start(e.a) + 8, start(e.b) - 14);
        const p = clamp01(easedProgress("ease_out", frame, es, 16, fps));
        const onPath = e.b === activeId;
        const col = onPath ? T.cyan : T.accent;
        const ang = Math.atan2(y2 - y1, x2 - x1);
        const mx = (x1 + x2) / 2, my = (y1 + y2) / 2;
        return (
          <g key={i} opacity={onPath ? 1 : 0.7}>
            <path d={`M${x1} ${y1} L${x2} ${y2}`} pathLength={1} strokeDasharray={1} strokeDashoffset={1 - p} stroke={col} strokeWidth={onPath ? 4 : 3} fill="none" />
            {p > 0.92 ? <polygon points="0,0 -18,-9 -18,9" transform={`translate(${x2} ${y2}) rotate(${(ang * 180) / Math.PI})`} fill={col} /> : null}
            {e.label && p > 0.6 ? <g opacity={clamp01((p - 0.6) / 0.4)}><rect x={mx - e.label.length * 7.5 - 8} y={my - 18} width={e.label.length * 15 + 16} height={36} rx={8} fill={T.bg} /><text x={mx} y={my + 9} fill={T.warn} fontSize={24} textAnchor="middle" fontFamily={T.sans}>{e.label}</text></g> : null}
          </g>
        );
      })}
      {layout.nodes.map((n) => <FlowNode key={n.id} n={n} bw={bw} bh={bh} active={n.id === activeId} />)}
    </svg>
  );
};

// ---------------- architecture (tiers) ----------------
export interface Tier { name: string; items: string[] }
export const AnimatedArchitecture: React.FC<{ tiers: Tier[] }> = ({ tiers }) => {
  const rowH = Math.min(150, (T.contentBottom - T.contentTop) / tiers.length - 24);
  return (
    <div style={{ position: "absolute", left: T.margin, right: T.margin, top: T.contentTop }}>
      {tiers.map((t, i) => <TierRow key={i} i={i} tier={t} h={rowH} last={i === tiers.length - 1} />)}
    </div>
  );
};
const TierRow: React.FC<{ i: number; tier: Tier; h: number; last: boolean }> = ({ i, tier, h, last }) => {
  const r = useReveal(`tier.${i}`, { effect: "slide", direction: "up" });
  return (
    <div style={{ ...r.style, position: "relative", height: h, marginBottom: 24, display: "flex", alignItems: "stretch", gap: 20 }}>
      <div style={{ width: 230, display: "grid", alignContent: "center", padding: "0 20px", background: T.panel, borderLeft: `4px solid ${T.accent}`, borderRadius: 10, fontSize: 26, fontWeight: 700, color: T.cyan }}>{tier.name}</div>
      {tier.items.map((it, k) => <div key={k} style={{ flex: 1, display: "grid", placeItems: "center", textAlign: "center", padding: 12, background: T.surface, border: `1px solid ${T.border}`, borderRadius: 12, fontSize: 28, fontWeight: 500, boxShadow: T.shadow }}>{it}</div>)}
      {!last ? <div style={{ position: "absolute", left: 345, bottom: -24, width: 3, height: 24, background: `linear-gradient(${T.accent}, transparent)`, opacity: r.p }} /> : null}
    </div>
  );
};

// ---------------- network ----------------
export interface NetNode { id: string; label: string; kind?: "host" | "server" | "attacker" | "cloud" }
export interface NetLink { a: string; b: string; label?: string }
const NET_COL: Record<string, string> = { host: T.accent, server: T.ok, attacker: T.danger, cloud: T.violet };
export const AnimatedNetwork: React.FC<{ nodes: NetNode[]; links: NetLink[] }> = ({ nodes, links }) => {
  const frame = useCurrentFrame(); const { fps } = useVideoConfig();
  const W = 1500, H = 640, cx = W / 2, cy = H / 2, rad = Math.min(250, 120 + nodes.length * 26);
  const pos = Object.fromEntries(nodes.map((n, i) => { const a = (i / nodes.length) * Math.PI * 2 - Math.PI / 2; return [n.id, { x: cx + Math.cos(a) * rad * 1.6, y: cy + Math.sin(a) * rad }]; }));
  const nStarts = useStartsOf(nodes.map((n) => `node.${n.id}`));
  const lStarts = useStartsOf(links.map((_, i) => `link.${i}`));
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} style={{ position: "absolute", left: (1920 - W) / 2, top: T.contentTop + 20 }}>
      {links.map((l, i) => {
        const A = pos[l.a], B = pos[l.b]; if (!A || !B) return null;
        const p = clamp01(easedProgress("ease_out", frame, lStarts[i] ?? 0, 16, fps));
        return <g key={i}><path d={`M${A.x} ${A.y} L${B.x} ${B.y}`} pathLength={1} strokeDasharray={1} strokeDashoffset={1 - p} stroke={T.accent} strokeWidth={3} />{l.label && p > 0.7 ? <text x={(A.x + B.x) / 2} y={(A.y + B.y) / 2 - 12} fill={T.warn} fontSize={22} textAnchor="middle" fontFamily={T.mono}>{l.label}</text> : null}</g>;
      })}
      {nodes.map((n, i) => {
        const p = clamp01(easedProgress("spring", frame, nStarts[i] ?? 0, 14, fps)); const c = NET_COL[n.kind ?? "host"];
        return <g key={n.id} opacity={p} transform={`translate(${pos[n.id].x} ${pos[n.id].y}) scale(${0.85 + 0.15 * p})`}><circle r={46} fill={T.surface} stroke={c} strokeWidth={4} /><text y={6} fill={T.fg} fontSize={15} fontWeight={700} textAnchor="middle" fontFamily={T.sans}>{(n.kind ?? "host").toUpperCase()}</text><text y={78} fill={T.fg} fontSize={26} fontWeight={500} textAnchor="middle" fontFamily={T.sans}>{n.label}</text></g>;
      })}
    </svg>
  );
};

// ---------------- process flow ----------------
export const AnimatedProcessFlow: React.FC<{ steps: string[] }> = ({ steps }) => {
  const n = steps.length; const w = (1728 - (n - 1) * 16) / n;
  return (
    <div style={{ position: "absolute", left: T.margin, right: T.margin, top: 340, display: "flex", gap: 16 }}>
      {steps.map((s, i) => <Step key={i} i={i} text={s} w={w} />)}
    </div>
  );
};
const Step: React.FC<{ i: number; text: string; w: number }> = ({ i, text, w }) => {
  const r = useReveal(`step.${i}`, { effect: "slide", direction: "right" });
  return (
    <div style={{ ...r.style, width: w, height: 240, background: T.surface, border: `1px solid ${T.border}`, borderTop: `4px solid ${T.accent}`, borderRadius: 14, padding: 24, boxShadow: T.shadow, boxSizing: "border-box" }}>
      <div style={{ fontSize: 22, color: T.cyan, fontWeight: 700, letterSpacing: 2 }}>STEP {i + 1}</div>
      <div style={{ marginTop: 14, fontSize: 30, fontWeight: 600, lineHeight: 1.25 }}>{text}</div>
    </div>
  );
};

// ---------------- timeline ----------------
export interface TimelineEvent { label: string; time?: string }
export const AnimatedTimeline: React.FC<{ events: TimelineEvent[] }> = ({ events }) => {
  const frame = useCurrentFrame(); const { fps } = useVideoConfig();
  const n = events.length; const y = 540;
  const starts = useStartsOf(events.map((_, i) => `event.${i}`));
  const last = Math.max(0, ...starts.map((s) => s ?? 0));
  const line = clamp01(easedProgress("ease_out", frame, Math.min(...starts.map((s) => s ?? 0)), Math.max(20, last), fps));
  return (
    <div style={{ position: "absolute", inset: 0 }}>
      <div style={{ position: "absolute", left: T.margin + 40, top: y, height: 4, width: (1728 - 80) * Math.min(1, line), background: `linear-gradient(90deg, ${T.accent}, ${T.cyan})`, borderRadius: 2 }} />
      {events.map((e, i) => <Milestone key={i} i={i} n={n} y={y} e={e} />)}
    </div>
  );
};
const Milestone: React.FC<{ i: number; n: number; y: number; e: TimelineEvent }> = ({ i, n, y, e }) => {
  const r = useReveal(`event.${i}`, { effect: "scale" });
  const x = T.margin + 40 + ((1728 - 80) * (i + 0.5)) / n;
  const up = i % 2 === 0;
  return (
    <div style={{ ...r.style, position: "absolute", left: x - 150, top: up ? y - 150 : y + 40, width: 300, textAlign: "center" }}>
      {up ? null : <div style={{ height: 0 }} />}
      <div style={{ position: "absolute", left: 135, top: up ? 142 : -46, width: 28, height: 28, borderRadius: 14, background: T.bg, border: `5px solid ${T.cyan}` }} />
      {e.time ? <div style={{ fontSize: 22, color: T.cyan, fontFamily: T.mono, fontWeight: 700 }}>{e.time}</div> : null}
      <div style={{ fontSize: 28, fontWeight: 600, lineHeight: 1.25, marginTop: 6 }}>{e.label}</div>
    </div>
  );
};
