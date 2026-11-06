"use client";
import { useApi } from "@/hooks/useApi";
import { Card, ErrorNote, PageHeader } from "@/components/ui";

export default function Analytics() {
  const { data, error } = useApi<any[]>("/analytics");
  return (<div className="space-y-5"><PageHeader title="Analytics" desc="Views, likes and comments collected from published videos." /><ErrorNote msg={error} />
    <Card><table className="w-full text-left text-sm"><thead className="text-slate-400"><tr><th className="p-2">Publication</th><th>Views</th><th>Likes</th><th>Comments</th><th>Collected</th></tr></thead>
      <tbody>{data?.map((a, i) => <tr key={i} className="border-t border-line"><td className="p-2">#{a.publication_id}</td><td>{a.views}</td><td>{a.likes}</td><td>{a.comments}</td><td>{a.collected_at}</td></tr>)}</tbody></table>
      {data?.length === 0 && <p className="p-2 text-sm text-slate-400">No data yet. Analytics are collected from YouTube once videos are published (workflow 12).</p>}</Card></div>);
}
