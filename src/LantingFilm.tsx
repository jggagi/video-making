import React from 'react';
import {Audio, Img, staticFile, useCurrentFrame} from 'remotion';
import timelineJson from './timeline.json';
import type {Shot, Timeline} from './types';

const timeline = timelineJson as Timeline;
const DISSOLVE_FRAMES = 22;
const DISSOLVE_HALF = DISSOLVE_FRAMES / 2;
const MATTE_TOP = 62;
const MATTE_BOTTOM = 114;
const SCENE_HEIGHT = 1080 - MATTE_TOP - MATTE_BOTTOM;

const easeInOut = (value: number) => {
  const t = Math.max(0, Math.min(1, value));
  return t * t * (3 - 2 * t);
};

const opacityForShot = (frame: number, shot: Shot, index: number) => {
  const start = shot.from;
  const end = shot.from + shot.duration;
  const isFirst = index === 0;
  const isLast = index === timeline.shots.length - 1;

  const fadeIn = isFirst
    ? easeInOut((frame - start) / 18)
    : easeInOut((frame - (start - DISSOLVE_HALF)) / DISSOLVE_FRAMES);
  const fadeOut = isLast
    ? 1 - easeInOut((frame - (end - 20)) / 19)
    : 1 - easeInOut((frame - (end - DISSOLVE_HALF)) / DISSOLVE_FRAMES);

  return Math.max(0, Math.min(1, fadeIn * fadeOut));
};

const moodImageStyle: Record<Shot['mood'], React.CSSProperties> = {
  joy: {filter: 'brightness(1.015) saturate(0.94) sepia(0.035)'},
  turn: {filter: 'brightness(0.99) saturate(0.78) sepia(0.025)'},
  reflect: {filter: 'brightness(0.975) saturate(0.68) sepia(0.018)'},
};

const cameraOrigin = (index: number) => {
  const origins = ['42% 45%', '58% 50%', '48% 42%', '54% 57%', '38% 52%'];
  return origins[index % origins.length];
};

const SceneImage: React.FC<{shot: Shot; index: number; frame: number}> = ({
  shot,
  index,
  frame,
}) => {
  const alpha = opacityForShot(frame, shot, index);
  const first = index === 0;
  const last = index === timeline.shots.length - 1;
  const start = first ? shot.from : shot.from - DISSOLVE_HALF;
  const end = last ? shot.from + shot.duration : shot.from + shot.duration + DISSOLVE_HALF;

  if (frame < start || frame > end || alpha < 0.001) {
    return null;
  }

  const localFrame = Math.max(0, Math.min(shot.duration - 1, frame - shot.from));
  const progress = localFrame / Math.max(1, shot.duration - 1);
  const direction = index % 2 === 0 ? 1 : -1;
  const panX = direction * (progress - 0.5) * 24;
  const panY = ((index % 3) - 1) * (progress - 0.5) * 10;
  const zoom = 1.045 + progress * 0.035;

  return (
    <div
      style={{
        position: 'absolute',
        inset: `${MATTE_TOP}px 0 ${MATTE_BOTTOM}px`,
        overflow: 'hidden',
        opacity: alpha,
        zIndex: index + 1,
      }}
    >
      <Img
        src={staticFile(`images/${shot.image}.png`)}
        style={{
          position: 'absolute',
          width: '100%',
          height: '100%',
          objectFit: 'cover',
          objectPosition: cameraOrigin(index),
          transform: `scale(${zoom}) translate3d(${panX}px, ${panY}px, 0)`,
          ...moodImageStyle[shot.mood],
        }}
      />
      <div
        style={{
          position: 'absolute',
          inset: 0,
          background:
            shot.mood === 'joy'
              ? 'linear-gradient(115deg, rgba(202, 166, 104, 0.06), transparent 54%), radial-gradient(ellipse at 50% 44%, transparent 52%, rgba(18, 26, 24, 0.12) 100%)'
              : shot.mood === 'turn'
                ? 'linear-gradient(115deg, rgba(83, 99, 93, 0.045), transparent 55%), radial-gradient(ellipse at 50% 44%, transparent 48%, rgba(18, 26, 26, 0.15) 100%)'
                : 'linear-gradient(115deg, rgba(104, 121, 119, 0.055), transparent 58%), radial-gradient(ellipse at 50% 44%, transparent 45%, rgba(17, 25, 27, 0.18) 100%)',
        }}
      />
    </div>
  );
};

