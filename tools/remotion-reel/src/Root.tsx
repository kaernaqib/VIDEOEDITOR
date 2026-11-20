import React from "react";
import { Composition } from "remotion";
import { PosterReel, PosterReelProps } from "./PosterReel";

const FPS = 30;

// placeholder props for the Studio; real reels pass --props=PUBLIC_DIR/props.json (job_to_props.py)
const defaults: PosterReelProps = {
  poster: null,
  posterPosY: 50,
  audio: null,
  headline: ["DAY 1 DI", "MELBOURNE"],
  accentLine: 0,
  durationFrames: 6 * FPS,
  clips: [],
  sfx: [],
  subs: [
    { a: 0.3, b: 1.4, w: ["Remotion", "Dah"], hi: 0 },
    { a: 1.4, b: 2.8, w: ["Siap", "Setup"], hi: 0 },
  ],
};

export const RemotionRoot: React.FC = () => (
  <Composition
    id="PosterReel"
    component={PosterReel}
    width={1080}
    height={1920}
    fps={FPS}
    durationInFrames={defaults.durationFrames}
    defaultProps={defaults}
    calculateMetadata={({ props }) => ({ durationInFrames: Math.max(1, props.durationFrames) })}
  />
);
