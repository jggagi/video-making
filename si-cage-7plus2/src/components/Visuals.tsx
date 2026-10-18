import React from 'react';
import {C, CN, FONT, GLOW, SCENE_HEIGHT, SCENE_WIDTH} from '../lib/theme';
export const Backdrop: React.FC = () => <svg width={SCENE_WIDTH} height={SCENE_HEIGHT} viewBox={`0 0 ${SCENE_WIDTH} ${SCENE_HEIGHT}`} style={{position: 'absolute', inset: 0}}>
  <defs><pattern id="cage-grid" width="64" height="64" patternUnits="userSpaceOnUse"><path d="M64 0H0V64" fill="none" stroke="rgba(255,255,255,0.03)"/></pattern><radialGradient id="cage-halo"><stop stopColor={C.cyan} stopOpacity="0.08"/><stop offset="1" stopColor={C.bg} stopOpacity="0"/></radialGradient></defs>
  <rect width="1920" height="1080" fill={C.bg}/><rect width="1920" height="1080" fill="url(#cage-grid)"/><ellipse cx="1100" cy="540" rx="1000" ry="650" fill="url(#cage-halo)"/>
  <path d="M64 216V198H82 M1838 198H1856V216 M64 896V914H82 M1838 914H1856V896" fill="none" stroke={C.muted} strokeOpacity="0.4"/>
</svg>;
export const ActLabel: React.FC<{number: string; title: string; kicker: string; color?: string}> = ({number, title, kicker, color = C.cyan}) => <div style={{position: 'absolute', left: 94, top: 222}}><div style={{fontFamily: FONT, fontSize: 13, letterSpacing: 3, color, marginBottom: 14, filter: color === C.cyan ? GLOW.cyan : color === C.gold ? GLOW.gold : undefined}}>{number} / {kicker}</div><div style={{fontFamily: CN, fontSize: 36, fontWeight: 500, color: C.white, letterSpacing: 1}}>{title}</div></div>;
