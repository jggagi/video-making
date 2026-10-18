import React from 'react';
import {AbsoluteFill, useCurrentFrame} from 'remotion';
import {Droplet, PetriDish} from '../components/Visuals';
import {C, FONT} from '../lib/theme';
import {ease, mix, seeded} from '../lib/math';
import {
  openingTitleOpacity,
  PORTRAIT_FONT,
  PortraitHeading,
  PortraitOpeningTitle,
} from './PortraitElements';

const CIRCUITS = Array.from({length: 24}, (_, i) => {
  const y = 560 + i * 25;
  const bend = 180 + seeded(i + 1) * 680;
  const shift = (i % 2 === 0 ? -1 : 1) * (30 + seeded(i + 80) * 65);
  return {i, y, bend, shift};
});

export const Act1Portrait: React.FC = () => {
  const frame = useCurrentFrame();
  const openingAlpha = openingTitleOpacity(frame);
  const detach = ease(frame, 90, 340);
  const dropY = 760 + ease(frame, 0, 900) * 7;
  const zoom = mix(1, 25, ease(frame, 900, 1520));
  const labOpacity = 1 - ease(frame, 1100, 1450);
  const digital = ease(frame, 1030, 1370);
  const blink = ease(frame, 80, 650);

  return <AbsoluteFill style={{overflow: 'hidden'}}>
    <svg width="1080" height="1920" viewBox="0 0 1080 1920" style={{position: 'absolute', inset: 0}}>
      <defs>
        <radialGradient id="act1-portrait-lab-light">
          <stop stopColor={C.amber} stopOpacity="0.13" />
          <stop offset="1" stopColor={C.amber} stopOpacity="0" />
        </radialGradient>
        <linearGradient id="act1-portrait-pipette-metal" x1="0" x2="1">
          <stop stopColor="#181b21" />
          <stop offset=".3" stopColor="#8a8066" />
          <stop offset=".5" stopColor="#e6c88a" />
          <stop offset=".7" stopColor="#4b4536" />
          <stop offset="1" stopColor="#0c1018" />
        </linearGradient>
        <radialGradient id="act1-portrait-core-halo">
          <stop stopColor={C.cyan} stopOpacity="0.28" />
          <stop offset="1" stopColor={C.cyan} stopOpacity="0" />
        </radialGradient>
        <clipPath id="act1-portrait-scene-clip">
          <rect x="80" y="460" width="880" height="910" />
        </clipPath>
      </defs>

      <g clipPath="url(#act1-portrait-scene-clip)">
        <g opacity={labOpacity} transform={`translate(520 ${dropY}) scale(${zoom}) translate(-520 ${-dropY})`}>
          <ellipse cx="520" cy="895" rx="350" ry="440" fill="url(#act1-portrait-lab-light)" />
          <path d="M250 1226H790 M290 1232H750" stroke={C.amber} strokeOpacity="0.18" />

          <path d="M468 510H572V548L550 590V658H530V635H510V658H490V590L468 548Z" fill="url(#act1-portrait-pipette-metal)" stroke="#bc9c67" strokeWidth="2" />
          <path d="M494 523V574L520 628" fill="none" stroke="#ffe1a0" strokeOpacity="0.34" strokeWidth="4" />
          <path d={`M516 658Q514 ${682 + detach * 20} 520 ${dropY - 56}Q526 ${682 + detach * 20} 524 658`} fill={C.amber} opacity={1 - detach} />
          <Droplet x={520} y={dropY} id="act1-portrait" />
          <PetriDish x={520} y={1140} />

          <g stroke={C.amber} strokeOpacity="0.32" fill="none">
            <path d="M808 805H826 M817 805V1128 M808 1128H826" />
            {Array.from({length: 10}, (_, i) => <path key={i} d={`M817 ${805 + i * 32}h${i % 2 === 0 ? 13 : 7}`} />)}
          </g>
          <text x="836" y="972" fill={C.amber} fontFamily={FONT} fontSize="16" opacity="0.78">120 mm</text>
        </g>

        <g opacity={digital}>
          <ellipse cx="520" cy="940" rx="440" ry="430" fill="url(#act1-portrait-core-halo)" />
          {CIRCUITS.map(({i, y, bend, shift}) => {
            const t = ((frame * (9 + i % 5) + seeded(i + 21) * 2200) % 2200) / 2200;
            const x = 80 + t * 880;
            const pulseY = x < bend ? y : x > bend + 50 ? y + shift : y + shift * (x - bend) / 50;
            return <g key={i}>
              <path d={`M80 ${y}H${bend}L${bend + 50} ${y + shift}H960`} fill="none" stroke={C.cyan} strokeOpacity={i % 4 === 0 ? 0.38 : 0.12} strokeWidth={i % 4 === 0 ? 2 : 1} />
              <circle cx={bend} cy={y} r="3" fill={C.cyan} opacity="0.58" />
              <path d={`M${x - 30} ${pulseY}h30`} stroke={C.cyan} strokeWidth="6" opacity="0.16" />
              <circle cx={x} cy={pulseY} r={i % 3 === 0 ? 3.2 : 2.2} fill={C.white} />
            </g>;
          })}
          {Array.from({length: 10}, (_, i) => <path key={`grid-${i}`} d={`M${160 + i * 80} 500V1340`} stroke={C.cyan} strokeOpacity="0.045" />)}
          <circle cx="520" cy="940" r={142 + Math.sin(frame / 30) * 5} fill={C.bg} stroke={C.cyan} strokeWidth="2" />
          <circle cx="520" cy="940" r="116" fill="none" stroke={C.cyan} strokeOpacity="0.36" strokeDasharray="5 11" transform={`rotate(${frame * 0.6} 520 940)`} />
          <circle cx="520" cy="940" r="88" fill="none" stroke={C.white} strokeOpacity="0.08" />
          <text x="520" y="932" textAnchor="middle" fill={C.white} fontFamily={FONT} fontSize="42">10¹⁰</text>
          <text x="520" y="970" textAnchor="middle" fill={C.cyan} fontFamily={FONT} fontSize="12" letterSpacing="2.4">COGNITIVE STEPS</text>
        </g>

        <text x="520" y="1300" textAnchor="middle" fill={C.white} fontFamily={PORTRAIT_FONT} fontSize="32" letterSpacing="1.5" opacity="0.82">
          水滴尚未落下 / 思考已进入另一种尺度
        </text>

        <g opacity={labOpacity * blink * 0.65} fill={C.bg} stroke="rgba(6,182,212,0.16)" strokeWidth="1">
          <path d={`M80 460H960V${460 + 370 * blink}Q520 ${460 + 250 * blink} 80 ${460 + 370 * blink}Z`} />
          <path d={`M80 1370H960V${1370 - 370 * blink}Q520 ${1370 - 250 * blink} 80 ${1370 - 370 * blink}Z`} />
        </g>
      </g>

      <rect x="80" y="460" width="880" height="910" fill={C.bg} opacity={openingAlpha * 0.8} />
    </svg>

    <PortraitHeading
      index="01"
      title="一瞬，两种时间"
      kicker="SPEED / TWO CLOCKS"
      color={C.amber}
      opacity={1 - openingAlpha}
    />
    <PortraitOpeningTitle frame={frame} />
  </AbsoluteFill>;
};
