import React from 'react';
import {useCurrentFrame} from 'remotion';
import {ActLabel} from './Visuals';
import {C, FONT} from '../lib/theme';
import {clamp, ease, fmt, mix, progress, rotate4, seeded, type Vec4} from '../lib/math';

export type Act3ManifoldEdge = readonly [from: number, to: number, axis: 0 | 1 | 2 | 3];
export type Act3ProjectedPoint = {x: number; y: number; depth: number};

const X_LEVELS = [-1.5, -0.5, 0.5, 1.5] as const;
const Y_LEVELS = [-1.5, -0.5, 0.5, 1.5] as const;
const Z_LEVELS = [-1, 1] as const;
const W_LEVELS = [-1, 1] as const;

const vertexIndex = (x: number, y: number, z: number, w: number) => ((x * 4 + y) * 2 + z) * 2 + w;

export const ACT3_MANIFOLD_VERTICES: readonly Vec4[] = X_LEVELS.flatMap((x) =>
  Y_LEVELS.flatMap((y) => Z_LEVELS.flatMap((z) => W_LEVELS.map((w) => [x, y, z, w] as Vec4))),
);

export const ACT3_MANIFOLD_EDGES: readonly Act3ManifoldEdge[] = (() => {
  const edges: Act3ManifoldEdge[] = [];
  for (let x = 0; x < 4; x += 1) {
    for (let y = 0; y < 4; y += 1) {
      for (let z = 0; z < 2; z += 1) {
        for (let w = 0; w < 2; w += 1) {
          const from = vertexIndex(x, y, z, w);
          if (x < 3) edges.push([from, vertexIndex(x + 1, y, z, w), 0]);
          if (y < 3) edges.push([from, vertexIndex(x, y + 1, z, w), 1]);
          if (z < 1) edges.push([from, vertexIndex(x, y, z + 1, w), 2]);
          if (w < 1) edges.push([from, vertexIndex(x, y, z, w + 1), 3]);
        }
      }
    }
  }
  return edges;
})();

const CENTER_X = 1275;
const CENTER_Y = 620;
const ROTATION_LOCK_FRAME = 2580;

/** Deterministically rotates a lattice vertex in 4D, then applies two perspective projections. */
export const projectAct3Vertex = (vertex: Vec4, frame: number): Act3ProjectedPoint => {
  const t = clamp(Math.min(frame, ROTATION_LOCK_FRAME), 0, ROTATION_LOCK_FRAME) / 60;
  let rotated = rotate4(vertex, 2, 3, 0.18 + t * 0.38); // ZW
  rotated = rotate4(rotated, 0, 1, -0.24 + t * 0.23); // XY
  rotated = rotate4(rotated, 0, 3, 0.12 + t * 0.16); // XW

  const perspective4 = 6 / (6 - rotated[3]);
  const x3 = rotated[0] * perspective4;
  const y3 = rotated[1] * perspective4;
  const z3 = rotated[2] * perspective4;
  const perspective3 = 7 / (7 - z3);
  return {
    x: CENTER_X + x3 * perspective3 * 150,
    y: CENTER_Y + y3 * perspective3 * 70,
    depth: z3,
  };
};

