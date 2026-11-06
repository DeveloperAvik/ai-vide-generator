import React from "react";
import { AbsoluteFill, Audio, staticFile } from "remotion";
import { TransitionSeries, linearTiming } from "@remotion/transitions";
import { fade } from "@remotion/transitions/fade";
import { slide } from "@remotion/transitions/slide";
import { wipe } from "@remotion/transitions/wipe";
import { Captions } from "../components/Captions";
import { SceneView } from "../scenes/SceneView";
import { LessonProps } from "../utils/types";
import { loadFonts } from "../utils/fonts";

loadFonts();

const pres = (t: string): any => (t === "slide" ? slide() : t === "wipe" ? wipe() : fade());

export const totalFrames = (p: LessonProps) =>
  Math.max(1, p.scenes.reduce((a, s) => a + s.frames, 0) - Math.max(0, p.scenes.length - 1) * p.transitionFrames);

export const Lesson: React.FC<LessonProps> = (p) => (
  <AbsoluteFill style={{ background: "#0a0f1c" }}>
    <TransitionSeries>
      {p.scenes.flatMap((s, i) => {
        const items = [
          <TransitionSeries.Sequence key={s.scene_id} durationInFrames={s.frames}>
            <SceneView scene={s} title={p.title} idx={i + 1} total={p.scenes.length} />
          </TransitionSeries.Sequence>,
        ];
        if (i < p.scenes.length - 1)
          items.push(<TransitionSeries.Transition key={`t${i}`} presentation={pres(s.transition)} timing={linearTiming({ durationInFrames: p.transitionFrames })} />);
        return items;
      })}
    </TransitionSeries>
    {p.music ? <Audio src={staticFile(p.music)} volume={0.08} loop /> : null}
    <Captions cues={p.cues} shorts={p.shorts} />
  </AbsoluteFill>
);