const Atmosphere: React.FC<{frame: number; image: Shot['image']}> = ({frame, image}) => {
  if (image !== 'landscape' && image !== 'gathering') {
    return null;
  }

  const flecks = [
    {x: 15, y: 27, phase: 0.2},
    {x: 28, y: 61, phase: 1.7},
    {x: 42, y: 35, phase: 2.8},
    {x: 59, y: 70, phase: 4.1},
    {x: 73, y: 30, phase: 5.2},
    {x: 86, y: 55, phase: 6.3},
  ];

  return (
    <div style={{position: 'absolute', inset: 0, overflow: 'hidden'}}>
      {flecks.map((fleck, index) => {
        const wave = Math.sin(frame * 0.018 + fleck.phase);
        const drift = Math.sin(frame * 0.008 + fleck.phase) * 7;
        return (
          <span
            key={index}
            style={{
              position: 'absolute',
              left: `${fleck.x}%`,
              top: `${fleck.y}%`,
              width: index % 2 === 0 ? 2 : 2.5,
              height: index % 2 === 0 ? 2 : 2.5,
              borderRadius: '50%',
              backgroundColor: 'rgba(248, 240, 211, 0.92)',
              opacity: 0.055 + (wave + 1) * 0.018,
              filter: 'blur(0.65px)',
              transform: `translate3d(${drift}px, ${Math.cos(frame * 0.009 + fleck.phase) * 5}px, 0)`,
            }}
          />
        );
      })}
    </div>
  );
};

const WaterLight: React.FC<{frame: number; image: Shot['image']}> = ({frame, image}) => {
  if (image !== 'stream') {
    return null;
  }

  const shimmer = Math.sin(frame * 0.035) * 8;
  const breathing = 0.62 + (Math.sin(frame * 0.027 + 1.2) + 1) * 0.1;

  return (
    <div
      style={{
        position: 'absolute',
        left: '-8%',
        right: '-8%',
        top: '49%',
        bottom: 0,
        opacity: breathing,
        transform: `translate3d(${shimmer}px, 0, 0)`,
        background:
          'linear-gradient(105deg, transparent 12%, rgba(244, 241, 219, 0.045) 42%, rgba(244, 241, 219, 0.012) 51%, transparent 80%)',
        mixBlendMode: 'screen',
      }}
    />
  );
};

const SceneAtmosphere: React.FC<{shot: Shot; localFrame: number}> = ({shot, localFrame}) => (
  <div
    style={{
      position: 'absolute',
      inset: `${MATTE_TOP}px 0 ${MATTE_BOTTOM}px`,
      overflow: 'hidden',
    }}
  >
    <div
      style={{
        position: 'absolute',
        inset: 0,
        background:
          'linear-gradient(90deg, rgba(12, 19, 18, 0.30) 0%, rgba(12, 19, 18, 0.12) 22%, transparent 48%)',
      }}
    />
    <Atmosphere frame={localFrame} image={shot.image} />
    <WaterLight frame={localFrame} image={shot.image} />
  </div>
);

const HeroColumns: React.FC<{shot: Shot; localFrame: number}> = ({shot, localFrame}) => {
  if (shot.hero.length === 0) {
    return null;
  }

  const fadeIn = easeInOut((localFrame - 16) / 14);
  const fadeOut = 1 - easeInOut((localFrame - (shot.duration - 39)) / 15);
  const alpha = fadeIn * fadeOut;
  if (alpha <= 0) {
    return null;
  }

  return (
    <div
      style={{
        position: 'absolute',
        left: 110,
        top: 156,
        height: 620,
        display: 'flex',
        flexDirection: 'row-reverse',
        alignItems: 'flex-start',
        gap: 27,
        opacity: alpha,
        color: '#f1ead8',
        fontFamily: 'Songti SC, STSong, SimSun, serif',
        fontSize: 69,
        fontWeight: 400,
        lineHeight: 1.13,
        letterSpacing: '0.11em',
        textShadow: '0 2px 18px rgba(15, 23, 21, 0.30)',
        pointerEvents: 'none',
      }}
    >
      {shot.hero.map((phrase, index) => {
        const reveal = easeInOut((localFrame - (21 + index * 4)) / 21);
        return (
          <span
            key={`${shot.id}-${phrase}`}
            style={{
              writingMode: 'vertical-rl',
              textOrientation: 'upright',
              display: 'block',
              clipPath: `inset(0 0 ${(1 - reveal) * 100}% 0)`,
            }}
          >
            {phrase}
          </span>
        );
      })}
    </div>
  );
};

