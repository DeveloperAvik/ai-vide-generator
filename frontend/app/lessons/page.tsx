"use client";
import Link from "next/link";
import { useState } from "react";
import { api, confirmDelete } from "@/lib/api";
import { useApi } from "@/hooks/useApi";
import { Badge, Btn, Card, EmptyState, ErrorNote, PageHeader, Skeleton, Td, Th, timeAgo, useAsyncAction } from "@/components/ui";
import type { Lesson } from "@/types";

const GATED = ["TECHNICAL_REVIEW", "APPROVAL_PENDING", "APPROVED", "SCHEDULED", "PUBLISHED"];
const FILTERS: [string, string[] | null][] = [["All", null], ["In progress", ["RESEARCHING", "SCRIPT_GENERATED", "SCRIPT_APPROVED", "ASSETS_GENERATING", "ASSETS_READY", "RENDERING", "QUALITY_CHECK", "TOPIC_PENDING"]], ["Needs review", ["TECHNICAL_REVIEW", "APPROVAL_PENDING"]], ["Failed", ["FAILED"]], ["Done", ["APPROVED", "SCHEDULED", "PUBLISHED"]]];

export default function Lessons() {
  const { data, error, reload } = useApi<Lesson[]>("/lessons", 5000);
  const { err, run } = useAsyncAction();
  const [f, setF] = useState(0);
  const rows = data?.filter((l) => !FILTERS[f][1] || FILTERS[f][1]!.includes(l.status));
  return (
    <div>
      <PageHeader title="Lessons" desc="Run the pipeline stage by stage. Lessons stop at human approval gates." />
      <ErrorNote msg={error ?? err} />
      <div role="tablist" className="mb-4 flex flex-wrap gap-1.5">
        {FILTERS.map(([name, sts], i) => {
          const n = data ? (sts ? data.filter((l) => sts.includes(l.status)).length : data.length) : 0;
          return (<button key={name} role="tab" aria-selected={f === i} onClick={() => setF(i)}
            className={`rounded-full px-3 py-1 text-xs font-medium ring-1 ring-inset transition ${f === i ? "bg-brand-500/15 text-brand-400 ring-brand-500/40" : "text-slate-400 ring-line hover:text-slate-200"}`}>{name} <span className="tnum ml-1 opacity-70">{n}</span></button>);
        })}
      </div>
      <Card className="!p-0 overflow-hidden">
        {!data ? <div className="space-y-3 p-5">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-8" />)}</div> : rows!.length === 0 ? <EmptyState title="No lessons match this filter" hint="Try another filter, or generate a course from the Courses page." /> : (
          <div className="overflow-x-auto"><table className="w-full">
            <thead className="border-b border-line bg-raised/40"><tr><Th>Lesson</Th><Th>Status</Th><Th className="text-right">Retries</Th><Th>Updated</Th><Th /></tr></thead>
            <tbody className="divide-y divide-line/60">{rows!.map((l) => (
              <tr key={l.id} className="transition hover:bg-raised/40">
                <Td className="max-w-md"><Link className="font-medium text-slate-100 hover:text-brand-400" href={`/lessons/${l.id}`}>{l.title}</Link>{l.draft && <span className="ml-2 rounded bg-rose-600/80 px-1.5 py-0.5 align-middle text-[10px] font-bold uppercase tracking-wide text-slate-50">Draft · unreviewed</span>}
                  {l.last_error && <div className="mt-0.5 truncate text-xs text-rose-300/80" title={l.last_error}>{l.last_error}</div>}</Td>
                <Td><Badge s={l.status} /></Td>
                <Td className="tnum text-right text-slate-400">{l.retry_count}</Td>
                <Td className="whitespace-nowrap text-xs text-slate-500">{timeAgo(l.updated_at)}</Td>
                <Td className="space-x-1.5 whitespace-nowrap text-right">
                  {l.status === "FAILED" ? <Btn size="sm" kind="danger" icon="refresh" onClick={() => run(async () => { await api(`/lessons/${l.id}/retry`, { method: "POST" }); reload(); }, "Retry started")}>Retry</Btn>
                    : !GATED.includes(l.status) && <Btn size="sm" kind="ghost" icon="play" onClick={() => run(async () => { await api(`/lessons/${l.id}/run`, { method: "POST" }); reload(); }, "Pipeline started")}>Run next</Btn>}
                  {!l.draft && l.status === "TOPIC_PENDING" && <Btn size="sm" kind="ghost" icon="film" onClick={() => run(async () => { await api(`/lessons/${l.id}/draft`, { method: "POST" }); reload(); }, "Quick draft started")}>Quick draft</Btn>}
                  {l.draft && <Btn size="sm" kind="ghost" icon="check" onClick={() => { if (window.confirm("Make this lesson official? It goes back to the start: source research, fact-check review and your approval. The draft video is kept as history.")) run(async () => { await api(`/lessons/${l.id}/draft/promote`, { method: "POST" }); reload(); }, "Back in the full pipeline"); }}>Make official</Btn>}
                  <Btn size="sm" kind="ghost" icon="trash" onClick={() => run(async () => { if (await confirmDelete(`/lessons/${l.id}`, `lesson "${l.title}"`)) reload(); }, "Lesson deleted")}>Delete</Btn>
                </Td></tr>))}</tbody></table></div>)}
      </Card>
    </div>
  );
}
