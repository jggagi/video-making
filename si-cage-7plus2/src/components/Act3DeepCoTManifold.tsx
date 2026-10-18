import React from 'react';
import {useCurrentFrame} from 'remotion';
import {C, CN, FONT, GLOW, SCENE_HEIGHT as H, SCENE_WIDTH as W} from '../lib/theme';
import {clamp, fade, manifold, seeded} from '../lib/math';
import {ActLabel, Backdrop} from './Visuals';

const CX = 1240;
const CY = 570;

const proofLines = [
  '∂L/∂θ = Σᵢ (∂L/∂yᵢ)(∂yᵢ/∂θ)',
  'J(x) = ∂f(x) / ∂x  ∈ ℝⁿˣⁿ',
  'det(J) ≠ 0  ⇒  local inverse exists',
  'P(A | B,C) = P(B | A,C)P(A | C) / P(B | C)',
  '∇·F = ∂Fₓ/∂x + ∂Fᵧ/∂y + ∂F𝓏/∂z',
  'limₙ→∞  Σₖ₌₁ⁿ 1/k² = π²/6',
  'rank(AB) ≤ min(rank(A), rank(B))',
  '∮∂Ω F · dr = ∬Ω (∇×F) · n dS',
];

const projectManifoldPoint = (x: number, y: number, z: number) => ({
  x: 1120 + x * 76,
  y: 562 + y * 76,
  z,
});

const ringPoints = (scale: number) => Array.from({length: 8}, (_, i) => {
  const angle = (Math.PI * 2 * i) / 8 - Math.PI / 8;
  return `${CX + Math.cos(angle) * scale},${CY + Math.sin(angle) * scale * 0.7}`;
}).join(' ');

