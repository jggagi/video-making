import React from 'react';
import {useCurrentFrame} from 'remotion';
import {C, CN, FONT, GLOW, SCENE_HEIGHT, SCENE_WIDTH} from '../lib/theme';
import {clamp, seeded, smooth, mix} from '../lib/math';
import {ActLabel} from './Visuals';

const W = SCENE_WIDTH;
const H = SCENE_HEIGHT;
const CX = W / 2;
const CY = H / 2;
const START_ZOOM_FRAME = 1100;
const MATRIX_FULL_FRAME = 1580;

const POINTS = Array.from({length: 80}, (_, index) => {
  const x = 705 + seeded(index + 20) * 920;
  const trendY = 593 - (x - 1165) * 0.31;
  const scatter = (seeded(index + 240) - 0.5) * 228;
  return {
    index,
    x,
    y: clamp(trendY + scatter, 365, 785),
    phase: seeded(index + 480) * Math.PI * 2,
    amplitude: 7 + seeded(index + 850) * 15,
    ignored: index % 20 >= 3,
  };
});

const MATRIX_CELLS = Array.from({length: 1600}, (_, index) => ({
  index,
  column: index % 40,
  row: Math.floor(index / 40),
  phase: seeded(index + 1700) * Math.PI * 2,
  gold: seeded(index + 2900) > 0.9,
}));
const CYAN_CELLS = MATRIX_CELLS.filter((cell) => !cell.gold);
const GOLD_CELLS = MATRIX_CELLS.filter((cell) => cell.gold);

const ARCS = Array.from({length: 144}, (_, index) => {
  const start = (index * 79 + 23) % 1600;
  const end = (start + 600 + Math.floor(seeded(index + 3400) * 800)) % 1600;
  const x1 = ((start % 40) + 0.5) * 48;
  const y1 = (Math.floor(start / 40) + 0.5) * 27;
  const x2 = ((end % 40) + 0.5) * 48;
  const y2 = (Math.floor(end / 40) + 0.5) * 27;
  const bend = (seeded(index + 4100) - 0.5) * 230;
  const bend2 = (seeded(index + 4700) - 0.5) * 210;
  return {
    index,
    path: `M ${x1.toFixed(1)} ${y1.toFixed(1)} C ${(x1 + bend).toFixed(1)} ${(y1 - bend2).toFixed(1)}, ${(x2 - bend).toFixed(1)} ${(y2 + bend2).toFixed(1)}, ${x2.toFixed(1)} ${y2.toFixed(1)}`,
    phase: seeded(index + 5300) * Math.PI * 2,
    gold: seeded(index + 5900) > 0.83,
  };
});
const CYAN_ARCS = ARCS.filter((arc) => !arc.gold);
const GOLD_ARCS = ARCS.filter((arc) => arc.gold);

const LINE_Y = (x: number) => 593 - (x - 1165) * 0.31;

