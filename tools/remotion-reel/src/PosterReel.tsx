import React from "react";
import {
  AbsoluteFill,
  Audio,
  Img,
  OffthreadVideo,
  Sequence,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { fitText } from "@remotion/layout-utils";

// Poster-frame layout (approved 19 Nov 2026), see CLAUDE.md:
// poster 0..610 fading to black between y 300..470, headline at y 375/482,
// landscape video in a 1080x806 band at y 608..1414, 1-3 word subtitles at y 1466.
// Props come from job_to_props.py (same job.json the ffmpeg renderer uses).

export type Clip = { src: string; startFromSec: number; from: number; frames: number; posX: number };
export type Sfx = { src: string; t: number; vol: number; dur: number };
export type Sub = { a: number; b: number; w: string[]; hi: number };

export type PosterReelProps = {
  poster: string | null;
  posterPosY: number;
  audio: string | null;
  headline: string[];
  accentLine: number;
  durationFrames: number;
  clips: Clip[];
  sfx: Sfx[];
  subs: Sub[];
};

const ACCENT = "#CA00FF";
const SUB_ACCENT = "#A773F8";
const BAND_Y = 608;
const BAND_H = 806;
const HEAD_Y = [375, 482];
const HEAD_FONT = "Impact";

const src = (s: string) => (/^(https?:|file:)/.test(s) ? s : staticFile(s));

const Headline: React.FC<{ lines: string[]; accent: number }> = ({ lines, accent }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return (
    <>
      {lines.map((raw, i) => {
        const text = raw.toUpperCase();
        const { fontSize } = fitText({ text, withinWidth: 1080 - 110, fontFamily: HEAD_FONT });
        const s = spring({ frame: frame - i * 4, fps, config: { damping: 13, mass: 0.7 } });
        const y = i < HEAD_Y.length ? HEAD_Y[i] : HEAD_Y[HEAD_Y.length - 1] + (i - 1) * 107;
        return (
          <div
            key={i}
            style={{
              position: "absolute",
              top: y,
              left: 0,
              width: 1080,
              textAlign: "center",
              fontFamily: HEAD_FONT,
              fontSize: Math.min(112, fontSize),
              lineHeight: 1,
              color: i === accent ? ACCENT : "white",
              textShadow: "0 4px 16px rgba(0,0,0,0.85)",
              transform: `translateY(-50%) scale(${interpolate(s, [0, 1], [0.7, 1])})`,
              opacity: Math.min(1, s * 1.5),
            }}
          >
            {text}
          </div>
        );
      })}
    </>
  );
};

const Subtitle: React.FC<{ subs: Sub[] }> = ({ subs }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const c = subs.find((s) => t >= s.a && t < s.b);
  if (!c) return null;
  const local = frame - Math.round(c.a * fps);
  const pop = interpolate(local, [0, 4], [0.88, 1], { extrapolateRight: "clamp" });
  const fade = interpolate(local, [0, 2], [0, 1], { extrapolateRight: "clamp" });
  return (
    <div
      style={{
        position: "absolute",
        top: 1466,
        left: 60,
        width: 960,
        textAlign: "center",
        fontFamily: "'Segoe UI', sans-serif",
        fontWeight: 700,
        fontSize: 66,
        lineHeight: 1.1,
        color: "white",
        transform: `translateY(-50%) scale(${pop})`,
        opacity: fade,
        textShadow: "0 0 10px rgba(167,115,248,0.9), 0 0 22px rgba(167,115,248,0.55), 0 2px 4px rgba(0,0,0,0.9)",
      }}
    >
      {c.w.map((w, i) => (
        <span key={i} style={{ color: i === c.hi ? SUB_ACCENT : "white" }}>
          {w}
          {i < c.w.length - 1 ? " " : ""}
        </span>
      ))}
    </div>
  );
};

export const PosterReel: React.FC<PosterReelProps> = ({
  poster,
  posterPosY,
  audio,
  headline,
  accentLine,
  clips,
  sfx,
  subs,
}) => {
  const { fps } = useVideoConfig();
  return (
    <AbsoluteFill style={{ backgroundColor: "black" }}>
      {/* poster, fading into black between y 300 and 470 */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          width: 1080,
          height: 610,
          overflow: "hidden",
          WebkitMaskImage: "linear-gradient(to bottom, black 300px, transparent 470px)",
          maskImage: "linear-gradient(to bottom, black 300px, transparent 470px)",
        }}
      >
        {poster ? (
          <Img
            src={src(poster)}
            style={{ width: "100%", height: "100%", objectFit: "cover", objectPosition: `50% ${posterPosY}%` }}
          />
        ) : (
          <div style={{ width: "100%", height: "100%", background: "linear-gradient(135deg,#ff7a18,#af002d 60%,#319197)" }} />
        )}
      </div>

      <Headline lines={headline} accent={accentLine} />

      {/* video band */}
      <div style={{ position: "absolute", top: BAND_Y, left: 0, width: 1080, height: BAND_H, overflow: "hidden" }}>
        {clips.map((c, i) => (
          <Sequence key={i} from={c.from} durationInFrames={c.frames} layout="none">
            <OffthreadVideo
              src={src(c.src)}
              startFrom={Math.round(c.startFromSec * fps)}
              muted
              style={{
                width: 1080,
                height: BAND_H,
                objectFit: "cover",
                objectPosition: `${c.posX}% 50%`,
                filter: "contrast(1.06) saturate(1.08)",
              }}
            />
          </Sequence>
        ))}
      </div>

      <Subtitle subs={subs} />

      {audio && <Audio src={src(audio)} />}
      {sfx.map((s, i) => (
        <Sequence key={i} from={Math.round(s.t * fps)} durationInFrames={Math.max(1, Math.round(s.dur * fps))} layout="none">
          <Audio src={src(s.src)} volume={s.vol} />
        </Sequence>
      ))}
    </AbsoluteFill>
  );
};
