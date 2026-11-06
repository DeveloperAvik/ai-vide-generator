import React from "react";
import { Composition } from "remotion";
import { Lesson, totalFrames } from "./compositions/Lesson";
import { GALLERY_SECTION, Gallery } from "./compositions/Gallery";
import { LessonProps, defaultProps } from "./utils/types";

export const Root: React.FC = () => (
  <>
    <Composition id="Lesson" component={Lesson as React.FC<any>} width={1920} height={1080} fps={30} durationInFrames={30}
      defaultProps={defaultProps}
      calculateMetadata={({ props }) => ({ durationInFrames: totalFrames(props as unknown as LessonProps), fps: (props as unknown as LessonProps).fps })} />
    <Composition id="Short" component={Lesson as React.FC<any>} width={1080} height={1920} fps={30} durationInFrames={30}
      defaultProps={{ ...defaultProps, shorts: true }}
      calculateMetadata={({ props }) => ({ durationInFrames: totalFrames(props as unknown as LessonProps), fps: (props as unknown as LessonProps).fps })} />
    <Composition id="Gallery" component={Gallery} width={1920} height={1080} fps={30} durationInFrames={GALLERY_SECTION * 5} />
  </>
);
