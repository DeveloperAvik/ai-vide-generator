import React from "react";
import { easedProgress, useStepper } from "../../motion";
import { Viz } from "../../utils/types";
import { SYN, T } from "../../utils/theme";
import { highlight } from "../code/highlight";
import { wrapLabel } from "../diagrams";

const clamp = (x: number, a = 0, b = 1) => Math.max(a, Math.min(b, x));
const hex = (n: number | bigint) => "0x" + n.toString(16);
const MONO: React.CSSProperties = { fontFamily: T.mono };

const Panel: React.FC<{ left: number; top?: number; width: number; height?: number; title?: string; children: React.ReactNode; style?: React.CSSProperties }> =
  ({ left, top = T.contentTop, width, height = 600, title, children, style }) => (
    <div style={{ position: "absolute", left, top, width, height, background: T.panel, border: `1px solid ${T.border}`, borderRadius: T.radius, boxShadow: T.shadow, padding: 24, boxSizing: "border-box", overflow: "hidden", ...style }}>
      {title ? <div style={{ fontSize: 20, letterSpacing: 2, color: T.muted, fontWeight: 600, marginBottom: 14 }}>{title.toUpperCase()}</div> : null}
      {children}
    </div>
  );

/** the teaching sentence for the current step, always inside the content area above the captions */
const StepNote: React.FC<{ text: string; color?: string }> = ({ text, color = T.fg }) => (
  <div style={{ position: "absolute", left: T.margin, right: T.margin, top: 812, minHeight: 56, fontSize: 28, fontWeight: 500, color, lineHeight: 1.35 }}>{text}</div>
);

