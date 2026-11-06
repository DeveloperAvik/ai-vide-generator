"use client";
import { use, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useApi } from "@/hooks/useApi";
import { Btn, Card, ErrorNote, useAsyncAction, PageHeader } from "@/components/ui";
import type { Scene } from "@/types";

export default function Storyboard({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { data, error, reload } = useApi<any>(`/lessons/${id}`);
  const [scenes, setScenes] = useState<Scene[]>([]);
  const { busy, err, run } = useAsyncAction();
  useEffect(() => { if (data?.storyboard) setScenes(data.storyboard.scenes); }, [data]);
  const upd = (i: number, patch: Partial<Scene>) => setScenes(scenes.map((s, k) => (k === i ? { ...s, ...patch } : s)));
  return (
    <div className="space-y-4">
      <PageHeader title="Storyboard Editor" desc="Edit narration, timing and transitions per scene." /><ErrorNote msg={error ?? err} />
      {data?.length && (() => { const L = data.length; const off = L.estimated_minutes < Math.max(5, L.requested_minutes * 0.8) || L.estimated_minutes > Math.min(12, L.requested_minutes * 1.2);
        return (<div className={`flex flex-wrap items-center justify-between gap-3 rounded-xl border p-4 text-sm ${off ? "border-amber-500/30 bg-amber-500/10 text-amber-200" : "border-line bg-surface text-slate-300"}`}>
          <div><b className="tnum">{L.estimated_minutes} min</b> estimated · requested {L.requested_minutes} min · <span className="tnum">{L.words}</span> narration words (target ≈ {L.target_words}){off && <span className="ml-2 font-medium">Outside the allowed range — rendering will fail the quality check.</span>}</div>
          <Btn kind="ghost" disabled={busy} onClick={() => run(async () => { await api(`/lessons/${id}/storyboard/regenerate`, { method: "POST" }); reload(); }, "Storyboard regenerated")}>Regenerate to fit length</Btn></div>); })()}
      {!data?.storyboard && <p className="text-slate-400">No storyboard yet. It is generated when assets are built (after script approval).</p>}
      {scenes.map((s, i) => (
        <Card key={s.scene_id} title={`${s.scene_id} · ${s.type}`}>
          <div className="grid gap-3 md:grid-cols-4">
            <label className="text-sm md:col-span-3">Narration<textarea rows={3} value={s.narration} onChange={(e) => upd(i, { narration: e.target.value })} /></label>
            <div className="space-y-2 text-sm"><label>Duration (s)<input type="number" value={s.duration_seconds} onChange={(e) => upd(i, { duration_seconds: +e.target.value })} /></label>
              <label>Transition<select value={s.transition} onChange={(e) => upd(i, { transition: e.target.value })}>{["fade", "slide", "wipe", "zoom", "none"].map((t) => <option key={t}>{t}</option>)}</select></label></div>
            <label className="text-sm md:col-span-3">On-screen text<input value={s.on_screen_text} onChange={(e) => upd(i, { on_screen_text: e.target.value })} /></label>
            <div className="flex items-end"><Btn kind="ghost" disabled={busy} onClick={() => run(async () => { await api(`/lessons/${id}/storyboard/regenerate-scene/${s.scene_id}`, { method: "POST" }); reload(); })}>Regenerate scene</Btn></div>
          </div>
        </Card>))}
      {scenes.length > 0 && <Btn disabled={busy} onClick={() => run(async () => { await api(`/lessons/${id}/storyboard`, { method: "PUT", json: { ...data.storyboard, scenes } }); reload(); })}>Save storyboard (new version)</Btn>}
    </div>
  );
}
