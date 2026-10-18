import React from 'react';
import {C, CN, FONT, GLOW} from '../lib/theme';
import {clamp, manifold, seeded, smooth} from '../lib/math';

export type PortraitStage = 'overload' | 'linear' | 'matrix' | 'manifold' | 'oracle' | 'ending' | 'hook';

type PortraitSceneProps = {stage: PortraitStage; frame: number};

const W = 1080;
const H = 1920;
const CX = 500;
const CY = 850;

const PortraitSvg: React.FC<{children: React.ReactNode}> = ({children}) => <svg
  width={W}
  height={H}
  viewBox="0 0 1080 1920"
  aria-hidden="true"
  style={{position: 'absolute', inset: 0, width: W, height: H, pointerEvents: 'none'}}
>
  <defs>
    <clipPath id="xhs-portrait-graphic-box"><rect x="72" y="540" width="858" height="670" /></clipPath>
  </defs>
  <g clipPath="url(#xhs-portrait-graphic-box)">
    <rect x="78" y="548" width="846" height="660" rx="18" fill="rgba(5,8,17,0.78)" stroke="rgba(148,184,211,0.22)" strokeWidth="1.2" />
    <path d="M98 592V568H122 M878 568H902V592 M98 1158V1182H122 M878 1182H902V1158" fill="none" stroke="rgba(148,184,211,0.52)" strokeWidth="1.4" />
    {children}
  </g>
</svg>;

const OverloadScene: React.FC<{frame: number}> = ({frame}) => {
  const variables = ['利率', '通胀', '汇率', '供电', '物流', '温度', '信贷', '算力', '航运'];
  const positions = variables.map((_, index) => {
    const angle = -Math.PI / 2 + index * Math.PI * 2 / 9;
    return {x: CX + Math.cos(angle) * 250, y: CY + Math.sin(angle) * 220};
  });
  const nodes = variables.map((label, index) => {
    const angle = -Math.PI / 2 + index * Math.PI * 2 / 9;
    const x0 = CX + Math.cos(angle) * 250;
    const y0 = CY + Math.sin(angle) * 220;
    const forgotten = frame >= 36 && index < 3;
    const fall = forgotten ? clamp((frame - 36) / 70) : 0;
    const x = x0 + (fall ? Math.sin((frame - 36) * 0.08 + index) * 15 * fall : 0);
    const y = y0 + fall * 112;
    const visible = frame >= index * 4;
    const color = forgotten ? '#8995a5' : C.amber;
    return <g key={label} opacity={visible ? 1 : 0}>
      <circle cx={x} cy={y} r="18" fill={color} fillOpacity={forgotten ? 0.2 : 0.95} stroke={color} strokeWidth="1.4" style={{filter: forgotten ? undefined : GLOW.gold}} />
      {!forgotten && <circle cx={x - 4} cy={y - 5} r="3" fill={C.white} fillOpacity="0.8"/>}
      <text x={x + Math.cos(angle) * 53} y={y + Math.sin(angle) * 53 + 8} textAnchor="middle" fill={color} fontFamily={CN} fontSize="22" fontWeight="600">{label}</text>
    </g>;
  });
  const hitAge = frame - 36;
  const hit = frame >= 36 ? 1 : 0;
  const burstProgress = clamp(hitAge / 12);
  const burstOpacity = frame >= 36 ? 1 - smooth(burstProgress) : 0;

  return <>
    <text x="120" y="610" fill={C.amber} fontFamily={FONT} fontSize="18" letterSpacing="1.5">VARIABLE LOAD / 09</text>
    <ellipse cx={CX} cy={CY} rx="250" ry="220" fill="rgba(245,158,11,0.025)" stroke={C.amber} strokeOpacity="0.4" strokeWidth="1.3" strokeDasharray="4 9" />
    <g style={{filter: frame < 36 ? GLOW.gold : undefined}}>
      {positions.flatMap((p, i) => positions.slice(i + 1).map((q, j) => frame >= (i + j + 1) * 4 && <line key={`${i}-${j}`} x1={p.x} y1={p.y} x2={q.x} y2={q.y} stroke={frame >= 36 ? C.red : C.amber} strokeWidth={frame >= 36 ? 1.6 : 1} strokeOpacity={frame >= 36 ? 0.24 : 0.24} strokeDasharray={frame >= 36 ? '5 8' : undefined}/>))}
    </g>
    {nodes}
    <g opacity={hit}>
      <circle cx={CX} cy={CY} r="19" fill={C.red} fillOpacity="0.24" stroke={C.red} strokeWidth="2.5" />
      <circle cx={CX} cy={CY} r="7" fill={C.red} />
      <circle cx={CX} cy={CY} r={22 + burstProgress * 98} fill="none" stroke={C.red} strokeOpacity={burstOpacity * 0.86} strokeWidth="2" />
      <circle cx={CX} cy={CY} r={36 + burstProgress * 135} fill="none" stroke={C.amber} strokeOpacity={burstOpacity * 0.56} strokeWidth="1.2" />
    </g>
    <text x={CX} y="1150" textAnchor="middle" fill={C.red} fillOpacity={hit} fontFamily={FONT} fontSize="36" fontWeight="700" letterSpacing="2">10 / 9</text>
    <text x={CX} y="1180" textAnchor="middle" fill={C.red} fillOpacity={hit * 0.78} fontFamily={FONT} fontSize="17" letterSpacing="1.5">CAPACITY EXCEEDED</text>
  </>;
};

