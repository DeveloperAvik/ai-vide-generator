// Usage: node scripts/render.mjs <props.json> <out.mp4> <publicDir> [Lesson|Short]
// Prints JSON lines: {"event":"progress","value":0..1} and {"event":"done"|"error"}. SIGTERM cancels the render.
import { bundle } from "@remotion/bundler";
import { renderMedia, selectComposition, makeCancelSignal } from "@remotion/renderer";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const [propsFile, out, publicDir, compId = "Lesson"] = process.argv.slice(2);
if (!propsFile || !out || !publicDir) { console.error("usage: render.mjs props.json out.mp4 publicDir [Lesson|Short]"); process.exit(2); }
const emit = (o) => console.log(JSON.stringify(o));
const root = path.dirname(fileURLToPath(import.meta.url));
const { cancel, cancelSignal } = makeCancelSignal();
process.on("SIGTERM", () => { cancel(); });
try {
  const inputProps = JSON.parse(readFileSync(propsFile, "utf8"));
  const serveUrl = await bundle({ entryPoint: path.join(root, "../src/index.ts"), publicDir: path.resolve(publicDir) });
  const chromiumOptions = { gl: "angle" }; // GPU-backed WebGL (Metal on macOS) for the 3D scenes
  const composition = await selectComposition({ serveUrl, id: compId, inputProps, chromiumOptions });
  await renderMedia({ composition, serveUrl, codec: "h264", audioCodec: "aac", outputLocation: path.resolve(out), inputProps, cancelSignal,
    chromiumOptions, crf: 20, pixelFormat: "yuv420p", onProgress: ({ progress }) => emit({ event: "progress", value: progress }) });
  emit({ event: "done", out: path.resolve(out) });
} catch (e) {
  emit({ event: "error", message: String(e?.message ?? e) });
  process.exit(1);
}
