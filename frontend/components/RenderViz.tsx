"use client";
import React, { memo, useEffect, useRef, useState } from "react";
import { Icon, IconName } from "./Icon";
import { Progress } from "./ui";
import { blobUrl } from "@/lib/api";
import type { Render, RenderScene, RenderStage } from "@/types";

export const ACTIVE = ["queued", "running", "cancelling"];

/* ---------- status ---------- */
export type RenderState = "preparing" | "queued" | "running" | "cancelling" | "done" | "failed" | "cancelled";
// "preparing" is derived: the job is running but the backend has not reported any progress yet.
export const stateOf = (status: string, progress: number): RenderState =>
  status === "running" && progress <= 0 ? "preparing" : (["queued", "running", "cancelling", "done", "failed", "cancelled"].includes(status) ? status : "queued") as RenderState;

const STATES: Record<RenderState, { text: string; icon: IconName; tone: string; anim: string }> = {
  preparing: { text: "Preparing", icon: "refresh", tone: "bg-sky-500/10 text-sky-300 ring-sky-500/25", anim: "animate-spin" },
  queued: { text: "Queued", icon: "clock", tone: "bg-slate-500/10 text-slate-300 ring-slate-500/20", anim: "animate-pulse" },
  running: { text: "Rendering", icon: "film", tone: "bg-sky-500/10 text-sky-300 ring-sky-500/25", anim: "animate-pulse" },
  cancelling: { text: "Cancelling", icon: "x", tone: "bg-amber-500/10 text-amber-300 ring-amber-500/25", anim: "animate-pulse" },
  done: { text: "Completed", icon: "check", tone: "bg-emerald-500/10 text-emerald-300 ring-emerald-500/25", anim: "" },
  failed: { text: "Failed", icon: "alert", tone: "bg-rose-500/10 text-rose-300 ring-rose-500/25", anim: "" },
  cancelled: { text: "Cancelled", icon: "x", tone: "bg-slate-500/10 text-slate-400 ring-slate-500/20", anim: "" },
};

