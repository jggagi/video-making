import React from 'react';
import {useCurrentFrame} from 'remotion';
import timeline from '../../timeline.json';
import {C, CN, FONT, GLOW, SCENE_HEIGHT, SCENE_WIDTH} from '../lib/theme';
import {clamp, fade, seeded, smooth, mix} from '../lib/math';
import {ActLabel} from './Visuals';

const W = SCENE_WIDTH;
const H = SCENE_HEIGHT;

const VARIABLES = [
  {cn: '利率', en: 'IR'},
  {cn: '通胀', en: 'CPI'},
  {cn: '汇率', en: 'FX'},
  {cn: '晶圆良率', en: 'YIELD'},
  {cn: '电网负荷', en: 'GRID'},
  {cn: '航运指数', en: 'BDI'},
  {cn: '原油库存', en: 'OIL'},
  {cn: '气候异常', en: 'ENSO'},
  {cn: '信贷违约', en: 'CDS'},
  {cn: '地缘摩擦', en: 'GEO'},
];

type NodePoint = {x: number; y: number; angle: number; radius: number};

const getNodePoint = (index: number, frame: number, count: number): NodePoint => {
  const angle = -Math.PI / 2 + (index / 9) * Math.PI * 2 + (seeded(index + 7) - 0.5) * 0.055;
  const strain = count > 7 ? (count - 6) * 3 : 0;
  const jitterX = Math.sin(frame * 1.8 + index) * strain;
  const jitterY = Math.cos(frame * 1.8 + index) * strain;
  const baseX = 1174 + Math.cos(angle) * 290;
  const baseY = 565 + Math.sin(angle) * 198;

  if (index === 9) {
    const impactFrame = Math.max(0, frame - 1200);
    const hit = Math.exp(-impactFrame * 0.055) * Math.cos(impactFrame * 0.31);
    return {x: 1174 + hit * 22, y: 565 + hit * 15, angle, radius: 31 + Math.max(0, hit) * 8};
  }

  const forgotten = frame >= 1200 && index < 3;
  if (forgotten) {
    const fallFrames = frame - 1200;
    const gravity = 0.45;
    return {
      x: baseX + jitterX + Math.sin(fallFrames * 0.12 + index) * Math.min(36, fallFrames * 0.22),
      y: baseY + jitterY + 0.5 * gravity * fallFrames * fallFrames,
      angle,
      radius: 24,
    };
  }

  return {x: baseX + jitterX, y: baseY + jitterY, angle, radius: 24};
};