const LinearScene: React.FC<{frame: number}> = ({frame}) => {
  const points = Array.from({length: 80}, (_, index) => {
    const x = 138 + seeded(index * 13 + 1) * 724;
    const lineY = 850 - (x - CX) * 0.36;
    const inlier = index % 20 < 3;
    const noise = inlier ? (seeded(index * 13 + 2) - 0.5) * 46 : 630 + seeded(index * 13 + 2) * 424;
    return {x, y: inlier ? lineY + noise : noise, inlier};
  });
  const scanX = 138 + ((frame * 3.2) % 724);

  return <>
    <text x="124" y="610" fill={C.white} fontFamily={CN} fontSize="22" fontWeight="600">示意数据</text>
    <text x="500" y="610" textAnchor="middle" fill={C.cyan} fontFamily={CN} fontSize="22" fontWeight="600">二维线性拟合</text>
    <text x="876" y="610" textAnchor="end" fill={C.muted} fontFamily={CN} fontSize="22">离群样本</text>
    {[690, 790, 890, 990].map((y) => <line key={`row-${y}`} x1="138" y1={y} x2="862" y2={y} stroke={C.cyan} strokeOpacity="0.1" strokeWidth="1" />)}
    {[238, 338, 438, 538, 638, 738].map((x) => <line key={`column-${x}`} x1={x} y1="650" x2={x} y2="1050" stroke={C.cyan} strokeOpacity="0.075" strokeWidth="1" />)}
    <path d="M138 980.3 L862 719.7" fill="none" stroke={C.gold} strokeOpacity="0.94" strokeWidth="3" style={{filter: GLOW.gold}} />
    <g>
      {points.map(({x, y, inlier}, index) => <circle key={`sample-${index}`} cx={x} cy={y} r={inlier ? 5.2 : 4.3} fill={inlier ? C.cyan : C.muted} fillOpacity={inlier ? 0.94 : 0.5} stroke={inlier ? C.white : 'none'} strokeOpacity="0.46" strokeWidth="0.8" />)}
    </g>
    <line x1={scanX} y1="650" x2={scanX} y2="1050" stroke={C.cyan} strokeOpacity="0.28" strokeWidth="1" />
    <text x="500" y="1102" textAnchor="middle" fill={C.white} fillOpacity="0.7" fontFamily={FONT} fontSize="18" letterSpacing="1">12 INLIERS / 68 IGNORED</text>
    <text x="500" y="1160" textAnchor="middle" fill={C.gold} fontFamily={FONT} fontSize="30" fontWeight="600" letterSpacing="1">y = kx + b</text>
  </>;
};

