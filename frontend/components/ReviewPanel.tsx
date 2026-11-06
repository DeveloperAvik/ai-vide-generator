"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useApi } from "@/hooks/useApi";
import { Badge, Btn, Card, EmptyState, ErrorNote, label, useAsyncAction } from "./ui";

type Tone = "neutral" | "info" | "warn" | "good" | "bad";
const SEV_TONE: Record<string, Tone> = { critical: "bad", high: "bad", medium: "warn", low: "info", info: "neutral" };
const CLAIM_TONE: Record<string, Tone> = { supported: "good", partially_supported: "warn", unsupported: "bad", contradicted: "bad", needs_human_review: "warn" };
const STATE: Record<string, { tone: Tone; text: string }> = {
  pending: { tone: "neutral", text: "Review pending" }, running: { tone: "info", text: "Review running" }, failed: { tone: "bad", text: "Review failed" },
  human_review_required: { tone: "warn", text: "Human review required" }, passed: { tone: "good", text: "Review passed - awaiting approval" },
  approved_for_rendering: { tone: "good", text: "Approved for rendering" },
};
const SEVERITIES = ["all", "critical", "high", "medium", "low", "info"];
const safeHref = (u: string) => (u.startsWith("https://") ? u : undefined);
const TABS = ["Findings", "Claims", "Sources", "Quality gate", "Revisions"] as const;

export function ReviewState({ state }: { state?: { state: string; blocked: boolean } }) {
  if (!state) return null;
  const s = STATE[state.state] ?? { tone: "neutral" as Tone, text: label(state.state) };
  return (<span className="inline-flex flex-wrap items-center gap-2"><Badge s={s.text} tone={s.tone} />{state.blocked && <Badge s="Blocked from rendering" tone="bad" />}</span>);
}

export function ReviewPanel({ id, sources, canDecide = true, onChange }: { id: string; sources: any[]; canDecide?: boolean; onChange: () => void }) {
  const [tab, setTab] = useState<(typeof TABS)[number]>("Findings");
  const review = useApi<any>(`/lessons/${id}/review`, 4000);
  const claims = useApi<any[]>(tab === "Claims" ? `/lessons/${id}/claims` : null, 6000);
  const gate = useApi<any>(tab === "Quality gate" ? `/lessons/${id}/gate` : null);
  const revs = useApi<any[]>(tab === "Revisions" ? `/lessons/${id}/revisions` : null);
  const { busy, err, run } = useAsyncAction();
  const st = review.data?.state;
  const refresh = () => { review.reload(); claims.reload(); gate.reload(); revs.reload(); onChange(); };
  const openBlocking = (review.data?.findings ?? []).filter((f: any) => f.status === "open" && f.blocks_approval).length;
  return (
    <Card title="Technical review & fact-checking" action={<ReviewState state={st} />}>
      <ErrorNote msg={review.error ?? err} />
      {st?.reasons?.length > 0 && st.state !== "running" && (
        <details className="mb-4 rounded-lg border border-amber-500/25 bg-amber-500/5 p-3 text-sm text-amber-200" open={st.blocked && st.state !== "passed"}>
          <summary className="cursor-pointer font-medium">{st.reasons.length} reason{st.reasons.length > 1 ? "s" : ""} the lesson cannot proceed{openBlocking ? ` · ${openBlocking} blocking finding${openBlocking > 1 ? "s" : ""} open` : ""}</summary>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-xs">{st.reasons.map((r: string, i: number) => <li key={i} className="break-words">{r}</li>)}</ul>
        </details>
      )}
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <Btn size="sm" kind="ghost" disabled={busy || st?.state === "running"} loading={st?.state === "running"} onClick={() => run(async () => { await api(`/lessons/${id}/review/run`, { method: "POST" }); refresh(); }, "Review started (uses the current script version)")}>
          {review.data?.runs?.length ? "Rerun review" : "Start review"}
        </Btn>
        <Btn size="sm" kind="ghost" disabled={busy} onClick={() => run(async () => { await api(`/lessons/${id}/research/verify`, { method: "POST" }); refresh(); }, "Re-fetching cited sources")}>Verify sources</Btn>
        {review.data?.runs?.[0] && <span className="text-xs text-slate-500">v{review.data.runs[0].script_version} · {review.data.runs[0].reviewer_model}{review.data.runs[0].simulated ? " · SIMULATED (mock LLM)" : ""} · {review.data.runs[0].status}</span>}
      </div>
      <div role="tablist" className="mb-4 flex gap-1 overflow-x-auto border-b border-line">
        {TABS.map((t) => (<button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)} className={`whitespace-nowrap px-3 py-2 text-sm transition ${tab === t ? "border-b-2 border-brand-400 text-slate-50" : "text-slate-400 hover:text-slate-200"}`}>{t}</button>))}
      </div>
      {tab === "Findings" && <Findings id={id} data={review.data} canDecide={canDecide} run={run} busy={busy} refresh={refresh} />}
      {tab === "Claims" && <Claims data={claims.data} canDecide={canDecide} run={run} busy={busy} refresh={refresh} />}
      {tab === "Sources" && <Sources items={sources} id={id} />}
      {tab === "Quality gate" && <Gate id={id} data={gate.data} run={run} busy={busy} refresh={refresh} />}
      {tab === "Revisions" && <Revisions id={id} data={revs.data} />}
    </Card>
  );
}

