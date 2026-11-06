"use client";
import React, { createContext, useCallback, useContext, useState } from "react";
import { Icon, IconName } from "./Icon";
import { useAnimatedNumber } from "@/hooks/useAnimatedNumber";

/* ---------- layout primitives ---------- */
export function PageHeader({ title, desc, actions }: { title: string; desc?: string; actions?: React.ReactNode }) {
  return (
    <header className="mb-7 flex flex-wrap items-end justify-between gap-3">
      <div><h1 className="text-2xl font-semibold tracking-tight text-slate-50">{title}</h1>{desc && <p className="mt-1 max-w-2xl text-sm text-slate-400">{desc}</p>}</div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </header>
  );
}

export const Card = ({ title, children, className = "", action }: { title?: string; children: React.ReactNode; className?: string; action?: React.ReactNode }) => (
  <section className={`rounded-xl border border-line bg-surface shadow-card ${className}`}>
    {title && (<div className="flex items-center justify-between border-b border-line/70 px-5 py-3"><h2 className="text-sm font-semibold text-slate-100">{title}</h2>{action}</div>)}
    <div className="p-5">{children}</div>
  </section>
);

/* ---------- buttons ---------- */
type Kind = "primary" | "danger" | "ghost" | "subtle";
export const Btn = ({ children, onClick, kind = "primary", disabled, type = "button", loading, icon, size = "md" }: { children?: React.ReactNode; onClick?: () => void; kind?: Kind; disabled?: boolean; type?: "button" | "submit"; loading?: boolean; icon?: IconName; size?: "sm" | "md" }) => {
  const styles: Record<Kind, string> = {
    primary: "bg-brand-500 text-on-brand hover:bg-brand-400 shadow-sm",
    danger: "bg-rose-600 text-white hover:bg-rose-500",
    ghost: "border border-line bg-transparent text-slate-200 hover:bg-raised hover:border-slate-500",
    subtle: "bg-raised text-slate-200 hover:bg-line",
  };
  return (
    <button type={type} disabled={disabled || loading} onClick={onClick}
      className={`inline-flex items-center justify-center gap-1.5 rounded-lg font-medium transition disabled:cursor-not-allowed disabled:opacity-40 ${size === "sm" ? "px-2.5 py-1 text-xs" : "px-3.5 py-2 text-sm"} ${styles[kind]}`}>
      {loading ? <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-current border-t-transparent" /> : icon && <Icon name={icon} className="h-3.5 w-3.5" />}
      {children}
    </button>
  );
};

/* ---------- status badges ---------- */
type Tone = "neutral" | "info" | "warn" | "good" | "bad";
const TONES: Record<Tone, string> = {
  neutral: "bg-slate-500/10 text-slate-300 ring-slate-500/20", info: "bg-sky-500/10 text-sky-300 ring-sky-500/25",
  warn: "bg-amber-500/10 text-amber-300 ring-amber-500/25", good: "bg-emerald-500/10 text-emerald-300 ring-emerald-500/25", bad: "bg-rose-500/10 text-rose-300 ring-rose-500/25",
};
const TONE_OF: Record<string, Tone> = {
  FAILED: "bad", failed: "bad", missing: "bad", unavailable: "neutral", no: "neutral", paid: "warn", unverified: "warn",
  TECHNICAL_REVIEW: "warn", APPROVAL_PENDING: "warn", APPROVED: "good", SCHEDULED: "good", PUBLISHED: "good", done: "good", cancelled: "neutral",
  RESEARCHING: "info", SCRIPT_GENERATED: "info", SCRIPT_APPROVED: "info", ASSETS_GENERATING: "info", ASSETS_READY: "info", RENDERING: "info", QUALITY_CHECK: "info", running: "info", queued: "info", cancelling: "warn",
};
const LABEL: Record<string, string> = { done: "OK", paid: "Paid", no: "No" };
export const label = (s: string) => LABEL[s] ?? s.toLowerCase().replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());
export const Badge = ({ s, tone }: { s: string; tone?: Tone }) => {
  const t = tone ?? TONE_OF[s] ?? "neutral";
  return (<span className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset ${TONES[t]}`}><span className="h-1.5 w-1.5 rounded-full bg-current" />{label(s)}</span>);
};

/* ---------- stats / progress ---------- */
export const Stat = ({ label: l, value, icon, tone = "neutral", hint }: { label: string; value: React.ReactNode; icon?: IconName; tone?: Tone; hint?: string }) => {
  const ring = { neutral: "text-slate-400 bg-slate-500/10", info: "text-sky-300 bg-sky-500/10", warn: "text-amber-300 bg-amber-500/10", good: "text-emerald-300 bg-emerald-500/10", bad: "text-rose-300 bg-rose-500/10" }[tone];
  return (
    <div className="rounded-xl border border-line bg-surface p-4 shadow-card">
      <div className="flex items-center justify-between"><span className="text-xs font-medium text-slate-400">{l}</span>{icon && <span className={`grid h-7 w-7 place-items-center rounded-lg ${ring}`}><Icon name={icon} className="h-3.5 w-3.5" /></span>}</div>
      <div className="tnum mt-2 text-3xl font-semibold tracking-tight text-slate-50">{value}</div>
      {hint && <div className="mt-1 text-xs text-slate-500">{hint}</div>}
    </div>
  );
};
export const Progress = ({ v, active = false }: { v: number; active?: boolean }) => {
  const clamped = Math.min(1, Math.max(0, v));
  const shown = useAnimatedNumber(clamped);
  const indeterminate = active && clamped <= 0; // backend has not reported any progress yet
  const pct = Math.round((active ? shown : clamped) * 100);
  return (
    <div className="flex items-center gap-2">
      <div className="relative h-2 w-full overflow-hidden rounded-full bg-raised" role="progressbar" aria-label={indeterminate ? "Progress not reported yet" : "Progress"}
        aria-valuenow={indeterminate ? undefined : Math.round(clamped * 100)} aria-valuemin={0} aria-valuemax={100}>
        {indeterminate ? (
          <div className="absolute inset-y-0 left-0 w-2/5 animate-indeterminate rounded-full bg-gradient-to-r from-transparent via-brand-500 to-transparent motion-reduce:w-full motion-reduce:opacity-40" />
        ) : (
          <div className={`relative h-full overflow-hidden rounded-full bg-gradient-to-r from-brand-600 to-brand-400 ${active ? "shadow-[0_0_12px_rgb(var(--brand-500)/.55)]" : "transition-all"}`} style={{ width: `${pct}%` }}>
            {active && <div className="absolute inset-0 -translate-x-full animate-[shimmer_1.4s_infinite] bg-gradient-to-r from-transparent via-white/40 to-transparent" />}
          </div>
        )}
      </div>
      {active && !indeterminate && <span className="tnum w-9 shrink-0 text-right text-xs text-brand-400">{pct}%</span>}
    </div>
  );
};

/* ---------- feedback ---------- */
export const ErrorNote = ({ msg }: { msg: string | null }) =>
  msg ? (<div role="alert" className="mb-4 flex items-start gap-2 rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-200"><Icon name="alert" className="mt-0.5 h-4 w-4 shrink-0" /><span className="break-words">{msg}</span></div>) : null;

export const Skeleton = ({ className = "h-4 w-full" }: { className?: string }) => (
  <div className={`relative overflow-hidden rounded-md bg-raised ${className}`}><div className="absolute inset-0 -translate-x-full animate-[shimmer_1.4s_infinite] bg-gradient-to-r from-transparent via-slate-50/[.05] to-transparent" /></div>
);

export const EmptyState = ({ icon = "inbox", title, hint, action }: { icon?: IconName; title: string; hint?: string; action?: React.ReactNode }) => (
  <div className="flex flex-col items-center justify-center py-10 text-center">
    <span className="grid h-11 w-11 place-items-center rounded-full bg-raised text-slate-400"><Icon name={icon} className="h-5 w-5" /></span>
    <p className="mt-3 text-sm font-medium text-slate-200">{title}</p>{hint && <p className="mt-1 max-w-sm text-xs text-slate-500">{hint}</p>}{action && <div className="mt-4">{action}</div>}
  </div>
);

/* ---------- toasts ---------- */
type Toast = { id: number; msg: string; tone: "good" | "bad" | "info" };
const ToastCtx = createContext<(msg: string, tone?: Toast["tone"]) => void>(() => {});
export const useToast = () => useContext(ToastCtx);
export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);
  const push = useCallback((msg: string, tone: Toast["tone"] = "good") => {
    const id = Date.now() + Math.random();
    setItems((x) => [...x, { id, msg, tone }]);
    setTimeout(() => setItems((x) => x.filter((t) => t.id !== id)), 4500);
  }, []);
  const c = { good: "border-emerald-500/30 text-emerald-200", bad: "border-rose-500/30 text-rose-200", info: "border-sky-500/30 text-sky-200" };
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div aria-live="polite" className="pointer-events-none fixed bottom-4 right-4 z-50 flex w-80 max-w-[calc(100vw-2rem)] flex-col gap-2">
        {items.map((t) => (<div key={t.id} className={`pointer-events-auto animate-toast rounded-lg border bg-raised px-3.5 py-2.5 text-sm shadow-xl ${c[t.tone]}`}>{t.msg}</div>))}
      </div>
    </ToastCtx.Provider>
  );
}

export function useAsyncAction() {
  const [busy, setBusy] = React.useState(false);
  const [err, setErr] = React.useState<string | null>(null);
  const toast = useToast();
  const run = async (fn: () => Promise<unknown>, okMsg?: string) => {
    setBusy(true); setErr(null);
    try { await fn(); if (okMsg) toast(okMsg); } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  };
  return { busy, err, run };
}

/* ---------- data table helpers ---------- */
export const Th = ({ children, className = "" }: { children?: React.ReactNode; className?: string }) => <th className={`border-b border-line bg-raised/50 px-3 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wider text-slate-400 ${className}`}>{children}</th>;
export const Td = ({ children, className = "" }: { children?: React.ReactNode; className?: string }) => <td className={`px-3 py-3 align-middle text-sm ${className}`}>{children}</td>;
export const timeAgo = (iso: string) => {
  const s = Math.max(1, Math.round((Date.now() - new Date(iso.endsWith("Z") || iso.includes("+") ? iso : iso + "Z").getTime()) / 1000));
  return s < 60 ? `${s}s ago` : s < 3600 ? `${Math.round(s / 60)}m ago` : s < 86400 ? `${Math.round(s / 3600)}h ago` : `${Math.round(s / 86400)}d ago`;
};
