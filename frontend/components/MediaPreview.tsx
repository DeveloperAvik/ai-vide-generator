"use client";
import { useEffect, useState } from "react";
import { blobUrl } from "@/lib/api";

export function Video({ renderId }: { renderId: number }) {
  const [src, setSrc] = useState<string | null>(null);
  const [vtt, setVtt] = useState<string | null>(null);
  useEffect(() => {
    let u: string | undefined;
    blobUrl(`/renders/${renderId}/video`).then((x) => { u = x; setSrc(x); }).catch(() => setSrc(null));
    return () => { if (u) URL.revokeObjectURL(u); };
  }, [renderId]);
  useEffect(() => { // SRT -> WebVTT for the <track>
    blobUrl(`/renders/${renderId}/subtitles`).then(async (u) => { const t = await (await fetch(u)).text(); setVtt(URL.createObjectURL(new Blob(["WEBVTT\n\n" + t.replace(/(\d\d:\d\d:\d\d),(\d\d\d)/g, "$1.$2")], { type: "text/vtt" }))); }).catch(() => {});
  }, [renderId]);
  if (!src) return <div className="aspect-video rounded-lg bg-slate-800 p-6 text-sm text-slate-400">Video unavailable</div>;
  return <video src={src} controls className="aspect-video w-full rounded-lg bg-black">{vtt && <track kind="subtitles" srcLang="en" label="English" src={vtt} />}</video>;
}

export function Thumb({ lessonId, version = 0 }: { lessonId: number; version?: number }) {
  const [src, setSrc] = useState<string | null>(null);
  useEffect(() => {
    let u: string | undefined;
    blobUrl(`/lessons/${lessonId}/thumbnail`).then((x) => { u = x; setSrc(x); }).catch(() => setSrc(null));
    return () => { if (u) URL.revokeObjectURL(u); };
  }, [lessonId, version]); // `version` bumps after a regenerate so the new image is fetched
  return src ? <img src={src} alt="Thumbnail" className="aspect-video w-full rounded-lg border border-line object-cover" /> : <div className="grid aspect-video place-items-center rounded-lg border border-dashed border-line bg-raised text-xs text-slate-500">No thumbnail yet</div>;
}