export const Act1BiologicalOverload: React.FC = () => {
  const frame = useCurrentFrame();
  const overloadFrame = timeline.overloadFrame;
  const snap = frame >= overloadFrame;
  const titleOpacity = fade(frame, timeline.silenceUntilFrame, 90);
  const networkOpacity = 1 - smooth((frame - 1770) / 110);
  const chunkCount = snap
    ? 10
    : (timeline.chunkFrames as number[]).filter((chunkFrame) => frame >= chunkFrame).length;
  const edgeCount = (chunkCount * (chunkCount - 1)) / 2;
  const snapFlash = snap ? 1 - smooth((frame - overloadFrame) / 18) : 0;
  const fragmentOpacity = snap ? 1 - smooth((frame - overloadFrame - 18) / 390) : 0;
  const letterSpacing = mix(14, 32, clamp((frame - 1800) / 900));
  const nodes = Array.from({length: chunkCount}, (_, index) => getNodePoint(index, frame, chunkCount));

  return <div style={{position: 'absolute', inset: 0, overflow: 'hidden', pointerEvents: 'none'}}>
    <div style={{position: 'absolute', inset: 0, opacity: networkOpacity}}>
      <ActLabel number="ACT 01" title="生物记忆的容量上限" kicker="WORKING MEMORY" color={C.amber}/>
      <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} style={{position: 'absolute', inset: 0}}>
        <defs>
          <radialGradient id="act1-node-glow">
            <stop offset="0" stopColor={C.amber} stopOpacity="0.92"/>
            <stop offset="0.4" stopColor={C.amber} stopOpacity="0.23"/>
            <stop offset="1" stopColor={C.amber} stopOpacity="0"/>
          </radialGradient>
          <radialGradient id="act1-impact-glow">
            <stop offset="0" stopColor={C.red} stopOpacity="0.55"/>
            <stop offset="1" stopColor={C.red} stopOpacity="0"/>
          </radialGradient>
        </defs>

        <circle cx="1174" cy="565" r="230" fill="none" stroke={C.amber} strokeOpacity="0.08" strokeDasharray="2 12"/>
        <circle cx="1174" cy="565" r="265" fill="none" stroke={snap ? C.red : C.amber} strokeOpacity={0.13 + snapFlash * 0.35} strokeDasharray="1 20"/>

        <g style={{filter: snap ? undefined : GLOW.gold}}>{nodes.map((point, i) => nodes.slice(i + 1).map((other, jOffset) => {
          const j = i + jOffset + 1;
          const forgottenEdge = snap && (i < 3 || j < 3);
          const opacity = snap
            ? (snapFlash * 0.95 + fragmentOpacity * (forgottenEdge ? 0.22 : 0.46))
            : 0.12 + (chunkCount / 9) * 0.12;
          return <g key={`edge-${i}-${j}`}>
            <line x1={point.x} y1={point.y} x2={other.x} y2={other.y}
              stroke={snap ? C.red : C.amber}
              strokeWidth={snapFlash > 0 ? 2.2 + snapFlash * 1.8 : 1.25}
              strokeOpacity={clamp(opacity)}
              strokeDasharray={snap ? '9 7 2 8' : undefined}
              strokeDashoffset={snap ? -((frame * 2 + i * 9 + j * 5) % 28) : undefined}/>
            {snap && !forgottenEdge && fragmentOpacity > 0.02 && <line
              x1={mix(point.x, other.x, 0.37)} y1={mix(point.y, other.y, 0.37)}
              x2={mix(point.x, other.x, 0.53)} y2={mix(point.y, other.y, 0.53)}
              stroke={C.red} strokeWidth="2.6" strokeOpacity={fragmentOpacity * 0.8}
              strokeDasharray="3 7"/>}
          </g>;
        }))}</g>

        {snap && frame < 1380 && <g>
          <circle cx="1174" cy="565" r={mix(60, 260, clamp((frame - 1200) / 130))} fill="url(#act1-impact-glow)" opacity={fragmentOpacity}/>
          <circle cx="1174" cy="565" r={mix(28, 250, clamp((frame - 1200) / 110))} fill="none" stroke={C.red} strokeOpacity={fragmentOpacity * 0.75} strokeWidth="2"/>
        </g>}

        {nodes.map((point, i) => {
          const forgotten = snap && i < 3;
          const isNew = i === 9;
          const labelRadialX = Math.cos(point.angle);
          const labelRadialY = Math.sin(point.angle);
          const textAnchor = labelRadialX > 0.36 ? 'start' : labelRadialX < -0.36 ? 'end' : 'middle';
          const labelX = isNew ? point.x + 48 : point.x + labelRadialX * 45;
          const labelY = isNew ? point.y - 13 : point.y + labelRadialY * 60 - (labelRadialY < -0.36 ? 16 : 0);
          const color = forgotten ? C.muted : isNew && snapFlash > 0.1 ? C.red : C.amber;
          const opacity = forgotten ? clamp((990 - point.y) / 170) : 1;
          return <g key={`node-${i}`} opacity={opacity}>
            <circle cx={point.x} cy={point.y} r={point.radius * 2.8} fill={forgotten ? 'transparent' : 'url(#act1-node-glow)'}/>
            <circle cx={point.x} cy={point.y} r={point.radius} fill={forgotten ? '#39424d' : (isNew && snapFlash > 0.1 ? C.red : '#fbbf24')} stroke={forgotten ? '#596574' : color} strokeWidth="1.8" style={{filter: forgotten || (isNew && snapFlash > 0.1) ? undefined : GLOW.gold}}/>
            {!forgotten && <circle cx={point.x - 6} cy={point.y - 7} r="4" fill={C.white} opacity="0.72"/>}
            <text x={labelX} y={labelY} textAnchor={isNew ? 'start' : textAnchor}
              fill={forgotten ? '#8995a3' : C.white} fontFamily={CN} fontSize="18" fontWeight="600">
              {i + 1}. {VARIABLES[i].cn}{forgotten ? '  [FORGOTTEN]' : ''}
            </text>
            {!forgotten && <text x={labelX} y={labelY + 21} textAnchor={isNew ? 'start' : textAnchor}
              fill={isNew ? C.red : C.amber} fontFamily={FONT} fontSize="10" letterSpacing="1.7" opacity="0.9">
              {VARIABLES[i].en}
            </text>}
          </g>;
        })}

        <g transform="translate(110 392)">
          <path d="M0 0h238M0 1v142" stroke={C.amber} strokeOpacity="0.38" fill="none"/>
          <text x="18" y="29" fill={C.amber} fontFamily={FONT} fontSize="12" letterSpacing="2">COUPLED SYSTEM</text>
          <text x="18" y="71" fill={snap ? C.red : C.white} fontFamily={FONT} fontSize="27">{chunkCount} <tspan fill={C.muted} fontSize="15">VARIABLES</tspan></text>
          <text x="18" y="106" fill={snap ? C.red : C.white} fontFamily={FONT} fontSize="22">{edgeCount} <tspan fill={C.muted} fontSize="14">ACTIVE EDGES</tspan></text>
          <text x="18" y="132" fill={snap ? C.red : C.muted} fontFamily={FONT} fontSize="10" letterSpacing="1.6">N × (N − 1) / 2</text>
        </g>

        {snap && frame < 1500 && <g transform="translate(1060 844)" opacity={fragmentOpacity}>
          <rect width="232" height="38" rx="2" fill="#180d13" stroke={C.red} strokeOpacity="0.7"/>
          <text x="116" y="25" textAnchor="middle" fill={C.red} fontFamily={FONT} fontSize="12" letterSpacing="1.1">SYNAPSE SNAP // PRUNING 03</text>
        </g>}
      </svg>
    </div>

    <div style={{position: 'absolute', inset: 0, opacity: titleOpacity, background: 'rgba(5,8,17,0.84)'}}>
      <ActLabel number="EPISODE 02" title="7±2 的囚笼" kicker="超智能系列" color={C.cyan}/>
      <div style={{position: 'absolute', left: 350, right: 100, top: 348, textAlign: 'center', color: C.white}}>
        <div style={{fontFamily: CN, fontSize: 86, fontWeight: 650, letterSpacing, filter: GLOW.cyan, lineHeight: 1.35}}>
          工作记忆与高维推演
        </div>
        <div style={{marginTop: 28, fontFamily: FONT, color: C.cyan, fontSize: 18, letterSpacing: 8, filter: GLOW.cyan}}>
          7 ± 2  →  10⁶
        </div>
        <div style={{width: 410, height: 1, margin: '44px auto 34px', background: `linear-gradient(90deg, transparent, ${C.cyan}, transparent)`}}/>
        <div style={{fontFamily: FONT, color: C.muted, fontSize: 13, letterSpacing: 1.4}}>
          [ WORKING MEMORY: 7 CHUNKS&nbsp; // &nbsp;ATTENTION MATRIX: 10<sup>6</sup> DIMENSIONS ]
        </div>
      </div>
    </div>
  </div>;
};