// =====================================================================================
// Buffer overflow: which bytes of the input land on the buffer, canary, saved RBP and RET
// =====================================================================================
const BufferOverflowAnimation: React.FC<Extract<Viz, { kind: "buffer_overflow" }>> = (v) => {
  const { sp, active } = useStepper(5);
  const N = v.buffer_size, L = v.input_length, cb = v.stack_canary ? 8 : 0, W = v.arch === "x86_64" ? 8 : 4;
  const rows = Math.min(8, Math.ceil(N / 8)), bpr = N / rows;
  const wr = (a: number, b: number, k: number) => Math.max(0, Math.min(L, b) - a) * k; // bytes of [a,b) written, scaled by step progress
  const written = wr(0, N, sp(2)) + wr(N, N + cb + W, sp(3)) + wr(N + cb + W, N + cb + 2 * W, sp(4));
  const fill = (a: number, b: number) => clamp((written - a) / (b - a));
  const over = Math.max(0, L - N);
  const fillHex = v.fill_byte.charCodeAt(0).toString(16).padStart(2, "0");
  const retBytes = clamp(Math.round(Math.max(0, written - (N + cb + W))), 0, W);
  const orig = BigInt(v.original_return);
  let retVal = orig;
  for (let i = 0; i < retBytes; i++) retVal = (retVal & ~(0xffn << BigInt(8 * i))) | (BigInt(parseInt(fillHex, 16)) << BigInt(8 * i));
  const retHex = "0x" + retVal.toString(16).padStart(W * 2, "0");
  const hijacked = retBytes > 0, rbpHit = written > N + cb, canaryHit = cb > 0 && written > N;
  const rowH = 52, w = 470;
    type R = { label: string; sub: string; a: number; b: number; color: string; value?: string };
  const stackRows: R[] = [
    { label: "RET", sub: `rbp+${W}`, a: N + cb + W, b: N + cb + 2 * W, color: T.danger, value: retHex },
    { label: "saved RBP", sub: "rbp", a: N + cb, b: N + cb + W, color: T.warn },
    ...(cb ? [{ label: "stack canary", sub: `rbp-${cb}`, a: N, b: N + cb, color: T.violet } as R] : []),
    ...Array.from({ length: rows }, (_, k) => { const r = rows - 1 - k; return { label: `${v.buffer_name}[${Math.round(r * bpr)}..${Math.round((r + 1) * bpr) - 1}]`, sub: "", a: r * bpr, b: (r + 1) * bpr, color: T.accent } as R; }),
  ];
  const top = T.contentTop + 28;
  const bufTop = top + (stackRows.length - rows) * rowH;
  const note = active <= 0 ? "Stack frame of the vulnerable function. Higher addresses are at the top; the stack grows downward."
    : active === 1 ? `${v.buffer_name} is a fixed ${N}-byte local buffer. Nothing in the program stops writes past its end.`
    : active === 2 ? `${Math.min(L, N)} of ${L} input bytes are copied into ${v.buffer_name}, filling it from low addresses upward.`
    : active === 3 ? (over > 0 ? `The copy does not stop at ${N} bytes: ${cb ? "the canary, then " : ""}the saved RBP is overwritten with 0x${fillHex}.` : `The input is ${L} bytes and the buffer holds ${N}: it fits, so nothing beyond the buffer is touched.`)
    : over > cb + W ? (cb ? "The canary no longer matches: the function aborts in __stack_chk_fail before it returns, so the hijack is stopped." : `RET now holds ${retHex}. On \`ret\`, RIP loads this value, so the attacker, not the program, picks where execution continues.`)
    : "No byte reached the return address: control flow is unchanged.";
  return (
    <>
      <Panel left={T.margin} width={760} height={600} title="Stack frame (high → low address)">
        <div style={{ position: "relative", height: 540 }}>
          {stackRows.map((r, i) => {
            const y = i * rowH + 6, fl = fill(r.a, r.b);
            const isBuf = r.color === T.accent;
            const reveal = isBuf ? sp(0) : sp(0);
            const hot = (r.label.startsWith("return") && hijacked) || (r.label === "saved RBP" && rbpHit) || (r.label.startsWith("stack canary") && canaryHit);
            const buffering = isBuf && active === 1;
            return (
              <div key={i} style={{ position: "absolute", left: 0, top: y, width: w, height: rowH - 8, opacity: reveal, transform: `translateX(${(1 - reveal) * -30}px)` }}>
                <div style={{ position: "absolute", inset: 0, borderRadius: 8, background: T.bg, border: `2px solid ${hot ? T.danger : buffering ? T.cyan : T.border}` }} />
                <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: `${fl * 100}%`, borderRadius: 8, background: hot ? "rgba(248,113,113,0.45)" : isBuf ? "rgba(59,130,246,0.45)" : `${r.color}55`, overflow: "hidden" }} />
                <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0 18px", ...MONO, fontSize: 24 }}>
                  <span style={{ color: T.fg, fontFamily: T.sans, fontWeight: 600, whiteSpace: "nowrap", fontSize: 22 }}>{r.label}</span>
                  <span style={{ color: hot ? "#fecaca" : T.muted, whiteSpace: "nowrap", fontSize: 21 }}>{r.value ?? (fl > 0 ? Array(8).fill(fillHex).join(" ") : "")}</span>
                </div>
                {r.sub ? <div style={{ position: "absolute", left: w + 16, top: 8, ...MONO, fontSize: 18, color: T.dim }}>{r.sub}</div> : null}
              </div>
            );
          })}
          {/* size brace for the buffer */}
          <div style={{ position: "absolute", left: w + 112, top: (stackRows.length - rows) * rowH + 6, height: rows * rowH - 8, whiteSpace: "nowrap", borderLeft: `3px solid ${active === 1 ? T.cyan : T.border}`, paddingLeft: 12, display: "flex", alignItems: "center", opacity: sp(1) }}>
            <span style={{ ...MONO, fontSize: 26, color: T.cyan, fontWeight: 700 }}>{N} bytes</span>
          </div>
        </div>
      </Panel>
      <Panel left={T.margin + 784} width={944} height={600} title="Input vs. buffer">
        <div style={{ ...MONO, fontSize: 28, lineHeight: 1.9, color: T.fg }}>
          <div>input length <span style={{ color: T.warn, fontWeight: 700 }}>{L} bytes</span></div>
          <div>buffer size <span style={{ color: T.cyan, fontWeight: 700 }}>{N} bytes</span></div>
          <div>overflow <span style={{ color: over > 0 ? T.danger : T.ok, fontWeight: 700 }}>{over > 0 ? `${over} bytes past the buffer` : "none"}</span></div>
          <div style={{ marginTop: 18, color: T.muted, fontSize: 22 }}>distance buffer → RET: {N + cb + W} bytes{cb ? " (incl. canary)" : ""}</div>
          <div style={{ color: T.muted, fontSize: 22 }}>(typical layout; padding is compiler dependent)</div>
        </div>
        <div style={{ marginTop: 28, height: 36, borderRadius: 8, overflow: "hidden", display: "flex", border: `1px solid ${T.border}`, opacity: sp(2) }}>
          <div style={{ width: `${(Math.min(L, N) / Math.max(L, N + cb + 2 * W)) * 100}%`, background: "rgba(59,130,246,0.6)" }} />
          {cb ? <div style={{ width: `${(Math.min(Math.max(L - N, 0), cb) / Math.max(L, N + cb + 2 * W)) * 100}%`, background: "rgba(167,139,250,0.7)" }} /> : null}
          <div style={{ width: `${(Math.max(0, Math.min(L - N - cb, W)) / Math.max(L, N + cb + 2 * W)) * 100}%`, background: "rgba(251,191,36,0.7)" }} />
          <div style={{ width: `${(Math.max(0, Math.min(L - N - cb - W, W)) / Math.max(L, N + cb + 2 * W)) * 100}%`, background: "rgba(248,113,113,0.8)" }} />
        </div>
        <div style={{ display: "flex", gap: 22, marginTop: 10, fontSize: 20, color: T.muted, fontFamily: T.sans }}>
          {[["buffer", T.accent], ...(cb ? [["canary", T.violet]] : []), ["saved RBP", T.warn], ["RET", T.danger]].map(([n, c]) => <span key={n}><span style={{ display: "inline-block", width: 12, height: 12, background: c, borderRadius: 3, marginRight: 8 }} />{n}</span>)}
        </div>
        {hijacked && !cb ? <div style={{ marginTop: 34, padding: 20, borderRadius: 12, border: `2px solid ${T.danger}`, background: "rgba(248,113,113,0.10)", ...MONO, fontSize: 26, opacity: sp(4) }}>
          <div style={{ color: T.muted, fontSize: 20, fontFamily: T.sans }}>after `ret`</div>
          rip ← <span style={{ color: T.danger, fontWeight: 700 }}>{retHex}</span>
        </div> : null}
      </Panel>
      <StepNote text={note} color={active >= 4 && over > cb + W && !cb ? "#fecaca" : T.fg} />
    </>
  );
};