export const CODE_LINES = [
  'import Mathlib.Data.Real.Basic',
  'import Mathlib.Analysis.SpecialFunctions.Pow.Real',
  'namespace Pulse.Invariant',
  'variable (H : Hamiltonian n)',
  'def orbit (x : State) := iterate H.step x',
  'theorem energy_conserved :',
  '  H.energy (H.step s) = H.energy s := by',
  '  simp [Hamiltonian.step, symplectic_map]',
  '  exact determinant_one H.flow',
  'lemma bounded_error (eps : ℝ) :',
  '  ‖estimate - exact‖ ≤ eps := by',
  '  rw [norm_le_iff_sq_le_sq]',
  '  nlinarith [rounding_bound eps]',
  'end Pulse.Invariant',
  'template <typename State, int N>',
  '__global__ void evolve(State* x, float dt) {',
  '  const int i = blockIdx.x * blockDim.x +',
  '              threadIdx.x;',
  '  if (i < N) x[i] = symplectic_step(x[i], dt);',
  '}',
  'static_assert(sizeof(State) == 32);',
  '// verify: conservation, bounds, replay',
  'CHECK(hamiltonian.energy(next) == energy);',
  'CHECK(max_residual(trace) < 1.0e-9);',
  'proof_term := kernel_refines_spec;',
  'by_cases h : stable (trajectory t)',
  '· exact preserve_invariant h',
  '· have := step_decreases_residual h',
  '  omega',
  'simp_all [finite_precision_model]',
  'theorem no_escape : ∀ k, state k ∈ Ω := by',
  '  induction k with | zero => exact init_in Ω',
  '  | succ k ih => exact step_closed ih',
  '#pragma unroll 4',
  'for (int axis = 0; axis < 4; ++axis) {',
  '  rotate_pair(v, plane[axis], theta[axis]);',
  '}',
  'assert(norm(v) <= certified_radius);',
  'certificate.verify(checkpoint_8400000);',
  '▶ reducing symbolic state space…',
] as const;

export const TERMINAL_COMMAND = 'EXECUTE_PULSE(theta=42.198401, B=14.2T)';
const AXIS_COLORS = [C.cyan, '#4bdcf2', '#a6f5ff', C.white] as const;

