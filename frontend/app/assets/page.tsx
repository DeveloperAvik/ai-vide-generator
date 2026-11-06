"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import { useApi } from "@/hooks/useApi";
import { Btn, Card, ErrorNote, useAsyncAction, PageHeader } from "@/components/ui";
import type { Lesson } from "@/types";

export default function Assets() {
  const { data: lessons } = useApi<Lesson[]>("/lessons");
  const [lid, setLid] = useState<number | null>(null);
  const { data: assets, reload } = useApi<any[]>(lid ? `/lessons/${lid}/assets` : null);
  const [scene, setScene] = useState("scene_001");
  const { busy, err, run } = useAsyncAction();
  const upload = (f: File) => run(async () => { const fd = new FormData(); fd.append("file", f); const r = await api<any>(`/lessons/${lid}/recordings/${scene}`, { method: "POST", body: fd }); alert(r.warning); reload(); });
  return (
    <div className="space-y-5"><PageHeader title="Asset Manager" desc="Attach lab recordings and review generated visuals per lesson." /><ErrorNote msg={err} />
      <Card title="Lesson"><select value={lid ?? ""} onChange={(e) => setLid(e.target.value ? +e.target.value : null)}><option value="">Select…</option>{lessons?.map((l) => <option key={l.id} value={l.id}>{l.title}</option>)}</select></Card>
      {lid && (<>
        <Card title="Attach lab recording (OBS / terminal / browser MP4)">
          <p className="mb-2 text-xs text-amber-300">Review recordings yourself for credentials, tokens, personal data and non-lab IPs before attaching; only text is scanned automatically. Recordings are not presented as evidence of real-world results.</p>
          <div className="flex flex-wrap gap-2"><input className="max-w-40" value={scene} onChange={(e) => setScene(e.target.value)} /><input type="file" accept=".mp4,.mov,.webm,.png,.jpg" disabled={busy} className="max-w-xs" onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])} /></div>
        </Card>
        <Card title="Generated visual assets"><ul className="grid gap-1 text-sm md:grid-cols-2">{assets?.map((a) => <li key={a.id} className="text-slate-300">{a.scene_id} · {a.kind} <span className="text-slate-500">{a.path}</span></li>)}</ul></Card>
      </>)}
    </div>
  );
}