const TunnelFlight: React.FC<{frame: number}> = ({frame}) => {
  const rings = Array.from({length: 22}, (_, i) => {
    const t = (frame * 0.008 + i / 22) % 1;
    const depth = Math.pow(t, 2.15);
    const scale = 14 + depth * 1530;
    const opacity = clamp(0.12 + (1 - t) * 0.53, 0.1, 0.66);
    return <polygon key={`ring-${i}`} points={ringPoints(scale)} fill="none" stroke={i % 4 === 0 ? C.white : C.cyan} strokeOpacity={opacity} strokeWidth={i % 4 === 0 ? 1.4 : 1} />;
  });

  const rails = Array.from({length: 8}, (_, i) => {
    const angle = (Math.PI * 2 * i) / 8 - Math.PI / 8;
    const x = CX + Math.cos(angle) * 930;
    const y = CY + Math.sin(angle) * 650;
    return <line key={`rail-${i}`} x1={CX} y1={CY} x2={x} y2={y} stroke={C.cyan} strokeOpacity="0.16" strokeWidth="1" />;
  });

  const fractureAge = frame - 154;
  const fragments = Array.from({length: 28}, (_, i) => {
    const angle = seeded(i + 71) * Math.PI * 2;
    const speed = 0.75 + seeded(i + 203) * 1.8;
    const distance = Math.max(0, fractureAge) * speed;
    const x1 = CX + Math.cos(angle) * (74 + distance);
    const y1 = CY + Math.sin(angle) * (46 + distance * 0.66);
    const x2 = x1 + Math.cos(angle + 0.7) * (12 + seeded(i + 313) * 24);
    const y2 = y1 + Math.sin(angle + 0.7) * (10 + seeded(i + 409) * 18);
    return <line key={`fracture-${i}`} x1={x1} y1={y1} x2={x2} y2={y2} stroke={i % 3 === 0 ? C.red : C.amber} strokeOpacity={clamp(1 - fractureAge / 190)} strokeWidth={i % 4 === 0 ? 2 : 1} />;
  });

  const stepRows = [
    {label: 'STEP 10,000', at: 260, x: 1050, y: 376, color: C.cyan},
    {label: 'STEP 500,000', at: 510, x: 1270, y: 482, color: C.white},
    {label: 'STEP 5,000,000', at: 760, x: 1020, y: 682, color: C.cyan},
  ];

  return <svg width={W} height={H} style={{position: 'absolute', inset: 0}}>
    <defs>
      <linearGradient id="act3-beam" x1="0" x2="1"><stop offset="0" stopColor={C.cyan} stopOpacity="0"/><stop offset="0.48" stopColor={C.cyan} stopOpacity="0.88"/><stop offset="1" stopColor={C.white} stopOpacity="0.12"/></linearGradient>
    </defs>
    <ellipse cx={CX} cy={CY} rx="810" ry="490" fill={C.cyan} fillOpacity="0.035" />
    <g style={{filter: GLOW.cyan}}>{rails}{rings}</g>
    <path d={`M${CX - 490} ${CY} L${CX + 700} ${CY}`} stroke="url(#act3-beam)" strokeWidth="12" strokeOpacity="0.3" style={{filter: GLOW.cyan}} />
    <path d={`M${CX - 250} ${CY} L${CX + 680} ${CY}`} stroke={C.white} strokeOpacity="0.78" strokeWidth="2" />
    <path d={`M${CX} ${CY - 3} L${CX + 700} ${CY - 3}`} stroke={C.cyan} strokeOpacity="0.82" strokeWidth="3" />

    {frame < 270 && <g opacity={clamp(1 - Math.max(0, frame - 132) / 96)} style={{filter: GLOW.gold}}>
      <ellipse cx={CX} cy={CY} rx="115" ry="76" fill="none" stroke={C.amber} strokeWidth="3" strokeOpacity="0.92" />
      <ellipse cx={CX} cy={CY} rx="101" ry="67" fill="none" stroke={C.amber} strokeWidth="1" strokeOpacity="0.48" />
      <rect x={CX - 191} y={CY - 136} width="382" height="28" fill={C.bg} fillOpacity="0.88" />
      <text x={CX} y={CY - 116} textAnchor="middle" fill={C.amber} fontFamily={CN} fontSize="16" letterSpacing="0.5">人类因果视界 / STEP_04</text>
    </g>}
    {fractureAge >= 0 && fractureAge < 230 && <g>{fragments}</g>}

    {stepRows.map(({label, at, x, y, color}) => {
      const enter = fade(frame, at, 24);
      const hold = label === 'STEP 5,000,000' ? 1 : clamp((at + 250 - frame) / 34);
      const opacity = enter * hold;
      return <g key={label} opacity={opacity} style={{filter: color === C.cyan ? GLOW.cyan : undefined}}>
        <line x1={CX - 100} y1={CY} x2={x - 18} y2={y - 8} stroke={color} strokeOpacity="0.36" strokeDasharray="4 8" />
        <circle cx={x - 18} cy={y - 14} r="3" fill={color} />
        <text x={x} y={y} fill={color} fontFamily={FONT} fontSize="23" fontWeight="600" letterSpacing="1.6">{label}</text>
        <text x={x} y={y + 26} fill={C.white} fillOpacity="0.62" fontFamily={FONT} fontSize="12" letterSpacing="2">PASSED · NO DECAY</text>
      </g>;
    })}

    {[0, 1].map((column) => proofLines.map((line, i) => {
      const y = 386 + ((i * 89 - frame * (0.32 + column * 0.08) + 760) % 760);
      const x = column === 0 ? 118 : 1500;
      const opacity = clamp(Math.min((y - 352) / 110, (886 - y) / 100)) * 0.55;
      return <text key={`proof-${column}-${i}`} x={x} y={y} fill={column === 0 ? C.muted : C.cyan} fillOpacity={opacity} fontFamily={FONT} fontSize="13" letterSpacing="0.4">{line}</text>;
    }))}
    <text x="118" y="842" fill={C.cyan} fillOpacity="0.7" fontFamily={FONT} fontSize="12" letterSpacing="2">FORMAL PROOF / JACOBIAN TRACE</text>
    <text x="1500" y="842" fill={C.cyan} fillOpacity="0.7" fontFamily={FONT} fontSize="12" letterSpacing="2">CAUSAL DEPTH → ∞</text>
  </svg>;
};

