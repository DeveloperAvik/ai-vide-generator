"use client";
import { useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { useApi } from "@/hooks/useApi";
import { Badge, Btn, Card, EmptyState, ErrorNote, useAsyncAction, PageHeader } from "@/components/ui";
import { Thumb, Video } from "@/components/MediaPreview";
import type { Lesson } from "@/types";

function Item({ l, reload }: { l: Lesson; reload: () => void }) {
  const { data } = useApi<any>(`/lessons/${l.id}`);
  const [notes, setNotes] = useState("");
  const { err, run } = useAsyncAction();
  const final = data?.quality?.find((q: any) => q.report.stage === "final");
  const decide = (decision: string) => run(async () => { await api(`/lessons/${l.id}/${l.status === "TECHNICAL_REVIEW" ? "script" : "video"}/decision`, { method: "POST", json: { decision, notes } }); reload(); });
  const scriptBlocked = l.status === "TECHNICAL_REVIEW" && !!data?.review && data.review.state !== "passed";
  return (
    <Card title={l.title}>
      <ErrorNote msg={err} /><div className="mb-3"><Badge s={l.status} /></div>
      {l.status === "APPROVAL_PENDING" && data?.render && (<div className="grid gap-4 md:grid-cols-3"><div className="md:col-span-2"><Video renderId={data.render.id} /></div><Thumb lessonId={l.id} /></div>)}
      {l.status === "TECHNICAL_REVIEW" && <p className="text-sm text-slate-400">Review the script and validation report on the lesson page, or approve here.</p>}
      {final && <ul className="mt-3 grid gap-1 text-sm md:grid-cols-2">{final.report.checks.map((c: any) => <li key={c.check} className={c.passed ? "text-emerald-300" : "text-rose-300"}>{c.passed ? "✓" : "✗"} {c.check} <span className="text-slate-500">{c.detail}</span></li>)}</ul>}
      <input className="mt-3" placeholder="Notes (optional)" value={notes} onChange={(e) => setNotes(e.target.value)} />
      <div className="mt-3 flex gap-2"><Btn disabled={scriptBlocked} onClick={() => decide("APPROVED")}>Approve</Btn><Btn kind="danger" onClick={() => decide("REJECTED")}>Reject</Btn>
        {scriptBlocked && <Link href={`/lessons/${l.id}`} className="self-center text-xs text-amber-300 underline">Blocked by the quality gate: resolve the findings on the lesson page first</Link>}</div>
    </Card>);
}

export default function Approvals() {
  const { data, error, reload } = useApi<Lesson[]>("/approvals/queue", 5000);
  return (<div className="space-y-5"><PageHeader title="Approval Queue" desc="Scripts and finished videos wait here. Nothing is uploaded until a person approves it." /><ErrorNote msg={error} />
    {data?.length === 0 && <Card><EmptyState icon="check" title="Nothing awaiting review" hint="Lessons appear here after technical validation and after the final render passes quality checks." /></Card>}{data?.map((l) => <Item key={l.id} l={l} reload={reload} />)}</div>);
}
