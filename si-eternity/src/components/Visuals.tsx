import React from 'react';
import {C, FONT} from '../lib/theme';

export const Backdrop: React.FC<{frame: number; accent?: string}> = ({frame, accent = C.cyan}) => (
  <svg width="1920" height="1080" viewBox="0 0 1920 1080" style={{position: 'absolute', inset: 0}}>
    <defs>
      <pattern id="void-grid" width="64" height="64" patternUnits="userSpaceOnUse"><path d="M64 0H0V64" fill="none" stroke="rgba(255,255,255,0.03)" strokeWidth="1" /></pattern>
      <radialGradient id="void-halo"><stop stopColor={accent} stopOpacity="0.075"/><stop offset="1" stopColor={C.bg} stopOpacity="0"/></radialGradient>
    </defs>
    <rect width="1920" height="1080" fill={C.bg}/><rect width="1920" height="1080" fill="url(#void-grid)"/>
    <ellipse cx={1150 + Math.sin(frame / 400) * 100} cy="500" rx="950" ry="650" fill="url(#void-halo)"/>
    <path d="M64 222V204H82 M1838 204H1856V222 M64 894V912H82 M1838 912H1856V894" fill="none" stroke={C.muted} strokeOpacity="0.4"/>
  </svg>
);

export const ActLabel: React.FC<{number: string; title: string; kicker: string; color?: string}> = ({number, title, kicker, color = C.cyan}) => (
  <div style={{position: 'absolute', left: 94, top: 224, fontFamily: FONT}}>
    <div style={{fontSize: 14, letterSpacing: 4, color, marginBottom: 12}}>{number} / {kicker}</div>
    <div style={{fontSize: 43, fontWeight: 600, color: C.white, letterSpacing: -1.8, lineHeight: 1.1}}>{title}</div>
  </div>
);

export const Droplet: React.FC<{x: number; y: number; scale?: number; opacity?: number; id?: string}> = ({x, y, scale = 1, opacity = 1, id = 'drop'}) => (
  <g transform={`translate(${x} ${y}) scale(${scale})`} opacity={opacity}>
    <defs>
      <radialGradient id={`${id}-body`} cx="33%" cy="28%" r="75%"><stop stopColor="#fff3c4" stopOpacity="0.95"/><stop offset="0.28" stopColor={C.amber} stopOpacity="0.8"/><stop offset="0.75" stopColor="#713a0c" stopOpacity="0.38"/><stop offset="1" stopColor="#fcd34d" stopOpacity="0.88"/></radialGradient>
      <radialGradient id={`${id}-halo`}><stop stopColor={C.amber} stopOpacity="0.17"/><stop offset="1" stopColor={C.amber} stopOpacity="0"/></radialGradient>
    </defs>
    <circle r="110" cy="10" fill={`url(#${id}-halo)`}/>
    <path d="M0 -60 C-4 -31 -36 -7 -36 19 C-36 67 36 67 36 19 C36 -7 4 -31 0 -60Z" fill={`url(#${id}-body)`} stroke="#ffd88a" strokeWidth="1.3"/>
    <path d="M-8 -23 C-18 -6 -27 5 -25 21" fill="none" stroke="#fff9dc" strokeOpacity="0.85" strokeWidth="4" strokeLinecap="round"/>
    <ellipse cx="10" cy="37" rx="15" ry="4" fill="#fff0a0" opacity="0.3"/>
  </g>
);

export const PetriDish: React.FC<{x?: number; y?: number; opacity?: number}> = ({x = 1120, y = 820, opacity = 1}) => (
  <g transform={`translate(${x} ${y})`} opacity={opacity}>
    <ellipse rx="246" ry="45" cy="34" fill={C.amber} opacity="0.035"/>
    <path d="M-224 0V25 C-224 81 224 81 224 25V0" fill="#1c1710" fillOpacity="0.5" stroke={C.amber} strokeOpacity="0.4" strokeWidth="2"/>
    <ellipse rx="224" ry="40" fill="#171711" fillOpacity="0.5" stroke={C.amber} strokeOpacity="0.7" strokeWidth="2"/>
    <ellipse rx="207" ry="31" fill="none" stroke={C.amber} strokeOpacity="0.22"/>
  </g>
);
