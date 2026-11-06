"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, token } from "@/lib/api";
import { Btn, ErrorNote } from "@/components/ui";
import { Icon } from "@/components/Icon";

export default function Login() {
  const r = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); setBusy(true); setErr(null);
    try { const t = await api<{ access_token: string }>("/auth/login", { method: "POST", json: { email, password } }); token.set(t.access_token); r.replace("/"); }
    catch (x: any) { setErr(x.message === "Invalid credentials" ? "Incorrect email or password." : x.message); } finally { setBusy(false); }
  };
  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <div className="relative hidden overflow-hidden border-r border-line bg-surface lg:block">
        <div className="absolute inset-0 bg-[radial-gradient(600px_400px_at_30%_20%,rgb(var(--brand-500)/.18),transparent),radial-gradient(500px_400px_at_80%_90%,rgb(var(--brand-600)/.18),transparent)]" />
        <div className="relative flex h-full flex-col justify-between p-12">
          <div className="flex items-center gap-2.5 text-slate-50"><span className="grid h-9 w-9 place-items-center rounded-lg bg-gradient-to-br from-brand-400 to-brand-600 text-on-brand"><Icon name="shield" className="h-5 w-5" /></span><b className="text-lg">AI Video Studio</b></div>
          <div>
            <h2 className="max-w-md text-3xl font-semibold leading-tight tracking-tight text-slate-50">From topic to reviewed, published lesson.</h2>
            <ul className="mt-6 space-y-3 text-sm text-slate-300">
              {["Researched, schema-validated scripts", "Local neural narration and lab footage", "Human approval before anything is published"].map((t) => (
                <li key={t} className="flex items-center gap-2.5"><Icon name="check" className="h-4 w-4 text-brand-400" />{t}</li>))}
            </ul>
          </div>
          <p className="text-xs text-slate-500">Educational use only. Test only systems you are authorized to test.</p>
        </div>
      </div>
      <div className="grid place-items-center p-6">
        <form onSubmit={submit} className="w-full max-w-sm space-y-4">
          <div><h1 className="text-2xl font-semibold tracking-tight text-slate-50">Sign in</h1><p className="mt-1 text-sm text-slate-400">Use your studio administrator account.</p></div>
          <ErrorNote msg={err} />
          <label className="block text-sm text-slate-300">Email<input className="mt-1.5" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="username" autoFocus /></label>
          <label className="block text-sm text-slate-300">Password<input className="mt-1.5" type="password" required value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" /></label>
          <button type="submit" disabled={busy} className="flex w-full items-center justify-center gap-2 rounded-lg bg-brand-500 px-4 py-2.5 text-sm font-semibold text-on-brand transition hover:bg-brand-400 disabled:opacity-50">{busy && <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white border-t-transparent" />}Sign in</button>
        </form>
      </div>
    </div>
  );
}