type MatrixCell = {index: number; x: number; y: number; intensity: number; gold: boolean};

const MatrixScene: React.FC<{frame: number}> = ({frame}) => {
  const cells: MatrixCell[] = Array.from({length: 40 * 40}, (_, index) => {
    const row = Math.floor(index / 40);
    const column = index % 40;
    return {
      index,
      x: 100 + column * 20,
      y: 560 + row * 15,
      intensity: 0.16 + seeded(index + 701) * 0.64,
      gold: seeded(index + 1701) > 0.94,
    };
  });
  const connections = Array.from({length: 36}, (_, index) => {
    const from = Math.floor(seeded(index + 2901) * 1600);
    const to = (from + 41 + Math.floor(seeded(index + 3901) * 240)) % 1600;
    const a = cells[from];
    const b = cells[to];
    const bend = (seeded(index + 4901) - 0.5) * 86;
    const middleX = (a.x + b.x) / 2 + bend;
    const middleY = clamp((a.y + b.y) / 2 - 42 - Math.abs(bend) * 0.18, 560, 1160);
    return {index, a, b, middleX, middleY};
  });
  const cyanCells = cells.filter((cell) => !cell.gold);
  const goldCells = cells.filter((cell) => cell.gold);

  return <>
    <g style={{filter: GLOW.cyan}}>
      {cyanCells.map(({index, x, y, intensity}) => <rect key={`cell-cyan-${index}`} x={x + 1.2} y={y + 1} width="17.6" height="13" rx="1" fill={C.cyan} fillOpacity={intensity * (0.72 + 0.28 * Math.abs(Math.sin(frame * 0.035 + index * 0.19)))} />)}
    </g>
    <g style={{filter: GLOW.gold}}>
      {goldCells.map(({index, x, y, intensity}) => <rect key={`cell-gold-${index}`} x={x + 1.2} y={y + 1} width="17.6" height="13" rx="1" fill={C.gold} fillOpacity={Math.min(1, intensity + 0.23)} />)}
    </g>
    <g fill="none" stroke={C.white} strokeOpacity="0.22" strokeWidth="1">
      {connections.map(({index, a, b, middleX, middleY}) => <path key={`connection-${index}`} d={`M${a.x + 10} ${a.y + 7.5} Q${middleX} ${middleY} ${b.x + 10} ${b.y + 7.5}`} strokeDasharray="4 7" strokeDashoffset={-frame * (0.15 + (index % 5) * 0.03)} />)}
    </g>
    <rect x="100" y="560" width="800" height="60" fill={C.bg} fillOpacity="0.96" stroke={C.cyan} strokeOpacity="0.24" strokeWidth="1" />
    <text x="118" y="600" fill={C.white} fontFamily={CN} fontSize="22" fontWeight="600">并行变量</text>
    <text x="500" y="600" textAnchor="middle" fill={C.cyan} fontFamily={CN} fontSize="22" fontWeight="600">关联同时点亮</text>
    <text x="500" y="1193" textAnchor="middle" fill={C.white} fillOpacity="0.78" fontFamily={FONT} fontSize="18" letterSpacing="1.4">1,600 CELLS / 40 × 40 / 36 LINKS</text>
  </>;
};

const fitManifold = (frame: number, radius: number, centerY: number) => {
  const source = manifold(frame, 120);
  const extent = Math.max(1, ...source.map(({x, y}) => Math.max(Math.abs(x), Math.abs(y))));
  const scale = radius / extent;
  return source.map(({x, y, z}) => ({x: CX + x * scale, y: centerY + y * scale, z}));
};

