import { cancelRender, continueRender, delayRender } from "remotion";
import inter400 from "@fontsource/inter/files/inter-latin-400-normal.woff2";
import inter600 from "@fontsource/inter/files/inter-latin-600-normal.woff2";
import inter700 from "@fontsource/inter/files/inter-latin-700-normal.woff2";
import mono400 from "@fontsource/jetbrains-mono/files/jetbrains-mono-latin-400-normal.woff2";
import mono700 from "@fontsource/jetbrains-mono/files/jetbrains-mono-latin-700-normal.woff2";

const FACES: [string, string, string][] = [["Inter", "400", inter400], ["Inter", "600", inter600], ["Inter", "700", inter700],
  ["JetBrains Mono", "400", mono400], ["JetBrains Mono", "700", mono700]];
let started = false;

/** Fonts ship inside the bundle (no network), and rendering waits for them: a missing font fails the render instead of
 *  silently producing different glyph metrics (which would shift every layout). Call once at module load. */
export const loadFonts = () => {
  if (started || typeof document === "undefined") return;
  started = true;
  const h = delayRender("fonts", { timeoutInMilliseconds: 30000 });
  Promise.all(FACES.map(([family, weight, url]) => new FontFace(family, `url(${url})`, { weight }).load().then((f) => (document.fonts as unknown as { add(f: FontFace): void }).add(f))))
    .then(() => continueRender(h)).catch((e) => cancelRender(e));
};