export const Act2LinearVsMatrix: React.FC = () => {
  const frame = useCurrentFrame();
  const zoomProgress = clamp((frame - START_ZOOM_FRAME) / (MATRIX_FULL_FRAME - START_ZOOM_FRAME));
  const easedZoom = smooth(zoomProgress);
  const matrixScale = Math.pow(50, easedZoom) / 50;
  const matrixOpacity = smooth((frame - START_ZOOM_FRAME) / 280);
  const chartScale = Math.pow(0.02, easedZoom);
  const chartOpacity = mix(1, 0.82, easedZoom);
  const labelOpacity = 1 - smooth((frame - 1160) / 320);

  return <div style={{position: 'absolute', inset: 0, overflow: 'hidden', pointerEvents: 'none'}}>
    <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} style={{position: 'absolute', inset: 0}}>
      {matrixOpacity > 0 && <g transform={`translate(${CX} ${CY}) scale(${matrixScale}) translate(${-CX} ${-CY})`} opacity={matrixOpacity}>
        <rect width={W} height={H} fill={C.bg}/>
        <path d="M0 190H1920 M0 930H1920" stroke={C.white} strokeOpacity="0.08"/>
        <g style={{filter: GLOW.cyan}}>
          {CYAN_CELLS.map((cell) => {
            const pulse = 0.5 + 0.5 * Math.sin(frame * 0.032 + cell.phase);
            return <rect key={`cell-${cell.index}`} x={cell.column * 48 + 1.5} y={cell.row * 27 + 1.4}
              width="44.5" height="23.2" rx="1.2" fill={C.cyan} fillOpacity={0.06 + pulse * 0.22}/>;
          })}
        </g>
        <g style={{filter: GLOW.gold}}>
          {GOLD_CELLS.map((cell) => {
            const pulse = 0.5 + 0.5 * Math.sin(frame * 0.032 + cell.phase);
            return <rect key={`cell-${cell.index}`} x={cell.column * 48 + 1.5} y={cell.row * 27 + 1.4}
              width="44.5" height="23.2" rx="1.2" fill={C.gold} fillOpacity={0.06 + pulse * 0.31}/>;
          })}
        </g>
        <g fill="none" strokeWidth="1.15" style={{filter: GLOW.cyan}}>
          {CYAN_ARCS.map((arc) => {
            const pulse = 0.14 + (0.5 + 0.5 * Math.sin(frame * 0.024 + arc.phase)) * 0.23;
            return <path key={`arc-${arc.index}`} d={arc.path} stroke={C.cyan} strokeOpacity={pulse}/>;
          })}
        </g>
        <g fill="none" strokeWidth="1.15" style={{filter: GLOW.gold}}>
          {GOLD_ARCS.map((arc) => {
            const pulse = 0.14 + (0.5 + 0.5 * Math.sin(frame * 0.024 + arc.phase)) * 0.23;
            return <path key={`arc-${arc.index}`} d={arc.path} stroke={C.gold} strokeOpacity={pulse}/>;
          })}
        </g>
      </g>}

      <g transform={`translate(${CX} ${CY}) scale(${chartScale}) translate(${-CX} ${-CY})`}
        opacity={chartOpacity}>
        <g>
          <rect x="650" y="304" width="1055" height="516" fill={C.bg} fillOpacity="0.25" stroke={C.cyan} strokeOpacity="0.25"/>
          {Array.from({length: 6}, (_, i) => {
            const x = 650 + i * 211;
            return <line key={`vgrid-${i}`} x1={x} y1="304" x2={x} y2="820" stroke={C.white} strokeOpacity="0.075"/>;
          })}
          {Array.from({length: 5}, (_, i) => {
            const y = 304 + i * 129;
            return <line key={`hgrid-${i}`} x1="650" y1={y} x2="1705" y2={y} stroke={C.white} strokeOpacity="0.075"/>;
          })}
          <path d="M680 785H1685 M680 785V332" fill="none" stroke={C.white} strokeOpacity="0.42" strokeWidth="1.2"/>
          <text x="1688" y="808" fill={C.muted} fontFamily={FONT} fontSize="11" letterSpacing="2">X / INPUT VARIABLES</text>
          <text x="665" y="324" fill={C.muted} fontFamily={FONT} fontSize="11" letterSpacing="2">Y / OBSERVED OUTCOME</text>
          <path d={`M700 ${LINE_Y(700)} L1645 ${LINE_Y(1645)}`} fill="none" stroke={C.amber} strokeWidth="3" strokeOpacity="0.92" style={{filter: GLOW.gold}}/>
          <path d={`M700 ${LINE_Y(700)} L1645 ${LINE_Y(1645)}`} fill="none" stroke={C.amber} strokeWidth="15" strokeOpacity="0.1"/>
          <g transform="translate(1360 330)">
            <path d="M0 0H302V108H0Z" fill="#0c1421" fillOpacity="0.92" stroke={C.amber} strokeOpacity="0.5"/>
            <text x="18" y="25" fill={C.amber} fontFamily={FONT} fontSize="11" letterSpacing="1.5">FORCED LINEAR MODEL</text>
            <text x="18" y="57" fill={C.white} fontFamily={FONT} fontSize="19">y = kx + b</text>
            <text x="18" y="84" fill={C.muted} fontFamily={FONT} fontSize="11">68 / 80 POINTS REJECTED AS NOISE</text>
          </g>

          {POINTS.map((point) => {
            const drift = Math.sin(frame * 0.017 + point.phase) * point.amplitude;
            const crossDrift = Math.cos(frame * 0.014 + point.phase * 0.83) * point.amplitude * 0.62;
            const x = point.x + drift;
            const y = point.y + crossDrift;
            const color = point.ignored ? '#718096' : C.amber;
            const isLabelled = point.ignored && [4, 19, 33, 51, 67].includes(point.index);
            return <g key={`point-${point.index}`}>
              <circle cx={x} cy={y} r={point.ignored ? 4.2 : 5.2} fill={color} fillOpacity={point.ignored ? 0.64 : 0.95}/>
              <circle cx={x} cy={y} r={point.ignored ? 9 : 11} fill={color} fillOpacity="0.09"/>
              {isLabelled && <g opacity="0.78">
                <path d={`M${x + 6} ${y - 4}l22 -15`} stroke={C.muted} strokeOpacity="0.75"/>
                <text x={x + 31} y={y - 20} fill={C.muted} fontFamily={FONT} fontSize="9" letterSpacing="0.5">NOISE {String(point.index + 1).padStart(2, '0')}</text>
              </g>}
            </g>;
          })}

          <g transform="translate(701 727)">
            <rect width="407" height="34" rx="2" fill="#09101a" fillOpacity="0.9" stroke={C.muted} strokeOpacity="0.32"/>
            <circle cx="15" cy="17" r="4" fill={C.muted}/>
            <text x="29" y="21" fill="#98a3b0" fontFamily={CN} fontSize="9.5" letterSpacing="0.15">
              [被忽略的离群点：归因为偶然与巧合]
            </text>
          </g>
          <text x="1233" y="786" fill={C.amber} fillOpacity="0.8" fontFamily={FONT} fontSize="10" letterSpacing="1.5">RIGID FIT / HIGH RESIDUAL ERROR</text>
        </g>
      </g>
    </svg>

    <div style={{position: 'absolute', inset: 0, opacity: labelOpacity}}>
      <div style={{filter: GLOW.cyan}}>
        <ActLabel number="ACT 02" title="二维直线的认知拐杖" kicker="LINEAR FIT → 40×40 MATRIX" color={C.cyan}/>
      </div>
    </div>

    {frame >= START_ZOOM_FRAME && <div style={{position: 'absolute', right: 106, bottom: 178, opacity: matrixOpacity, textAlign: 'right'}}>
      <div style={{fontFamily: FONT, color: C.cyan, fontSize: 11, letterSpacing: 2, filter: GLOW.cyan}}>SELF-ATTENTION / 40 × 40 VIEW</div>
      <div style={{fontFamily: FONT, color: C.gold, fontSize: 10, letterSpacing: 1.4, marginTop: 8, filter: GLOW.gold}}>100,000+ COUPLED VARIABLES · ZERO PRUNING</div>
    </div>}
  </div>;
};