const CueCaption: React.FC<{shot: Shot; localFrame: number}> = ({shot, localFrame}) => {
  const cue = shot.cues.find(
    (item) => localFrame >= item.from && localFrame < item.from + item.duration,
  );
  if (!cue || shot.id === 'judgment') {
    return null;
  }

  const cueFrame = localFrame - cue.from;
  const fadeIn = easeInOut(cueFrame / 7);
  const fadeOut = easeInOut((cue.duration - cueFrame) / 7);

  return (
    <div
      style={{
        position: 'absolute',
        left: 125,
        right: 125,
        bottom: 17,
        maxWidth: 1670,
        margin: '0 auto',
        textAlign: 'center',
        color: '#f0eadb',
        fontFamily: 'Songti SC, STSong, SimSun, serif',
        fontSize: 36,
        fontWeight: 400,
        lineHeight: 1.34,
        letterSpacing: '0.035em',
        textShadow: '0 1px 12px rgba(0, 0, 0, 0.48)',
        opacity: fadeIn * fadeOut,
        pointerEvents: 'none',
      }}
    >
      {cue.text}
    </div>
  );
};

const JudgmentStatement: React.FC<{shot: Shot; localFrame: number}> = ({shot, localFrame}) => {
  if (shot.id !== 'judgment') {
    return null;
  }

  const cue = shot.cues[0];
  const visible = localFrame >= cue.from && localFrame < cue.from + cue.duration;
  if (!visible) {
    return null;
  }

  const cueFrame = localFrame - cue.from;
  const alpha = easeInOut(cueFrame / 8) * easeInOut((cue.duration - cueFrame) / 8);

  return (
    <div
      style={{
        position: 'absolute',
        left: 210,
        right: 210,
        top: 346,
        textAlign: 'center',
        color: '#f1ead8',
        fontFamily: 'Songti SC, STSong, SimSun, serif',
        fontSize: 51,
        fontWeight: 400,
        lineHeight: 1.74,
        letterSpacing: '0.055em',
        whiteSpace: 'pre-line',
        textShadow: '0 2px 22px rgba(11, 18, 19, 0.60)',
        opacity: alpha,
        pointerEvents: 'none',
      }}
    >
      {'固知一死生为虚诞，\n齐彭殇为妄作。'}
    </div>
  );
};

const ChapterLabel: React.FC<{shot: Shot; localFrame: number}> = ({shot, localFrame}) => {
  if (!shot.chapter) {
    return null;
  }

  const fadeIn = easeInOut((localFrame - 6) / 12);
  const fadeOut = 1 - easeInOut((localFrame - (shot.duration - 29)) / 12);

  return (
    <div
      style={{
        position: 'absolute',
        top: 18,
        left: 0,
        right: 0,
        color: 'rgba(241, 234, 216, 0.74)',
        fontFamily: 'Songti SC, STSong, SimSun, serif',
        fontSize: 19,
        letterSpacing: '0.28em',
        textAlign: 'center',
        opacity: fadeIn * fadeOut,
        pointerEvents: 'none',
      }}
    >
      {shot.chapter}
    </div>
  );
};

const OpeningTitle: React.FC<{shot: Shot; localFrame: number}> = ({shot, localFrame}) => {
  if (shot.kind !== 'title') {
    return null;
  }

  const fadeIn = easeInOut((localFrame - 14) / 15);
  const fadeOut = 1 - easeInOut((localFrame - 84) / 24);
  const alpha = fadeIn * fadeOut;

  return (
    <div
      style={{
        position: 'absolute',
        inset: 0,
        opacity: alpha,
        color: '#f3eddd',
        textAlign: 'center',
        fontFamily: 'Songti SC, STSong, SimSun, serif',
        textShadow: '0 3px 28px rgba(10, 18, 17, 0.52)',
        pointerEvents: 'none',
      }}
    >
      <div
        style={{
          position: 'absolute',
          inset: '62px 0 114px',
          background:
            'radial-gradient(ellipse at 50% 43%, rgba(16, 24, 22, 0.26) 0%, rgba(16, 24, 22, 0.12) 37%, transparent 72%)',
        }}
      />
      <div style={{position: 'absolute', top: 330, left: 0, right: 0}}>
        <div
          style={{
            fontSize: 112,
            lineHeight: 1.2,
            fontWeight: 400,
            letterSpacing: '0.22em',
            paddingLeft: '0.22em',
          }}
        >
          兰亭集序
        </div>
        <div
          style={{
            marginTop: 29,
            fontSize: 27,
            lineHeight: 1.5,
            letterSpacing: '0.28em',
            paddingLeft: '0.28em',
            color: 'rgba(243, 237, 221, 0.88)',
          }}
        >
          王羲之 · 东晋
        </div>
        <div
          style={{
            marginTop: 56,
            fontSize: 20,
            letterSpacing: '0.45em',
            paddingLeft: '0.45em',
            color: 'rgba(243, 237, 221, 0.78)',
          }}
        >
          暮春之初
        </div>
      </div>
    </div>
  );
};

