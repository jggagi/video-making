import React from 'react';
import {useCurrentFrame} from 'remotion';
import {C, FONT} from '../lib/theme';
import {clamp, ease, mix, seeded, type Vec3} from '../lib/math';
import {ActLabel, Droplet, PetriDish} from './Visuals';

const PHI = (1 + Math.sqrt(5)) / 2;
const rawIcosahedron: Vec3[] = [
  [-1, PHI, 0], [1, PHI, 0], [-1, -PHI, 0], [1, -PHI, 0],
  [0, -1, PHI], [0, 1, PHI], [0, -1, -PHI], [0, 1, -PHI],
  [PHI, 0, -1], [PHI, 0, 1], [-PHI, 0, -1], [-PHI, 0, 1],
];
const vertexLength = Math.sqrt(1 + PHI * PHI);

/** Unit-radius vertices for a regular icosahedron. */
export const ICOSAHEDRON_VERTICES: readonly Vec3[] = rawIcosahedron.map(([x, y, z]) => [
  x / vertexLength, y / vertexLength, z / vertexLength,
]);

const edgeLengthSquared = 4 / (vertexLength * vertexLength);
const squaredDistance = (a: Vec3, b: Vec3) =>
  (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2;

/** The 30 undirected edges, represented as vertex-index pairs. */
export const ICOSAHEDRON_EDGES: readonly (readonly [number, number])[] = (() => {
  const edges: [number, number][] = [];
  for (let i = 0; i < ICOSAHEDRON_VERTICES.length; i++) {
    for (let j = i + 1; j < ICOSAHEDRON_VERTICES.length; j++) {
      if (Math.abs(squaredDistance(ICOSAHEDRON_VERTICES[i], ICOSAHEDRON_VERTICES[j]) - edgeLengthSquared) < 1e-6) {
        edges.push([i, j]);
      }
    }
  }
  return edges;
})();

/** The 20 triangular faces, represented as vertex-index triples. */
export const ICOSAHEDRON_FACES: readonly (readonly [number, number, number])[] = (() => {
  const edgeSet = new Set(ICOSAHEDRON_EDGES.map(([a, b]) => `${a}:${b}`));
  const hasEdge = (a: number, b: number) => edgeSet.has(`${Math.min(a, b)}:${Math.max(a, b)}`);
  const faces: [number, number, number][] = [];
  for (let i = 0; i < ICOSAHEDRON_VERTICES.length; i++) {
    for (let j = i + 1; j < ICOSAHEDRON_VERTICES.length; j++) {
      for (let k = j + 1; k < ICOSAHEDRON_VERTICES.length; k++) {
        if (hasEdge(i, j) && hasEdge(i, k) && hasEdge(j, k)) faces.push([i, j, k]);
      }
    }
  }
  return faces;
})();

/** Rotate one normalized icosahedron vertex deterministically for a frame. */
export const rotateIcosahedronVertex = (v: Vec3, frame: number): Vec3 => {
  const ax = frame * 0.008;
  const ay = frame * 0.011;
  const az = frame * 0.004;
  const cx = Math.cos(ax), sx = Math.sin(ax);
  const cy = Math.cos(ay), sy = Math.sin(ay);
  const cz = Math.cos(az), sz = Math.sin(az);
  const x1 = v[0], y1 = v[1] * cx - v[2] * sx, z1 = v[1] * sx + v[2] * cx;
  const x2 = x1 * cy + z1 * sy, y2 = y1, z2 = -x1 * sy + z1 * cy;
  return [x2 * cz - y2 * sz, x2 * sz + y2 * cz, z2];
};

type DigitalNode = {x: number; y: number; r: number; opacity: number; color: string};

export const DIGITAL_NODE_COUNT = 500;
export const IMPACT_LOCAL_FRAME = 2400;
export const gearState = (frame: number) => ({rotation: frame * 0.002, jitter: Math.sin(frame * 2.5) * 0.8});
export const laboratoryState = (frame: number) => {
  const t = clamp((frame - 2100) / 300);
  return {dropY: mix(445, 788, t * t), impacted: frame >= IMPACT_LOCAL_FRAME};
};

const makeGearPath = (teeth: number, rootRadius: number, tipRadius: number) => {
  const points: string[] = [];
  const toothWidth = (Math.PI * 2) / teeth;
  for (let i = 0; i < teeth; i++) {
    const a = i * toothWidth;
    const samples: [number, number][] = [
      [0.04, rootRadius], [0.19, rootRadius], [0.29, tipRadius],
      [0.68, tipRadius], [0.78, rootRadius], [0.96, rootRadius],
    ];
    for (const [fraction, radius] of samples) {
      const angle = a + fraction * toothWidth - Math.PI / 2;
      points.push(`${points.length === 0 ? 'M' : 'L'}${(Math.cos(angle) * radius).toFixed(2)},${(Math.sin(angle) * radius).toFixed(2)}`);
    }
  }
  return `${points.join(' ')} Z`;
};

const astRows: {x: number; y: number; label: string}[] = [
  {x: 440, y: 488, label: 'PROGRAM'},
  {x: 300, y: 570, label: 'IF'}, {x: 440, y: 570, label: 'CALL'}, {x: 580, y: 570, label: 'RETURN'},
  {x: 230, y: 654, label: 'BOOL'}, {x: 335, y: 654, label: 'VAR'}, {x: 440, y: 654, label: 'NUM'},
  {x: 545, y: 654, label: 'VAR'}, {x: 650, y: 654, label: 'BOOL'},
];

export const DigitalField: React.FC<{frame: number}> = ({frame}) => {
  const tick = Math.floor(frame / 2);
  const nodes = React.useMemo<DigitalNode[]>(() => Array.from({length: DIGITAL_NODE_COUNT}, (_, i) => {
    const x = 82 + seeded(i * 3 + 11) * 796;
    const y = 425 + seeded(i * 3 + 12) * 490;
    const flicker = seeded(i * 37 + tick * 503 + 17);
    return {
      x: x + (flicker - 0.5) * 2.8,
      y: y + (seeded(i * 41 + tick * 509 + 23) - 0.5) * 2.8,
      r: 1.35 + seeded(i * 3 + 13) * 1.75,
      opacity: 0.23 + flicker * 0.62,
      color: i % 7 === 0 ? C.white : C.cyan,
    };
  }), [tick]);

  const wavePaths = [0, 1, 2].map((wave) => {
    const phase = tick * 0.022 + wave * 1.55;
    const points = Array.from({length: 45}, (_, i) => {
      const x = 82 + (796 * i) / 44;
      const y = 810 + wave * 34 + Math.sin(i * 0.23 + phase) * (11 + wave * 3);
      return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`;
    });
    return points.join(' ');
  });

  return <g>
    <path d="M440 500L300 570 M440 500L440 570 M440 500L580 570 M300 590L230 654 M300 590L335 654 M440 590L440 654 M580 590L545 654 M580 590L650 654" fill="none" stroke={C.cyan} strokeOpacity="0.21" strokeWidth="1.2" />
    {astRows.map((node, i) => <g key={`ast-${i}`}>
      <rect x={node.x - 43} y={node.y - 13} width="86" height="26" rx="3" fill="#071b27" fillOpacity="0.94" stroke={C.cyan} strokeOpacity="0.48" />
      <text x={node.x} y={node.y + 4} textAnchor="middle" fill={i === 0 ? C.white : C.cyan} fillOpacity="0.9" fontFamily={FONT} fontSize="10" letterSpacing="1.1">{node.label}</text>
    </g>)}
    <text x="95" y="704" fill={C.cyan} fillOpacity="0.55" fontFamily={FONT} fontSize="12" letterSpacing="2">AST / TOKEN FIELD</text>
    <path d={wavePaths[0]} fill="none" stroke={C.cyan} strokeOpacity="0.38" strokeWidth="1.2" />
    <path d={wavePaths[1]} fill="none" stroke={C.cyan} strokeOpacity="0.24" strokeWidth="1" />
    <path d={wavePaths[2]} fill="none" stroke={C.white} strokeOpacity="0.13" strokeWidth="1" />
    {nodes.map((node, i) => <circle key={`node-${i}`} cx={node.x} cy={node.y} r={node.r} fill={node.color} opacity={node.opacity} />)}
    <text x="95" y="923" fill={C.muted} fillOpacity="0.72" fontFamily={FONT} fontSize="12" letterSpacing="1.8">500 NODES · STATE REWRITES EVERY 2 FRAMES</text>
  </g>;
};

export const GearMechanism: React.FC<{frame: number}> = ({frame}) => {
  const {jitter, rotation} = gearState(frame);
  const gearPath = React.useMemo(() => makeGearPath(36, 207, 235), []);
  return <g>
    <g transform={`translate(${1420 + jitter} 590)`}>
      <circle r="248" fill="none" stroke={C.amber} strokeOpacity="0.15" strokeWidth="1" />
      <circle r="242" fill="none" stroke={C.amber} strokeOpacity="0.23" strokeWidth="1" strokeDasharray="2 8" />
      <g transform={`rotate(${rotation})`}>
        <path d={gearPath} fill="#3b260a" fillOpacity="0.56" stroke={C.amber} strokeOpacity="0.92" strokeWidth="2.2" />
        <circle r="199" fill="none" stroke={C.amber} strokeOpacity="0.42" strokeWidth="1.4" />
        <circle r="176" fill="none" stroke={C.amber} strokeOpacity="0.34" strokeWidth="1" strokeDasharray="3 5" />
        {Array.from({length: 48}, (_, i) => {
          const angle = (i * Math.PI * 2) / 48 - Math.PI / 2;
          const long = i % 4 === 0;
          const r1 = long ? 183 : 189;
          const r2 = long ? 199 : 196;
          return <line key={`tick-${i}`} x1={Math.cos(angle) * r1} y1={Math.sin(angle) * r1} x2={Math.cos(angle) * r2} y2={Math.sin(angle) * r2} stroke={C.gold} strokeOpacity={long ? 0.73 : 0.32} strokeWidth={long ? 1.8 : 0.9} />;
        })}
        {Array.from({length: 12}, (_, i) => {
          const angle = (i * Math.PI * 2) / 12;
          return <line key={`spoke-${i}`} x1={Math.cos(angle) * 54} y1={Math.sin(angle) * 54} x2={Math.cos(angle) * 154} y2={Math.sin(angle) * 154} stroke={C.amber} strokeOpacity="0.39" strokeWidth="8" strokeLinecap="round" />;
        })}
        <circle r="126" fill="none" stroke={C.amber} strokeOpacity="0.24" strokeWidth="1" />
        <circle r="52" fill="#0c1117" stroke={C.gold} strokeOpacity="0.72" strokeWidth="3" />
        <circle r="28" fill="#f59e0b" fillOpacity="0.18" stroke={C.amber} strokeOpacity="0.68" strokeWidth="2" />
        <circle r="9" fill={C.gold} fillOpacity="0.8" />
      </g>
      <path d="M-265 0h28 M237 0h28 M0-265v28 M0 237v28" stroke={C.white} strokeOpacity="0.42" strokeWidth="1" />
      <path d="M-10 -258L0 -270L10 -258" fill="none" stroke={C.gold} strokeOpacity="0.75" strokeWidth="1.5" />
    </g>

    <g transform="translate(1680 844) rotate(-8)">
      <path d="M-80 -53H50L78 -31V48L52 68H-80Z" fill="#171d23" fillOpacity="0.92" stroke={C.amber} strokeOpacity="0.73" strokeWidth="2" />
      <path d="M-64 -39H30V53H-64Z" fill="#2b1e0b" fillOpacity="0.67" stroke={C.gold} strokeOpacity="0.34" />
      <ellipse cx="-80" cy="7" rx="16" ry="60" fill="#10161d" stroke={C.amber} strokeOpacity="0.7" strokeWidth="2" />
      <ellipse cx="-80" cy="7" rx="6" ry="27" fill="none" stroke={C.gold} strokeOpacity="0.45" />
      <ellipse cx="51" cy="8" rx="27" ry="39" fill="#211807" stroke={C.amber} strokeOpacity="0.74" strokeWidth="2" />
      <circle cx="51" cy="8" r="16" fill="#0a0f13" stroke={C.gold} strokeOpacity="0.52" strokeWidth="2" />
      <path d="M-42 -53V-74 M-12 -53V-74 M18 -53V-74 M-42 68V87 M-12 68V87 M18 68V87" stroke={C.amber} strokeOpacity="0.72" strokeWidth="3" />
      <text x="-28" y="14" textAnchor="middle" fill={C.gold} fillOpacity="0.76" fontFamily={FONT} fontSize="11" letterSpacing="2">STEP / 01</text>
    </g>
    <path d="M1614 835L1544 755" fill="none" stroke={C.amber} strokeOpacity="0.56" strokeWidth="8" />
    <g transform="translate(1542 753)" fill="none" stroke={C.amber} strokeOpacity="0.68" strokeWidth="2">
      <circle r="64" /><circle r="51" strokeOpacity="0.34" />
      {Array.from({length: 12}, (_, i) => <line key={`small-tooth-${i}`} x1={Math.cos((i * Math.PI * 2) / 12) * 52} y1={Math.sin((i * Math.PI * 2) / 12) * 52} x2={Math.cos((i * Math.PI * 2) / 12) * 65} y2={Math.sin((i * Math.PI * 2) / 12) * 65} />)}
    </g>

    <path d="M1008 580L1284 580" stroke={C.cyan} strokeOpacity="0.47" strokeWidth="1.4" strokeDasharray="8 8" />
    <g transform="translate(1295 580) rotate(45)">
      <rect x="-5" y="-30" width="10" height="60" rx="2" fill="#dbeafe" fillOpacity="0.88" />
      <rect x="-2" y="-28" width="4" height="56" fill={C.cyan} fillOpacity="0.68" />
    </g>
    <text x="1375" y="883" fill={C.amber} fillOpacity="0.78" fontFamily={FONT} fontSize="12" letterSpacing="2">STEPPER / PHASE LOCK</text>
    <text x="1010" y="550" fill={C.cyan} fillOpacity="0.68" fontFamily={FONT} fontSize="11" letterSpacing="2">LASER INTERFEROMETER</text>
  </g>;
};

export const Laboratory: React.FC<{frame: number; opacity: number}> = ({frame, opacity}) => {
  const {dropY, impacted: impactVisible} = laboratoryState(frame);
  const afterImpact = frame - IMPACT_LOCAL_FRAME;
  const flash = impactVisible ? Math.exp(-afterImpact / 10) : 0;
  const laserPulse = impactVisible
    ? 0.17 + 0.12 * (0.5 + 0.5 * Math.sin(afterImpact * 0.035)) + 0.66 * Math.exp(-afterImpact / 22)
    : 0;
  const icoFrame = Math.max(0, afterImpact);
  const vertices = ICOSAHEDRON_VERTICES.map((v) => rotateIcosahedronVertex(v, icoFrame));
  const faces = ICOSAHEDRON_FACES.map((indices) => {
    const points = indices.map((i) => vertices[i]);
    const depth = (points[0][2] + points[1][2] + points[2][2]) / 3;
    return {indices, points, depth};
  }).sort((a, b) => a.depth - b.depth);
  const projected = vertices.map(([x, y, z]) => {
    const perspective = 1 + z * 0.12;
    return [x * 92 * perspective, y * 92 * perspective, z] as const;
  });
  const magneticRings = impactVisible ? [0, 1, 2].map((i) => ({
    radius: 10 + afterImpact * (2.7 + i * 0.28) + i * 18,
    opacity: Math.max(0, 0.48 - afterImpact / (170 + i * 55)),
  })) : [];

  return <g opacity={opacity}>
    <defs>
      <linearGradient id="act4-lab-wash" x1="0" y1="0" x2="1" y2="1"><stop stopColor="#0a1e2a" /><stop offset="0.52" stopColor="#07131d" /><stop offset="1" stopColor="#10140f" /></linearGradient>
      <pattern id="act4-lab-grid" width="48" height="48" patternUnits="userSpaceOnUse"><path d="M48 0H0V48" fill="none" stroke="#8ba8b8" strokeOpacity="0.07" strokeWidth="1" /></pattern>
      <radialGradient id="act4-impact-glow"><stop stopColor={C.cyan} stopOpacity="0.5" /><stop offset="1" stopColor={C.cyan} stopOpacity="0" /></radialGradient>
    </defs>
    <rect width="1920" height="1080" fill="url(#act4-lab-wash)" />
    <rect width="1920" height="1080" fill="url(#act4-lab-grid)" />
    <path d="M70 860H1850 M120 254H1800" stroke={C.white} strokeOpacity="0.09" strokeWidth="1" />
    <path d="M170 859V832H570V859 M1450 859V832H1760V859" fill="#0b1419" fillOpacity="0.42" stroke={C.white} strokeOpacity="0.12" />
    <path d="M165 304H850 M1360 304H1750" stroke={C.white} strokeOpacity="0.08" strokeWidth="1" />
    <circle cx="1120" cy="576" r="430" fill="url(#act4-impact-glow)" opacity="0.14" />

    <g transform="translate(1120 0)">
      <path d="M-26 208H26L19 282L12 331L0 370L-12 331L-19 282Z" fill="#13202a" stroke="#8ba8b8" strokeOpacity="0.66" strokeWidth="2" />
      <path d="M-18 226H18 M-15 249H15 M-12 272H12" stroke={C.white} strokeOpacity="0.16" strokeWidth="1" />
      <path d="M-8 370H8" stroke={C.amber} strokeOpacity="0.86" strokeWidth="2" />
      <path d="M42 247V367 M36 247H48 M36 367H48" stroke={C.white} strokeOpacity="0.28" strokeWidth="1" />
    </g>
    <text x="1172" y="301" fill={C.muted} fillOpacity="0.82" fontFamily={FONT} fontSize="11" letterSpacing="1.2">MICRODOSER / 04</text>

    <g transform="translate(1675 330)">
      <rect x="-74" y="-32" width="148" height="64" rx="5" fill="#0c1820" fillOpacity="0.9" stroke={C.white} strokeOpacity="0.23" />
      <circle cx="-50" cy="0" r="4" fill={C.gold} />
      <text x="-35" y="-2" fill={C.muted} fontFamily={FONT} fontSize="10" letterSpacing="1.8">TIME SNAP</text>
      <text x="-35" y="18" fill={C.white} fontFamily={FONT} fontSize="17" letterSpacing="1.2">1×  /  REAL</text>
    </g>

    <g transform="translate(1480 0)">
      <path d="M0 433V806" stroke={C.white} strokeOpacity="0.39" strokeWidth="1.2" />
      {Array.from({length: 25}, (_, i) => {
        const y = 434 + i * 15;
        const major = i % 5 === 0;
        return <line key={`millimeter-${i}`} x1="0" y1={y} x2={major ? -24 : -12} y2={y} stroke={C.white} strokeOpacity={major ? 0.52 : 0.25} strokeWidth={major ? 1.4 : 0.8} />;
      })}
      <text x="-38" y="418" textAnchor="end" fill={C.white} fillOpacity="0.82" fontFamily={FONT} fontSize="13" letterSpacing="1.5">120 mm</text>
      <text x="20" y="446" fill={C.muted} fillOpacity="0.64" fontFamily={FONT} fontSize="9" letterSpacing="1">CALIBRATED DROP PATH</text>
    </g>

    <PetriDish x={1120} y={820} />
    {frame >= 2100 && !impactVisible && <Droplet x={1120} y={dropY} scale={0.62} opacity={1} id="act4-drop" />}

    {impactVisible && <g>
      <path d="M770 820H1470" stroke={C.cyan} strokeOpacity={laserPulse} strokeWidth={2.2} />
      <path d="M800 820H1440" stroke={C.white} strokeOpacity={Math.min(0.78, flash * 0.75)} strokeWidth={1} />
      <circle cx="1120" cy="820" r={18 + flash * 68} fill="url(#act4-impact-glow)" opacity={flash} />
      {magneticRings.map((ring, i) => <ellipse key={`wave-${i}`} cx="1120" cy="820" rx={ring.radius} ry={Math.max(3, ring.radius * 0.2)} fill="none" stroke={i % 2 === 0 ? C.gold : C.amber} strokeOpacity={ring.opacity} strokeWidth={i === 0 ? 2.1 : 1.2} />)}
      <path d="M1110 820H1130 M1120 810V830" stroke={C.gold} strokeOpacity={0.42 + flash * 0.55} strokeWidth="1.5" />
      <g transform={`translate(1120 ${mix(790, 670, ease(icoFrame, 0, 55)) + Math.sin(icoFrame * 0.022) * 9})`}>
        {faces.map(({indices, depth}, i) => {
          const shade = clamp(0.48 + depth * 0.48, 0.12, 0.94);
          const points = indices.map((index) => `${projected[index][0].toFixed(2)},${projected[index][1].toFixed(2)}`).join(' ');
          return <polygon key={`face-${i}`} points={points} fill={i % 3 === 0 ? C.gold : C.amber} fillOpacity={0.13 + shade * 0.28} stroke={C.gold} strokeOpacity="0.22" strokeWidth="0.7" />;
        })}
        {ICOSAHEDRON_EDGES.map(([a, b], i) => <line key={`edge-${i}`} x1={projected[a][0]} y1={projected[a][1]} x2={projected[b][0]} y2={projected[b][1]} stroke={C.gold} strokeOpacity={0.76 + Math.max(0, (projected[a][2] + projected[b][2]) / 8)} strokeWidth="1.7" />)}
        {projected.map(([x, y, z], i) => <circle key={`vertex-${i}`} cx={x} cy={y} r="3.2" fill={z > 0 ? '#fff2ad' : C.gold} opacity={0.74 + Math.max(0, z) * 0.2} />)}
      </g>
      <text x="1120" y="790" textAnchor="middle" fill={C.gold} fillOpacity="0.82" fontFamily={FONT} fontSize="11" letterSpacing="2.2">ONE REALITY / ONE STRIKE</text>
    </g>}
  </g>;
};

const EyelidReopening: React.FC<{frame: number}> = ({frame}) => {
  if (frame < 1900 || frame >= 2400) return null;
  const open = ease(frame, 2100, 2400);
  const upperOuter = mix(430, 194, open);
  const upperCenter = mix(285, 194, open);
  const lowerOuter = mix(815, 938, open);
  const lowerCenter = mix(940, 938, open);
  return <svg width="1920" height="1080" viewBox="0 0 1920 1080" style={{position: 'absolute', inset: 0, opacity: ease(frame, 1900, 2100)}} aria-hidden="true">
    <path d={`M0 194H1920V${upperOuter} Q960 ${upperCenter} 0 ${upperOuter}Z`} fill={C.bg} stroke="rgba(6,182,212,0.2)" strokeWidth="1" />
    <path d={`M0 938H1920V${lowerOuter} Q960 ${lowerCenter} 0 ${lowerOuter}Z`} fill={C.bg} stroke="rgba(6,182,212,0.2)" strokeWidth="1" />
  </svg>;
};

const CinematicEnding: React.FC<{frame: number}> = ({frame}) => {
  const quoteOpacity = ease(frame, 3300, 3340);
  const titleOpacity = ease(frame, 3340, 3420);
  const scan = ease(frame, 3420, 3570);
  const scanOpacity = ease(frame, 3420, 3430) * (1 - ease(frame, 3570, 3599));
  const scanX = mix(540, 1380, scan);
  const scanTail = Math.max(540, scanX - 94);
  const scanY = 505;

  return <div style={{position: 'absolute', inset: 0, overflow: 'hidden', pointerEvents: 'none', fontFamily: FONT}}>
    <div style={{position: 'absolute', top: 306, left: 0, right: 0, textAlign: 'center', opacity: quoteOpacity, color: C.white, fontSize: 23, letterSpacing: 2.5, fontWeight: 400}}>
      人类眨眼一瞬，硅基已历万年。
    </div>
    <div style={{position: 'absolute', top: 418, left: 0, right: 0, height: 174, display: 'flex', alignItems: 'center', justifyContent: 'center', opacity: titleOpacity}}>
      <div style={{fontFamily: '"PingFang SC", "Hiragino Sans GB", sans-serif', color: C.white, fontSize: 128, lineHeight: 1, fontWeight: 300, letterSpacing: 32, whiteSpace: 'nowrap', textShadow: '0 0 22px rgba(6,182,212,0.22)'}}>
        一 眼 万 年
      </div>
    </div>
    <div style={{position: 'absolute', top: 626, left: 0, right: 0, textAlign: 'center', opacity: titleOpacity, color: C.cyan, fontSize: 20, lineHeight: 1.4, letterSpacing: '0.4em', fontWeight: 400}}>
      ONE BLINK, TEN MILLENNIA
    </div>
    <svg width="1920" height="1080" viewBox="0 0 1920 1080" style={{position: 'absolute', inset: 0, opacity: scanOpacity}} aria-hidden="true">
      <defs>
        <linearGradient id="act4-ending-trail" x1="0" y1="0" x2="1" y2="0">
          <stop stopColor={C.cyan} stopOpacity="0" />
          <stop offset="1" stopColor={C.cyan} stopOpacity="0.88" />
        </linearGradient>
        <radialGradient id="act4-ending-core">
          <stop stopColor={C.white} stopOpacity="0.96" />
          <stop offset="0.36" stopColor={C.cyan} stopOpacity="0.62" />
          <stop offset="1" stopColor={C.cyan} stopOpacity="0" />
        </radialGradient>
      </defs>
      <line x1={scanTail} y1={scanY} x2={scanX} y2={scanY} stroke={C.cyan} strokeOpacity="0.12" strokeWidth="8" />
      <line x1={scanTail} y1={scanY} x2={scanX} y2={scanY} stroke="url(#act4-ending-trail)" strokeWidth="2" />
      <circle cx={scanX} cy={scanY} r="11" fill="url(#act4-ending-core)" />
      <line x1={scanX - 2.5} y1={scanY} x2={scanX + 2.5} y2={scanY} stroke={C.white} strokeOpacity="0.96" strokeWidth="1.5" />
    </svg>
  </div>;
};

/** Act 4: a deterministic passage from digital abstraction to physical reality. */
export const Act4SplitWorld: React.FC = () => {
  const frame = clamp(useCurrentFrame(), 0, 3599);
  const splitOpacity = 1 - ease(frame, 1900, 2100);
  const laboratoryOpacity = ease(frame, 1900, 2100);
  const fadeToVoid = ease(frame, 3280, 3300);

  return <div style={{position: 'absolute', inset: 0, width: 1920, height: 1080, overflow: 'hidden', pointerEvents: 'none'}}>
    <svg width="1920" height="1080" viewBox="0 0 1920 1080" style={{position: 'absolute', inset: 0, fontFamily: FONT}}>
      {frame < 2100 && <g opacity={splitOpacity}>
        <rect x="0" y="206" width="960" height="738" fill="#06131e" fillOpacity="0.57" />
        <rect x="960" y="206" width="960" height="738" fill="#17140d" fillOpacity="0.36" />
        <path d="M960 206V944" stroke={C.white} strokeOpacity="0.48" strokeWidth="1.2" />
        <path d="M948 206H972 M948 944H972" stroke={C.white} strokeOpacity="0.56" strokeWidth="1.5" />
        <DigitalField frame={frame} />
        <GearMechanism frame={frame} />
        <text x="95" y="350" fill={C.cyan} fontFamily={FONT} fontSize="17" fontWeight="600" letterSpacing="3.2">DIGITAL / BITS</text>
        <text x="95" y="377" fill={C.muted} fillOpacity="0.86" fontFamily={FONT} fontSize="11" letterSpacing="1.8">REWRITABLE STATE · 500 NODES</text>
        <text x="1045" y="350" fill={C.amber} fontFamily={FONT} fontSize="17" fontWeight="600" letterSpacing="3.2">PHYSICAL / ATOMS</text>
        <text x="1045" y="377" fill={C.muted} fillOpacity="0.86" fontFamily={FONT} fontSize="11" letterSpacing="1.8">MASS · FRICTION · ALIGNMENT</text>
      </g>}

      <Laboratory frame={frame} opacity={laboratoryOpacity} />
      <rect width="1920" height="1080" fill={C.bg} opacity={fadeToVoid} />
    </svg>

    <div style={{position: 'absolute', inset: 0, opacity: splitOpacity}}>
      <ActLabel number="04" title="The wall is made of atoms." kicker="ASYMMETRY / BITS ↔ ATOMS" color={C.cyan} />
    </div>
    <div style={{position: 'absolute', inset: 0, opacity: laboratoryOpacity * (1 - fadeToVoid)}}>
      <ActLabel number="04" title="One move in reality." kicker="ONE-SHOT / THE PHYSICAL ANSWER" color={C.gold}/>
      <div style={{position: 'absolute', left: 94, top: 435, width: 640, fontFamily: FONT}}>
        <div style={{fontSize: 66, lineHeight: 1.16, letterSpacing: -2.6, fontWeight: 600}}>
          {frame < IMPACT_LOCAL_FRAME ? <>THE WORLD<br/><span style={{color: C.amber}}>CATCHES UP.</span></> : <>ONE SHOT.<br/><span style={{color: C.gold}}>A NEW ORDER.</span></>}
        </div>
        <div style={{marginTop: 35, width: 60, height: 2, backgroundColor: C.gold}}/>
        <div style={{fontSize: 13, lineHeight: 2, letterSpacing: 1, color: C.muted, marginTop: 23}}>
          θ = 42.198401° / B = 14.2 T<br/>
          {frame < IMPACT_LOCAL_FRAME ? 'VERIFIED SOLUTION / AWAITING CONTACT' : 'CRYSTAL LATTICE / PHASE LOCKED'}
        </div>
      </div>
    </div>
    <EyelidReopening frame={frame} />
    {frame >= 3300 ? <CinematicEnding frame={frame} /> : null}
  </div>;
};
