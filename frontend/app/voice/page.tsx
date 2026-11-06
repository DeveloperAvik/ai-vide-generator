"use client";
import { useState } from "react";
import { api, blobUrl } from "@/lib/api";
import { useApi } from "@/hooks/useApi";
import { Badge, Btn, Card, ErrorNote, useAsyncAction, PageHeader } from "@/components/ui";

export default function VoiceConfig() {
  const { data, error } = useApi<any>("/system/providers");
  const [text, setText] = useState("Welcome to the lesson. Today we look at how injection flaws work and how to defend against them.");
  const [src, setSrc] = useState<string | null>(null);
  const [used, setUsed] = useState<string>("");
  const { busy, err, run } = useAsyncAction();
  const preview = (provider?: string) => run(async () => {
    const res: Response = await api("/system/voice/preview", { method: "POST", json: { text, provider } });
    setUsed(res.headers.get("X-Voice-Provider") ?? ""); setSrc(URL.createObjectURL(await res.blob()));
  });
  return (
    <div className="space-y-5"><PageHeader title="Voice Configuration" desc="Narration voices. Kokoro (local, Apache-2.0) is the production default." /><ErrorNote msg={error ?? err} />
      <p className="text-sm text-slate-400">Kokoro is the production voice (Piper is the fallback). macOS <code>say</code> is a development fallback and is disabled in production. The same model file is used for every lesson, which keeps the instructor's voice consistent.</p>
      <div className="grid gap-3 md:grid-cols-3">{data?.voice.map((p: any) => (
        <Card key={p.name}><div className="flex items-center justify-between"><b>{p.name}</b><span className="space-x-2">{p.paid && <Badge s="paid" />}<Badge s={p.available ? "done" : "unavailable"} /></span></div><p className="mt-2 text-sm text-slate-400">{p.detail}</p>
          <div className="mt-2"><Btn kind="ghost" disabled={!p.available || busy} onClick={() => preview(p.name)}>Preview</Btn></div></Card>))}</div>
      <Card title="Preview text"><textarea rows={3} maxLength={400} value={text} onChange={(e) => setText(e.target.value)} />
        <div className="mt-3 flex items-center gap-3"><Btn disabled={busy} onClick={() => preview()}>{busy ? "Synthesizing…" : "Preview default voice"}</Btn>{src && <audio src={src} controls autoPlay />}{used && <span className="text-xs text-slate-400">provider: {used}</span>}</div></Card>
    </div>
  );
}