const ClosingTitle: React.FC<{shot: Shot; localFrame: number}> = ({shot, localFrame}) => {
  if (shot.kind !== 'end') {
    return null;
  }

  const fadeIn = easeInOut((localFrame - 14) / 17);
  const fadeOut = 1 - easeInOut((localFrame - 84) / 21);
  const alpha = fadeIn * fadeOut;

  return (
    <div
      style={{
        position: 'absolute',
        inset: 0,
        opacity: alpha,
        color: '#f3eddd',
        textAlign: 'center',
        fontFamily: 'Songti SC, STSong, SimSun, serif',
        textShadow: '0 3px 28px rgba(10, 18, 17, 0.54)',
        pointerEvents: 'none',
      }}
    >
      <div
        style={{
          position: 'absolute',
          inset: '62px 0 114px',
          background:
            'radial-gradient(ellipse at 50% 43%, rgba(16, 24, 22, 0.28) 0%, rgba(16, 24, 22, 0.12) 39%, transparent 74%)',
        }}
      />
      <div style={{position: 'absolute', top: 323, left: 0, right: 0}}>
        <div
          style={{
            fontSize: 100,
            lineHeight: 1.18,
            fontWeight: 400,
            letterSpacing: '0.22em',
            paddingLeft: '0.22em',
          }}
        >
          兰亭集序
        </div>
        <div
          style={{
            marginTop: 35,
            fontSize: 39,
            lineHeight: 1.5,
            letterSpacing: '0.045em',
            color: 'rgba(243, 237, 221, 0.94)',
          }}
        >
          后之览者，亦将有感于斯文。
        </div>
        <div
          style={{
            marginTop: 66,
            fontSize: 18,
            letterSpacing: '0.2em',
            paddingLeft: '0.2em',
            color: 'rgba(243, 237, 221, 0.70)',
          }}
        >
          原文 · 王羲之 | 水墨意境短片
        </div>
      </div>
    </div>
  );
};

const ShotOverlay: React.FC<{shot: Shot; localFrame: number}> = ({shot, localFrame}) => (
  <>
    <SceneAtmosphere shot={shot} localFrame={localFrame} />
    <ChapterLabel shot={shot} localFrame={localFrame} />
    <HeroColumns shot={shot} localFrame={localFrame} />
    <CueCaption shot={shot} localFrame={localFrame} />
    <JudgmentStatement shot={shot} localFrame={localFrame} />
    <OpeningTitle shot={shot} localFrame={localFrame} />
    <ClosingTitle shot={shot} localFrame={localFrame} />
  </>
);

export const LantingFilm: React.FC = () => {
  const frame = useCurrentFrame();
  const activeShot = timeline.shots.find(
    (shot) => frame >= shot.from && frame < shot.from + shot.duration,
  );
  const activeLocalFrame = activeShot ? frame - activeShot.from : 0;

  return (
    <div
      style={{
        position: 'relative',
        width: 1920,
        height: 1080,
        overflow: 'hidden',
        backgroundColor: '#111917',
        color: '#f1ead8',
        fontFamily: 'Songti SC, STSong, SimSun, serif',
      }}
    >
      {timeline.shots.map((shot, index) => (
        <SceneImage key={shot.id} shot={shot} index={index} frame={frame} />
      ))}

      <div
        style={{
          position: 'absolute',
          inset: 0,
          zIndex: 100,
          background:
            'linear-gradient(180deg, #111715 0px, #111715 62px, transparent 62px, transparent 963px, rgba(17, 22, 21, 0.94) 963px, #111715 100%), linear-gradient(180deg, transparent 72%, rgba(12, 17, 16, 0.22) 85%, rgba(12, 17, 16, 0.82) 93%, #111715 100%)',
          pointerEvents: 'none',
        }}
      />

      {activeShot && (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            zIndex: 120,
            overflow: 'hidden',
          }}
        >
          <ShotOverlay shot={activeShot} localFrame={activeLocalFrame} />
        </div>
      )}

      <Audio src={staticFile('audio/soundtrack.wav')} />
    </div>
  );
};
