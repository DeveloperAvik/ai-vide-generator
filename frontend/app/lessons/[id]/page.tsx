"use client";
import Link from "next/link";
import { use, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useApi } from "@/hooks/useApi";
import { Badge, Btn, Card, EmptyState, ErrorNote, useAsyncAction } from "@/components/ui";
import { PipelineStepper } from "@/components/PipelineStepper";
import { Icon } from "@/components/Icon";
import { ReviewPanel, ReviewState } from "@/components/ReviewPanel";
import { Thumb, Video } from "@/components/MediaPreview";

const GATED = ["TECHNICAL_REVIEW", "APPROVAL_PENDING", "APPROVED", "SCHEDULED", "PUBLISHED"];
const WAITING = ["RESEARCHING", "ASSETS_GENERATING", "RENDERING", "QUALITY_CHECK"];
/** Plain-language "what do I do now?" for each stage. */
function nextHint(status: string): string {
  if (status === "FAILED") return "Something went wrong. Check the error above, then retry.";
  if (status === "TECHNICAL_REVIEW") return "Review the validation report below, then approve or reject the script.";
  if (status === "APPROVAL_PENDING") return "The video is ready. Watch it and approve or reject it in the Approval Queue.";
  if (["APPROVED", "SCHEDULED", "PUBLISHED"].includes(status)) return "Approved. Publish it from the YouTube page.";
  if (WAITING.includes(status)) return "Working on it. This page updates by itself.";
  return "Ready for the next step in the pipeline.";
}

