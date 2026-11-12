"use client";
import { useEffect, useRef, useState } from "react";
import { api, blobUrl } from "@/lib/api";
import { useApi } from "@/hooks/useApi";
import { Badge, Btn, Card, EmptyState, ErrorNote, PageHeader, Progress, useAsyncAction } from "@/components/ui";

type Opts = { styles: string[]; music: string[]; max_photos: number; duration_s: [number, number] };
type Item = { id: string; status: string; stage: string; progress: number; created: string; error: string | null; topic: string; style: string };
type Detail = Item & { simulated?: boolean; plan?: { title: string; caption: string; hashtags: string[]; scenes: { headline: string; narration: string }[] }; result?: { duration: number; voiceover: boolean; music: string; warnings: string[] } };

function Player({ id }: { id: string }) {
  const [src, setSrc] = useState<string | null>(null);
  useEffect(() => {
    let u: string | null = null;
    blobUrl(`/reels/${id}/video`).then((x) => { u = x; setSrc(x); }).catch(() => setSrc(null));
    return () => { if (u) URL.revokeObjectURL(u); };
  }, [id]);
  if (!src) return <p className="text-sm text-slate-400">Loading video…</p>;
  return (
    <div className="space-y-2">
      <video src={src} controls className="mx-auto max-h-[560px] rounded-lg border border-line" />
      <a href={src} download={`reel-${id}.mp4`} className="block text-center text-sm text-sky-400 underline">Download MP4</a>
    </div>
  );
}

export default function Reels() {
  const { data: opts } = useApi<Opts>("/reels/options");
  const { data: list, reload } = useApi<Item[]>("/reels", 3000);
  const [sel, setSel] = useState<string | null>(null);
  const { data: detail } = useApi<Detail>(sel ? `/reels/${sel}` : null, 2000);
  const { err, busy, run } = useAsyncAction();
  const [f, setF] = useState({ topic: "", style: "trending", style_notes: "", duration_s: 30, music: "auto", voiceover: true, captions: true });
  const [files, setFiles] = useState<File[]>([]);
  const fileRef = useRef<HTMLInputElement>(null);
  const max = opts?.max_photos ?? 12;

  const submit = () => run(async () => {
    const fd = new FormData();
    Object.entries(f).forEach(([k, v]) => fd.append(k, String(v)));
    files.forEach((p) => fd.append("photos", p));
    const r = await api<{ id: string }>("/reels", { method: "POST", body: fd });
    setSel(r.id); setFiles([]); if (fileRef.current) fileRef.current.value = ""; reload();
  }, "Reel queued");

  return (
    <div className="space-y-5">
      <PageHeader title="Instagram Reels" desc="Any topic (plus optional photos) becomes a 9:16 video with narration, captions and music." />
      <ErrorNote msg={err} />
      <div className="grid gap-5 lg:grid-cols-2">
        <Card title="Create a reel">
          <div className="grid gap-3">
            <label className="text-sm">Topic<input value={f.topic} maxLength={300} placeholder="e.g. 3 habits that make studying easier" onChange={(e) => setF({ ...f, topic: e.target.value })} /></label>
            <div className="grid grid-cols-2 gap-3">
              <label className="text-sm">Style<select value={f.style} onChange={(e) => setF({ ...f, style: e.target.value })}>{(opts?.styles ?? ["trending"]).map((s) => <option key={s}>{s}</option>)}</select></label>
              <label className="text-sm">Music<select value={f.music} onChange={(e) => setF({ ...f, music: e.target.value })}>{(opts?.music ?? ["auto"]).map((s) => <option key={s}>{s}</option>)}</select></label>
            </div>
            <label className="text-sm">Extra direction (optional)<input value={f.style_notes} maxLength={400} placeholder="funny, for beginners, Gen-Z tone…" onChange={(e) => setF({ ...f, style_notes: e.target.value })} /></label>
            <label className="text-sm">Length: {f.duration_s}s<input type="range" min={opts?.duration_s[0] ?? 10} max={opts?.duration_s[1] ?? 90} step={5} value={f.duration_s} onChange={(e) => setF({ ...f, duration_s: +e.target.value })} /></label>
            <div className="flex gap-5 text-sm">
              <label className="flex items-center gap-2"><input type="checkbox" checked={f.voiceover} onChange={(e) => setF({ ...f, voiceover: e.target.checked })} />Voiceover</label>
              <label className="flex items-center gap-2"><input type="checkbox" checked={f.captions} onChange={(e) => setF({ ...f, captions: e.target.checked })} />Captions</label>
            </div>
            <label className="text-sm">Photos (optional, up to {max})
              <input ref={fileRef} type="file" accept="image/jpeg,image/png,image/webp" multiple onChange={(e) => setFiles(Array.from(e.target.files ?? []).slice(0, max))} /></label>
            {files.length > 0 && <p className="text-xs text-slate-400">{files.length} photo(s) selected, used in order.</p>}
            <Btn onClick={submit} loading={busy} disabled={busy || f.topic.trim().length < 3} icon="film">Generate reel</Btn>
            <p className="text-xs text-slate-400">Scripts are not fact-checked. Review before posting; download the MP4 and upload it to Instagram.</p>
          </div>
        </Card>
        <Card title="Preview">
          {!sel || !detail ? <p className="text-sm text-slate-400">Select or create a reel.</p> : (
            <div className="space-y-3">
              <div className="flex items-center gap-2 text-sm"><Badge s={detail.status} />{detail.simulated && <span className="text-amber-400">Template script (LLM is mock)</span>}</div>
              {detail.status === "done" ? <Player key={sel} id={sel} /> : detail.status === "error" ? <ErrorNote msg={detail.error} /> : <Progress v={detail.progress} active />}
              {detail.result?.warnings.map((w) => <p key={w} className="text-xs text-amber-400">{w}</p>)}
              {detail.plan && (
                <details className="text-sm"><summary className="cursor-pointer">Script and caption</summary>
                  <p className="mt-2 font-medium">{detail.plan.title}</p>
                  <ol className="list-decimal pl-5">{detail.plan.scenes.map((s, i) => <li key={i}><b>{s.headline}:</b> {s.narration}</li>)}</ol>
                  <p className="mt-2 whitespace-pre-wrap">{detail.plan.caption}{"\n"}{detail.plan.hashtags.map((h) => `#${h}`).join(" ")}</p>
                </details>)}
            </div>)}
        </Card>
      </div>
      <Card title="Your reels">
        {!list?.length ? <EmptyState icon="film" title="No reels yet" hint="Create your first one above." /> : (
          <div className="divide-y divide-line">{list.map((r) => (
            <button key={r.id} onClick={() => setSel(r.id)} className={`flex w-full items-center justify-between gap-3 py-2 text-left text-sm ${sel === r.id ? "text-sky-400" : ""}`}>
              <span className="truncate">{r.topic} <span className="text-slate-400">· {r.style}</span></span>
              <span className="flex w-40 shrink-0 items-center gap-2">{r.status === "running" || r.status === "queued" ? <Progress v={r.progress} active /> : <Badge s={r.status} />}</span>
            </button>))}</div>)}
      </Card>
    </div>
  );
}
