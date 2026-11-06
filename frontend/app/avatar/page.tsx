"use client";
import { useApi } from "@/hooks/useApi";
import { Badge, Card, ErrorNote, PageHeader } from "@/components/ui";

export default function AvatarConfig() {
  const { data, error } = useApi<any>("/system/providers");
  return (
    <div className="space-y-5"><PageHeader title="Avatar Configuration" desc="Instructor avatar providers and their availability." /><ErrorNote msg={error} />
      <p className="text-sm text-slate-400">Providers are configured with environment variables in <code>.env</code> (see docs/API_SETUP.md). Paid providers stay disabled until credentials are set.</p>
      <div className="grid gap-3 md:grid-cols-2">{data?.avatar.map((p: any) => (
        <Card key={p.name}><div className="flex items-center justify-between"><b>{p.name}</b><span className="space-x-2">{p.paid && <Badge s="paid" />}<Badge s={p.available ? "done" : "unavailable"} /></span></div><p className="mt-2 text-sm text-slate-400">{p.detail}</p></Card>))}</div>
    </div>
  );
}
