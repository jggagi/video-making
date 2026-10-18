import React from 'react';
import {AbsoluteFill, Audio, staticFile, useCurrentFrame} from 'remotion';
import spec from './history-study-v3.json';

const PAPER = '#d9cbb1';
const INK = '#111714';
const SERIF = '"Songti SC", "STSong", serif';
const SANS = '"PingFang SC", sans-serif';
const clamp = (n: number) => Math.min(1, Math.max(0, n));
const smooth = (n: number) => {const t = clamp(n); return t * t * (3 - 2 * t);};
const progress = (frame: number, from: number, to: number) => smooth((frame - from) / (to - from));
const pagePath = 'M 250 220 Q 594 155 954 213 Q 1280 155 1650 224 L 1728 827 Q 1302 781 959 842 Q 623 782 189 827 Z';

const PageGrain: React.FC = () => <svg width="1920" height="1080" style={{position: 'absolute', inset: 0, pointerEvents: 'none', opacity: 0.12, mixBlendMode: 'multiply'}}>
  <defs><filter id="history-paper-grain"><feTurbulence type="fractalNoise" baseFrequency=".55" numOctaves="3" seed="1918" stitchTiles="stitch"/></filter></defs>
  <rect width="1920" height="1080" filter="url(#history-paper-grain)"/>
</svg>;

const PrintedPage: React.FC<{frame: number;focus: number}> = ({frame, focus}) => <>
  <svg width="1920" height="1080" style={{position: 'absolute', inset: 0}}>
    <defs>
      <linearGradient id="study-paper" x1="0" x2="1"><stop stopColor="#9e8c72"/><stop offset=".18" stopColor={PAPER}/><stop offset=".47" stopColor="#cfbfa4"/><stop offset=".501" stopColor="#87765f"/><stop offset=".54" stopColor="#ccbc9e"/><stop offset=".83" stopColor="#dcd0b8"/><stop offset="1" stopColor="#ac987c"/></linearGradient>
      <clipPath id="study-page"><path d={pagePath}/></clipPath>
    </defs>
    <path d={pagePath} fill="url(#study-paper)"/>
    <g clipPath="url(#study-page)" fill="none" stroke="#615a47" opacity=".19">
      {Array.from({length: 10}, (_, i) => <path key={i} d={`M ${258 + i * 8} ${214 + i * 3} Q 630 ${163 + i * 2} 957 ${209 + i * 2} Q 1300 ${166 + i * 2} ${1654 + i * 4} ${222 + i * 3}`}/>)}
      <path d="M 954 213 Q 946 480 959 842" strokeWidth="4"/>
      <path d="M 235 775 Q 550 761 746 793 M 1178 790 Q 1428 765 1688 797"/>
    </g>
  </svg>
  <div style={{position: 'absolute', left: 342, top: 235, width: 1228, height: 539, overflow: 'hidden', fontFamily: SERIF, fontWeight: 600, color: '#272a21'}}>
    {Array.from({length: 10}, (_, i) => {
      const emphasized = i === 3;
      return <div key={i} style={{position: 'absolute', top: 9 + i * 53, left: (i % 3 - 1) * 13, fontSize: emphasized ? 40 : 31 + i % 3, letterSpacing: emphasized ? 18 : 13, whiteSpace: 'nowrap', transform: `rotate(${i % 2 ? -0.7 : 0.55}deg)`, opacity: emphasized ? .62 + focus * .33 : (.34 + i % 4 * .055) * (1 - focus * .17)}}>{'仁义道德'.repeat(9)}</div>;
    })}
    <div style={{position: 'absolute', top: 0, left: 599, width: 35, height: '100%', background: 'linear-gradient(90deg, transparent, rgba(86,73,52,.25), transparent)'}}/>
  </div>
  <svg width="1920" height="1080" style={{position: 'absolute', inset: 0, opacity: .22, pointerEvents: 'none'}}>
    {Array.from({length: 35}, (_, i) => <line key={i} x1={300 + (i * 163) % 1280} x2={316 + (i * 163) % 1280} y1={249 + (i * 71) % 530} y2={248 + (i * 71) % 530} stroke="#514737" strokeWidth={i % 4 === 0 ? 2 : 1}/>)}
  </svg>
  <PageGrain/>
  <div style={{position: 'absolute', inset: 0, background: `linear-gradient(${114 + frame * .025}deg, rgba(17,23,20,.32), transparent 35%, transparent 60%, rgba(17,23,20,.28))`}}/>
</>;

