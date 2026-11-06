"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, token } from "@/lib/api";
import { Icon, IconName } from "./Icon";
import { ThemeToggle } from "./ThemeToggle";

const NAV: { group: string; items: [string, string, IconName][] }[] = [
  { group: "Production", items: [["/", "Overview", "home"], ["/courses", "Courses", "book"], ["/modules", "Modules", "layers"], ["/lessons", "Lessons", "list"], ["/assets", "Asset Manager", "image"]] },
  { group: "Studio", items: [["/avatar", "Avatar", "user"], ["/voice", "Voice", "mic"], ["/renders", "Video Rendering", "film"]] },
  { group: "Publishing", items: [["/approvals", "Approval Queue", "check"], ["/youtube", "YouTube", "send"], ["/analytics", "Analytics", "chart"]] },
  { group: "System", items: [["/settings", "Settings", "sliders"], ["/health", "System Health", "activity"]] },
];

function ApiStatus() {
  const [h, setH] = useState<{ ok: boolean; llm?: string } | null>(null);
  useEffect(() => {
    const tick = () => api("/health").then((d: any) => setH({ ok: d.status === "ok", llm: d.llm_provider })).catch(() => setH({ ok: false }));
    tick(); const i = setInterval(tick, 15000); return () => clearInterval(i);
  }, []);
  return (
    <div role="status" className="flex h-9 items-center gap-2 rounded-lg border border-line bg-surface px-3 text-xs text-slate-400">
      <span className={`h-2 w-2 rounded-full ${h === null ? "bg-slate-600" : h.ok ? "bg-emerald-400 shadow-[0_0_8px] shadow-emerald-400/60" : "bg-rose-500"}`} />
      <span>{h === null ? "Checking API…" : h.ok ? "API online" : "API unreachable"}</span>
      {h?.llm && <span className="rounded bg-raised px-1.5 py-0.5 font-mono text-[10px] uppercase text-slate-300">{h.llm}</span>}
    </div>
  );
}

export default function Shell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const router = useRouter();
  const [ok, setOk] = useState(false);
  const [open, setOpen] = useState(false);
  useEffect(() => { if (path !== "/login" && !token.get()) router.replace("/login"); else setOk(true); }, [path, router]);
  useEffect(() => setOpen(false), [path]);
  if (path === "/login") return <>{children}</>;
  if (!ok) return null;
  const active = (h: string) => (h === "/" ? path === "/" : path.startsWith(h));
  return (
    <div className="min-h-screen md:flex">
      <header className="sticky top-0 z-30 flex items-center justify-between border-b border-line bg-canvas/90 px-4 py-3 backdrop-blur md:hidden">
        <Brand />
        <div className="flex items-center gap-2"><ThemeToggle />
          <button aria-label="Toggle menu" aria-expanded={open} className="grid h-9 w-9 place-items-center rounded-lg border border-line text-slate-300" onClick={() => setOpen(!open)}><Icon name={open ? "x" : "menu"} className="h-5 w-5" /></button></div>
      </header>
      <aside className={`${open ? "flex" : "hidden"} fixed inset-x-0 top-[61px] bottom-0 z-20 flex-col overflow-y-auto border-r border-line bg-surface p-4 md:sticky md:top-0 md:flex md:h-screen md:w-64 md:shrink-0`}>
        <div className="mb-7 hidden px-2 pt-1 md:block"><Brand /></div>
        <nav className="flex-1 space-y-6" aria-label="Main">
          {NAV.map((g) => (
            <div key={g.group}>
              <div className="mb-2 px-3 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">{g.group}</div>
              <ul className="space-y-0.5">
                {g.items.map(([h, l, ic]) => (
                  <li key={h}>
                    <Link href={h} aria-current={active(h) ? "page" : undefined}
                      className={`group flex items-center gap-3 rounded-lg px-3 py-2 text-[13px] transition ${active(h) ? "bg-brand-500/10 font-medium text-brand-400 ring-1 ring-inset ring-brand-500/20" : "text-slate-400 hover:bg-raised hover:text-slate-100"}`}>
                      <Icon name={ic} className={`h-4 w-4 ${active(h) ? "text-brand-400" : "text-slate-500 group-hover:text-slate-300"}`} />{l}
                    </Link>
                  </li>))}
              </ul>
            </div>))}
        </nav>
        <div className="mt-4 border-t border-line pt-3">
          <button onClick={() => { token.clear(); router.replace("/login"); }} className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-[13px] text-slate-500 transition hover:bg-raised hover:text-slate-200"><Icon name="logout" className="h-4 w-4" />Sign out</button>
        </div>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="sticky top-0 z-10 hidden items-center justify-end gap-2 border-b border-line bg-canvas/80 px-10 py-3 backdrop-blur md:flex"><ApiStatus /><ThemeToggle /></div>
        <main className="min-w-0 flex-1 px-4 py-6 md:px-10 md:py-8"><div className="mx-auto max-w-6xl">{children}</div></main>
      </div>
    </div>
  );
}

function Brand() {
  return (
    <Link href="/" className="flex items-center gap-2.5">
      <span className="grid h-8 w-8 place-items-center rounded-lg bg-gradient-to-br from-brand-400 to-brand-600 text-on-brand shadow-sm"><Icon name="shield" className="h-4 w-4" /></span>
      <span className="leading-tight"><span className="block text-sm font-semibold text-slate-50">AI Video Studio</span><span className="block text-[11px] text-slate-500">Teaching video production for any topic</span></span>
    </Link>
  );
}