function Findings({ id, data, canDecide, run, busy, refresh }: any) {
  const [sev, setSev] = useState("all");
  const list = (data?.findings ?? []).filter((f: any) => sev === "all" || f.severity === sev);
  const counts = (s: string) => (data?.findings ?? []).filter((f: any) => s === "all" || f.severity === s).length;
  return (
    <div>
      <div className="mb-3 flex flex-wrap gap-1.5" role="group" aria-label="Severity filter">
        {SEVERITIES.map((s) => (<button key={s} onClick={() => setSev(s)} aria-pressed={sev === s} className={`rounded-full px-2.5 py-1 text-xs ring-1 ring-inset transition ${sev === s ? "bg-brand-500/15 text-brand-300 ring-brand-500/40" : "text-slate-400 ring-line hover:text-slate-200"}`}>{label(s)} · {counts(s)}</button>))}
      </div>
      {!data ? null : list.length === 0 ? <EmptyState icon="shield" title={data.runs.length ? "No findings" : "Review not run yet"} hint={data.runs.length ? "The reviewer reported nothing for this filter and script version." : "Start the review to get an independent technical check."} /> : (
        <ul className="space-y-3">{list.map((f: any) => <Finding key={f.id} f={f} canDecide={canDecide} run={run} busy={busy} refresh={refresh} />)}</ul>)}
    </div>
  );
}

