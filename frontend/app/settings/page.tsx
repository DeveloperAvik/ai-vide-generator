"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useApi } from "@/hooks/useApi";
import { Badge, Btn, Card, ErrorNote, useAsyncAction, PageHeader } from "@/components/ui";

export default function Settings() {
  const { data: cfg, error, reload } = useApi<any>("/system/ai-config");
  const [f, setF] = useState<any>({});
  const [key, setKey] = useState("");
  const [result, setResult] = useState<string | null>(null);
  const { busy, err, run } = useAsyncAction();
  useEffect(() => { if (cfg) setF(cfg); }, [cfg]);
  const set = (k: string, v: string) => setF({ ...f, [k]: v });
  const save = () => run(async () => {
    const body: any = { llm_provider: f.llm_provider, llm_fallback_provider: f.llm_fallback_provider, anthropic_model: f.anthropic_model, ollama_url: f.ollama_url, ollama_model: f.ollama_model };
    if (key) body.anthropic_api_key = key;
    await api("/system/ai-config", { method: "PUT", json: body });
    setKey(""); setResult("Saved."); reload();
  });
  const test = (p?: string) => run(async () => { const r = await api<any>(`/system/ai-config/test${p ? `?provider=${p}` : ""}`, { method: "POST" }); setResult(`${r.provider}: ${r.ok ? "OK" : "failed"} ${r.note}`); });
  return (
    <div className="space-y-5"><PageHeader title="Settings · AI providers" desc="Choose the LLM provider, fallback and credentials." /><ErrorNote msg={error ?? err} />
      {result && <div className="rounded-lg border border-sky-800 bg-sky-950 p-3 text-sm">{result}</div>}
      {cfg && (<Card title={`Environment: ${cfg.app_env}`}>
        {cfg.app_env === "production" && <p className="mb-3 text-xs text-amber-300">Production mode: the mock provider and the macOS voice are disabled.</p>}
        <div className="grid gap-3 md:grid-cols-2">
          <label className="text-sm">Primary provider<select value={f.llm_provider ?? ""} onChange={(e) => set("llm_provider", e.target.value)}>{cfg.app_env !== "production" && <option value="mock">mock (offline demo only)</option>}<option value="anthropic">anthropic (API key)</option><option value="ollama">ollama (local)</option></select></label>
          <label className="text-sm">Fallback provider<select value={f.llm_fallback_provider ?? ""} onChange={(e) => set("llm_fallback_provider", e.target.value)}><option value="">none</option><option value="ollama">ollama</option><option value="anthropic">anthropic</option></select></label>
          <label className="text-sm">Anthropic model<input value={f.anthropic_model ?? ""} onChange={(e) => set("anthropic_model", e.target.value)} /></label>
          <label className="text-sm">Anthropic API key {cfg.anthropic_key_set && <Badge s="done" />}<input type="password" autoComplete="off" placeholder={cfg.anthropic_key_set ? "•••• saved (leave blank to keep)" : "sk-ant-…  (console.anthropic.com; Claude Pro is not an API key)"} value={key} onChange={(e) => setKey(e.target.value)} /></label>
          <label className="text-sm">Ollama URL<input value={f.ollama_url ?? ""} onChange={(e) => set("ollama_url", e.target.value)} /></label>
          <label className="text-sm">Ollama model<input value={f.ollama_model ?? ""} onChange={(e) => set("ollama_model", e.target.value)} /></label>
        </div>
        <div className="mt-4 flex flex-wrap gap-2"><Btn disabled={busy} onClick={save}>Save</Btn><Btn kind="ghost" disabled={busy} onClick={() => test()}>Test primary</Btn><Btn kind="ghost" disabled={busy} onClick={() => test("anthropic")}>Test Anthropic</Btn><Btn kind="ghost" disabled={busy} onClick={() => test("ollama")}>Test Ollama</Btn></div>
        <p className="mt-3 text-xs text-slate-500">The key is stored server-side (mode 0600) and never sent back to the browser. Tests make one real, tiny API call.</p>
      </Card>)}
    </div>
  );
}