export default function LessonPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { data, error, reload } = useApi<any>(`/lessons/${id}`, 5000);
  const [text, setText] = useState("");
  const [dirty, setDirty] = useState(false);
  const { busy, err, run } = useAsyncAction();
  const [thumbV, setThumbV] = useState(0);
  const [headline, setHeadline] = useState("");
  useEffect(() => { if (data?.script && !dirty) setText(JSON.stringify(data.script, null, 2)); }, [data, dirty]);
  const tech = data?.quality?.find((q: any) => q.report.stage === "technical");
  return (
    <div className="space-y-5">
      <div>
        <Link href="/lessons" className="mb-2 inline-flex items-center gap-1 text-xs text-slate-500 hover:text-slate-300"><Icon name="chevron" className="h-3 w-3 rotate-180" />All lessons</Link>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-3"><h1 className="text-[22px] font-semibold tracking-tight text-slate-50">{data?.lesson.title ?? "Lesson"}</h1>{data && <Badge s={data.lesson.status} />}</div>
          <Link className="inline-flex items-center gap-1.5 rounded-lg border border-line px-3 py-1.5 text-sm text-slate-200 transition hover:bg-raised" href={`/lessons/${id}/storyboard`}>Storyboard editor<Icon name="chevron" className="h-3.5 w-3.5" /></Link>
        </div>
        {data && <div className="mt-4 rounded-xl border border-line bg-surface p-3"><PipelineStepper status={data.lesson.status} lastGood={data.lesson.last_good_status} /></div>}
        {data && (() => {
          const st: string = data.lesson.status;
          const action = st === "FAILED" ? <Btn kind="danger" icon="refresh" loading={busy} onClick={() => run(async () => { await api(`/lessons/${id}/retry`, { method: "POST" }); reload(); }, "Retry started")}>Retry</Btn>
            : st === "APPROVAL_PENDING" || st === "TECHNICAL_REVIEW" ? <Link href="/approvals" className="inline-flex items-center gap-1.5 rounded-lg bg-brand-500 px-3.5 py-2 text-sm font-medium text-on-brand hover:bg-brand-400">Open approval queue</Link>
            : !GATED.includes(st) && !WAITING.includes(st) ? <Btn icon="play" loading={busy} onClick={() => run(async () => { await api(`/lessons/${id}/run`, { method: "POST" }); reload(); }, "Pipeline started")}>Run next step</Btn> : null;
          return (<div className="mt-3 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-brand-500/20 bg-brand-500/5 px-4 py-3">
            <div><div className="text-[11px] font-semibold uppercase tracking-wider text-brand-400">What&apos;s next</div><p className="text-sm text-slate-200">{nextHint(st)}</p></div>{action}</div>);
        })()}
        {data?.lesson.last_error && <div className="mt-3"><ErrorNote msg={data.lesson.last_error} /></div>}
      </div>
      <ErrorNote msg={error ?? err} />
      {data?.render?.status === "done" && (
        <Card title="Video & thumbnail">
          <div className="grid gap-5 lg:grid-cols-5">
            <div className="lg:col-span-3"><Video renderId={data.render.id} /></div>
            <div className="space-y-3 lg:col-span-2">
              <Thumb lessonId={Number(id)} version={thumbV} />
              <label className="block text-xs text-slate-400">Thumbnail headline <span className="text-slate-500">(short is better, 3-6 words)</span>
                <input className="mt-1" maxLength={80} value={headline} placeholder={data.lesson.title} onChange={(e) => setHeadline(e.target.value)} /></label>
              <Btn kind="ghost" icon="refresh" loading={busy} onClick={() => run(async () => { await api(`/lessons/${id}/thumbnail/regenerate`, { method: "POST", json: { text: headline.trim() || null } }); setThumbV((v) => v + 1); }, "Thumbnail updated")}>Regenerate thumbnail</Btn>
            </div>
          </div>
        </Card>)}
      <div className="grid gap-5 lg:grid-cols-2">
        <Card title={`AI Script Editor (version ${data?.script_version ?? "-"})`}>
          <p className="mb-2 text-xs text-slate-400">Mode A: generate JSON with ai/prompts/lesson.md in Claude, paste here and save. Same strict validation as API output.</p>
          <textarea className="h-96 font-mono text-xs leading-relaxed" value={text} onChange={(e) => { setText(e.target.value); setDirty(true); }} spellCheck={false} />
          <div className="mt-3 flex gap-2"><Btn disabled={busy || !dirty} onClick={() => run(async () => { await api(`/lessons/${id}/script/import`, { method: "POST", json: JSON.parse(text) }); setDirty(false); reload(); })}>Save as new version</Btn>
            <Btn kind="ghost" onClick={() => { setDirty(false); reload(); }}>Discard edits</Btn></div>
        </Card>
        <div className="space-y-5">
          <Card title="Technical validation">
            {!tech ? <EmptyState icon="shield" title="Not run yet" hint="Technical validation runs after the script is generated." /> : (<>
              <div className="mb-2">{tech.passed ? <Badge s="done" /> : <Badge s="failed" />} <ReviewState state={data.review} /></div>
              <ul className="space-y-1 text-sm">{tech.report.issues.map((i: any, k: number) => <li key={k} className={i.severity === "error" ? "text-rose-300" : "text-amber-300"}>{i.severity}: {i.msg}</li>)}</ul>
              {data.lesson.status === "TECHNICAL_REVIEW" && (<div className="mt-3 flex gap-2">
                <Btn disabled={!tech.passed || (data.review && data.review.state !== "passed")} onClick={() => run(async () => { await api(`/lessons/${id}/script/decision`, { method: "POST", json: { decision: "APPROVED", stage: "script" } }); reload(); })}>Approve script</Btn>
                <Btn kind="danger" onClick={() => run(async () => { await api(`/lessons/${id}/script/decision`, { method: "POST", json: { decision: "REJECTED", stage: "script" } }); reload(); })}>Reject</Btn></div>)}
            </>)}
          </Card>
          <Card title="Research sources">
            <ul className="space-y-2 text-sm">{data?.sources.map((s: any) => (<li key={s.url}><a className="text-sky-300 break-all" href={s.url.startsWith("https://") ? s.url : undefined} target="_blank" rel="noreferrer noopener">{s.url}</a> {s.verified ? <Badge s="done" /> : <Badge s="unverified" />}<div className="text-xs text-slate-500">retrieved {s.retrieved_at}</div></li>))}</ul>
            {data?.sources.length === 0 && <EmptyState icon="book" title="No sources yet" hint="Sources are fetched during research." />}
          </Card>
        </div>
      </div>
      <ReviewPanel id={id} sources={data?.sources ?? []} onChange={reload} />
    </div>
  );
}
