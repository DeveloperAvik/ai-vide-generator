"use client";
import { useState } from "react";
import { api, confirmDelete } from "@/lib/api";
import { useApi } from "@/hooks/useApi";
import { Btn, Card, ErrorNote, useAsyncAction, PageHeader } from "@/components/ui";
import { RenderCard } from "@/components/RenderViz";
import { Video } from "@/components/MediaPreview";
import type { Lesson, Render } from "@/types";

export default function Renders() {
  const { data, error, reload } = useApi<Render[]>("/renders", 3000);
  const { data: lessons, reload: rl } = useApi<Lesson[]>("/lessons", 5000);
  const [sel, setSel] = useState<number | null>(null);
  const { err, run } = useAsyncAction();
  const ready = lessons?.filter((l) => ["ASSETS_READY", "RENDERING"].includes(l.status) || (l.status === "FAILED" && l.last_error.startsWith("render")));
  return (
    <div className="space-y-5"><PageHeader title="Video Rendering" desc="Render jobs, progress and previews." /><ErrorNote msg={error ?? err} />
      <Card title="Ready to render">{ready?.length ? ready.map((l) => (<div key={l.id} className="flex items-center justify-between py-1 text-sm">{l.title}
        <Btn onClick={() => run(async () => { await api(l.status === "FAILED" ? `/lessons/${l.id}/retry` : `/lessons/${l.id}/stage/render`, { method: "POST" }); rl(); reload(); })}>{l.status === "FAILED" ? "Retry render" : "Render"}</Btn></div>)) : <p className="text-sm text-slate-400">Nothing waiting.</p>}</Card>
      <div className="grid gap-5 lg:grid-cols-2">
        <Card title="Render jobs"><div className="space-y-3">{data?.map((r) => (<RenderCard key={r.id} r={r} onCompleted={setSel} actions={<>{r.status === "done" && <Btn kind="ghost" icon="play" onClick={() => setSel(r.id)}>Preview</Btn>}{r.status === "running" && <Btn kind="danger" onClick={() => run(async () => { await api(`/renders/${r.id}/cancel`, { method: "POST" }); reload(); })}>Cancel</Btn>}{!["running", "queued", "cancelling"].includes(r.status) && <Btn kind="ghost" onClick={() => run(async () => { if (await confirmDelete(`/renders/${r.id}`, `render #${r.id}`)) { if (sel === r.id) setSel(null); reload(); rl(); } }, "Render deleted")}>Delete</Btn>}</>} />))}</div></Card>
        <Card title="Preview">{sel ? <div key={sel} className="animate-fade-up"><Video renderId={sel} /></div> : <p className="text-sm text-slate-400">Select a finished render.</p>}</Card>
      </div>
    </div>
  );
}