// =====================================================================================
// Stack frames
// =====================================================================================
const StackFrames: React.FC<Extract<Viz, { kind: "stack_frames" }>> = (v) => {
  const { sp, active } = useStepper(v.frames.length);
  const W = v.arch === "x86_64" ? 8 : 4;
  const rowsOf = (f: typeof v.frames[number]) => f.args.length + 2 + f.locals.length + 0.7;
  const total = v.frames.reduce((a, f) => a + rowsOf(f) + 0.35, 0);
  const rowH = Math.min(52, 500 / total);
  let y = 0;
  const af = v.frames[Math.max(0, active)];
  return (
    <>
      <Panel left={T.margin} width={900} height={600} title={`Call stack - ${v.arch} (grows downward ↓)`}>
        <div style={{ position: "relative" }}>
          {v.frames.map((f, fi) => {
            const p = sp(fi), top = y; y += (rowsOf(f) + 0.35) * rowH;
            const cur = fi === active;
            const rows: { k: string; l: string; r: string; c: string }[] = [
              ...f.args.map((a, i) => ({ k: `a${i}`, l: `arg: ${a}`, r: "", c: T.muted })),
              { k: "ret", l: "return address", r: f.return_address, c: T.danger },
              { k: "rbp", l: "saved RBP", r: "", c: T.warn },
              ...f.locals.map((l) => ({ k: l.name, l: `${l.name}`, r: `${l.size} B`, c: T.accent })),
            ];
            return (
              <div key={fi} style={{ position: "absolute", left: 0, top: top, width: 840, opacity: p, transform: `translateY(${(1 - p) * -24}px)`, border: `2px solid ${cur ? T.cyan : T.border}`, borderRadius: 10, background: cur ? "rgba(34,211,238,0.05)" : "transparent" }}>
                <div style={{ position: "absolute", left: 12, top: -14, background: T.panel, padding: "0 10px", ...MONO, fontSize: 22, color: cur ? T.cyan : T.muted, fontWeight: 700 }}>{f.function}()</div>
                <div style={{ height: rowH * 0.7 }} />
                {rows.map((r, i) => (
                  <div key={r.k} style={{ height: rowH, display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0 20px", borderTop: i ? `1px solid ${T.border}` : "none", ...MONO, fontSize: Math.min(26, rowH * 0.55) }}>
                    <span style={{ color: r.c === T.accent ? T.fg : r.c }}>{r.l}</span><span style={{ color: T.muted }}>{r.r}</span>
                    {cur && r.k === "rbp" ? <span style={{ position: "absolute", right: -88, color: T.warn, fontSize: 22, fontWeight: 700 }}>← rbp</span> : null}
                  </div>
                ))}
                {cur ? <span style={{ position: "absolute", right: -88, bottom: 4, color: T.cyan, fontSize: 22, fontWeight: 700, ...MONO }}>← rsp</span> : null}
              </div>
            );
          })}
        </div>
      </Panel>
      <Panel left={T.margin + 930} width={798} height={600} title="Active frame">
        <div style={{ ...MONO, fontSize: 34, color: T.cyan, fontWeight: 700 }}>{af.function}()</div>
        <div style={{ marginTop: 20, fontSize: 28, lineHeight: 1.7 }}>
          <div>locals: <span style={{ ...MONO, color: T.fg }}>{af.locals.length ? af.locals.map((l) => `${l.name}[${l.size}]`).join(", ") : "none"}</span></div>
          <div>returns to: <span style={{ ...MONO, color: T.danger }}>{af.return_address}</span></div>
          <div style={{ color: T.muted, fontSize: 24, marginTop: 14 }}>{W}-byte slots; the callee's frame sits below its caller's.</div>
        </div>
      </Panel>
      <StepNote text={af.note || `${af.function}() is called: its return address and saved RBP are pushed, then space for its locals.`} />
    </>
  );
};

// =====================================================================================
// Heap: glibc-style chunk sizes and tcache LIFO lists (illustrative)
// =====================================================================================
const chunkSize = (req: number) => Math.max(32, (req + 8 + 15) & ~15);
const Heap: React.FC<Extract<Viz, { kind: "heap" }>> = (v) => {
  const { sp, active } = useStepper(v.ops.length);
  const base = 0x55d0c0a0e2a0n;
  // simulate every op up to the active one
  type C = { name: string; addr: bigint; size: number; req: number; free: boolean; next: string };
  const chunks: C[] = []; const tcache: Record<number, string[]> = {};
  let cursor = base;
  v.ops.forEach((o, i) => {
    if (i > active) return;
    if (o.op === "malloc") { const size = chunkSize(o.size ?? 1); chunks.push({ name: o.chunk, addr: cursor, size, req: o.size ?? 1, free: false, next: "" }); cursor += BigInt(size); }
    else { const c = chunks.find((x) => x.name === o.chunk && !x.free); if (c) { c.free = true; const l = (tcache[c.size] ??= []); c.next = l.length ? l[0] : "NULL"; l.unshift(c.name); } }
  });
  const dataH = (size: number) => 92 + Math.min(30, (size - 16) / 10);
  const total = chunks.reduce((a, c) => a + 40 + dataH(c.size) + 12, 0);
  const k = Math.min(1, 500 / Math.max(total, 1));
  let y = 0;
  const op = v.ops[Math.max(0, active)];
  return (
    <>
      <Panel left={T.margin} width={1000} height={600} title="Heap (low → high address) - glibc-style, illustrative">
        <div style={{ position: "relative", transform: `scale(${k})`, transformOrigin: "0 0" }}>
          {chunks.map((c) => {
            const top = y, h = 40 + dataH(c.size); y += h + 12;
            const idx = v.ops.findIndex((o) => o.op === "malloc" && o.chunk === c.name);
            const fidx = v.ops.findIndex((o) => o.op === "free" && o.chunk === c.name);
            const born = sp(idx), freed = fidx >= 0 && fidx <= active ? sp(fidx) : 0;
            return (
              <div key={c.name} style={{ position: "absolute", left: 0, top, width: 900, height: h, opacity: born, transform: `translateX(${(1 - born) * -40}px)` }}>
                <div style={{ position: "absolute", inset: 0, border: `2px solid ${c.free ? T.dim : T.accent}`, borderRadius: 10, background: c.free ? `rgba(91,107,136,${0.15 * freed})` : "rgba(59,130,246,0.08)" }} />
                <div style={{ height: 40, display: "flex", alignItems: "center", padding: "0 16px", background: "rgba(167,139,250,0.20)", borderRadius: "8px 8px 0 0", ...MONO, fontSize: 22, gap: 24 }}>
                  <span style={{ color: T.violet, fontWeight: 700 }}>chunk {c.name}</span><span style={{ color: T.muted }}>prev_size: 0x0</span><span style={{ color: T.fg }}>size: {hex(c.size | 1)}</span>
                  <span style={{ marginLeft: "auto", color: T.dim }}>{hex(c.addr)}</span>
                </div>
                <div style={{ padding: "10px 16px", ...MONO, fontSize: 22, color: c.free ? T.muted : T.fg }}>
                  {c.free ? <>[user data] <span style={{ color: T.warn }}>next → {c.next}</span> <span style={{ color: T.dim }}> key: tcache</span></> : <>[user data] malloc({c.req}) → {hex(c.addr + 16n)}</>}
                  <div style={{ color: T.dim, fontSize: 18, marginTop: 4 }}>{c.size} bytes total ({c.size - 8} usable incl. next chunk's prev_size)</div>
                </div>
              </div>
            );
          })}
        </div>
      </Panel>
      <Panel left={T.margin + 1030} width={698} height={600} title="tcache bins (LIFO)">
        {Object.keys(tcache).length === 0 ? <div style={{ color: T.dim, fontSize: 26 }}>empty - nothing freed yet</div> : Object.entries(tcache).map(([sz, l]) => (
          <div key={sz} style={{ marginBottom: 22 }}>
            <div style={{ ...MONO, fontSize: 24, color: T.cyan, fontWeight: 700 }}>bin {hex(Number(sz))}</div>
            <div style={{ ...MONO, fontSize: 28, marginTop: 6 }}>{l.length ? [...l, "NULL"].join("  →  ") : "empty"}</div>
          </div>
        ))}
        <div style={{ marginTop: 24, color: T.muted, fontSize: 22, lineHeight: 1.45 }}>A freed chunk is pushed on the front of its size's list; the next malloc of that size gets it back (last in, first out).</div>
      </Panel>
      <StepNote text={op.note || (op.op === "malloc" ? `malloc(${op.size}) → ${chunkSize(op.size ?? 1)}-byte chunk ${op.chunk}: size field ${hex(chunkSize(op.size ?? 1) | 1)} (size | PREV_INUSE).` : `free(${op.chunk}): the chunk is not returned to the OS; it joins its tcache list.`)} />
    </>
  );
};

// =====================================================================================
// Registers + assembly execution
// =====================================================================================
export const RegisterVisualization: React.FC<{ names: string[]; values: Record<string, string>; changed: Record<string, string>; p: number }> = ({ names, values, changed, p }) => (
  <div style={{ display: "grid", gap: 10 }}>
    {names.map((n) => {
      const ch = n in changed;
      return (
        <div key={n} style={{ display: "flex", alignItems: "center", gap: 18, padding: "10px 16px", borderRadius: 10, ...MONO, fontSize: 28, background: ch ? `rgba(251,191,36,${0.16 * p + 0.04})` : T.bg, border: `1px solid ${ch ? T.warn : T.border}` }}>
          <span style={{ width: 80, color: T.cyan, fontWeight: 700 }}>{n}</span>
          <span style={{ color: ch ? T.warn : T.fg }}>{values[n] ?? "0x0"}</span>
          {ch ? <span style={{ marginLeft: "auto", color: T.dim, fontSize: 20, opacity: p }}>was {changed[n]}</span> : null}
        </div>
      );
    })}
  </div>
);

const AssemblyExecution: React.FC<Extract<Viz, { kind: "assembly" }>> = (v) => {
  const { sp, active, frame, fps } = useStepper(v.steps.length);
  const cur = Math.max(0, active);
  const values: Record<string, string> = {}; let changed: Record<string, string> = {};
  v.registers.forEach((r) => (values[r] = "0x0"));
  v.steps.forEach((s, i) => {
    if (i > cur) return;
    changed = {};
    s.set.forEach((x) => { changed[x.reg] = values[x.reg]; values[x.reg] = x.value; });
    if ("rip" in values || v.registers.includes("rip")) values["rip"] = v.instructions[s.line].addr; // rip is always the address of the executing line
  });
  const lh = Math.min(66, 500 / v.instructions.length);
  const line = v.steps[cur].line, prev = cur > 0 ? v.steps[cur - 1].line : line;
  const startF = (sp(cur) >= 1 ? 0 : 0);
  void startF; void frame; void fps;
  const barY = (prev + (line - prev) * sp(cur, 14)) * lh;
  return (
    <>
      <Panel left={T.margin} width={940} height={600} title="Disassembly">
        <div style={{ position: "relative", marginTop: 6 }}>
          <div style={{ position: "absolute", left: -8, right: -8, top: barY, height: lh, background: "rgba(59,130,246,0.18)", borderLeft: `4px solid ${T.accent}` }} />
          {v.instructions.map((ins, i) => (
            <div key={i} style={{ position: "relative", height: lh, display: "flex", alignItems: "center", gap: 20, ...MONO, fontSize: Math.min(34, lh * 0.55), opacity: i <= Math.max(...v.steps.slice(0, cur + 1).map((s) => s.line), line) ? 1 : 0.75 }}>
              <span style={{ width: 28, color: T.accent, fontWeight: 700 }}>{i === line ? "▶" : ""}</span>
              <span style={{ color: T.dim, width: 120 }}>{ins.addr}</span>
              <span>{highlight(ins.text, "asm").map((t, k) => <span key={k} style={{ color: SYN[t.k] }}>{t.t}</span>)}</span>
              {ins.comment ? <span style={{ color: T.dim, fontSize: Math.min(22, lh * 0.42) }}>; {ins.comment}</span> : null}
            </div>
          ))}
        </div>
      </Panel>
      <Panel left={T.margin + 970} width={758} height={600} title="Registers">
        <RegisterVisualization names={v.registers} values={values} changed={changed} p={sp(cur)} />
      </Panel>
      <StepNote text={v.steps[cur].note || `Executing ${v.instructions[line].text}`} />
    </>
  );
};

// =====================================================================================
// Control-flow graph
// =====================================================================================
const ControlFlow: React.FC<Extract<Viz, { kind: "control_flow" }>> = (v) => {
  const { sp, active } = useStepper(v.path.length);
  const depth: Record<string, number> = { [v.blocks[0].id]: 0 };
  for (let i = 0; i < v.blocks.length; i++) v.edges.forEach((e) => { if (e.a in depth && !(e.b in depth)) depth[e.b] = depth[e.a] + 1; });
  v.blocks.forEach((b) => { if (!(b.id in depth)) depth[b.id] = 0; });
  const layers: string[][] = [];
  v.blocks.forEach((b) => (layers[depth[b.id]] ??= []).push(b.id));
  const bw = 400, lineH = 30, gapY = 56, gapX = 56;
  const hOf = (id: string) => 34 + v.blocks.find((b) => b.id === id)!.lines.length * lineH;
  const layerH = layers.map((l) => Math.max(...l.map(hOf)));
  const natH = layerH.reduce((a, h) => a + h + gapY, -gapY);
  const natW = Math.max(...layers.map((l) => l.length * (bw + gapX) - gapX));
  const s = Math.min(1, 580 / natH, 1680 / natW);
  const pos: Record<string, { x: number; y: number; h: number }> = {};
  let yy = 0;
  layers.forEach((l, li) => { const wRow = l.length * (bw + gapX) - gapX; l.forEach((id, i) => (pos[id] = { x: (natW - wRow) / 2 + i * (bw + gapX), y: yy, h: hOf(id) })); yy += layerH[li] + gapY; });
  const cur = v.path[Math.max(0, active)];
  const visitedAt = (id: string) => v.path.findIndex((p) => p === id);
  const edgeStep = (a: string, b: string) => { for (let i = 1; i < v.path.length; i++) if (v.path[i - 1] === a && v.path[i] === b) return i; return -1; };
  return (
    <>
      <div style={{ position: "absolute", left: (1920 - natW * s) / 2, top: T.contentTop + 10, width: natW, height: natH, transform: `scale(${s})`, transformOrigin: "0 0" }}>
        <svg width={natW} height={natH} style={{ position: "absolute", inset: 0, overflow: "visible" }}>
          {v.edges.map((e, i) => {
            const A = pos[e.a], B = pos[e.b]; const es = edgeStep(e.a, e.b); const on = es >= 0 && es <= active;
            const back = depth[e.b] <= depth[e.a];
            const x1 = A.x + bw / 2, y1 = A.y + A.h, x2 = B.x + bw / 2, y2 = B.y;
            const d = back ? `M${A.x + bw} ${A.y + A.h / 2} C ${natW + 30} ${A.y + A.h / 2}, ${natW + 30} ${B.y + B.h / 2}, ${B.x + bw} ${B.y + B.h / 2}` : `M${x1} ${y1} C ${x1} ${(y1 + y2) / 2}, ${x2} ${(y1 + y2) / 2}, ${x2} ${y2}`;
            const p = on ? sp(es) : 0;
            return (<g key={i}>
              <path d={d} fill="none" stroke={T.border} strokeWidth={3} />
              {on ? <path d={d} fill="none" stroke={T.cyan} strokeWidth={5} pathLength={1} strokeDasharray={1} strokeDashoffset={1 - p} /> : null}
              {e.label ? <text x={(x1 + x2) / 2 + (back ? natW / 2 : 14)} y={(y1 + y2) / 2} fill={T.warn} fontSize={22} fontFamily={T.mono}>{e.label}</text> : null}
            </g>);
          })}
        </svg>
        {v.blocks.map((b) => {
          const P = pos[b.id], vi = visitedAt(b.id), seen = vi >= 0 && vi <= active, isCur = b.id === cur;
          const p = seen ? sp(vi) : 0;
          return (
            <div key={b.id} style={{ position: "absolute", left: P.x, top: P.y, width: bw, height: P.h, boxSizing: "border-box", borderRadius: 10, background: seen ? T.surface : T.panel, border: `${isCur ? 3 : 2}px solid ${isCur ? T.cyan : seen ? T.accent : T.border}`, opacity: seen ? 1 : 0.55, boxShadow: isCur ? "0 0 0 4px rgba(34,211,238,0.12)" : "none", transform: `scale(${1 + 0.02 * (isCur ? p : 0)})` }}>
              <div style={{ height: 34, padding: "0 14px", display: "flex", alignItems: "center", ...MONO, fontSize: 20, color: isCur ? T.cyan : T.muted, borderBottom: `1px solid ${T.border}`, fontWeight: 700 }}>{b.id}</div>
              {b.lines.map((l, i) => <div key={i} style={{ height: lineH, padding: "0 14px", display: "flex", alignItems: "center", ...MONO, fontSize: 21, whiteSpace: "nowrap" }}><span style={{ whiteSpace: "pre" }}>{highlight(l, "asm").map((t, k) => <span key={k} style={{ color: SYN[t.k] }}>{t.t}</span>)}</span></div>)}
            </div>
          );
        })}
      </div>
      <StepNote text={`Execution reaches block ${cur}${active > 0 ? ` from ${v.path[active - 1]}` : ""} (step ${Math.max(0, active) + 1} of ${v.path.length}).`} />
    </>
  );
};

// =====================================================================================
// Packet flow (sequence of messages between hosts)
// =====================================================================================
const PacketFlow: React.FC<Extract<Viz, { kind: "packet_flow" }>> = (v) => {
  const { sp, active } = useStepper(v.packets.length);
  const n = v.nodes.length, colW = 1500 / n, cx = (id: string) => 210 + colW * (v.nodes.findIndex((x) => x.id === id) + 0.5);
  const rowH = Math.min(78, 430 / v.packets.length), y0 = 340;
  return (
    <>
      {v.nodes.map((nd, i) => (
        <React.Fragment key={nd.id}>
          <div style={{ position: "absolute", left: cx(nd.id) - 130, top: T.contentTop + 10, width: 260, height: 70, display: "grid", placeItems: "center", background: T.surface, border: `2px solid ${i === 0 ? T.accent : i === n - 1 ? T.ok : T.violet}`, borderRadius: 12, fontSize: 28, fontWeight: 600 }}>{nd.label}</div>
          <div style={{ position: "absolute", left: cx(nd.id) - 1, top: T.contentTop + 80, width: 2, height: 500, background: `repeating-linear-gradient(${T.border} 0 10px, transparent 10px 20px)` }} />
        </React.Fragment>
      ))}
      <svg width={1920} height={1080} style={{ position: "absolute", left: 0, top: 0 }}>
        {v.packets.map((p, i) => {
          if (i > active) return null;
          const a = cx(p.src), b = cx(p.dst), y = y0 + i * rowH, pr = sp(i), cur = i === active, dir = b > a ? 1 : -1;
          const x = a + (b - a) * pr;
          return (<g key={i} opacity={cur ? 1 : 0.6}>
            <line x1={a} y1={y} x2={x} y2={y} stroke={cur ? T.cyan : T.accent} strokeWidth={cur ? 5 : 3} />
            {pr > 0.95 ? <polygon points="0,0 -16,-9 -16,9" transform={`translate(${b} ${y}) ${dir < 0 ? "scale(-1,1)" : ""}`} fill={cur ? T.cyan : T.accent} /> : null}
            {cur && pr < 1 ? <circle cx={x} cy={y} r={9} fill={T.warn} /> : null}
            <text x={(a + b) / 2} y={y - 12} textAnchor="middle" fill={T.fg} fontSize={24} fontWeight={600} fontFamily={T.mono} opacity={clamp(pr * 2)}>{p.label}</text>
            {p.detail ? <text x={(a + b) / 2} y={y + 24} textAnchor="middle" fill={T.muted} fontSize={19} fontFamily={T.mono} opacity={clamp(pr * 2)}>{p.detail}</text> : null}
          </g>);
        })}
      </svg>
      <StepNote text={`${v.nodes.find((x) => x.id === v.packets[Math.max(0, active)].src)?.label} → ${v.nodes.find((x) => x.id === v.packets[Math.max(0, active)].dst)?.label}: ${v.packets[Math.max(0, active)].label}`} />
    </>
  );
};

// =====================================================================================
// Process execution / malware lifecycle
// =====================================================================================
export const ProcessExecutionAnimation: React.FC<{ stages: { label: string; detail: string }[] }> = ({ stages }) => {
  const { sp, active } = useStepper(stages.length);
  const cur = Math.max(0, active), n = stages.length, w = (1728 - (n - 1) * 12) / n;
  return (
    <>
      <div style={{ position: "absolute", left: T.margin, right: T.margin, top: T.contentTop + 10, display: "flex", gap: 12 }}>
        {stages.map((s, i) => {
          const done = i < cur, on = i === cur;
          return (
            <div key={i} style={{ width: w, height: 110, boxSizing: "border-box", padding: "16px 18px", borderRadius: 12, background: on ? "rgba(59,130,246,0.22)" : T.panel, border: `2px solid ${on ? T.cyan : done ? T.accent : T.border}`, opacity: i <= active ? 0.55 + 0.45 * sp(i) : 0.4 }}>
              <div style={{ ...MONO, fontSize: 18, color: on ? T.cyan : T.dim, fontWeight: 700 }}>{done ? "✓ " : ""}{String(i + 1).padStart(2, "0")}</div>
              <div style={{ marginTop: 6, fontSize: n > 5 ? 22 : 26, fontWeight: 600, lineHeight: 1.2 }}>{s.label}</div>
            </div>
          );
        })}
      </div>
      <div style={{ position: "absolute", left: T.margin, right: T.margin, top: T.contentTop + 150, height: 4, background: T.border, borderRadius: 2 }}>
        <div style={{ height: 4, width: `${((cur + sp(cur)) / n) * 100}%`, background: `linear-gradient(90deg, ${T.accent}, ${T.cyan})`, borderRadius: 2 }} />
      </div>
      <Panel left={T.margin} top={T.contentTop + 190} width={1728} height={380} title={`Stage ${cur + 1} of ${n}`}>
        <div key={cur} style={{ opacity: sp(cur), transform: `translateY(${(1 - sp(cur)) * 16}px)` }}>
          <div style={{ fontSize: 52, fontWeight: 700, color: T.cyan }}>{stages[cur].label}</div>
          <div style={{ marginTop: 22, fontSize: 36, lineHeight: 1.45, color: T.fg, maxWidth: 1500 }}>{stages[cur].detail}</div>
        </div>
      </Panel>
    </>
  );
};

// =====================================================================================
// ELF / PE / process memory layout
// =====================================================================================
const LayoutStack: React.FC<Extract<Viz, { kind: "layout" }>> = (v) => {
  const { sp, active } = useStepper(v.regions.length);
  const cur = Math.max(0, active), n = v.regions.length, h = Math.min(78, 500 / n);
  const title = v.format === "elf" ? "ELF file structure" : v.format === "pe" ? "PE file structure" : "Process virtual memory (high → low)";
  const r = v.regions[cur];
  return (
    <>
      <Panel left={T.margin} width={900} height={600} title={title}>
        {v.regions.map((g, i) => {
          const on = i === cur, p = i <= active ? sp(i) : 0;
          return (
            <div key={i} style={{ height: h - 8, marginBottom: 8, display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0 20px", borderRadius: 8, opacity: p, transform: `translateX(${(1 - p) * -30}px)`, background: on ? "rgba(59,130,246,0.25)" : T.bg, border: `2px solid ${on ? T.cyan : T.border}`, ...MONO, fontSize: 24 }}>
              <span style={{ color: on ? T.fg : T.muted, fontWeight: on ? 700 : 500, fontFamily: T.mono }}>{g.name}</span>
              <span style={{ color: T.dim, fontSize: 20 }}>{g.range}</span>
            </div>
          );
        })}
      </Panel>
      <Panel left={T.margin + 930} width={798} height={600} title="Selected">
        <div key={cur} style={{ opacity: sp(cur) }}>
          <div style={{ ...MONO, fontSize: 38, color: T.cyan, fontWeight: 700 }}>{r.name}</div>
          {r.range ? <div style={{ ...MONO, fontSize: 24, color: T.muted, marginTop: 8 }}>{r.range}</div> : null}
          {r.flags ? <div style={{ display: "inline-block", marginTop: 14, padding: "4px 14px", borderRadius: 8, border: `1px solid ${T.warn}`, color: T.warn, ...MONO, fontSize: 24 }}>{r.flags}</div> : null}
          <div style={{ marginTop: 26, fontSize: 30, lineHeight: 1.5 }}>{r.note}</div>
        </div>
      </Panel>
    </>
  );
};

export const VisualizationView: React.FC<{ viz: Viz }> = ({ viz }) => {
  switch (viz.kind) {
    case "buffer_overflow": return <BufferOverflowAnimation {...viz} />;
    case "stack_frames": return <StackFrames {...viz} />;
    case "heap": return <Heap {...viz} />;
    case "assembly": return <AssemblyExecution {...viz} />;
    case "control_flow": return <ControlFlow {...viz} />;
    case "packet_flow": return <PacketFlow {...viz} />;
    case "lifecycle": return <ProcessExecutionAnimation stages={viz.stages} />;
    case "layout": return <LayoutStack {...viz} />;
  }
};
export { BufferOverflowAnimation, StackFrames as StackMemoryVisualization, Heap as HeapMemoryVisualization, AssemblyExecution, ControlFlow as ControlFlowVisualization, PacketFlow as PacketFlowAnimation, LayoutStack };
export const _unused = { easedProgress, wrapLabel };
