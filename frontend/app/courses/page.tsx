"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { api, confirmDelete } from "@/lib/api";
import { useApi } from "@/hooks/useApi";
import { Btn, Card, ErrorNote, useAsyncAction, PageHeader } from "@/components/ui";
import type { Course } from "@/types";

interface Domain { key: string; label: string; audience: string }

export default function Courses() {
  const { data, error, reload } = useApi<Course[]>("/courses");
  const { data: domains } = useApi<Domain[]>("/domains");
  const [f, setF] = useState({ course_name: "", domain: "general", difficulty: "Intermediate", target_audience: "Learners", videos_per_week: 3, duration_minutes: 8 });
  const label = (k?: string) => domains?.find((d) => d.key === k)?.label ?? k;
  const { busy, err, run } = useAsyncAction();
  const router = useRouter();
  const quick = useAsyncAction();
  const [q, setQ] = useState({ topic: "", domain: "general", minutes: 5 });
  return (
    <div className="space-y-6">
      <PageHeader title="Courses" desc="Generate a curriculum with the configured AI provider, or browse existing courses." />
      <Card title="Quick video (draft)">
        <p className="mb-3 text-sm text-slate-400">One topic in, one video out. Skips source research and the fact-check review, so it is ready much sooner. Every frame is stamped <b className="text-rose-300">UNREVIEWED DRAFT</b> and it can not be approved or published until you choose “Make official” on the Lessons page.</p>
        <ErrorNote msg={quick.err} />
        <div className="grid gap-3 md:grid-cols-3">
          <label className="text-sm md:col-span-3">Topic<input value={q.topic} placeholder="e.g. How gradient descent trains a neural network" onChange={(e) => setQ({ ...q, topic: e.target.value })} /></label>
          <label className="text-sm">Subject area<select value={q.domain} onChange={(e) => setQ({ ...q, domain: e.target.value })}>{(domains ?? [{ key: "general", label: "General / Any topic", audience: "" }]).map((d) => <option key={d.key} value={d.key}>{d.label}</option>)}</select></label>
          <label className="text-sm">Minutes (5-25)<input type="number" min={5} max={25} value={q.minutes} onChange={(e) => setQ({ ...q, minutes: +e.target.value })} /></label>
        </div>
        <div className="mt-3"><Btn loading={quick.busy} disabled={q.topic.trim().length < 3} icon="play" onClick={() => quick.run(async () => { await api("/quick-video", { method: "POST", json: q }); router.push("/lessons"); }, "Draft video started")}>{quick.busy ? "Starting…" : "Make quick video"}</Btn></div>
      </Card>
      <Card title="Generate a course (uses the configured LLM provider)">
        <ErrorNote msg={err} />
        <div className="grid gap-3 md:grid-cols-2">
          <label className="text-sm">Subject area<select value={f.domain} onChange={(e) => { const d = domains?.find((x) => x.key === e.target.value); setF({ ...f, domain: e.target.value, target_audience: d?.audience ?? f.target_audience }); }}>{(domains ?? [{ key: "general", label: "General / Any topic", audience: "" }]).map((d) => <option key={d.key} value={d.key}>{d.label}</option>)}</select></label>
          <label className="text-sm">Course topic<input value={f.course_name} placeholder="e.g. Active Directory attack paths, Intro to transformers, Rust ownership" onChange={(e) => setF({ ...f, course_name: e.target.value })} /></label>
          <label className="text-sm">Difficulty<select value={f.difficulty} onChange={(e) => setF({ ...f, difficulty: e.target.value })}><option>Beginner</option><option>Intermediate</option><option>Advanced</option></select></label>
          <label className="text-sm">Audience<input value={f.target_audience} onChange={(e) => setF({ ...f, target_audience: e.target.value })} /></label>
          <label className="text-sm">Minutes per video (5-25)<input type="number" min={5} max={25} value={f.duration_minutes} onChange={(e) => setF({ ...f, duration_minutes: +e.target.value })} /></label>
        </div>
        <div className="mt-3"><Btn loading={busy} disabled={f.course_name.trim().length < 3} icon="plus" onClick={() => run(async () => { await api("/courses/generate", { method: "POST", json: f }); reload(); }, "Course generated")}>{busy ? "Generating…" : "Generate course"}</Btn></div>
      </Card>
      <ErrorNote msg={error} />
      <div className="grid gap-3 md:grid-cols-2">
        {data?.map((c) => (<Card key={c.id} className="transition hover:border-slate-500"><Link href="/modules" className="text-base font-semibold text-slate-50 hover:text-brand-400">{c.name}</Link><p className="mt-1.5 line-clamp-2 text-sm text-slate-400">{c.description}</p><div className="mt-3 flex flex-wrap gap-1.5 text-[11px] text-slate-400"><span className="rounded-full bg-brand-500/15 px-2 py-0.5 text-brand-400">{label(c.domain)}</span><span className="rounded-full bg-raised px-2 py-0.5">{c.difficulty}</span><span className="rounded-full bg-raised px-2 py-0.5">{c.duration_minutes} min videos</span><span className="rounded-full bg-raised px-2 py-0.5">{c.videos_per_week}/week</span></div>
          <div className="mt-3"><Btn size="sm" kind="ghost" icon="trash" onClick={() => run(async () => { if (await confirmDelete(`/courses/${c.id}`, `course "${c.name}" and all its lessons and videos`)) reload(); }, "Course deleted")}>Delete course</Btn></div></Card>))}
      </div>
    </div>
  );
}
