import React from 'react';
import {useCurrentFrame} from 'remotion';
import {C, CN, FONT, GLOW, SCENE_HEIGHT as H, SCENE_WIDTH as W} from '../lib/theme';
import {clamp, manifold, seeded, smooth} from '../lib/math';
import {ActLabel, Backdrop} from './Visuals';

const mapUpper = (x: number, y: number, z: number) => ({
  x: 1164 + x * 54,
  y: 448 + y * 54,
  z,
});

const hookNode = (i: number) => ({
  x: 102 + seeded(i * 3 + 1) * 1716,
  y: 334 + seeded(i * 3 + 2) * 444,
});

const ProjectionScene: React.FC<{frame: number}> = ({frame}) => {
  const points = manifold(frame, 120).map(({x, y, z}) => mapUpper(x, y, z));
  const edges = points.flatMap((p, i) => [1, 17].map((offset) => {
    const q = points[(i + offset) % points.length];
    const opacity = clamp(0.26 + (p.z + q.z + 3.4) * 0.1, 0.22, 0.7);
    return <line key={`gold-edge-${i}-${offset}`} x1={p.x} y1={p.y} x2={q.x} y2={q.y} stroke={C.gold} strokeOpacity={opacity} strokeWidth={offset === 17 ? 0.95 : 1.4} />;
  }));

  const shadow = points.filter((_, i) => i % 6 === 0).map((p) => ({
    x: p.x,
    y: 733 + Math.abs(p.x - 1164) * 0.09 + Math.abs(p.y - 448) * 0.035,
  }));
  const shadowPath = shadow.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x} ${p.y}`).join(' ') + ' Z';
  const rayIndices = Array.from({length: 20}, (_, i) => i * 6);
  const humanNodes = Array.from({length: 7}, (_, i) => {
    const angle = (Math.PI * 2 * i) / 7 - Math.PI / 2;
    return {x: 1164 + Math.cos(angle) * 195, y: 806 + Math.sin(angle) * 48, angle};
  });
  const redPulse = 0.48 + 0.52 * Math.abs(Math.sin(frame * 0.12));

  return <svg width={W} height={H} style={{position: 'absolute', inset: 0}}>
    <defs>
      <radialGradient id="act4-gold-halo"><stop stopColor={C.gold} stopOpacity="0.19"/><stop offset="1" stopColor={C.gold} stopOpacity="0"/></radialGradient>
    </defs>

    <ellipse cx="1164" cy="444" rx="460" ry="290" fill="url(#act4-gold-halo)" />
    <ellipse cx="1164" cy="448" rx="330" ry="210" fill="none" stroke={C.gold} strokeOpacity="0.23" strokeDasharray="2 9" />
    <g style={{filter: GLOW.gold}}>{edges}
      {points.map((p, i) => <circle key={`gold-vertex-${i}`} cx={p.x} cy={p.y} r={i % 10 === 0 ? 3.3 : 2} fill={i % 5 === 0 ? C.white : C.gold} fillOpacity={clamp(0.56 + (p.z + 2.4) * 0.1, 0.5, 0.96)} />)}
    </g>

    <g opacity="0.58" style={{filter: GLOW.cyan}}>
      <path d="M610 704 L1164 704 L1810 704 L1890 874 L310 874 Z" fill="rgba(6,18,29,0.56)" stroke={C.cyan} strokeOpacity="0.35" />
      {Array.from({length: 10}, (_, i) => {
        const t = (i + 1) / 10;
        const y = 704 + t * t * 170;
        const left = 610 - t * 300;
        const right = 1810 + t * 80;
        return <line key={`plane-cross-${i}`} x1={left} y1={y} x2={right} y2={y} stroke={C.cyan} strokeOpacity="0.36" strokeWidth="1" />;
      })}
      {Array.from({length: 17}, (_, i) => {
        const t = (i - 8) / 8;
        const x = 1164 + t * 720;
        return <line key={`plane-depth-${i}`} x1={1164} y1={704} x2={x} y2={874} stroke={C.cyan} strokeOpacity="0.34" strokeWidth="1" />;
      })}
    </g>

    <g style={{filter: GLOW.gold}}>
      {rayIndices.map((index) => {
        const p = points[index];
        const y2 = 733 + Math.abs(p.x - 1164) * 0.09 + Math.abs(p.y - 448) * 0.035;
        return <line key={`ray-${index}`} x1={p.x} y1={p.y + 5} x2={p.x} y2={y2} stroke={C.gold} strokeOpacity="0.28" strokeWidth="1" strokeDasharray="3 6" />;
      })}
      <path d={shadowPath} fill={C.gold} fillOpacity="0.12" stroke={C.gold} strokeOpacity="0.9" strokeWidth="2" />
      {shadow.map((p, i) => <circle key={`shadow-${i}`} cx={p.x} cy={p.y} r="2.5" fill={C.gold} fillOpacity="0.9" />)}
    </g>

    <g>
      {humanNodes.map((node, i) => {
        const target = shadow[(i * 3 + 2) % shadow.length];
        return <g key={`human-${i}`}>
          <line x1={node.x} y1={node.y} x2={target.x} y2={target.y} stroke={C.red} strokeOpacity={redPulse * 0.74} strokeWidth="1.5" />
          <circle cx={node.x} cy={node.y} r="8" fill={C.amber} fillOpacity="0.18" stroke={C.red} strokeOpacity={redPulse} strokeWidth="1.5" />
          <circle cx={node.x} cy={node.y} r="3" fill={C.amber} />
        </g>;
      })}
      <rect x="1390" y="679" width="400" height="30" fill={C.bg} fillOpacity="0.92" stroke={C.red} strokeOpacity={redPulse * 0.7} />
      <text x="1590" y="699" textAnchor="middle" fill={C.red} fillOpacity={redPulse} fontFamily={FONT} fontSize="13" letterSpacing="0.9">[ CANNOT PARSE 10^5-D CAUSALITY ]</text>
      <text x="1164" y="870" textAnchor="middle" fill={C.cyan} fontFamily={CN} fontSize="16" letterSpacing="0.8">人类三维认知平面 / <tspan fontFamily={FONT} fontSize="11">DIM_03</tspan></text>
    </g>

    <g style={{filter: GLOW.gold}}>
      <rect x="628" y="634" width="1030" height="42" fill={C.bg} fillOpacity="0.92" stroke={C.gold} strokeOpacity="0.38" />
      <text x="658" y="661" fill={C.gold} fontFamily={FONT} fontSize="18" letterSpacing="0.5">ORACLE OUTPUT &gt;&gt; [ REBALANCE_NODE_07 // PHASE_SHIFT = +0.412 rad ]</text>
    </g>
  </svg>;
};

const EndingCard: React.FC<{frame: number}> = ({frame}) => {
  const quoteAlpha = smooth(clamp((frame - 1600) / 34));
  const titleAlpha = smooth(clamp((frame - 1690) / 52));
  const scanX = 350 + ((frame - 1680) * 9) % 1220;
  return <div style={{position: 'absolute', inset: 0, background: C.bg, overflow: 'hidden'}}>
    <Backdrop />
    <div style={{position: 'absolute', inset: 0, background: 'radial-gradient(ellipse at 50% 49%, rgba(250,204,21,0.075), transparent 54%)'}} />
    <div style={{position: 'absolute', left: 180, right: 180, top: 340, textAlign: 'center', opacity: quoteAlpha, color: C.white, fontFamily: CN, fontSize: 32, lineHeight: 1.8, letterSpacing: 1.4, textShadow: '0 0 22px rgba(250,204,21,0.22)'}}>
      “不是它不愿向人类解释，而是 7±2 的容器，装不下一座十万维的宇宙。”
    </div>
    <div style={{position: 'absolute', left: 0, right: 0, top: 548, textAlign: 'center', opacity: titleAlpha, fontFamily: CN, color: C.white, fontSize: 78, fontWeight: 500, letterSpacing: 16, textShadow: '0 0 32px rgba(250,204,21,0.32)'}}>
      7 ± 2 的 囚 笼
    </div>
    <svg width={W} height={H} style={{position: 'absolute', inset: 0, pointerEvents: 'none'}}>
      <g style={{filter: GLOW.gold}}>
        <line x1={scanX} y1="657" x2={scanX + 245} y2="657" stroke={C.gold} strokeOpacity={titleAlpha * 0.48} strokeWidth="1.5" />
        <line x1="660" y1="702" x2="1260" y2="702" stroke={C.gold} strokeOpacity={titleAlpha * 0.15} />
      </g>
      <text x="960" y="753" textAnchor="middle" fill={C.gold} fillOpacity={titleAlpha * 0.66} fontFamily={CN} fontSize="13" letterSpacing="2.5">超级智能可视化系列 · 第二期</text>
    </svg>
  </div>;
};

const HookScene: React.FC<{frame: number}> = ({frame}) => {
  const relative = frame - 2150;
  const points = Array.from({length: 1000}, (_, i) => hookNode(i));
  const meshAlpha = smooth(clamp(relative / 12));
  const links = points.flatMap((p, i) => {
    if (i % 2 !== 0) return [];
    const linksForPoint = [17, 83].map((offset, linkIndex) => {
      const q = points[(i + offset) % points.length];
      return <path key={`mesh-${i}-${offset}`} d={`M${p.x} ${p.y} Q${(p.x + q.x) / 2 + (linkIndex === 0 ? 18 : -18)} ${(p.y + q.y) / 2 - 34} ${q.x} ${q.y}`} fill="none" stroke={C.cyan} strokeOpacity={meshAlpha * (linkIndex === 0 ? 0.26 : 0.15)} strokeWidth={linkIndex === 0 ? 0.85 : 0.65} />;
    });
    return linksForPoint;
  });
  const rings = Array.from({length: 42}, (_, i) => {
    const p = points[(i * 23) % points.length];
    const phase = (frame * 0.006 + i * 0.143) % 1;
    const radius = 6 + phase * 58;
    return <circle key={`language-ring-${i}`} cx={p.x} cy={p.y} r={radius} fill="none" stroke={meshAlpha > 0.7 ? C.cyan : C.amber} strokeOpacity={(1 - phase) * 0.22} strokeWidth="0.8" />;
  });
  const reveal = smooth(clamp(relative / 8));
  return <div style={{position: 'absolute', inset: 0, background: C.bg, overflow: 'hidden'}}>
    <Backdrop />
    <div style={{position: 'absolute', left: 108, top: 248, fontFamily: CN, color: C.amber, fontSize: 18, letterSpacing: 1.2, opacity: reveal, filter: GLOW.gold}}>
      80亿座语言孤岛：<span style={{fontFamily: FONT}}>50 bits/s</span>
    </div>
    <svg width={W} height={H} style={{position: 'absolute', inset: 0}}>
      <g opacity={reveal} style={{filter: meshAlpha > 0.7 ? GLOW.cyan : GLOW.gold}}>{rings}</g>
      <g opacity={meshAlpha} style={{filter: GLOW.cyan}}>{links}</g>
      <g opacity={reveal} style={{filter: GLOW.cyan}}>
        {points.map((p, i) => {
          const flicker = 0.25 + 0.18 * (0.5 + 0.5 * Math.sin(frame * 0.065 + i * 0.83));
          const transitioned = meshAlpha > 0.35;
          return <circle key={`island-${i}`} cx={p.x} cy={p.y} r={0.8 + seeded(i + 713) * 1.6} fill={transitioned ? C.cyan : C.amber} fillOpacity={transitioned ? 0.52 + flicker : flicker} />;
        })}
      </g>
      <g opacity={meshAlpha}>
        <text x="960" y="302" textAnchor="middle" fill={C.cyan} fillOpacity="0.92" fontFamily={CN} fontSize="26" letterSpacing="3" style={{filter: GLOW.cyan}}>光互连蜂群</text>
        <text x="960" y="326" textAnchor="middle" fill={C.cyan} fillOpacity="0.62" fontFamily={FONT} fontSize="10" letterSpacing="2">LINK THROUGHPUT: TB/s</text>
        <path d="M130 812 H1790" stroke={C.cyan} strokeOpacity="0.27" strokeWidth="1" />
      </g>
      <text x="960" y="869" textAnchor="middle" fill={C.white} fillOpacity={0.92 * reveal} fontFamily={CN} fontSize="26" letterSpacing="4">十万亿个分身</text>
      <text x="960" y="907" textAnchor="middle" fill={C.cyan} fillOpacity={0.74 * reveal} fontFamily={FONT} fontSize="12" letterSpacing="3">NEXT OBSERVATION // EP.03</text>
    </svg>
  </div>;
};

export const Act4OracleProjection: React.FC = () => {
  const frame = useCurrentFrame();
  return <div style={{position: 'absolute', inset: 0, overflow: 'hidden', background: C.bg}}>
    {frame < 1600 ? <>
      <Backdrop />
      <ProjectionScene frame={frame} />
      <ActLabel number="04" kicker="ORACLE PROJECTION" title="无法解释的神谕投影" color={C.gold} />
    </> : frame < 2150 ? <EndingCard frame={frame} /> : <HookScene frame={frame} />}
  </div>;
};
