"use client";
import { useApi } from "@/hooks/useApi";
import { Badge, Card, ErrorNote, PageHeader } from "@/components/ui";

export default function Health() {
  const { data, error } = useApi<any>("/health", 5000);
  const { data: logs } = useApi<any[]>("/logs", 5000);
  return (<div className="space-y-5"><PageHeader title="System Health" desc="Service status and the execution / audit log." /><ErrorNote msg={error} />
    {data && <Card title="Services"><ul className="space-y-1 text-sm">{["database", "ffmpeg", "ffprobe"].map((k) => <li key={k}>{k}: <Badge s={data[k] ? "done" : "failed"} /></li>)}<li>LLM provider: {data.llm_provider}</li></ul></Card>}
    <Card title="Recent execution & audit log"><div className="max-h-96 overflow-auto text-xs">{logs?.map((l) => (<div key={l.id} className={`border-t border-line py-1 ${l.level === "error" ? "text-rose-300" : ""}`}>{l.at} · {l.stage} · {l.actor} · {l.message.slice(0, 200)}</div>))}</div></Card></div>);
}
