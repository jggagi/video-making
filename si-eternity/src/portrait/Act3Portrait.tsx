import React from 'react';
import {useCurrentFrame} from 'remotion';
import {
  ACT3_MANIFOLD_EDGES,
  ACT3_MANIFOLD_VERTICES,
  CODE_LINES,
  projectAct3Vertex,
  TERMINAL_COMMAND,
} from '../components/Act3DepthManifold';
import {clamp, ease, fmt, mix, progress, seeded} from '../lib/math';
import {C, FONT} from '../lib/theme';
import {PortraitHeading, PortraitPanel, PORTRAIT_FONT} from './PortraitElements';

const SOURCE_CENTER_X = 1275;
const SOURCE_CENTER_Y = 620;
const PORTRAIT_CENTER_X = 520;
const PORTRAIT_CENTER_Y = 1050;
const PROJECTION_SCALE = 0.85;
const ROTATION_LOCK_FRAME = 2580;
const CODE_LINE_HEIGHT = 28;
const CODE_SCROLL_PER_FRAME = (CODE_LINE_HEIGHT * 4.25) / 20;
const CODE_VIEW_HEIGHT = 244;
const AXIS_COLORS = [C.cyan, '#4bdcf2', '#a6f5ff', C.white] as const;

const MemoryLimitGlass: React.FC<{frame: number}> = ({frame}) => {
  if (frame >= 370) return null;
  if (frame < 300) return <div style={{position: 'absolute', left: 40, top: 76, width: 800, height: 156, display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', border: '1px solid rgba(239,68,68,0.6)', borderRadius: 12, background: 'linear-gradient(130deg, rgba(15,16,27,0.94), rgba(20,12,22,0.94))', boxShadow: '0 0 32px rgba(239,68,68,0.14)', color: C.white, fontFamily: PORTRAIT_FONT}}>
    <span style={{fontSize: 26, letterSpacing: 4, color: '#fca5a5'}}>工作记忆</span>
    <span style={{fontFamily: FONT, fontSize: 54, lineHeight: 1.2, fontWeight: 600, color: '#fff1f2', textShadow: '0 0 18px rgba(239,68,68,0.35)'}}>7±2</span>
  </div>;

  const scatter = ease(frame, 300, 370);
  const fade = 1 - scatter;
  const textPieces = [
    {text: '工作', left: 296, top: 100},
    {text: '记忆', left: 398, top: 100},
    {text: '7±2', left: 512, top: 90},
  ];
  return <div style={{position: 'absolute', inset: 0, pointerEvents: 'none'}}>
    {Array.from({length: 12}, (_, index) => {
      const left = 86 + (index % 4) * 174;
      const top = 82 + Math.floor(index / 4) * 48;
      const dx = (seeded(index + 31) - 0.5) * 260 * scatter;
      const dy = (seeded(index + 47) - 0.5) * 180 * scatter;
      const rotate = (seeded(index + 71) - 0.5) * 54 * scatter;
      return <i key={`shard-${index}`} style={{position: 'absolute', left, top, width: 42 + seeded(index + 91) * 42, height: 2, background: index % 3 === 0 ? C.red : C.cyan, opacity: fade * 0.75, transform: `translate(${dx}px, ${dy}px) rotate(${rotate}deg)`, boxShadow: '0 0 12px rgba(239,68,68,0.35)'}} />;
    })}
    {textPieces.map(({text, left, top}, index) => {
      const dx = (seeded(index + 7) - 0.5) * 190 * scatter;
      const dy = (seeded(index + 19) - 0.5) * 150 * scatter;
      const rotate = (seeded(index + 37) - 0.5) * 22 * scatter;
      return <span key={text} style={{position: 'absolute', left, top, color: index === 2 ? '#fff1f2' : '#fca5a5', fontFamily: index === 2 ? FONT : PORTRAIT_FONT, fontWeight: 600, fontSize: index === 2 ? 54 : 26, opacity: fade, transform: `translate(${dx}px, ${dy}px) rotate(${rotate}deg)`, textShadow: '0 0 14px rgba(239,68,68,0.55)'}}>{text}</span>;
    })}
  </div>;
};

export const Act3Portrait: React.FC = () => {
  const frame = clamp(useCurrentFrame(), 0, 2699);
  const codeScroll = frame * CODE_SCROLL_PER_FRAME;
  const firstLine = Math.floor(codeScroll / CODE_LINE_HEIGHT);
  const lineOffset = codeScroll % CODE_LINE_HEIGHT;
  const codeRows = Math.ceil(CODE_VIEW_HEIGHT / CODE_LINE_HEIGHT) + 2;
  const depthCount = Math.floor(8_400_000 * progress(frame, 0, 2699));
  const collapse = ease(frame, 2200, ROTATION_LOCK_FRAME);
  const geometryOpacity = 1 - collapse;
  const projectedPoints = ACT3_MANIFOLD_VERTICES.map((vertex) => {
    const point = projectAct3Vertex(vertex, frame);
    const x = PORTRAIT_CENTER_X + (point.x - SOURCE_CENTER_X) * PROJECTION_SCALE;
    const y = PORTRAIT_CENTER_Y + (point.y - SOURCE_CENTER_Y) * PROJECTION_SCALE;
    return {x: mix(x, PORTRAIT_CENTER_X, collapse), y: mix(y, PORTRAIT_CENTER_Y, collapse), depth: mix(point.depth, 0, collapse)};
  });
  const pathByAxis = ['', '', '', ''];
  for (const [from, to, axis] of ACT3_MANIFOLD_EDGES) {
    const a = projectedPoints[from];
    const b = projectedPoints[to];
    pathByAxis[axis] += `M${a.x.toFixed(2)},${a.y.toFixed(2)}L${b.x.toFixed(2)},${b.y.toFixed(2)}`;
  }
  const allPaths = pathByAxis.join(' ');
  const pointReveal = ease(frame, 2470, ROTATION_LOCK_FRAME);
  const commandProgress = ease(frame, 2260, 2590);
  const visibleCommand = TERMINAL_COMMAND.slice(0, Math.floor(TERMINAL_COMMAND.length * commandProgress));
  const commaIndex = TERMINAL_COMMAND.indexOf(',');
  const commandLineOne = visibleCommand.slice(0, commaIndex + 1);
  const commandLineTwo = visibleCommand.length > commaIndex + 1 ? visibleCommand.slice(commaIndex + 1).trimStart() : '';
  const codePhase = frame < 300 ? '工作记忆达到上限' : frame < 2200 ? '形式化验证继续' : frame < ROTATION_LOCK_FRAME ? '解空间正在收束' : '参数已锁定';

  return <div style={{position: 'absolute', inset: 0, color: C.white, fontFamily: FONT}}>
    <PortraitHeading index="03" title="直觉之外，继续向下" kicker="DEPTH / VERIFICATION" />

    <PortraitPanel top={470} height={330}>
      <div style={{position: 'absolute', left: 18, top: 14, right: 18, height: CODE_VIEW_HEIGHT, overflow: 'hidden', background: 'linear-gradient(135deg, rgba(8,18,31,0.92), rgba(5,8,17,0.72))'}}>
        {Array.from({length: codeRows}, (_, row) => {
          const lineNumber = firstLine + row;
          const line = CODE_LINES[lineNumber % CODE_LINES.length];
          const color = line.startsWith('theorem') || line.startsWith('lemma') || line.startsWith('def ')
            ? C.cyan
            : line.includes('CHECK') || line.includes('assert') ? C.gold : '#a4b6ca';
          return <div key={`${lineNumber}-${row}`} style={{position: 'absolute', left: 12, top: row * CODE_LINE_HEIGHT - lineOffset, height: CODE_LINE_HEIGHT, display: 'grid', gridTemplateColumns: '46px 1fr', columnGap: 14, alignItems: 'center', whiteSpace: 'pre', font: `22px/${CODE_LINE_HEIGHT}px ${FONT}`, color, textShadow: '0 0 10px rgba(6,182,212,0.12)'}}>
            <span style={{color: 'rgba(120,137,158,0.58)', textAlign: 'right'}}>{fmt((lineNumber % 840) + 1)}</span>
            <span>{line}</span>
          </div>;
        })}
        <div style={{position: 'absolute', inset: 0, pointerEvents: 'none', background: 'linear-gradient(180deg, rgba(5,8,17,0.25), transparent 14%, transparent 78%, rgba(5,8,17,0.56))'}} />
      </div>

      <div style={{position: 'absolute', left: 18, right: 18, bottom: 10, height: 54, display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderTop: `1px solid ${C.line}`, paddingTop: 5}}>
        <span style={{fontFamily: PORTRAIT_FONT, color: C.cyan, fontSize: 28}}>已验证深度</span>
        <span style={{fontFamily: FONT, color: C.white, fontSize: 34, fontVariantNumeric: 'tabular-nums'}}>{fmt(depthCount)} <small style={{fontSize: 20, color: C.muted}}>/ 8,400,000</small></span>
      </div>
      <MemoryLimitGlass frame={frame} />
    </PortraitPanel>

    <PortraitPanel top={830} height={460} accent={C.gold}>
      <div style={{position: 'absolute', left: 18, top: 12, right: 18, display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: C.muted, fontFamily: PORTRAIT_FONT, fontSize: 22}}>
        <span style={{color: C.cyan}}>64 顶点 · 160 条边</span>
        <span style={{color: frame >= ROTATION_LOCK_FRAME ? C.gold : C.muted}}>{codePhase}</span>
      </div>
      <svg width="880" height="460" viewBox="80 830 880 460" style={{position: 'absolute', inset: 0}} aria-hidden="true">
        <defs>
          <radialGradient id="portrait-manifold-halo">
            <stop stopColor={C.gold} stopOpacity="0.88" />
            <stop offset="0.2" stopColor={C.gold} stopOpacity="0.33" />
            <stop offset="1" stopColor={C.gold} stopOpacity="0" />
          </radialGradient>
          <filter id="portrait-manifold-glow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="2.5" />
          </filter>
        </defs>
        <g opacity={geometryOpacity}>
          <ellipse cx={PORTRAIT_CENTER_X} cy={PORTRAIT_CENTER_Y} rx="355" ry="174" fill="none" stroke={C.cyan} strokeOpacity="0.1" strokeDasharray="3 12" transform={`rotate(-18 ${PORTRAIT_CENTER_X} ${PORTRAIT_CENTER_Y})`} />
          <ellipse cx={PORTRAIT_CENTER_X} cy={PORTRAIT_CENTER_Y} rx="305" ry="104" fill="none" stroke="#6cecff" strokeOpacity="0.1" strokeDasharray="8 10" transform={`rotate(27 ${PORTRAIT_CENTER_X} ${PORTRAIT_CENTER_Y})`} />
          <path d={allPaths} fill="none" stroke={C.cyan} strokeOpacity="0.22" strokeWidth="4" strokeLinejoin="round" filter="url(#portrait-manifold-glow)" />
          {pathByAxis.map((path, axis) => <path
            key={`axis-${axis}`}
            d={path}
            fill="none"
            stroke={AXIS_COLORS[axis]}
            strokeOpacity={0.46 - axis * 0.05}
            strokeWidth={axis === 3 ? 1.4 : 1.8}
            strokeLinecap="square"
            strokeLinejoin="miter"
          />)}
          {projectedPoints.map((point, index) => {
            const depthScale = clamp(0.58 + point.depth * 0.08, 0.35, 1.2);
            return <circle key={`vertex-${index}`} cx={point.x} cy={point.y} r={1.8 * depthScale} fill={index % 4 === 0 ? C.white : C.cyan} opacity={0.68 + clamp(point.depth * 0.08, 0, 0.25)} />;
          })}
        </g>
        <g opacity={pointReveal}>
          <circle cx={PORTRAIT_CENTER_X} cy={PORTRAIT_CENTER_Y} r="36" fill="url(#portrait-manifold-halo)" />
          <circle cx={PORTRAIT_CENTER_X} cy={PORTRAIT_CENTER_Y} r="5.5" fill={C.gold} />
          <circle cx={PORTRAIT_CENTER_X} cy={PORTRAIT_CENTER_Y} r="2" fill="#fffde8" />
        </g>
      </svg>
    </PortraitPanel>

    <PortraitPanel top={1300} height={80} accent={C.gold}>
      <div style={{position: 'absolute', left: 18, top: 0, height: 80, display: 'flex', alignItems: 'center', color: C.muted, fontFamily: PORTRAIT_FONT, fontSize: 20, whiteSpace: 'nowrap'}}>执行指令</div>
      <div style={{position: 'absolute', left: 152, top: 10, right: 12, color: C.gold, fontFamily: FONT, fontSize: 22, lineHeight: '28px', letterSpacing: 0.1, whiteSpace: 'nowrap', textShadow: '0 0 12px rgba(250,204,21,0.18)'}}>
        <div>{commandLineOne || (frame >= 2200 ? '收束中…' : '')}</div>
        <div>{commandLineTwo}</div>
      </div>
    </PortraitPanel>
  </div>;
};

export default Act3Portrait;