function Finding({ f, canDecide, run, busy, refresh }: any) {
  const [fix, setFix] = useState(f.recommended_correction ?? "");
  const [note, setNote] = useState("");
  const open = f.status === "open";
  const decide = (decision: string) => run(async () => { await api(`/review/findings/${f.id}/decision`, { method: "POST", json: { decision, note, correction: decision === "accept" ? fix : undefined } }); refresh(); },
    decision === "accept" ? "Correction applied as a new script revision - rerun the review" : "Decision recorded");
  return (
    <li className={`rounded-lg border p-3 ${open && f.blocks_approval ? "border-rose-500/40 bg-rose-500/5" : "border-line bg-raised/40"}`}>
      <div className="flex flex-wrap items-center gap-2"><Badge s={f.severity} tone={SEV_TONE[f.severity]} /><span className="text-xs text-slate-400">{label(f.category)} · {f.section || "unknown section"}</span>
        {f.blocks_approval && open && <Badge s="Blocks approval" tone="bad" />}{!f.blocks_approval && open && <Badge s="Advisory" tone="neutral" />}{!open && <Badge s={f.status} tone={f.status === "accepted" ? "good" : "neutral"} />}</div>
      <blockquote className="mt-2 break-words border-l-2 border-slate-500 pl-3 text-sm text-slate-300">{f.problem_text}</blockquote>
      <p className="mt-2 break-words text-sm text-slate-200">{f.explanation}</p>
      {f.evidence && <p className="mt-1 break-words text-xs text-slate-400"><span className="font-medium">Evidence:</span> {f.evidence}</p>}
      {f.objective && <p className="mt-1 break-words text-xs text-slate-400"><span className="font-medium">Objective:</span> {f.objective}</p>}
      {f.policy_note && <p className="mt-1 break-words text-xs text-slate-500">Gate policy: {f.policy_note}</p>}
      {f.recommended_correction && (
        <div className="mt-3 grid gap-2 sm:grid-cols-2">
          <div className="rounded-md bg-rose-500/10 p-2 text-xs text-rose-200"><div className="mb-1 font-semibold uppercase tracking-wide opacity-70">Current</div><span className="break-words">{f.problem_text}</span></div>
          <div className="rounded-md bg-emerald-500/10 p-2 text-xs text-emerald-200"><div className="mb-1 font-semibold uppercase tracking-wide opacity-70">Suggested</div>
            {open && canDecide ? <textarea aria-label="Correction text" className="h-20 w-full text-xs" value={fix} onChange={(e) => setFix(e.target.value)} /> : <span className="break-words">{f.recommended_correction}</span>}</div>
        </div>)}
      {f.decision_note && <p className="mt-2 text-xs text-slate-400">Decision note: {f.decision_note}</p>}
      {open && canDecide && (
        <div className="mt-3 space-y-2">
          <input aria-label="Decision note" className="w-full text-sm" placeholder="Note (min 10 characters; required to reject or waive)" value={note} onChange={(e) => setNote(e.target.value)} />
          <div className="flex flex-wrap gap-2">
            <Btn size="sm" disabled={busy || !f.recommended_correction} onClick={() => decide("accept")}>Accept &amp; apply</Btn>
            <Btn size="sm" kind="ghost" disabled={busy || note.trim().length < 10} onClick={() => decide("reject")}>Reject finding</Btn>
            {f.blocks_approval && <Btn size="sm" kind="danger" disabled={busy || note.trim().length < 10} onClick={() => decide("waive")}>Waive{f.severity === "critical" || f.severity === "high" ? " (admin)" : ""}</Btn>}
          </div>
        </div>)}
    </li>
  );
}

function Claims({ data, canDecide, run, busy, refresh }: any) {
  if (!data) return null;
  if (!data.length) return <EmptyState icon="book" title="No claims extracted" hint="Claims are extracted when the technical review runs." />;
  return (
    <ul className="space-y-3">{data.map((c: any) => (
      <li key={c.id} className={`rounded-lg border p-3 ${c.blocks ? "border-rose-500/40 bg-rose-500/5" : "border-line bg-raised/40"}`}>
        <div className="flex flex-wrap items-center gap-2"><Badge s={label(c.status)} tone={CLAIM_TONE[c.status]} />{c.critical && <Badge s="Critical claim" tone="warn" />}
          <span className="text-xs text-slate-400">{label(c.category)} · {c.section}{c.confidence != null ? ` · confidence ${(c.confidence * 100).toFixed(0)}%` : ""}</span>
          {c.needs_human && !c.human_decision && <Badge s="Human review required" tone="warn" />}{c.human_decision && <Badge s={`Human: ${c.human_decision}`} tone="info" />}</div>
        <p className="mt-2 break-words text-sm text-slate-200">{c.text}</p>
        {c.evidence_excerpt ? (<blockquote className="mt-2 break-words border-l-2 border-emerald-500/50 pl-3 text-xs text-slate-300">“{c.evidence_excerpt}”
          {c.evidence_section && <div className="mt-1 text-slate-500">Section: {c.evidence_section}</div>}
          {c.sources.map((s: any) => <div key={s.id} className="text-slate-500">Source: <a className="text-sky-300 underline" href={safeHref(s.url)} target="_blank" rel="noreferrer noopener">{s.title || s.url}</a> ({s.publisher})</div>)}</blockquote>)
          : <p className="mt-2 text-xs text-slate-500">No supporting evidence was found in the retrieved sources.</p>}
        {c.reviewer_notes && <p className="mt-1 break-words text-xs text-slate-400">Reviewer: {c.reviewer_notes}</p>}
        {canDecide && c.status !== "supported" && !c.human_decision && (
          <div className="mt-2 flex flex-wrap gap-2">
            <ClaimDecision id={c.id} busy={busy} run={run} refresh={refresh} />
          </div>)}
      </li>))}
    </ul>
  );
}

