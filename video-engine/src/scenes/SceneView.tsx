import React from "react";
import { AbsoluteFill, Audio, Img, OffthreadVideo, interpolate, staticFile, useCurrentFrame } from "remotion";
import { Frame } from "../components/Frame";
import { CameraRig } from "../components/CameraRig";
import { SceneProps } from "../utils/types";
import { Graph3D } from "../components/three/Graph3D";
import { Stack3D } from "../components/three/Stack3D";
import { AnimatedBulletList, KineticTypography, LowerThird } from "../components/typography";
import { AnimatedFlowchart } from "../components/diagrams";
import { BrowserInteractionAnimation, CodeTypingAnimation, TerminalWindow } from "../components/code";
import { VisualizationView } from "../components/security";
import { MotionProvider } from "../motion";
import { T } from "../utils/theme";

const splitLines = (s: string, width = 22): string[] => {
  const out: string[] = []; let cur = "";
  for (const w of s.split(/\s+/).filter(Boolean)) { if ((cur + " " + w).trim().length > width && cur) { out.push(cur); cur = w; } else cur = (cur + " " + w).trim(); }
  return cur ? [...out, cur] : out;
};

const Instructor: React.FC<{ scene: SceneProps; title: string }> = ({ scene, title }) => {
  const frame = useCurrentFrame();
  const slow = interpolate(frame, [0, scene.frames], [1, 1.035], { extrapolateRight: "clamp" }); // portrait drifts in very slowly
  return (
    <>
      {scene.recording
        ? <OffthreadVideo src={staticFile(scene.recording)} muted style={{ position: "absolute", inset: 0, width: 1920, height: 1080, objectFit: "cover" }} />
        : scene.portrait ? <div style={{ position: "absolute", right: 120, top: 150, height: 760, width: 640, borderRadius: 24, overflow: "hidden", boxShadow: T.shadow, border: `1px solid ${T.border}` }}>
          <Img src={staticFile(scene.portrait)} style={{ width: "100%", height: "100%", objectFit: "cover", transform: `scale(${slow})` }} /></div> : null}
      <div style={{ position: "absolute", left: T.margin, top: 300, width: 940 }}>
        <KineticTypography lines={splitLines(scene.on_screen_text || title)} size={78} start={6} />
      </div>
      <LowerThird name={scene.brand ?? "Teaching Studio"} title={title} start={20} hold={Math.max(30, Math.min(120, scene.frames - 80))} />
    </>
  );
};

const Body: React.FC<{ scene: SceneProps; title: string }> = ({ scene, title }) => (
  <>
    {scene.type === "instructor" && <Instructor scene={scene} title={title} />}
    {["slide", "summary", "quiz"].includes(scene.type) && <AnimatedBulletList items={scene.bullets ?? []} quiz={scene.type === "quiz"} correct={scene.quiz_answer ?? null} />}
    {scene.type === "diagram" && scene.visualization && <VisualizationView viz={scene.visualization} />}
    {scene.type === "diagram" && !scene.visualization && scene.mode3d === "flow" && scene.graph3d && <Graph3D graph={scene.graph3d} />}
    {scene.type === "diagram" && !scene.visualization && scene.mode3d === "stack" && <Stack3D layers={scene.bullets ?? []} highlight={scene.highlight_layer} />}
    {scene.type === "diagram" && !scene.visualization && !scene.mode3d && scene.layout && <AnimatedFlowchart layout={scene.layout} />}
    {scene.type === "diagram" && !scene.visualization && !scene.mode3d && !scene.layout && scene.svg && <Img src={staticFile(scene.svg)} style={{ position: "absolute", left: 285, top: 190, width: 1350, height: 630 }} />}
    {scene.type === "code" && <CodeTypingAnimation code={scene.code ?? ""} language={scene.language} sceneFrames={scene.frames} />}
    {(scene.type === "terminal" || scene.type === "browser") && (scene.recording
      ? <OffthreadVideo src={staticFile(scene.recording)} muted style={{ position: "absolute", left: 90, top: 190, width: 1740, height: 630, objectFit: "contain", background: "#000" }} />
      : scene.type === "browser" ? <BrowserInteractionAnimation lines={scene.terminal_lines ?? []} sceneFrames={scene.frames} /> : <TerminalWindow lines={scene.terminal_lines ?? []} sceneFrames={scene.frames} />)}
  </>
);

export const SceneView: React.FC<{ scene: SceneProps; title: string; idx: number; total: number }> = ({ scene, title, idx, total }) => {
  const footer = `${title}  ·  ${idx}/${total}  ·  Educational content - authorized labs only`;
  const heading = scene.type === "instructor" ? title : scene.on_screen_text || title;
  return (
    <MotionProvider scene={scene}>
      <AbsoluteFill>
        <Frame title={heading} footer={footer}>
          <CameraRig camera={scene.motion?.camera ?? "none"} frames={scene.frames}><Body scene={scene} title={title} /></CameraRig>
        </Frame>
        {scene.audio ? <Audio src={staticFile(scene.audio)} /> : null}
      </AbsoluteFill>
    </MotionProvider>
  );
};

export const FadeWrap: React.FC<{ frames: number; children: React.ReactNode }> = ({ frames, children }) => {
  const f = useCurrentFrame();
  const o = interpolate(f, [0, 8, frames - 8, frames], [0, 1, 1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return <AbsoluteFill style={{ opacity: o }}>{children}</AbsoluteFill>;
};