const CodeWaterfall: React.FC<{frame: number}> = ({frame}) => {
  const lineHeight = 20;
  const scroll = frame * 4.25;
  const firstLine = Math.floor(scroll / lineHeight);
  const offset = scroll % lineHeight;
  const rows = Math.ceil(410 / lineHeight) + 2;

  return (
    <div style={{
      position: 'absolute', left: 94, top: 390, width: 546, height: 410, overflow: 'hidden',
      border: `1px solid ${C.line}`, borderRadius: 8,
      background: 'linear-gradient(135deg, rgba(8,18,31,0.96), rgba(5,8,17,0.88))',
      boxShadow: 'inset 0 0 38px rgba(6,182,212,0.045)',
    }}>
      <div style={{position: 'absolute', inset: 0, overflow: 'hidden', opacity: 0.8}}>
        {Array.from({length: rows}, (_, row) => {
          const lineNumber = firstLine + row;
          const line = CODE_LINES[lineNumber % CODE_LINES.length];
          const color = line.startsWith('theorem') || line.startsWith('lemma') || line.startsWith('def ')
            ? C.cyan
            : line.includes('CHECK') || line.includes('assert') ? C.gold : '#91a7bc';
          return (
            <div key={`${lineNumber}-${row}`} style={{
              position: 'absolute', left: 14, top: row * lineHeight - offset,
              display: 'grid', gridTemplateColumns: '32px 1fr', columnGap: 12,
              height: lineHeight, alignItems: 'center', whiteSpace: 'pre',
              font: `12px/1 ${FONT}`, color, textShadow: '0 0 10px rgba(6,182,212,0.1)',
            }}>
              <span style={{color: 'rgba(120,137,158,0.45)', textAlign: 'right'}}>{fmt((lineNumber % 840) + 1)}</span>
              <span>{line}</span>
            </div>
          );
        })}
        <div style={{position: 'absolute', inset: 0, background: 'linear-gradient(180deg, rgba(5,8,17,0.2), transparent 18%, transparent 76%, rgba(5,8,17,0.75))'}} />
      </div>

      {frame < 300 ? (
        <div style={{
          position: 'absolute', left: 24, top: 147, width: 496, height: 108,
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
          borderTop: `1px solid ${C.red}`, borderBottom: `1px solid ${C.red}`,
          background: 'rgba(13,8,15,0.9)', boxShadow: `0 0 36px rgba(239,68,68,${0.08 + 0.1 * (0.5 + 0.5 * Math.sin(frame / 3))})`,
          opacity: 0.78 + 0.22 * (0.5 + 0.5 * Math.sin(frame / 3)),
          fontFamily: FONT,
        }}>
          <span style={{fontSize: 11, letterSpacing: 3, color: C.red}}>HUMAN WORKING MEMORY</span>
          <span style={{fontSize: 36, lineHeight: '42px', fontWeight: 700, color: '#fff1f2', letterSpacing: 2}}>7 ± 2</span>
          <span style={{fontSize: 10, letterSpacing: 2.4, color: '#fca5a5'}}>CHUNK CEILING / 5—9</span>
        </div>
      ) : (
        <div style={{position: 'absolute', left: 24, top: 147, width: 496, height: 108, fontFamily: FONT, pointerEvents: 'none'}}>
          {['HUMAN', '7 ± 2', 'MEMORY', 'LIMIT'].map((piece, index) => {
            const dx = (seeded(index * 7 + 3) - 0.5) * 260 * ease(frame, 300, 390);
            const dy = (seeded(index * 7 + 4) - 0.5) * 130 * ease(frame, 300, 390);
            const spin = (seeded(index * 7 + 5) - 0.5) * 46 * ease(frame, 300, 390);
            const positions = [
              {left: 55, top: 25, fontSize: 13},
              {left: 184, top: 28, fontSize: 36},
              {left: 307, top: 63, fontSize: 12},
              {left: 346, top: 18, fontSize: 11},
            ];
            const pos = positions[index];
            return <span key={piece} style={{
              position: 'absolute', ...pos, color: C.red, fontWeight: 700, letterSpacing: 2,
              transform: `translate(${dx}px, ${dy}px) rotate(${spin}deg)`,
              opacity: 1 - ease(frame, 315, 410), textShadow: '0 0 14px rgba(239,68,68,0.6)',
            }}>{piece}</span>;
          })}
          {Array.from({length: 7}, (_, shard) => {
            const startX = 22 + shard * 65;
            const dx = (seeded(shard + 31) - 0.5) * 280 * ease(frame, 300, 382);
            const dy = (seeded(shard + 47) - 0.5) * 135 * ease(frame, 300, 382);
            return <i key={shard} style={{
              position: 'absolute', left: startX, top: 52, width: 36 + seeded(shard + 71) * 24, height: 1,
              background: C.red, opacity: (1 - ease(frame, 310, 390)) * 0.85,
              transform: `translate(${dx}px, ${dy}px) rotate(${(seeded(shard + 89) - 0.5) * 24}deg)`,
            }} />;
          })}
          <span style={{
            position: 'absolute', left: 78, bottom: -2, width: 340, textAlign: 'center',
            color: C.amber, fontSize: 10, letterSpacing: 2,
            opacity: ease(frame, 325, 380),
          }}>COMPREHENSION EXCEEDED</span>
        </div>
      )}
    </div>
  );
};