export const MadmanHistoryScene: React.FC<{frame: number;endingFade?: boolean;showChrome?: boolean}> = ({frame, endingFade = true, showChrome = true}) => {
  const v = spec.visual;
  const opening = 1 - progress(frame, 0, v.pageTurnEnd);
  const focus = progress(frame, v.printFocusStart, v.printFocusEnd);
  const crack = progress(frame, v.crackStart, v.crackEnd);
  const word = progress(frame, v.wordRevealStart, v.wordRevealEnd);
  const camera = progress(frame, 34, 318);
  const caption = spec.captions.find(c => frame >= c.from && frame < c.end);
  const captionOpacity = caption ? progress(frame, caption.from, caption.from + 6) * smooth((caption.end - frame) / 6) : 0;
  const fadeOut = endingFade ? 1 - progress(frame, 468, 480) : 1;
  const gap = crack * 166;
  const tearingEdge = 'polygon(0 0,100% 0,100% 47.3%,95% 47.5%,90% 47.1%,84% 47.7%,77% 47.2%,70% 47.6%,63% 47.2%,57% 47.4%,49% 47.0%,43% 47.5%,36% 47.1%,30% 47.4%,24% 47.0%,17% 47.5%,10% 47.1%,4% 47.4%,0 47.2%)';
  const lowerEdge = 'polygon(0 47.2%,4% 47.4%,10% 47.1%,17% 47.5%,24% 47.0%,30% 47.4%,36% 47.1%,43% 47.5%,49% 47.0%,57% 47.4%,63% 47.2%,70% 47.6%,77% 47.2%,84% 47.7%,90% 47.1%,95% 47.5%,100% 47.3%,100% 100%,0 100%)';
  return <AbsoluteFill style={{background: '#0c100e', color: PAPER, overflow: 'hidden'}}>
    <AbsoluteFill style={{opacity: fadeOut}}>
      <AbsoluteFill style={{background: 'radial-gradient(ellipse at 50% 45%, #2b2d22 0%, #131915 57%, #080c0a 100%)'}}/>
      <div style={{position: 'absolute', inset: 0, transform: `translateY(${-camera * 20}px) scale(${.985 + camera * .125}) rotate(${-0.55 + camera * .35}deg)`, transformOrigin: '50% 48%'}}>
        <svg width="1920" height="1080" style={{position: 'absolute', inset: 0}}>
          <path d={pagePath} fill="#000" opacity=".66" transform="translate(8 23)"/>
          <path d={pagePath} fill={INK}/>
          <path d="M 295 514 L 415 507 L 602 516 L 743 509 L 970 515 L 1210 507 L 1410 518 L 1650 511" stroke="#6c5a44" strokeWidth={2 + crack * 6} opacity={crack * (1 - crack) * .75}/>
        </svg>
        <div style={{position: 'absolute', left: 0, right: 0, top: 451, textAlign: 'center', fontFamily: SERIF, fontWeight: 900, fontSize: 137, letterSpacing: 47, color: '#b74938', lineHeight: 1, opacity: word, clipPath: `inset(0 ${100 - word * 100}% 0 0)`, transform: `translateY(${(1 - word) * 8}px)`, textShadow: '0 2px 1px #080b08'}}>吃人</div>
        <AbsoluteFill style={{clipPath: tearingEdge, transform: `translateY(${-gap * .39}px) rotate(${-crack * .18}deg)`}}><PrintedPage frame={frame} focus={focus}/></AbsoluteFill>
        <AbsoluteFill style={{clipPath: lowerEdge, transform: `translateY(${gap * .61}px) rotate(${crack * .18}deg)`}}><PrintedPage frame={frame} focus={focus}/></AbsoluteFill>
        {opening > 0 ? <div style={{position: 'absolute', left: 960, top: 194, width: 716, height: 628, transformOrigin: '0% 50%', transform: `perspective(1700px) rotateY(${-opening * 82}deg)`, background: 'linear-gradient(90deg, #706650, #ddcfb2 16%, #c8b796 89%, #897557)', opacity: opening, boxShadow: '18px 5px 28px rgba(0,0,0,.35)'}}/> : null}
        <div style={{position: 'absolute', inset: 0, background: 'radial-gradient(ellipse at 50% 45%, transparent 25%, rgba(9,14,10,.22) 80%)'}}/>
      </div>
      <AbsoluteFill style={{background: 'linear-gradient(180deg, rgba(7,10,8,.35), transparent 27%, transparent 73%, rgba(7,10,8,.6))'}}/>
      <div style={{position: 'absolute', left: 112, top: 114, display: 'flex', alignItems: 'center', gap: 20, fontFamily: SANS, fontSize: 20, letterSpacing: 5, opacity: .7 * progress(frame, 5, 25) * (1 - crack)}}><span style={{height: 1, width: 38, background: PAPER}}/>日记 · 三</div>
      <div style={{position: 'absolute', left: 86, top: 769, fontFamily: SERIF, fontSize: 20, letterSpacing: 5, writingMode: 'vertical-rl', opacity: .54 * progress(frame, 30, 60) * (1 - crack)}}>字缝之间</div>
      <div style={{position: 'absolute', left: 0, right: 0, top: 0, height: 84, background: '#080b09'}}/>
      <div style={{position: 'absolute', left: 0, right: 0, top: 914, bottom: 0, background: '#080b09'}}/>
      {showChrome ? <><div style={{position: 'absolute', left: 112, top: 28, fontFamily: SANS, fontSize: 17, letterSpacing: 5, color: '#909488'}}>狂人日记 / 鲁迅</div>
      <div style={{position: 'absolute', right: 112, top: 29, fontFamily: SANS, fontSize: 15, letterSpacing: 3, color: '#797d73'}}>原文节选 · 字缝</div></> : null}
      {caption ? <div style={{position: 'absolute', top: 946, left: 110, right: 110, fontFamily: SERIF, fontSize: 37, lineHeight: 1.5, letterSpacing: 2, textAlign: 'center', color: PAPER, opacity: captionOpacity}}>{caption.text}</div> : null}
    </AbsoluteFill>
  </AbsoluteFill>;
};

export const MadmanHistoryStudy: React.FC = () => {
  const frame = useCurrentFrame();
  return <AbsoluteFill><MadmanHistoryScene frame={frame}/><Audio src={staticFile(spec.audioFile)}/></AbsoluteFill>;
};
