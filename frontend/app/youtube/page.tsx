"use client";
import { api } from "@/lib/api";
import { useApi } from "@/hooks/useApi";
import { Badge, Btn, Card, ErrorNote, useAsyncAction, PageHeader } from "@/components/ui";
import type { Lesson } from "@/types";

export default function YouTube() {
  const { data: st, error } = useApi<any>("/youtube/status");
  const { data: lessons, reload } = useApi<Lesson[]>("/lessons?status=APPROVED");
  const { err, run } = useAsyncAction();
  return (
    <div className="space-y-5"><PageHeader title="YouTube Publishing" desc="Uploads are private by default and require an approved lesson." /><ErrorNote msg={error ?? err} />
      <Card title="Connection">
        {st && <ul className="space-y-1 text-sm"><li>OAuth client secrets configured: <Badge s={st.client_secrets_configured ? "done" : "missing"} /></li><li>Authorized: <Badge s={st.authorized ? "done" : "no"} /></li></ul>}
        <div className="mt-3"><Btn disabled={!st?.client_secrets_configured} onClick={() => run(async () => { const r = await api<any>("/youtube/oauth/start"); window.location.href = r.authorization_url; })}>Connect YouTube account</Btn>
          {!st?.client_secrets_configured && <p className="mt-2 text-xs text-slate-400">Set YOUTUBE_CLIENT_SECRETS in .env — see docs/YOUTUBE_SETUP.md.</p>}</div>
      </Card>
      <Card title="Approved lessons (uploads default to PRIVATE)">
        {lessons?.length === 0 && <p className="text-sm text-slate-400">No approved lessons.</p>}
        {lessons?.map((l) => (<div key={l.id} className="flex items-center justify-between py-1 text-sm">{l.title}
          <Btn disabled={!st?.ready_to_upload} onClick={() => run(async () => { await api(`/lessons/${l.id}/youtube/publish`, { method: "POST", json: { publish_at: new Date(Date.now() + 48 * 3600e3).toISOString() } }); reload(); })}>Upload private + schedule +48h</Btn></div>))}
      </Card>
    </div>
  );
}
