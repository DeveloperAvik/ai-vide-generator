// Authenticated dashboard screenshots via Chrome DevTools Protocol (dev tool; no extra deps).
// usage: node scripts/shot.mjs <outdir> "name|/path|width" ...
import { spawn } from "node:child_process";
import { readFileSync, mkdirSync, writeFileSync, readdirSync } from "node:fs";
import path from "node:path";
const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), "../..");
const env = Object.fromEntries(readFileSync(`${root}/.env`, "utf8").split("\n").filter((l) => l.includes("=") && !l.startsWith("#")).map((l) => [l.split("=")[0], l.slice(l.indexOf("=") + 1)]));
const [out, ...pages] = process.argv.slice(2);
mkdirSync(out, { recursive: true });
const base = `${root}/video-engine/node_modules/.remotion/chrome-headless-shell/mac-arm64/chrome-headless-shell-mac-arm64/chrome-headless-shell`;
const login = await fetch("http://localhost:8000/api/auth/login", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ email: env.FIRST_ADMIN_EMAIL, password: env.FIRST_ADMIN_PASSWORD }) });
const token = (await login.json()).access_token;
const chrome = spawn(base, ["--remote-debugging-port=9333", "--no-sandbox", "--hide-scrollbars", "about:blank"], { stdio: "ignore" });
await new Promise((r) => setTimeout(r, 1500));
const targets = await (await fetch("http://127.0.0.1:9333/json")).json();
const ws = new WebSocket(targets.find((t) => t.type === "page").webSocketDebuggerUrl);
await new Promise((r) => (ws.onopen = r));
let id = 0; const pending = new Map();
ws.onmessage = (m) => { const d = JSON.parse(m.data); pending.get(d.id)?.(d); };
const send = (method, params = {}) => new Promise((res) => { const i = ++id; pending.set(i, res); ws.send(JSON.stringify({ id: i, method, params })); });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
await send("Page.enable");
await send("Page.navigate", { url: "http://localhost:3000/login" }); await sleep(1500);
await send("Runtime.evaluate", { expression: `localStorage.setItem("studio_token", ${JSON.stringify(token)})` });
for (const p of pages) {
  const [name, route, w = "1440", h = "900"] = p.split("|");
  await send("Emulation.setDeviceMetricsOverride", { width: +w, height: +h, deviceScaleFactor: 1, mobile: +w < 700 });
  await send("Page.navigate", { url: "http://localhost:3000" + route }); await sleep(3000);
  const shot = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: false });
  writeFileSync(`${out}/${name}.png`, Buffer.from(shot.result.data, "base64")); console.log("shot", name);
}
chrome.kill(); process.exit(0);
