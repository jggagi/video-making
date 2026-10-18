import React from 'react';
import {AbsoluteFill} from 'remotion';
import {C, CN, FONT, GLOW} from '../lib/theme';
import {manifold} from '../lib/math';

export const XHSCover: React.FC = () => {
  const points = manifold(360, 120).map((p) => ({x: 605 + p.x * 74, y: 850 + p.y * 74}));
  const nodes = Array.from({length: 9}, (_, i) => {
    const a = i / 9 * Math.PI * 2 - Math.PI / 2;
    return {x: 370 + Math.cos(a) * 220, y: 885 + Math.sin(a) * 190};
  });
  return <AbsoluteFill style={{background: C.bg, overflow: 'hidden'}}>
    <div lang="zh-CN" style={{position: 'absolute', width: 1080, height: 1440, transform: 'scale(2)', transformOrigin: '0 0', fontFamily: CN, color: C.white}}>
      <div style={{position: 'absolute', inset: 0, background: 'radial-gradient(ellipse at 60% 58%, rgba(6,182,212,.14), transparent 65%)'}}/>
      <div style={{position: 'absolute', left: 86, top: 112, fontFamily: FONT, fontSize: 22, letterSpacing: 2.5, color: C.cyan}}>COGNITION / EP.02</div>
      <div style={{position: 'absolute', left: 82, top: 208, fontSize: 100, fontWeight: 650, lineHeight: 1.2, letterSpacing: -2}}>
        第<span style={{color: C.gold, filter: GLOW.gold}}>10</span>个变量<br/>大脑就过载？
      </div>
      <div style={{position: 'absolute', left: 87, top: 497, fontSize: 34, letterSpacing: 1, color: '#b8c6d2'}}>用60秒，走进7±2的囚笼</div>
      <svg width="1080" height="1440" viewBox="0 0 1080 1440" style={{position: 'absolute', inset: 0}}>
        <defs><radialGradient id="cover-gold"><stop stopColor={C.gold} stopOpacity=".35"/><stop offset="1" stopColor={C.gold} stopOpacity="0"/></radialGradient></defs>
        <circle cx="350" cy="880" r="320" fill="url(#cover-gold)"/>
        <g style={{filter: GLOW.cyan}}>
          {points.map((p, i) => {
            const q = points[(i + 17) % points.length];
            const t = points[(i + 1) % points.length];
            return <g key={i}><path d={`M${p.x} ${p.y}L${q.x} ${q.y}M${p.x} ${p.y}L${t.x} ${t.y}`} fill="none" stroke={C.cyan} strokeWidth="1.5" strokeOpacity=".75"/><circle cx={p.x} cy={p.y} r="2.4" fill={C.cyan}/></g>;
          })}
        </g>
        <g style={{filter: GLOW.gold}}>
          {nodes.flatMap((p, i) => nodes.slice(i + 1).map((q, j) => <line key={`${i}-${j}`} x1={p.x} y1={p.y} x2={q.x} y2={q.y} stroke={C.gold} strokeWidth="1.5" strokeOpacity=".3"/>))}
          {nodes.map((p, i) => <circle key={i} cx={p.x} cy={p.y} r="18" fill={C.gold}/>)}
        </g>
        <circle cx="370" cy="885" r="28" fill={C.red}/>
        <path d="M350 875l40 26m-41 -12l27 26m-9 -42l23 14" stroke={C.red} strokeWidth="6" strokeLinecap="round"/>
      </svg>
      <div style={{position: 'absolute', left: 87, top: 1190, color: C.white, fontSize: 36, fontWeight: 500, lineHeight: 1.6}}>我们接住了答案，<br/>却装不下全部因果。</div>
      <div style={{position: 'absolute', left: 87, top: 1358, fontSize: 20, color: C.muted, letterSpacing: 1}}>超级智能思想实验 · 概念可视化</div>
    </div>
  </AbsoluteFill>;
};