function ClaimDecision({ id, busy, run, refresh }: any) {
  const [note, setNote] = useState("");
  const go = (decision: string) => run(async () => { await api(`/review/claims/${id}/decision`, { method: "POST", json: { decision, note } }); refresh(); }, "Decision recorded");
  return (<div className="flex w-full flex-wrap gap-2"><input aria-label="Claim decision note" className="min-w-0 flex-1 text-sm" placeholder="How did you verify this? (min 10 characters)" value={note} onChange={(e) => setNote(e.target.value)} />
    <Btn size="sm" kind="ghost" disabled={busy || note.trim().length < 10} onClick={() => go("accepted")}>Accept claim</Btn>
    <Btn size="sm" kind="ghost" disabled={busy || note.trim().length < 10} onClick={() => go("rejected")}>Reject claim</Btn></div>);
}

function Sources({ items, id }: { items: any[]; id: string }) {
  const [open, setOpen] = useState<number | null>(null);
  const text = useApi<any>(open ? `/lessons/${id}/sources/${open}/text` : null);
  if (!items?.length) return <EmptyState icon="book" title="No sources yet" hint="Sources are fetched during research and technical review." />;
  return (
    <ul className="space-y-2">{items.map((s) => (
      <li key={s.id ?? s.url} className="rounded-lg border border-line bg-raised/40 p-3 text-sm">
        <div className="flex flex-wrap items-center gap-2"><Badge s={s.status === "ok" ? "Retrieved" : label(s.status || "unverified")} tone={s.verified ? "good" : "bad"} />
          <span className="text-xs text-slate-400">{s.publisher || "unknown publisher"}{s.category ? ` · ${label(s.category)}` : ""}</span></div>
        <a className="mt-1 block break-all text-sky-300 underline" href={safeHref(s.url)} target="_blank" rel="noreferrer noopener">{s.title || s.url}</a>
        <dl className="mt-1 grid gap-x-4 text-xs text-slate-500 sm:grid-cols-2">
          <div>Retrieved: {s.retrieved_at ? new Date(s.retrieved_at).toLocaleString() : "-"}</div><div>Published/updated: {s.published_at || "not stated"}</div>
          <div className="break-words">Section: {s.section || "-"}</div><div>Hash: {s.content_hash ? s.content_hash.slice(0, 12) : "-"}</div></dl>
        {s.excerpt && <p className="mt-2 line-clamp-3 break-words text-xs text-slate-400">{s.excerpt}</p>}
        {s.verified && s.id && <button className="mt-2 text-xs text-brand-300 underline" onClick={() => setOpen(open === s.id ? null : s.id)}>{open === s.id ? "Hide" : "Read"} stored text</button>}
        {open === s.id && text.data && (<div className="mt-2 max-h-72 overflow-auto rounded-md bg-surface p-2 text-xs text-slate-300">{text.data.sections.map(([h, t]: [string, string], i: number) => <div key={i} className="mb-2"><div className="font-semibold text-slate-200">{h || "(intro)"}</div><div className="break-words">{t}</div></div>)}</div>)}
      </li>))}
    </ul>
  );
}

