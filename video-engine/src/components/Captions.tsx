import React from "react";
import { useCurrentFrame, useVideoConfig } from "remotion";
import { Cue } from "../utils/types";
import { T } from "../utils/theme";

export const Captions: React.FC<{ cues: Cue[]; shorts?: boolean }> = ({ cues, shorts }) => {
  const { fps } = useVideoConfig();
  const t = useCurrentFrame() / fps;
  const cue = cues.find((c) => t >= c.start && t < c.end);
  if (!cue) return null;
  return (
    <div style={{ position: "absolute", left: shorts ? 60 : 160, right: shorts ? 60 : 160, bottom: shorts ? 360 : 80, textAlign: "center" }}>
      <span style={{ background: "rgba(0,0,0,.7)", color: "white", fontFamily: T.sans, fontWeight: 700, fontSize: shorts ? 56 : 40,
        padding: "10px 24px", borderRadius: 16, lineHeight: 1.5, boxDecorationBreak: "clone", WebkitBoxDecorationBreak: "clone" }}>{cue.text}</span>
    </div>
  );
};
