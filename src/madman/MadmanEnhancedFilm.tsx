import React from 'react';
import {AbsoluteFill, Audio, Img, staticFile, useCurrentFrame} from 'remotion';
import timeline from './full-v4-timeline.json';
import {MadmanHistoryScene} from './MadmanHistoryStudy';

const PAPER = '#e1d7c2';
const RED = '#b74b3c';
const SERIF = '"Songti SC", "STSong", serif';
const SANS = '"PingFang SC", sans-serif';
type Shot = typeof timeline.shots[number];
const clamp = (n: number) => Math.min(1, Math.max(0, n));
const smooth = (n: number) => {const t = clamp(n); return t * t * (3 - 2 * t);};
const ease = (frame: number, from: number, duration = 24) => smooth((frame - from) / duration);

const Woodcut: React.FC<{name: string;scale?: number;origin?: string;darken?: number;verticalOffset?: number}> = ({name, scale = 1.02, origin = '50% 50%', darken = .05, verticalOffset = 0}) => <AbsoluteFill style={{overflow: 'hidden'}}>
  <Img src={staticFile(`madman/${name}.png`)} style={{width: 1920, height: 1080, objectFit: 'cover', transform: `translateY(${verticalOffset}px) scale(${scale})`, transformOrigin: origin}}/>
  <AbsoluteFill style={{background: `rgba(8,12,10,${darken})`}}/>
  <AbsoluteFill style={{background: 'linear-gradient(180deg, rgba(7,11,9,.18), transparent 35%, transparent 65%, rgba(7,11,9,.76))'}}/>
</AbsoluteFill>;

const Grain: React.FC = () => <svg width="1920" height="1080" style={{position: 'absolute', inset: 0, opacity: .045, mixBlendMode: 'soft-light', pointerEvents: 'none'}}>
  <defs><filter id="v4-grain"><feTurbulence type="fractalNoise" baseFrequency=".66" numOctaves="2" seed="1918" stitchTiles="stitch"/></filter></defs>
  <rect width="1920" height="1080" filter="url(#v4-grain)"/>
</svg>;

const Label: React.FC<{shot: Shot;frame: number}> = ({shot, frame}) => <div style={{position: 'absolute', left: 112, top: 116, display: 'flex', gap: 20, alignItems: 'center', fontFamily: SANS, fontSize: 20, letterSpacing: 5, color: PAPER, opacity: ease(frame, 12) * .67}}><span style={{width: 38, height: 1, background: PAPER}}/>日记 · {shot.section}</div>;

const Caption: React.FC<{shot: Shot;frame: number}> = ({shot, frame}) => {
  if (['title', 'history', 'moon', 'question', 'children', 'plea'].includes(shot.id)) return null;
  const cue = shot.cues.find(c => frame >= c.from && frame < c.from + c.duration);
  if (!cue) return null;
  const opacity = ease(frame, cue.from, 8) * smooth((cue.from + cue.duration - frame) / 8);
  return <div style={{position: 'absolute', top: 945, left: 110, right: 110, fontFamily: SERIF, fontSize: 37, letterSpacing: 2, lineHeight: 1.5, textAlign: 'center', color: PAPER, opacity}}>{cue.text}</div>;
};

const MoonShadow: React.FC<{frame: number}> = ({frame}) => <svg width="1920" height="1080" style={{position: 'absolute', inset: 0, pointerEvents: 'none'}}>
  <defs><filter id="v4-cloud-soft"><feGaussianBlur stdDeviation="12"/></filter></defs>
  <path d="M 1060 177 Q 1210 139 1374 166 Q 1450 154 1566 178 Q 1675 191 1790 169 L 1790 198 Q 1580 218 1400 203 Q 1260 187 1060 207 Z" fill="#111f26" filter="url(#v4-cloud-soft)" opacity=".22" transform={`translate(${frame * .75 - 110},${60 + Math.sin(frame / 86) * 7})`}/>
</svg>;

const Title: React.FC<{frame: number}> = ({frame}) => <>
  <Woodcut name="moon" scale={1.025 + frame / 120 * .02} origin="73% 47%" darken={.13} verticalOffset={60}/>
  <MoonShadow frame={frame}/>
  <div style={{position: 'absolute', left: 148, top: 288, opacity: ease(frame, 10, 30)}}>
    <div style={{fontFamily: SANS, fontSize: 20, letterSpacing: 7, color: '#b7b6a7'}}>LU XUN / 1918</div>
    <div style={{fontFamily: SERIF, fontSize: 156, fontWeight: 700, letterSpacing: 17, lineHeight: 1.15, color: PAPER, marginTop: 32}}>狂人日记</div>
    <div style={{fontFamily: SERIF, fontSize: 29, letterSpacing: 10, color: '#c8c0ae', marginTop: 40, display: 'flex', alignItems: 'center', gap: 24}}><span style={{height: 3, width: 42, background: RED}}/>鲁迅</div>
    <div style={{fontFamily: SANS, fontSize: 18, letterSpacing: 5, color: '#92968b', marginTop: 70}}>原文节选 · 木刻意象短片</div>
  </div>
</>;