export const Act3DepthManifold: React.FC = () => {
  const frame = clamp(useCurrentFrame(), 0, 2699);
  const collapse = ease(frame, 2200, 2580);
  const points = ACT3_MANIFOLD_VERTICES.map((vertex) => projectAct3Vertex(vertex, frame));
  const collapsedPoints = points.map((point) => ({
    x: mix(point.x, CENTER_X, collapse),
    y: mix(point.y, CENTER_Y, collapse),
    depth: mix(point.depth, 0, collapse),
  }));
  const pathByAxis = ['', '', '', ''];
  for (const [from, to, axis] of ACT3_MANIFOLD_EDGES) {
    const a = collapsedPoints[from];
    const b = collapsedPoints[to];
    pathByAxis[axis] += `M${a.x.toFixed(2)},${a.y.toFixed(2)}L${b.x.toFixed(2)},${b.y.toFixed(2)}`;
  }
  const allPaths = pathByAxis.join(' ');
  const depthCount = Math.floor(8_400_000 * progress(frame, 0, 2699));
  const depthProgress = progress(frame, 0, 2699);
  const commandProgress = ease(frame, 2260, 2590);
  const visibleCommand = TERMINAL_COMMAND.slice(0, Math.floor(TERMINAL_COMMAND.length * commandProgress));
  const geometryOpacity = 1 - collapse;

  return (
    <div data-act3-depth-manifold="true" data-shatter-frame="300" style={{position: 'absolute', inset: 0, fontFamily: FONT, color: C.white}}>
      <ActLabel number="03" title="Deeper than intuition." kicker="DEPTH / FORMAL VERIFICATION" color={C.cyan} />

      <div style={{position: 'absolute', left: 94, top: 345, color: C.muted, fontSize: 11, letterSpacing: 2.2}}>
        FORMAL TRACE <span style={{color: C.cyan}}>／</span> MODEL CHECK
      </div>
      <div style={{position: 'absolute', right: 94, top: 345, color: C.muted, fontSize: 11, letterSpacing: 2.2, textAlign: 'right'}}>
        4-SPACE ROTATION <span style={{color: C.cyan}}>ZW · XY · XW</span>
      </div>
      <CodeWaterfall frame={frame} />

      <div style={{position: 'absolute', left: 94, top: 813, color: C.muted, fontSize: 11, letterSpacing: 1.7}}>
        VERIFIED DEPTH <span style={{color: C.white, fontSize: 15, fontWeight: 700}}>{fmt(depthCount)}</span>
        <span style={{color: C.muted}}> / 8,400,000</span>
      </div>
      <div style={{position: 'absolute', left: 94, top: 841, width: 546, height: 2, background: 'rgba(120,137,158,0.2)'}}>
        <div style={{width: `${depthProgress * 100}%`, height: '100%', background: `linear-gradient(90deg, ${C.cyan}, ${C.gold})`, boxShadow: '0 0 12px rgba(6,182,212,0.6)'}} />
      </div>
      <div style={{position: 'absolute', left: 94, top: 854, color: C.muted, fontSize: 10, letterSpacing: 1.8}}>
        {frame < 300 ? 'HUMAN THROUGHPUT BOUND' : frame < 2200 ? 'MACHINE VERIFICATION CONTINUES' : 'SOLUTION CONVERGING'}
      </div>

      <div style={{position: 'absolute', left: 700, top: 368, color: C.muted, fontSize: 11, letterSpacing: 2}}>
        64 VERTICES <span style={{color: C.cyan}}>·</span> 160 ADJACENT EDGES
      </div>
      <div style={{position: 'absolute', right: 94, top: 368, color: C.muted, fontSize: 10, letterSpacing: 1.5, textAlign: 'right'}}>
        4×4×2×2 LATTICE
      </div>

      <svg width="1920" height="1080" viewBox="0 0 1920 1080" style={{position: 'absolute', inset: 0, pointerEvents: 'none'}} aria-hidden="true">
        <defs>
          <linearGradient id="act3-point" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="#fff6bf" />
            <stop offset="0.45" stopColor={C.gold} />
            <stop offset="1" stopColor="#dd8a12" />
          </linearGradient>
          <radialGradient id="act3-point-halo">
            <stop stopColor={C.gold} stopOpacity="0.92" />
            <stop offset="0.18" stopColor={C.gold} stopOpacity="0.35" />
            <stop offset="1" stopColor={C.gold} stopOpacity="0" />
          </radialGradient>
          <filter id="act3-shared-glow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="3" result="soft" />
            <feMerge><feMergeNode in="soft" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
          <clipPath id="act3-manifold-clip"><rect x="680" y="390" width="1160" height="475" rx="14" /></clipPath>
        </defs>

        <g clipPath="url(#act3-manifold-clip)" opacity={geometryOpacity}>
          <ellipse cx={CENTER_X} cy={CENTER_Y} rx="414" ry="198" fill="none" stroke={C.cyan} strokeOpacity="0.11" strokeDasharray="2 10" transform={`rotate(-18 ${CENTER_X} ${CENTER_Y})`} />
          <ellipse cx={CENTER_X} cy={CENTER_Y} rx="360" ry="112" fill="none" stroke="#6cecff" strokeOpacity="0.11" strokeDasharray="7 9" transform={`rotate(27 ${CENTER_X} ${CENTER_Y})`} />
          <ellipse cx={CENTER_X} cy={CENTER_Y} rx="158" ry="286" fill="none" stroke={C.cyan} strokeOpacity="0.08" strokeDasharray="3 12" transform={`rotate(31 ${CENTER_X} ${CENTER_Y})`} />
          <path d={allPaths} fill="none" stroke={C.cyan} strokeOpacity="0.22" strokeWidth="4.4" strokeLinejoin="round" filter="url(#act3-shared-glow)" />
          {pathByAxis.map((path, axis) => <path
            key={axis}
            d={path}
            fill="none"
            stroke={AXIS_COLORS[axis]}
            strokeOpacity={0.42 - axis * 0.045}
            strokeWidth={axis === 3 ? 1.35 : 1.7}
            strokeLinecap="square"
            strokeLinejoin="miter"
          />)}
          {collapsedPoints.map((point, index) => {
            const depthScale = clamp(0.58 + point.depth * 0.08, 0.35, 1.2);
            return <circle
              key={index}
              cx={point.x}
              cy={point.y}
              r={1.65 * depthScale}
              fill={index % 4 === 0 ? C.white : C.cyan}
              opacity={0.65 + clamp(point.depth * 0.08, 0, 0.25)}
            />;
          })}
        </g>

        <g opacity={ease(frame, 2140, 2280)}>
          <rect x="735" y="850" width="1080" height="48" rx="7" fill="rgba(7,12,20,0.94)" stroke={C.gold} strokeOpacity="0.48" />
          <circle cx="758" cy="874" r="4" fill={C.gold} />
          <text x="1275" y="880" textAnchor="middle" fill={C.gold} fontFamily={FONT} fontSize="18" letterSpacing="0.5">
            {visibleCommand}
          </text>
        </g>

        <g opacity={ease(frame, 2470, 2660)}>
          <circle cx={CENTER_X} cy={CENTER_Y} r={14 + collapse * 2} fill="url(#act3-point-halo)" />
          <circle cx={CENTER_X} cy={CENTER_Y} r={2.5 + collapse * 3.5} fill="url(#act3-point)" />
          <circle cx={CENTER_X} cy={CENTER_Y} r="1.4" fill="#fffde8" />
        </g>
      </svg>

      <div style={{position: 'absolute', left: 700, top: 818, color: C.muted, fontSize: 10, letterSpacing: 1.6, opacity: 1 - collapse}}>
        MANIFOLD PROJECTION <span style={{color: C.cyan}}>→ 3D → 2D</span>
      </div>
      <div style={{position: 'absolute', left: 94, top: 903, width: 1732, height: 2, background: 'rgba(120,137,158,0.2)'}}>
        <div style={{width: `${progress(frame, 0, 2699) * 100}%`, height: '100%', background: C.cyan, boxShadow: '0 0 8px rgba(6,182,212,0.65)'}} />
      </div>
      <div style={{position: 'absolute', left: 94, top: 912, fontSize: 9, letterSpacing: 2, color: C.muted}}>
        ACT 03 <span style={{color: C.cyan}}>／</span> DEPTH PROOF <span style={{marginLeft: 12, color: C.white}}>{String(Math.min(100, Math.floor(progress(frame, 0, 2699) * 100))).padStart(3, '0')}%</span>
      </div>
    </div>
  );
};