function Gate({ id, data, run, busy, refresh }: any) {
  if (!data) return null;
  const g = data.pre_tts ?? data.script;
  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        {g ? <Badge s={g.passed ? "Gate passed" : "Blocked from rendering"} tone={g.passed ? "good" : "bad"} /> : <Badge s="Not evaluated" tone="neutral" />}
        {g && <span className="text-xs text-slate-500">{data.pre_tts ? "pre-TTS gate" : "script gate"} · script v{g.script_version}{g.storyboard_version ? ` · storyboard v${g.storyboard_version}` : ""}</span>}
        <Btn size="sm" kind="ghost" disabled={busy} onClick={() => run(async () => { await api(`/lessons/${id}/gate/evaluate?stage=pre_tts`, { method: "POST" }); refresh(); })}>Evaluate now</Btn>
      </div>
      {!g ? <EmptyState icon="shield" title="No gate result yet" hint="The gate is evaluated before TTS and rendering; you can also evaluate it now." /> : (
        <ul className="space-y-1.5">{g.checks.map((c: any) => (
          <li key={c.check} className="flex items-start gap-2 text-sm"><span aria-hidden className={`mt-0.5 ${c.passed ? "text-emerald-400" : c.blocking ? "text-rose-400" : "text-amber-400"}`}>{c.passed ? "✓" : c.blocking ? "✕" : "!"}</span>
            <span className="sr-only">{c.passed ? "passed" : "failed"}</span><div className="min-w-0"><div className="text-slate-200">{label(c.check)}{!c.blocking && <span className="ml-2 text-xs text-slate-500">(advisory)</span>}</div><div className="break-words text-xs text-slate-500">{c.detail}</div></div></li>))}
        </ul>)}
    </div>
  );
}

function Revisions({ id, data }: { id: string; data?: any[] | null }) {
  const [sel, setSel] = useState<number | null>(null);
  const [diff, setDiff] = useState<{ field: string; a: string; b: string }[] | null>(null);
  useEffect(() => {
    if (!sel || sel < 2) { setDiff(null); return; }
    (async () => {
      const [a, b] = await Promise.all([api(`/lessons/${id}/revisions/${sel - 1}`), api(`/lessons/${id}/revisions/${sel}`)]);
      const out: any[] = [];
      for (const k of Object.keys(b.content)) { const x = JSON.stringify(a.content[k]), y = JSON.stringify(b.content[k]); if (x !== y) out.push({ field: k, a: typeof a.content[k] === "string" ? a.content[k] : x, b: typeof b.content[k] === "string" ? b.content[k] : y }); }
      setDiff(out);
    })().catch(() => setDiff([]));
  }, [sel, id]);
  if (!data) return null;
  return (
    <div>
      <ul className="space-y-1.5">{data.map((r) => (
        <li key={r.version}><button onClick={() => setSel(sel === r.version ? null : r.version)} className="flex w-full flex-wrap items-center gap-2 rounded-lg border border-line bg-raised/40 px-3 py-2 text-left text-sm hover:bg-raised">
          <Badge s={`v${r.version}`} tone="info" /><span className="text-slate-300">{r.generated_by}</span><span className="text-xs text-slate-500">{r.change_note || "generated"}</span><span className="ml-auto text-xs text-slate-500">{new Date(r.created_at).toLocaleString()}</span></button></li>))}
      </ul>
      {sel && sel >= 2 && diff && (diff.length === 0 ? <p className="mt-3 text-xs text-slate-500">No field differs from the previous version.</p> :
        <div className="mt-3 space-y-3">{diff.map((d) => (<div key={d.field}><div className="mb-1 text-xs font-semibold text-slate-300">{label(d.field)}</div>
          <div className="grid gap-2 sm:grid-cols-2"><div className="break-words rounded-md bg-rose-500/10 p-2 text-xs text-rose-200">{d.a}</div><div className="break-words rounded-md bg-emerald-500/10 p-2 text-xs text-emerald-200">{d.b}</div></div></div>))}</div>)}
    </div>
  );
}
