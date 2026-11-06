const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export const token = {
  get: () => (typeof window === "undefined" ? null : window.localStorage.getItem("studio_token")),
  set: (t: string) => window.localStorage.setItem("studio_token", t),
  clear: () => window.localStorage.removeItem("studio_token"),
};

export class ApiError extends Error { constructor(public status: number, msg: string) { super(msg); } }

export async function api<T = any>(path: string, init: RequestInit & { json?: unknown } = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const t = token.get();
  if (t) headers.set("Authorization", `Bearer ${t}`);
  if (init.json !== undefined) { headers.set("Content-Type", "application/json"); init.body = JSON.stringify(init.json); }
  const res = await fetch(`${BASE}/api${path}`, { ...init, headers });
  if (res.status === 401 && typeof window !== "undefined" && !path.startsWith("/auth")) { token.clear(); window.location.href = "/login"; }
  if (!res.ok) {
    let detail = res.statusText;
    try { const j = await res.json(); detail = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail); } catch {}
    throw new ApiError(res.status, detail);
  }
  return res.headers.get("content-type")?.includes("json") ? res.json() : (res as any);
}

/** DELETE after a confirm(). A 409 (published / job in flight) is offered again as a forced delete. Resolves false if the user backed out. */
export async function confirmDelete(path: string, what: string): Promise<boolean> {
  if (!window.confirm(`Delete ${what}? This permanently removes its data and files and cannot be undone.`)) return false;
  try { await api(path, { method: "DELETE" }); return true; }
  catch (e) {
    if (e instanceof ApiError && e.status === 409 && window.confirm(`${e.message}\n\nDelete anyway?`)) { await api(`${path}${path.includes("?") ? "&" : "?"}force=true`, { method: "DELETE" }); return true; }
    throw e;
  }
}

/** Authenticated fetch of a binary resource as an object URL (for <video>/<img>, which can't send headers). */
export async function blobUrl(path: string): Promise<string> {
  const res = await fetch(`${BASE}/api${path}`, { headers: { Authorization: `Bearer ${token.get() ?? ""}` } });
  if (!res.ok) throw new ApiError(res.status, "media unavailable");
  return URL.createObjectURL(await res.blob());
}