export const RenderStatus = memo(function RenderStatus({ status, progress = 0, pop = false }: { status: string; progress?: number; pop?: boolean }) {
  const st = stateOf(status, progress), m = STATES[st];
  return (
    <span role="status" aria-label={`Render ${m.text.toLowerCase()}`} className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-0.5 text-[11px] font-medium ring-1 ring-inset ${m.tone} ${pop ? "animate-pop" : ""}`}>
      <Icon name={m.icon} className={`h-3 w-3 ${m.anim}`} />{m.text}
    </span>
  );
});

/* ---------- pipeline stages (only when the backend reports one) ---------- */
const STAGES: { key: RenderStage; label: string; icon: IconName }[] = [
  { key: "script", label: "Script preparation", icon: "list" }, { key: "scenes", label: "Scene generation", icon: "layers" },
  { key: "images", label: "Image generation", icon: "image" }, { key: "voice", label: "Voice synthesis", icon: "mic" },
  { key: "video", label: "Video rendering", icon: "film" }, { key: "finalize", label: "Finalization", icon: "check" },
];

export const StageTrack = memo(function StageTrack({ stage, status }: { stage?: string; status: string }) {
  const at = STAGES.findIndex((s) => s.key === stage);
  if (at < 0) return null; // unknown/absent stage: show nothing rather than invent one
  const live = ACTIVE.includes(status), finished = status === "done";
  return (
    <ol aria-label="Render pipeline stages" className="mt-3 grid grid-cols-3 gap-1.5 sm:grid-cols-6">
      {STAGES.map((s, i) => {
        const st = finished || i < at ? "done" : i === at ? (live ? "active" : "stopped") : "pending";
        const cls = { done: "border-emerald-500/25 text-emerald-300", active: "border-brand-500/60 bg-brand-500/10 text-brand-400 shadow-[0_0_10px_rgb(var(--brand-500)/.25)]", stopped: "border-rose-500/30 text-rose-300", pending: "border-line text-slate-500" }[st];
        return (
          <li key={s.key} aria-current={st === "active" ? "step" : undefined} className={`flex flex-col items-center gap-1 rounded-lg border px-1.5 py-1.5 text-center text-[10px] leading-tight transition-colors duration-500 ${cls}`}>
            <Icon name={st === "done" ? "check" : s.icon} className={`h-3.5 w-3.5 ${st === "active" ? "animate-pulse" : ""}`} />
            <span>{s.label}</span><span className="sr-only">{st === "done" ? "complete" : st === "active" ? "in progress" : st === "stopped" ? "stopped" : "pending"}</span>
          </li>
        );
      })}
    </ol>
  );
});

/* ---------- scenes ---------- */
function SceneCard({ scene, index }: { scene: RenderScene; index: number }) {
  const [src, setSrc] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  useEffect(() => {
    if (scene.status !== "done" || !scene.thumbnail_url) return;
    let u: string | undefined, dead = false;
    blobUrl(scene.thumbnail_url).then((x) => { u = x; if (!dead) setSrc(x); }).catch(() => {});
    return () => { dead = true; if (u) URL.revokeObjectURL(u); };
  }, [scene.status, scene.thumbnail_url]);
  const ring = { pending: "border-line", active: "border-brand-500/70 shadow-[0_0_12px_rgb(var(--brand-500)/.35)]", done: "border-emerald-500/30" }[scene.status];
  return (
    <li aria-label={`Scene ${index + 1}: ${scene.status}`} aria-current={scene.status === "active" ? "step" : undefined} className={`relative aspect-video overflow-hidden rounded-md border bg-raised ${ring}`}>
      {(scene.status !== "done" || !loaded) && <div className="absolute inset-0 overflow-hidden"><div className={`absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-slate-50/[.08] to-transparent ${scene.status === "pending" ? "" : "animate-[shimmer_1.4s_infinite]"}`} /></div>}
      {src && <img src={src} alt="" onLoad={() => setLoaded(true)} className={`absolute inset-0 h-full w-full object-cover transition-opacity duration-700 ${loaded ? "opacity-100" : "opacity-0"}`} />}
      <span className="tnum absolute bottom-0.5 left-1 text-[10px] text-slate-400">{index + 1}</span>
      {scene.status === "done" && <Icon name="check" className="absolute right-1 top-1 h-3 w-3 text-emerald-300" />}
    </li>
  );
}

/** Scene cards when the API provides them; otherwise a film-strip driven only by the overall progress value. */
export const SceneStrip = memo(function SceneStrip({ scenes, progress, active }: { scenes?: RenderScene[]; progress: number; active: boolean }) {
  if (scenes?.length) return <ul aria-label="Scenes" className="mt-3 grid grid-cols-4 gap-1.5 sm:grid-cols-6">{scenes.map((s, i) => <SceneCard key={s.scene_id} scene={s} index={i} />)}</ul>;
  const N = 16, lit = Math.floor(Math.min(1, progress) * N);
  return (
    <div aria-hidden className="mt-3" title="Per-scene status is not reported by the backend; this shows overall progress only.">
      <div className="flex gap-1">{Array.from({ length: N }, (_, i) => (
        <span key={i} className={`h-5 flex-1 rounded-sm border transition-colors duration-500 ${i < lit ? "border-brand-500/40 bg-brand-500/25" : i === lit && active ? "animate-pulse border-brand-500/60 bg-brand-500/10" : "border-line bg-raised"}`} />
      ))}</div>
    </div>
  );
});

/* ---------- card ---------- */
const SPARKS = [["8%", "70%", "0s"], ["24%", "40%", "1.1s"], ["46%", "75%", "2.1s"], ["68%", "35%", "0.6s"], ["86%", "65%", "1.7s"]];

export const RenderCard = memo(function RenderCard({ r, actions, onCompleted }: { r: Render; actions?: React.ReactNode; onCompleted?: (id: number) => void }) {
  const live = ACTIVE.includes(r.status);
  const prev = useRef<string | undefined>(undefined); // undefined on first mount, so page loads / refreshes never celebrate
  const [celebrate, setCelebrate] = useState(false);
  useEffect(() => {
    const was = prev.current;
    prev.current = r.status;
    if (r.status === "done" && was && ACTIVE.includes(was)) {
      setCelebrate(true); onCompleted?.(r.id);
      const t = setTimeout(() => setCelebrate(false), 2500);
      return () => clearTimeout(t);
    }
  }, [r.status, r.id, onCompleted]);
  return (
    <article aria-label={`Render ${r.id}`} className={`relative overflow-hidden rounded-xl border bg-surface p-4 text-sm transition-colors duration-700 ${live ? "border-brand-500/30" : celebrate ? "border-emerald-500/50" : "border-line"}`}>
      {live && (<>
        <div aria-hidden className="pointer-events-none absolute inset-0 animate-sheen bg-[linear-gradient(110deg,transparent_20%,rgb(var(--brand-500)/.07)_40%,rgb(var(--brand-600)/.07)_60%,transparent_80%)] bg-[length:200%_100%]" />
        <div aria-hidden className="pointer-events-none absolute inset-0">{SPARKS.map(([l, t, d], i) => <span key={i} className="absolute h-1 w-1 animate-sparkle rounded-full bg-brand-400 opacity-0 shadow-[0_0_6px_rgb(var(--brand-400)/.9)]" style={{ left: l, top: t, animationDelay: d }} />)}</div>
      </>)}
      {celebrate && <div aria-hidden className="pointer-events-none absolute right-6 top-6 h-8 w-8 animate-ring rounded-full border-2 border-emerald-400" />}
      <div className="relative">
        <div className="flex items-center justify-between gap-2">
          <span className="min-w-0 truncate">#{r.id} · lesson {r.lesson_id} · {r.engine}</span>
          <RenderStatus status={r.status} progress={r.progress} pop={celebrate} />
        </div>
        <div className="mt-3"><Progress v={r.status === "done" ? 1 : r.progress} active={live} /></div>
        {live && <StageTrack stage={r.stage} status={r.status} />}
        {r.stage && !live && r.status === "failed" && <StageTrack stage={r.stage} status={r.status} />}
        {live && <SceneStrip scenes={r.scenes} progress={r.progress} active={r.status === "running"} />}
        <div role="alert" hidden={!r.error} className="mt-2 text-xs text-rose-300">{r.error}</div>
        {celebrate && <p role="status" className="mt-2 animate-fade-up text-xs text-emerald-300">Render complete — preview is ready.</p>}
        {actions && <div className="mt-2 space-x-2">{actions}</div>}
      </div>
    </article>
  );
});