const ManifoldScene: React.FC<{frame: number}> = ({frame}) => {
  const points = fitManifold(frame, 220, CY);
  const edges = points.flatMap((point, index) => [1, 17].map((offset) => {
    const next = points[(index + offset) % points.length];
    const localDepth = clamp(0.38 + (point.z + next.z + 3.4) * 0.11, 0.2, 0.8);
    return {index, offset, point, next, opacity: localDepth * (offset === 1 ? 0.88 : 0.48)};
  }));
  const reveal = smooth(clamp(frame / 38));

  return <>
    <text x="500" y="600" textAnchor="middle" fill={C.white} fontFamily={CN} fontSize="24" fontWeight="600">高维流形</text>
    <text x="128" y="936" fill={C.cyan} fontFamily={CN} fontSize="24" fontWeight="600">变量耦合</text>
    <text x="872" y="1002" textAnchor="end" fill={C.cyan} fontFamily={CN} fontSize="24" fontWeight="600">因果轨迹</text>
    <ellipse cx={CX} cy={CY} rx="235" ry="218" fill="rgba(6,182,212,0.035)" stroke={C.cyan} strokeOpacity="0.15" strokeWidth="1" />
    <g opacity={reveal} style={{filter: GLOW.cyan}}>
      {edges.map(({index, offset, point, next, opacity}) => <line key={`manifold-edge-${index}-${offset}`} x1={point.x} y1={point.y} x2={next.x} y2={next.y} stroke={C.cyan} strokeOpacity={opacity} strokeWidth={offset === 1 ? 1.5 : 0.85} />)}
    </g>
    <g opacity={reveal} style={{filter: GLOW.cyan}}>
      {points.map((point, index) => <circle key={`manifold-node-${index}`} cx={point.x} cy={point.y} r={index % 10 === 0 ? 4.1 : 2.7} fill={index % 6 === 0 ? C.white : C.cyan} fillOpacity={clamp(0.46 + (point.z + 2.2) * 0.13, 0.34, 0.98)} />)}
    </g>
    <text x="500" y="1152" textAnchor="middle" fill={C.cyan} fontFamily={FONT} fontSize="19" letterSpacing="2">4D → 3D / PROJECTED CROSS-SECTION</text>
  </>;
};

