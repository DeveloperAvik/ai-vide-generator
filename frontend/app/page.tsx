"use client";
import Link from "next/link";
import { useApi } from "@/hooks/useApi";
import { Badge, Card, EmptyState, ErrorNote, PageHeader, Progress, Skeleton, Stat, timeAgo } from "@/components/ui";
import { Icon } from "@/components/Icon";
import type { Lesson } from "@/types";

const GROUPS: { name: string; statuses: string[]; color: string }[] = [
  { name: "Script", statuses: ["TOPIC_PENDING", "RESEARCHING", "SCRIPT_GENERATED", "TECHNICAL_REVIEW"], color: "bg-slate-500" },
  { name: "Assets", statuses: ["SCRIPT_APPROVED", "ASSETS_GENERATING", "ASSETS_READY"], color: "bg-sky-500" },
  { name: "Render & QC", statuses: ["RENDERING", "QUALITY_CHECK"], color: "bg-indigo-500" },
  { name: "Awaiting approval", statuses: ["APPROVAL_PENDING"], color: "bg-amber-400" },
  { name: "Ready / published", statuses: ["APPROVED", "SCHEDULED", "PUBLISHED"], color: "bg-emerald-500" },
  { name: "Failed", statuses: ["FAILED"], color: "bg-rose-500" },
];

export default function Overview() {
  const { data: d, error } = useApi<any>("/dashboard", 10000);
  const { data: lessons } = useApi<Lesson[]>("/lessons", 10000);
  const { data: logs } = useApi<any[]>("/logs", 10000);
  const counts = GROUPS.map((g) => ({ ...g, n: lessons?.filter((l) => g.statuses.includes(l.status)).length ?? 0 }));
  const total = lessons?.length ?? 0;
  const attention = lessons?.filter((l) => ["FAILED", "APPROVAL_PENDING", "TECHNICAL_REVIEW"].includes(l.status)) ?? [];
  const activity = (logs ?? []).filter((l) => l.stage !== "audit").slice(0, 8);
  return (
    <div>
      <PageHeader title="Overview" desc="Production status across all courses." />
      <ErrorNote msg={error} />
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {!d ? Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-[104px]" />) : (<>
          <Stat label="Courses" value={d.courses} icon="book" hint={`${d.lessons} lessons`} />
          <Stat label="Videos rendered" value={d.videos_generated} icon="film" tone="info" hint={`${d.weekly_done} this week`} />
          <Stat label="Awaiting approval" value={d.pending_approval} icon="clock" tone={d.pending_approval ? "warn" : "neutral"} hint={d.pending_approval ? "Needs your review" : "Queue is clear"} />
          <Stat label="Failures" value={d.failed + d.failed_renders} icon="alert" tone={d.failed + d.failed_renders ? "bad" : "good"} hint={`${d.failed} lessons · ${d.failed_renders} renders`} />
        </>)}
      </div>

      <div className="mt-5 grid gap-5 lg:grid-cols-3">
        <Card title="Pipeline" className="lg:col-span-2">
          {!lessons ? <Skeleton className="h-16" /> : total === 0 ? <EmptyState icon="layers" title="No lessons yet" hint="Generate a course to create lessons." action={<Link className="text-sm text-brand-400" href="/courses">Go to Courses →</Link>} /> : (<>
            <div className="flex h-3 overflow-hidden rounded-full bg-raised" role="img" aria-label="Lessons by pipeline stage">
              {counts.filter((c) => c.n).map((c) => <div key={c.name} className={c.color} style={{ width: `${(c.n / total) * 100}%` }} title={`${c.name}: ${c.n}`} />)}
            </div>
            <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-3">
              {counts.map((c) => (<div key={c.name} className="flex items-center gap-2.5"><span className={`h-2.5 w-2.5 rounded-sm ${c.color}`} /><div><dt className="text-xs text-slate-400">{c.name}</dt><dd className="tnum text-lg font-semibold text-slate-50">{c.n}</dd></div></div>))}
            </dl>
          </>)}
        </Card>
        <Card title="Weekly target">
          {!d ? <Skeleton className="h-16" /> : (<>
            <div className="flex items-baseline gap-1.5"><span className="tnum text-4xl font-semibold text-slate-50">{d.weekly_done}</span><span className="text-slate-500">/ {d.weekly_target} videos</span></div>
            <div className="mt-3"><Progress v={d.weekly_done / d.weekly_target} /></div>
            <p className="mt-3 text-xs text-slate-500">{d.weekly_done >= d.weekly_target ? "Target reached for this week." : `${d.weekly_target - d.weekly_done} more to hit this week's target.`}</p>
          </>)}
        </Card>
      </div>

      <div className="mt-5 grid gap-5 lg:grid-cols-2">
        <Card title="Needs attention">
          {!lessons ? <Skeleton className="h-20" /> : attention.length === 0 ? <EmptyState icon="check" title="All clear" hint="No failures and nothing waiting for review." /> : (
            <ul className="divide-y divide-line/70">{attention.slice(0, 6).map((l) => (
              <li key={l.id} className="flex items-center justify-between gap-3 py-2.5">
                <div className="min-w-0"><Link href={`/lessons/${l.id}`} className="block truncate text-sm font-medium text-slate-100 hover:text-brand-400">{l.title}</Link>{l.last_error && <p className="truncate text-xs text-rose-300/80" title={l.last_error}>{l.last_error}</p>}</div>
                <div className="flex shrink-0 items-center gap-2"><Badge s={l.status} /><Link href={l.status === "APPROVAL_PENDING" || l.status === "TECHNICAL_REVIEW" ? "/approvals" : `/lessons/${l.id}`} aria-label="Open" className="text-slate-500 hover:text-slate-50"><Icon name="chevron" /></Link></div>
              </li>))}</ul>)}
        </Card>
        <Card title="Recent activity">
          {!logs ? <Skeleton className="h-20" /> : activity.length === 0 ? <EmptyState icon="activity" title="No activity yet" /> : (
            <ul className="space-y-2.5">{activity.map((a) => (
              <li key={a.id} className="flex items-start gap-2.5 text-sm">
                <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${a.level === "error" ? "bg-rose-500" : "bg-emerald-400/80"}`} />
                <div className="min-w-0 flex-1"><span className="font-medium text-slate-200">{a.stage.replace(/_/g, " ")}</span> <span className="text-slate-400">{String(a.message).split("\n")[0].slice(0, 90)}</span></div>
                <time className="shrink-0 text-xs text-slate-500">{timeAgo(a.at)}</time>
              </li>))}</ul>)}
        </Card>
      </div>
    </div>
  );
}