const Moon: React.FC<{shot: Shot;frame: number}> = ({shot, frame}) => <>
  <Woodcut name="moon" scale={1.045 + frame / shot.duration * .03} origin="73% 47%" verticalOffset={60}/>
  <MoonShadow frame={120 + frame}/>
  <Label shot={shot} frame={frame}/>
  <div style={{position: 'absolute', left: 166, top: 382, fontFamily: SERIF, fontSize: 78, letterSpacing: 8, lineHeight: 1.7, color: PAPER, opacity: ease(frame, 12, 22)}}><div>今天晚上，</div><div>很好的月光。</div></div>
</>;

const Watch: React.FC<{shot: Shot;frame: number}> = ({shot, frame}) => {
  const left = frame >= 132 && frame < 192;
  const right = frame >= 192;
  const scale = left ? 1.72 + (frame - 132) * .0005 : right ? 1.74 + (frame - 192) * .0005 : 1.025 + frame * .00036;
  return <>
    <Woodcut name="crowd" scale={scale} origin={left ? '28% 38%' : right ? '73% 34%' : '50% 50%'} darken={left || right ? .09 : .10}/>
    <AbsoluteFill style={{background: `linear-gradient(90deg,rgba(6,10,8,${right ? .4 : .03}),transparent 37%,transparent 63%,rgba(6,10,8,${left ? .4 : .03}))`}}/>
    <Label shot={shot} frame={frame}/>
  </>;
};

const Question: React.FC<{shot: Shot;frame: number}> = ({shot, frame}) => <>
  <Woodcut name="crowd" scale={1.12 - ease(frame, 0, 170) * .04} darken={.80}/>
  <Label shot={shot} frame={frame}/>
  <div style={{position: 'absolute', top: 305, left: 180, right: 180, fontFamily: SERIF, fontSize: 116, lineHeight: 1.6, fontWeight: 600, letterSpacing: 13, textAlign: 'center', color: PAPER}}>
    <div style={{opacity: ease(frame, 8, 18)}}>从来如此，</div>
    <div style={{opacity: ease(frame, 38, 20)}}>便<span style={{color: '#cb5747'}}>对</span>么？</div>
    <div style={{margin: '35px auto 0', width: 108, height: 2, background: RED, transform: `scaleX(${ease(frame, 64, 32)})`}}/>
  </div>
</>;

const Complicity: React.FC<{shot: Shot;frame: number}> = ({shot, frame}) => {
  const admission = ease(frame, 122, 26);
  const shadow = ease(frame, 26, 200);
  return <>
    <AbsoluteFill style={{background: '#111714'}}/>
    <Img src={staticFile('madman/moon.png')} style={{position: 'absolute', width: 1920, height: 1080, objectFit: 'cover', transform: `scale(${2.13 + frame * .0002}) translateX(-175px)`, transformOrigin: '78% 65%', opacity: .78}}/>
    <AbsoluteFill style={{background: 'linear-gradient(90deg,#111714 6%,rgba(17,23,20,.96) 27%,rgba(17,23,20,.7) 48%,rgba(17,23,20,.12) 74%,rgba(17,23,20,.5))'}}/>
    <svg width="1920" height="1080" style={{position: 'absolute', inset: 0, opacity: .18 + shadow * .08}}>
      <path d={`M ${1190 + shadow * 80} 84 L ${1290 + shadow * 80} 84 L ${1490 + shadow * 38} 914 L ${1390 + shadow * 38} 914 Z`} fill="#090d0b"/>
      <path d={`M ${1510 + shadow * 45} 84 L ${1560 + shadow * 45} 84 L ${1710 + shadow * 18} 914 L ${1660 + shadow * 18} 914 Z`} fill="#090d0b"/>
    </svg>
    <Label shot={shot} frame={frame}/>
    <div style={{position: 'absolute', left: 147, top: 280, fontFamily: SERIF, fontSize: 61, letterSpacing: 10, color: PAPER, opacity: admission}}>今天才明白，</div>
    <div style={{position: 'absolute', left: 146, top: 488, display: 'flex', gap: 17, alignItems: 'baseline', color: PAPER, fontFamily: SERIF, opacity: ease(frame, 144, 32)}}><span style={{fontSize: 143, fontWeight: 700, color: RED, lineHeight: 1}}>我</span><span style={{fontSize: 65, letterSpacing: 8}}>也在其中</span></div>
    <div style={{position: 'absolute', left: 149, top: 671, fontFamily: SERIF, fontSize: 66, letterSpacing: 8, color: '#c9c2b0', opacity: ease(frame, 178, 28)}}>混了多年；</div>
  </>;
};