const OracleScene: React.FC<{frame: number}> = ({frame}) => {
  const points = fitManifold(frame, 175, 760);
  const edges = points.flatMap((point, index) => [1, 17].map((offset) => ({
    point,
    next: points[(index + offset) % points.length],
    index,
    offset,
    opacity: clamp(0.34 + (point.z + 2.2) * 0.11, 0.2, 0.72) * (offset === 1 ? 0.85 : 0.46),
  })));
  const rays = Array.from({length: 20}, (_, index) => {
    const point = points[index * 6];
    const projectionY = 1082 + Math.abs(point.x - CX) * 0.2;
    return {point, projectionY, index};
  });
  const humanNodes = Array.from({length: 7}, (_, index) => {
    const angle = -Math.PI / 2 + index * Math.PI * 2 / 7;
    return {x: CX + Math.cos(angle) * 280, y: 1133 + Math.sin(angle) * 24, index};
  });
  const reveal = smooth(clamp(frame / 34));

  return <>
    <text x="500" y="590" textAnchor="middle" fill={C.gold} fontFamily={CN} fontSize="24" fontWeight="600">十万维因果</text>
    <ellipse cx={CX} cy="760" rx="220" ry="190" fill="rgba(250,204,21,0.045)" stroke={C.gold} strokeOpacity="0.2" strokeDasharray="3 9" />
    <g opacity={reveal} style={{filter: GLOW.gold}}>
      {edges.map(({point, next, index, offset, opacity}) => <line key={`oracle-edge-${index}-${offset}`} x1={point.x} y1={point.y} x2={next.x} y2={next.y} stroke={C.gold} strokeOpacity={opacity} strokeWidth={offset === 1 ? 1.2 : 0.75} />)}
      {points.map((point, index) => <circle key={`oracle-vertex-${index}`} cx={point.x} cy={point.y} r={index % 10 === 0 ? 3.5 : 2.1} fill={index % 5 === 0 ? C.white : C.gold} fillOpacity={clamp(0.48 + (point.z + 2.2) * 0.12, 0.35, 0.94)} />)}
    </g>
    <g opacity={reveal}>
      <path d="M160 1070 L840 1070 L900 1180 L100 1180 Z" fill="rgba(6,25,38,0.72)" stroke={C.cyan} strokeOpacity="0.55" strokeWidth="1.6" style={{filter: GLOW.cyan}} />
      {[1092, 1115, 1140, 1165].map((y) => <line key={`plane-row-${y}`} x1={Math.max(100, 160 - (y - 1070) * 0.54)} y1={y} x2={Math.min(900, 840 + (y - 1070) * 0.54)} y2={y} stroke={C.cyan} strokeOpacity="0.31" strokeWidth="1" />)}
      {[-2, -1, 0, 1, 2].map((offset) => <line key={`plane-ray-${offset}`} x1={CX} y1="1070" x2={CX + offset * 150} y2="1180" stroke={C.cyan} strokeOpacity="0.28" strokeWidth="1" />)}
    </g>
    <g opacity={reveal} style={{filter: GLOW.gold}}>
      {rays.map(({point, projectionY, index}) => <line key={`oracle-ray-${index}`} x1={point.x} y1={point.y + 3} x2={point.x} y2={projectionY} stroke={C.gold} strokeOpacity="0.35" strokeWidth="1" strokeDasharray="3 6" />)}
    </g>
    <g opacity={reveal}>
      {humanNodes.map(({x, y, index}) => <g key={`human-node-${index}`}>
        <circle cx={x} cy={y} r="10" fill={C.amber} fillOpacity="0.28" stroke={C.red} strokeOpacity="0.9" strokeWidth="2" />
        <circle cx={x} cy={y} r="3.4" fill={C.amber} />
      </g>)}
    </g>
    <text x="500" y="1042" textAnchor="middle" fill={C.cyan} fontFamily={CN} fontSize="22" fontWeight="600">人类可接住的答案</text>
    <text x="500" y="1198" textAnchor="middle" fill={C.gold} fontFamily={FONT} fontSize="17" letterSpacing="0.8">[ ORACLE OUTPUT // 1 ANSWER ← 10^5 DIMENSIONS ]</text>
  </>;
};

const EndingScene: React.FC<{frame: number}> = ({frame}) => {
  const reveal = smooth(clamp(frame / 32));
  const orbitMarks = Array.from({length: 9}, (_, index) => {
    const angle = -Math.PI / 2 + index * Math.PI * 2 / 9;
    const inner = 178;
    const outer = 195;
    return {index, x1: CX + Math.cos(angle) * inner, y1: 860 + Math.sin(angle) * inner, x2: CX + Math.cos(angle) * outer, y2: 860 + Math.sin(angle) * outer};
  });
  const drift = Math.sin(frame * 0.025) * 5;

  return <>
    <circle cx={CX} cy="860" r="200" fill="rgba(250,204,21,0.028)" stroke={C.gold} strokeOpacity={0.22 + reveal * 0.58} strokeWidth="1.8" />
    <circle cx={CX} cy="860" r="178" fill="none" stroke={C.amber} strokeOpacity="0.48" strokeWidth="1" strokeDasharray="2 8" />
    <g style={{filter: GLOW.gold}}>
      {orbitMarks.map(({index, x1, y1, x2, y2}) => <line key={`memory-mark-${index}`} x1={x1} y1={y1} x2={x2} y2={y2} stroke={index < 7 ? C.gold : C.red} strokeOpacity={0.58 + reveal * 0.38} strokeWidth="2.5" />)}
      <text x={CX} y={884 + drift} textAnchor="middle" fill={C.gold} fillOpacity={reveal} fontFamily={FONT} fontSize="104" fontWeight="700" letterSpacing="-3">7 ± 2</text>
    </g>
    <text x={CX} y="950" textAnchor="middle" fill={C.white} fillOpacity={reveal * 0.92} fontFamily={CN} fontSize="24" fontWeight="500">有限的工作记忆</text>
    <text x={CX} y="1006" textAnchor="middle" fill={C.gold} fillOpacity={reveal * 0.66} fontFamily={FONT} fontSize="18" letterSpacing="2">WORKING MEMORY / MODEL</text>
  </>;
};

const HookScene: React.FC<{frame: number}> = ({frame}) => {
  const points = Array.from({length: 300}, (_, index) => ({
    x: 100 + seeded(index * 3 + 1) * 800,
    y: 590 + seeded(index * 3 + 2) * 550,
    radius: 1.25 + seeded(index * 3 + 3) * 1.7,
  }));
  const links = points.flatMap((point, index) => [13, 47].map((offset, kind) => {
    const next = points[(index + offset) % points.length];
    return {point, next, index, kind};
  }));
  const rings = Array.from({length: 34}, (_, index) => {
    const point = points[(index * 37) % points.length];
    const phase = (frame * 0.018 + index * 0.173) % 1;
    const radius = 5 + phase * 38;
    return {point, index, phase, radius};
  });

  return <>
    <g style={{filter: GLOW.cyan}}>
      {links.map(({point, next, index, kind}) => {
        const bend = kind === 0 ? -18 : 24;
        const opacity = kind === 0 ? 0.22 : 0.13;
        return <path key={`hook-link-${index}-${kind}`} d={`M${point.x} ${point.y} Q${(point.x + next.x) / 2 + bend} ${(point.y + next.y) / 2 - 22} ${next.x} ${next.y}`} fill="none" stroke={C.cyan} strokeOpacity={opacity} strokeWidth={kind === 0 ? 0.9 : 0.7} strokeDasharray={kind === 0 ? '3 10' : '2 13'} strokeDashoffset={-frame * (kind === 0 ? 0.35 : 0.2)} />;
      })}
    </g>
    <g style={{filter: GLOW.cyan}}>
      {rings.map(({point, index, phase, radius}) => <circle key={`flow-ring-${index}`} cx={point.x} cy={point.y} r={radius} fill="none" stroke={C.cyan} strokeOpacity={(1 - phase) * 0.42} strokeWidth="1.1" />)}
    </g>
    <g>
      {points.map(({x, y, radius}, index) => {
        const pulse = 0.42 + 0.28 * (0.5 + 0.5 * Math.sin(frame * 0.04 + index * 0.81));
        return <circle key={`hook-node-${index}`} cx={x} cy={y} r={radius} fill={index % 11 === 0 ? C.white : C.cyan} fillOpacity={pulse} />;
      })}
    </g>
    <rect x="100" y="560" width="800" height="60" fill={C.bg} fillOpacity="0.94" stroke={C.cyan} strokeOpacity="0.24" strokeWidth="1" />
    <text x="500" y="596" textAnchor="middle" fill={C.cyan} fillOpacity="0.9" fontFamily={FONT} fontSize="18" letterSpacing="1.8">OPTICAL INTERCONNECT / TB/s</text>
  </>;
};

export const PortraitScene: React.FC<PortraitSceneProps> = ({stage, frame}) => {
  const safeFrame = Math.max(0, Math.floor(frame));
  const scene = {
    overload: <OverloadScene frame={safeFrame} />,
    linear: <LinearScene frame={safeFrame} />,
    matrix: <MatrixScene frame={safeFrame} />,
    manifold: <ManifoldScene frame={safeFrame} />,
    oracle: <OracleScene frame={safeFrame} />,
    ending: <EndingScene frame={safeFrame} />,
    hook: <HookScene frame={safeFrame} />,
  }[stage];

  return <PortraitSvg>{scene}</PortraitSvg>;
};
