import React from 'react';
import {interpolate} from 'remotion';
import {C, FONT} from '../lib/theme';
import {ease, mix} from '../lib/math';

export const PORTRAIT_WIDTH = 1080;
export const PORTRAIT_HEIGHT = 1920;
export const PORTRAIT_FONT = '"PingFang SC", "Hiragino Sans GB", sans-serif';
export const openingTitleOpacity = (frame: number) => interpolate(frame, [60, 105, 300, 360], [0, 1, 1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});

export const PortraitHeading: React.FC<{index: string; title: string; kicker: string; color?: string; opacity?: number}> = ({index, title, kicker, color = C.cyan, opacity = 1}) => <div style={{position: 'absolute', left: 80, top: 340, width: 880, opacity}}>
  <div style={{fontFamily: FONT, fontSize: 20, letterSpacing: 3, color}}>{index} / {kicker}</div>
  <div style={{fontFamily: PORTRAIT_FONT, fontSize: 50, fontWeight: 400, letterSpacing: 2, color: C.white, marginTop: 14}}>{title}</div>
</div>;

export const PortraitPanel: React.FC<{top: number; height: number; children: React.ReactNode; accent?: string}> = ({top, height, children, accent = C.cyan}) => <div style={{position: 'absolute', left: 80, top, width: 880, height, overflow: 'hidden', border: `1px solid ${C.line}`, borderRadius: 12, background: `radial-gradient(ellipse at 50% 35%, ${accent}0a, transparent 80%), rgba(5,8,17,0.86)`}}>{children}</div>;

export const PortraitOpeningTitle: React.FC<{frame: number}> = ({frame}) => <div style={{position: 'absolute', left: 80, top: 660, width: 880, opacity: openingTitleOpacity(frame), textAlign: 'center', color: C.white}}>
  <div style={{fontFamily: PORTRAIT_FONT, fontSize: 88, fontWeight: 300, lineHeight: 1.3, letterSpacing: interpolate(frame, [60, 360], [16, 36], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}), whiteSpace: 'pre', textShadow: '0 0 30px rgba(6,182,212,0.5)'}}>一 眼 万 年</div>
  <div style={{fontFamily: FONT, fontSize: 28, color: C.cyan, letterSpacing: '0.3em', lineHeight: 2, marginTop: 34}}>ONE BLINK,<br/>TEN MILLENNIA</div>
  <div style={{fontFamily: FONT, fontSize: 28, color: C.amber, lineHeight: 1.9, marginTop: 30}}>[ Δt_atom = 0.30s ]<br/>[ Δt_bit = 10^4 Years ]</div>
</div>;

export const PortraitEndingTitle: React.FC<{frame: number}> = ({frame}) => {
  const quote = ease(frame, 3300, 3340);
  const title = ease(frame, 3340, 3420);
  const scanX = mix(170, 870, ease(frame, 3420, 3570));
  const laser = ease(frame, 3420, 3430) * (1 - ease(frame, 3570, 3599));
  return <div style={{position: 'absolute', inset: 0, backgroundColor: C.bg, textAlign: 'center'}}>
    <div style={{position: 'absolute', left: 80, top: 490, width: 880, fontFamily: PORTRAIT_FONT, color: C.white, fontSize: 40, fontWeight: 300, lineHeight: 1.8, letterSpacing: 3, opacity: quote}}>人类眨眼一瞬，<br/>硅基已历万年。</div>
    <div style={{position: 'absolute', left: 80, top: 760, width: 880, height: 140, display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: PORTRAIT_FONT, fontSize: 96, fontWeight: 300, color: C.white, letterSpacing: 18, whiteSpace: 'pre', opacity: title, textShadow: '0 0 30px rgba(6,182,212,0.3)'}}>一 眼 万 年</div>
    <div style={{position: 'absolute', left: 80, top: 985, width: 880, fontFamily: FONT, fontSize: 23, color: C.cyan, letterSpacing: '0.3em', lineHeight: 2, opacity: title}}>ONE BLINK,<br/>TEN MILLENNIA</div>
    <svg width="1080" height="1920" style={{position: 'absolute', inset: 0, opacity: laser}}><defs><linearGradient id="portrait-end-laser"><stop stopColor={C.cyan} stopOpacity="0"/><stop offset="1" stopColor={C.cyan}/></linearGradient></defs><line x1={Math.max(170, scanX - 120)} y1="830" x2={scanX} y2="830" stroke={C.cyan} strokeWidth="10" strokeOpacity="0.10"/><line x1={Math.max(170, scanX - 120)} y1="830" x2={scanX} y2="830" stroke="url(#portrait-end-laser)" strokeWidth="2"/><circle cx={scanX} cy="830" r="4" fill={C.white}/></svg>
  </div>;
};
