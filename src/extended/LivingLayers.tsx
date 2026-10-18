import React from 'react';
import {Img, staticFile} from 'remotion';

type LivingMode = 'bamboo' | 'spring' | 'interior' | 'landscape' | 'reflection';

const clamp = (value: number) => Math.max(0, Math.min(1, value));
const bambooAsset = staticFile('museum/bamboo-clean.png');
const butterflyAsset = staticFile('extended/butterfly.png');
type BambooPoint = readonly [number, number];
const bambooLeafRegions: readonly (readonly BambooPoint[])[] = [
  [[10, 45], [15, 39], [20, 41], [25, 49], [27, 59], [24, 68], [19, 66], [14, 58]],
  [[33, 32], [39, 25], [45, 29], [51, 38], [55, 49], [52, 61], [47, 64], [40, 57], [35, 47]],
  [[59, 16], [65, 10], [71, 12], [77, 21], [82, 35], [80, 49], [74, 57], [68, 51], [63, 38]],
];
const bambooClipPath = (region: readonly BambooPoint[]) =>
  `polygon(${region.map(([x, y]) => `${x}% ${y}%`).join(', ')})`;
const bambooMaskPolygons = bambooLeafRegions
  .map(region => {
    const points = region
      .map(([x, y]) => `${(x * 11.3).toFixed(2)},${(y * 7.53).toFixed(2)}`)
      .join(' ');
    return `<polygon points="${points}" fill="black"/>`;
  })
  .join('');
const bambooBaseMaskSvg = `<svg xmlns="http://www.w3.org/2000/svg" width="1130" height="753"><defs><mask id="bamboo-leaf-cutouts" maskUnits="userSpaceOnUse" x="0" y="0" width="1130" height="753" mask-type="luminance"><rect width="1130" height="753" fill="white"/>${bambooMaskPolygons}</mask></defs><rect width="1130" height="753" fill="white" mask="url(#bamboo-leaf-cutouts)"/></svg>`;
const bambooBaseMask = `url("data:image/svg+xml,${encodeURIComponent(bambooBaseMaskSvg)}")`;

const BambooBough: React.FC<{frame: number; intensity: number}> = ({frame, intensity}) => {
  const sway = Math.sin(frame * 0.027) * 1.05 + Math.sin(frame * 0.011 + 0.8) * 0.48;
  const lift = Math.sin(frame * 0.021 + 0.4) * 3.4;
  const motion = (phase: number, speed: number, amount: number) =>
    Math.sin(frame * speed + phase) * amount;
  const imageStyle: React.CSSProperties = {
    position: 'absolute',
    inset: 0,
    width: '100%',
    height: '100%',
    objectFit: 'contain',
  };

  return (
    <div
      aria-hidden="true"
      style={{
        position: 'absolute',
        left: 850,
        top: -160,
        width: 1130,
        height: 753,
        opacity: 0.86 * intensity,
        transformOrigin: '100% 9%',
        transform: `translateY(${lift}px) rotate(${sway}deg)`,
      }}
    >
      <Img
        src={bambooAsset}
        style={{
          ...imageStyle,
          maskImage: bambooBaseMask,
          WebkitMaskImage: bambooBaseMask,
          maskMode: 'alpha',
          maskRepeat: 'no-repeat',
          WebkitMaskRepeat: 'no-repeat',
        }}
      />
      <Img
        src={bambooAsset}
        style={{
          ...imageStyle,
          clipPath: bambooClipPath(bambooLeafRegions[0]),
          transformOrigin: '21% 46%',
          transform: `rotate(${motion(0.2, 0.043, 0.62)}deg)`,
        }}
      />
      <Img
        src={bambooAsset}
        style={{
          ...imageStyle,
          clipPath: bambooClipPath(bambooLeafRegions[1]),
          transformOrigin: '39% 35%',
          transform: `rotate(${motion(2.1, 0.038, 0.68)}deg)`,
        }}
      />
      <Img
        src={bambooAsset}
        style={{
          ...imageStyle,
          clipPath: bambooClipPath(bambooLeafRegions[2]),
          transformOrigin: '66% 21%',
          transform: `rotate(${motion(4.0, 0.034, 0.58)}deg)`,
        }}
      />
    </div>
  );
};

const SpringButterflies: React.FC<{frame: number; intensity: number}> = ({frame, intensity}) => {
  const butterflies = [
    {baseX: 1260, baseY: 332, driftX: 76, driftY: 31, phase: 0.4, speed: 0.014, width: 47},
    {baseX: 1550, baseY: 470, driftX: 62, driftY: 26, phase: 2.7, speed: 0.011, width: 39},
  ];

  return (
    <>
      {butterflies.map((butterfly, index) => {
        const x = butterfly.baseX + Math.sin(frame * butterfly.speed + butterfly.phase) * butterfly.driftX;
        const y = butterfly.baseY + Math.sin(frame * butterfly.speed * 1.8 + butterfly.phase + 1) * butterfly.driftY;
        const flutter = Math.sin(frame * 0.47 + butterfly.phase) * 38;
        const squash = 0.82 + (Math.sin(frame * 0.47 + butterfly.phase) + 1) * 0.09;

        return (
          <div
            key={index}
            aria-hidden="true"
            style={{
              position: 'absolute',
              left: x,
              top: y,
              width: butterfly.width,
              height: butterfly.width * 0.72,
              opacity: intensity,
              transform: `rotate(${Math.sin(frame * 0.025 + butterfly.phase) * 9}deg)`,
            }}
          >
            <Img
              src={butterflyAsset}
              style={{
                width: '100%',
                height: '100%',
                objectFit: 'contain',
                transformOrigin: '50% 50%',
                transform: `perspective(240px) rotateY(${flutter}deg) scaleX(${squash})`,
              }}
            />
          </div>
        );
      })}
      <SunMotes frame={frame} intensity={intensity} />
    </>
  );
};