const Children: React.FC<{shot: Shot;frame: number}> = ({shot, frame}) => {
  const p = ease(frame, 20, 180);
  return <>
    <Woodcut name="child" scale={1.015 + frame / shot.duration * .026} origin="77% 65%" darken={.08}/>
    <svg width="1920" height="1080" style={{position: 'absolute', inset: 0, pointerEvents: 'none'}}>
      <path d={`M 1070 84 L ${1180 + p * 88} 84 L ${1090 + p * 74} 914 L 982 914 Z`} fill="#111713" opacity={.12 + p * .16}/>
      <path d={`M ${1772 - p * 65} 84 H 1920 V 914 H ${1794 - p * 65} Z`} fill="#080c0a" opacity={.12 + p * .16}/>
    </svg>
    <Label shot={shot} frame={frame}/>
    <div style={{position: 'absolute', left: 145, top: 342, fontFamily: SERIF, fontSize: 64, lineHeight: 1.8, letterSpacing: 7, color: PAPER}}><div style={{opacity: ease(frame, 12, 20)}}>没有吃过人的孩子，</div><div style={{opacity: ease(frame, 80, 26)}}>或者还有？</div></div>
  </>;
};

const Plea: React.FC<{shot: Shot;frame: number}> = ({shot, frame}) => <>
  <Woodcut name="child" scale={1.041} origin="77% 65%" darken={.52 + ease(frame, 54, 100) * .26}/>
  <div style={{position: 'absolute', left: 140, right: 140, top: 407, fontFamily: SERIF, fontSize: 138, fontWeight: 600, letterSpacing: 16, textAlign: 'center', color: PAPER, opacity: ease(frame, 0, 13)}}>救救孩子<span style={{fontSize: 66, letterSpacing: 2}}>……</span></div>
  <div style={{position: 'absolute', top: 762, left: 0, right: 0, fontFamily: SANS, fontSize: 23, letterSpacing: 6, textAlign: 'center', color: '#b3b2a4', opacity: ease(frame, 74, 24)}}>鲁迅 ·《狂人日记》· 一九一八年四月</div>
</>;

const Scene: React.FC<{shot: Shot;frame: number}> = ({shot, frame}) => <AbsoluteFill>
  {shot.id === 'title' ? <Title frame={frame}/> : null}
  {shot.id === 'moon' ? <Moon shot={shot} frame={frame}/> : null}
  {shot.id === 'watch' ? <Watch shot={shot} frame={frame}/> : null}
  {shot.id === 'history' ? <MadmanHistoryScene frame={frame} endingFade={false} showChrome={false}/> : null}
  {shot.id === 'question' ? <Question shot={shot} frame={frame}/> : null}
  {shot.id === 'complicity' ? <Complicity shot={shot} frame={frame}/> : null}
  {shot.id === 'children' ? <Children shot={shot} frame={frame}/> : null}
  {shot.id === 'plea' ? <Plea shot={shot} frame={frame}/> : null}
  {shot.id !== 'history' ? <Grain/> : null}
</AbsoluteFill>;

export const MadmanEnhancedFilm: React.FC = () => {
  const frame = useCurrentFrame();
  const current = timeline.shots.find(s => frame >= s.from && frame < s.from + s.duration) ?? timeline.shots[timeline.shots.length - 1];
  const active = timeline.shots.filter(s => frame >= s.from && frame < s.from + s.duration + 12);
  return <AbsoluteFill style={{background: '#080c0a', overflow: 'hidden'}}>
    {active.map(shot => <AbsoluteFill key={shot.id} style={{opacity: shot.from === 0 ? 1 : ease(frame, shot.from, 12)}}><Scene shot={shot} frame={Math.min(frame - shot.from, shot.duration - 1)}/></AbsoluteFill>)}
    <div style={{position: 'absolute', top: 0, left: 0, right: 0, height: 84, background: '#080c0a'}}/>
    <div style={{position: 'absolute', top: 914, left: 0, right: 0, bottom: 0, background: '#080c0a'}}/>
    {current.id === 'history' ? <div style={{position: 'absolute', top: 946, left: 110, right: 110, fontFamily: SERIF, fontSize: 37, letterSpacing: 2, lineHeight: 1.5, textAlign: 'center', color: PAPER}}>{(() => {const f = frame - current.from; const c = current.captions?.find(c => f >= c.from && f < c.end); return c ? <span style={{opacity: ease(f, c.from, 6) * smooth((c.end - f) / 6)}}>{c.text}</span> : null;})()}</div> : <Caption shot={current} frame={frame - current.from}/>}
    {current.id === 'plea' ? <div style={{position: 'absolute', top: 978, left: 0, right: 0, textAlign: 'center', fontFamily: SANS, fontSize: 17, letterSpacing: 3, color: '#737b70', opacity: ease(frame - current.from, 98, 22)}}>原文节选 · AI 木刻意象 · 百炼合成男声</div> : null}
    <div style={{position: 'absolute', left: 112, top: 29, fontFamily: SANS, fontSize: 17, letterSpacing: 5, color: '#969a8e', opacity: ease(frame, 16)}}>狂人日记 / 鲁迅</div>
    <div style={{position: 'absolute', right: 112, top: 30, fontFamily: SANS, fontSize: 15, letterSpacing: 3, color: '#757c70', opacity: ease(frame, 16)}}>原文节选 · 木刻意象</div>
    <Audio src={staticFile(timeline.audioFile)}/>
    <AbsoluteFill style={{background: '#080c0a', opacity: 1 - ease(frame, 0, 18), pointerEvents: 'none'}}/>
  </AbsoluteFill>;
};