const ManifoldView: React.FC<{frame: number}> = ({frame}) => {
  const points = manifold(frame, 120).map(({x, y, z}) => projectManifoldPoint(x, y, z));
  const edges = points.flatMap((p, i) => [1, 17].map((offset, edgeType) => {
    const q = points[(i + offset) % points.length];
    const opacity = clamp(0.18 + (p.z + q.z + 3.4) * 0.12, 0.16, 0.65);
    const accent = edgeType === 1;
    return <line key={`edge-${i}-${offset}`} x1={p.x} y1={p.y} x2={q.x} y2={q.y} stroke={accent ? C.white : C.cyan} strokeOpacity={opacity * (accent ? 0.72 : 1)} strokeWidth={accent ? 0.85 : 1.15} />;
  }));
  const brightEdges = Array.from({length: 12}, (_, k) => {
    const i = k * 10;
    const p = points[i];
    const q = points[(i + 17) % points.length];
    return <line key={`bright-${i}`} x1={p.x} y1={p.y} x2={q.x} y2={q.y} stroke={C.cyan} strokeOpacity="0.55" strokeWidth="3" />;
  });
  const labels = [
    {index: 4, text: '太平洋温跃层', dx: 138, dy: -84, align: 'start' as const},
    {index: 34, text: 'ASML 光刻胶纯度', dx: -158, dy: -78, align: 'end' as const},
    {index: 64, text: '联邦基金期货', dx: -166, dy: 88, align: 'end' as const},
    {index: 94, text: '全球算力相变', dx: 146, dy: 90, align: 'start' as const},
  ];
  const reveal = clamp(frame / 56);

  return <svg width={W} height={H} style={{position: 'absolute', inset: 0}}>
    <defs>
      <radialGradient id="act3-manifold-halo"><stop stopColor={C.cyan} stopOpacity="0.16"/><stop offset="1" stopColor={C.cyan} stopOpacity="0"/></radialGradient>
    </defs>
    <ellipse cx="1120" cy="562" rx="520" ry="370" fill="url(#act3-manifold-halo)" opacity={reveal} />
    <g opacity={reveal} style={{filter: GLOW.cyan}}>{edges}{brightEdges}
      {points.map((p, i) => <circle key={`vertex-${i}`} cx={p.x} cy={p.y} r={i % 10 === 0 ? 3.4 : 2.15} fill={i % 7 === 0 ? C.white : C.cyan} fillOpacity={clamp(0.48 + (p.z + 2.4) * 0.13, 0.42, 0.98)} />)}
    </g>
    <g opacity={reveal} style={{filter: GLOW.cyan}}>
      {labels.map(({index, text, dx, dy, align}) => {
        const p = points[index];
        const tx = p.x + dx;
        const ty = p.y + dy;
        const x2 = tx + (align === 'start' ? -9 : 9);
        return <g key={text}>
          <path d={`M${p.x} ${p.y} L${x2} ${ty - 5}`} fill="none" stroke={C.cyan} strokeOpacity="0.62" strokeWidth="1" />
          <circle cx={p.x} cy={p.y} r="5" fill={C.bg} stroke={C.white} strokeWidth="1.5" />
          <text x={tx} y={ty} textAnchor={align} fill={C.white} stroke={C.bg} strokeWidth="4" paintOrder="stroke" fontFamily={CN} fontSize="16" letterSpacing="1">{text}</text>
          <text x={tx} y={ty + 20} textAnchor={align} fill={C.cyan} fillOpacity="0.76" fontFamily={FONT} fontSize="10" letterSpacing="1.2">VARIABLE // {String(index + 1).padStart(3, '0')}</text>
        </g>;
      })}
    </g>
    <text x="1120" y="855" textAnchor="middle" fill={C.cyan} fillOpacity="0.82" fontFamily={CN} fontSize="17" letterSpacing="1.4">10万余个耦合变量 · 单一连续流形</text>
    <text x="1120" y="879" textAnchor="middle" fill={C.white} fillOpacity="0.44" fontFamily={FONT} fontSize="10" letterSpacing="2.5">PROJECTED CROSS-SECTION / 4D ROTATION LOCKED TO FRAME</text>
  </svg>;
};

export const Act3DeepCoTManifold: React.FC = () => {
  const frame = useCurrentFrame();
  const inManifold = frame >= 1300;
  return <div style={{position: 'absolute', inset: 0, overflow: 'hidden', background: C.bg}}>
    <Backdrop />
    {inManifold ? <ManifoldView frame={frame - 1300} /> : <TunnelFlight frame={frame} />}
    {frame < 1600 && <ActLabel number="03" kicker="DEEP CHAIN OF THOUGHT" title={inManifold ? '高维流形的秩序' : '超越人类的因果视界'} color={C.cyan} />}
  </div>;
};