const SunMotes: React.FC<{frame: number; intensity: number}> = ({frame, intensity}) => {
  const motes = [
    {x: 1110, y: 285, size: 3, phase: 0.1, speed: 0.22},
    {x: 1435, y: 240, size: 2, phase: 1.8, speed: 0.17},
    {x: 1705, y: 360, size: 3, phase: 3.3, speed: 0.2},
    {x: 1320, y: 545, size: 2, phase: 5.1, speed: 0.15},
  ];

  return (
    <>
      {motes.map((mote, index) => {
        const drift = (frame * mote.speed + mote.phase * 21) % 94;
        const pulse = 0.45 + (Math.sin(frame * 0.025 + mote.phase) + 1) * 0.2;

        return (
          <div
            key={index}
            aria-hidden="true"
            style={{
              position: 'absolute',
              left: mote.x + Math.sin(frame * 0.012 + mote.phase) * 14,
              top: mote.y - drift,
              width: mote.size,
              height: mote.size,
              borderRadius: '50%',
              background: '#fff1c7',
              boxShadow: '0 0 8px rgba(255, 237, 185, 0.62)',
              opacity: pulse * intensity,
            }}
          />
        );
      })}
    </>
  );
};

const InteriorShadows: React.FC<{frame: number; intensity: number}> = ({frame, intensity}) => {
  const driftX = Math.sin(frame * 0.009) * 22;
  const driftY = Math.sin(frame * 0.013 + 0.8) * 12;

  return (
    <div
      aria-hidden="true"
      style={{
        position: 'absolute',
        left: 900,
        top: 365,
        width: 1000,
        height: 490,
        borderRadius: '50%',
        opacity: 0.12 * intensity,
        filter: 'blur(20px)',
        mixBlendMode: 'multiply',
        transform: `translate(${driftX}px, ${driftY}px) rotate(-8deg)`,
        background:
          'radial-gradient(ellipse at 76% 42%, rgba(28, 47, 34, 0.68) 0%, rgba(28, 47, 34, 0.2) 23%, transparent 53%), radial-gradient(ellipse at 42% 68%, rgba(31, 51, 37, 0.46) 0%, rgba(31, 51, 37, 0.15) 27%, transparent 58%), linear-gradient(112deg, transparent 19%, rgba(30, 48, 35, 0.42) 21%, transparent 25%, transparent 37%, rgba(30, 48, 35, 0.35) 40%, transparent 44%, transparent 58%, rgba(30, 48, 35, 0.32) 61%, transparent 65%)',
      }}
    />
  );
};

const GroundHaze: React.FC<{frame: number; intensity: number}> = ({frame, intensity}) => {
  const drift = Math.sin(frame * 0.008) * 34;

  return (
    <>
      <div
        aria-hidden="true"
        style={{
          position: 'absolute',
          left: 180 + drift,
          top: 748,
          width: 930,
          height: 112,
          borderRadius: '50%',
          background: 'radial-gradient(ellipse, rgba(224, 233, 217, 0.5) 0%, rgba(224, 233, 217, 0.2) 38%, transparent 72%)',
          filter: 'blur(32px)',
          opacity: 0.14 * intensity,
        }}
      />
      <div
        aria-hidden="true"
        style={{
          position: 'absolute',
          left: 1030 - drift * 0.6,
          top: 786,
          width: 720,
          height: 78,
          borderRadius: '50%',
          background: 'radial-gradient(ellipse, rgba(231, 236, 219, 0.44) 0%, rgba(231, 236, 219, 0.15) 42%, transparent 74%)',
          filter: 'blur(28px)',
          opacity: 0.12 * intensity,
        }}
      />
    </>
  );
};

const WaterRipples: React.FC<{frame: number; intensity: number}> = ({frame, intensity}) => {
  const ripples = [0, 1, 2, 3];

  return (
    <svg
      aria-hidden="true"
      width={1920}
      height={1080}
      viewBox="0 0 1920 1080"
      style={{position: 'absolute', inset: 0, overflow: 'hidden'}}
    >
      {ripples.map(index => {
        const phase = (frame * 0.0045 + index * 0.25) % 1;
        const radiusX = 180 + phase * 520;
        const radiusY = radiusX * 0.22;

        return (
          <ellipse
            key={index}
            cx={850}
            cy={740}
            rx={radiusX}
            ry={radiusY}
            fill="none"
            stroke="#dce9dc"
            strokeWidth={1.6}
            opacity={0.14 * (1 - phase) * intensity}
          />
        );
      })}
    </svg>
  );
};

export const LivingLayers: React.FC<{
  frame: number;
  mode: LivingMode;
  intensity?: number;
}> = ({frame, mode, intensity = 1}) => {
  const level = clamp(intensity);

  return (
    <div
      aria-hidden="true"
      style={{
        position: 'absolute',
        inset: 0,
        width: 1920,
        height: 1080,
        overflow: 'hidden',
        pointerEvents: 'none',
      }}
    >
      {mode === 'bamboo' || mode === 'landscape' ? <BambooBough frame={frame} intensity={level} /> : null}
      {mode === 'spring' ? <SpringButterflies frame={frame} intensity={level} /> : null}
      {mode === 'interior' ? <InteriorShadows frame={frame} intensity={level} /> : null}
      {mode === 'landscape' ? <GroundHaze frame={frame} intensity={level} /> : null}
      {mode === 'reflection' ? <WaterRipples frame={frame} intensity={level} /> : null}
    </div>
  );
};
