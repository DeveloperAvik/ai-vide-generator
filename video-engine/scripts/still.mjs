// Dev/QA tool: render single frames of the Lesson composition to PNG so the animation can be inspected without a full render.
// usage: node scripts/still.mjs <props.json> <publicDir> <outDir> <frame> [frame...]   (frames are timeline frames)
// env COMP=Gallery renders the QA component gallery instead of the Lesson (props file may then be "{}")
import { bundle } from "@remotion/bundler";
import { renderStill, selectComposition } from "@remotion/renderer";
import { readFileSync, mkdirSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const [propsFile, publicDir, outDir, ...frames] = process.argv.slice(2);
if (!propsFile || !publicDir || !outDir || !frames.length) { console.error("usage: still.mjs props.json publicDir outDir frame..."); process.exit(2); }
const root = path.dirname(fileURLToPath(import.meta.url));
const inputProps = JSON.parse(readFileSync(propsFile, "utf8"));
mkdirSync(outDir, { recursive: true });
const serveUrl = await bundle({ entryPoint: path.join(root, "../src/index.ts"), publicDir: path.resolve(publicDir) });
const composition = await selectComposition({ serveUrl, id: process.env.COMP ?? "Lesson", inputProps });
for (const f of frames) {
  const out = path.resolve(outDir, `frame_${String(f).padStart(5, "0")}.png`);
  await renderStill({ composition, serveUrl, output: out, frame: Number(f), inputProps });
  console.log(out);
}
