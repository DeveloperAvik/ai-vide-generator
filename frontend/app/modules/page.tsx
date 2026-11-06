"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Badge, Card, ErrorNote, PageHeader } from "@/components/ui";
import type { Course } from "@/types";

export default function Modules() {
  const [courses, setCourses] = useState<Course[]>([]);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { (async () => { try { const list: Course[] = await api("/courses"); setCourses(await Promise.all(list.map((c) => api<Course>(`/courses/${c.id}`)))); } catch (e: any) { setErr(e.message); } })(); }, []);
  return (
    <div className="space-y-6"><PageHeader title="Modules" desc="Every module and lesson, grouped by course." /><ErrorNote msg={err} />
      {courses.map((c) => (<Card key={c.id} title={c.name}>
        {c.modules?.map((m) => (<div key={m.id} className="mb-4"><h3 className="font-semibold">{m.position + 1}. {m.title}</h3><p className="text-sm text-slate-400">{m.description}</p>
          <ul className="mt-2 space-y-1">{m.lessons.map((l) => (<li key={l.id} className="flex items-center justify-between text-sm"><Link className="text-sky-300" href={`/lessons/${l.id}`}>{l.title}</Link><Badge s={l.status} /></li>))}</ul></div>))}
      </Card>))}
    </div>
  );
}
