import React from 'react';
import {AbsoluteFill, Audio, Img, staticFile, useCurrentFrame} from 'remotion';
import timeline from './timeline.json';

const W = 1920;
const H = 1080;
const PAPER = '#e6deca';
const INK = '#101414';
const RED = '#a43b32';
const SERIF = '"Songti SC", "STSong", serif';
const SANS = '"PingFang SC", sans-serif';
type Shot = typeof timeline.shots[number];
type FilmProps = {timelineData?: typeof timeline; audioSrc?: string; voiced?: boolean};
const clamp = (v: number) => Math.min(1, Math.max(0, v));
const smooth = (v: number) => {const t = clamp(v); return t * t * (3 - 2 * t);};
const fade = (f: number, start: number, length = 24) => smooth((f - start) / length);

const PrintTexture: React.FC = () => <svg width={W} height={H} style={{position: 'absolute', inset: 0, opacity: 0.07, mixBlendMode: 'soft-light', pointerEvents: 'none'}}>
  <defs><filter id="madman-grain"><feTurbulence type="fractalNoise" baseFrequency="0.67" numOctaves="2" seed="1918" stitchTiles="stitch"/></filter></defs>
  <rect width="100%" height="100%" filter="url(#madman-grain)" opacity="0.9"/>
</svg>;

const Dust: React.FC<{frame: number}> = ({frame}) => <svg width={W} height={H} style={{position: 'absolute', inset: 0, pointerEvents: 'none'}}>
  {Array.from({length: 22}, (_, i) => {
    const x = (i * 139.7 + frame * (0.07 + i % 4 * 0.015)) % W;
    const y = 90 + (i * 73.3 - frame * 0.09 + 1200) % 880;
    return <circle key={i} cx={x} cy={y} r={i % 3 === 0 ? 1.4 : 0.7} fill={PAPER} opacity={0.12 + Math.sin(frame * 0.015 + i) * 0.07}/>;
  })}
</svg>;

const Art: React.FC<{name: string;frame: number;duration: number;darken?: number;reverse?: boolean}> = ({name, frame, duration, darken = 0, reverse = false}) => {
  const p = clamp(frame / duration);
  const scale = 1.015 + p * (name === 'crowd' ? 0.085 : 0.035);
  return <AbsoluteFill style={{overflow: 'hidden'}}>
    <Img src={staticFile(`madman/${name}.png`)} style={{width: W, height: H, objectFit: 'cover', transform: `scale(${scale}) translate(${(reverse ? -1 : 1) * (p - 0.5) * 26}px, ${name === 'child' ? -p * 9 : 0}px)`, transformOrigin: name === 'moon' ? '73% 47%' : '50% 50%'}}/>
    <AbsoluteFill style={{background: `rgba(8,12,13,${darken})`}}/>
    <AbsoluteFill style={{background: 'linear-gradient(180deg, rgba(7,10,12,.24), transparent 34%, transparent 65%, rgba(7,10,12,.75))'}}/>
  </AbsoluteFill>;
};

const SceneLabel: React.FC<{shot: Shot;frame: number;light?: boolean}> = ({shot, frame, light = true}) => <div style={{position: 'absolute', left: 112, top: 115, display: 'flex', gap: 20, alignItems: 'center', opacity: fade(frame, 12) * 0.72, color: light ? PAPER : '#393b35', fontFamily: SANS, fontSize: 20, letterSpacing: 5}}>
  <span style={{height: 1, width: 38, background: light ? PAPER : '#393b35'}}/>
  <span>日记 · {shot.section}</span>
</div>;

const Caption: React.FC<{shot: Shot;frame: number}> = ({shot, frame}) => {
  const cue = shot.cues.find(c => frame >= c.from && frame < c.from + c.duration);
  if (!cue || ['moon', 'question', 'children', 'plea'].includes(shot.id)) return null;
  const local = frame - cue.from;
  const opacity = fade(local, 0, 12) * smooth((cue.duration - local) / 10);
  return <div style={{position: 'absolute', left: 110, right: 110, top: 945, textAlign: 'center', fontFamily: SERIF, fontSize: 37, lineHeight: 1.5, color: PAPER, letterSpacing: 2, opacity}}>{cue.text}</div>;
};

const Title: React.FC<{frame: number}> = ({frame}) => <>
  <Art name="moon" frame={frame} duration={408} darken={0.10}/>
  <div style={{position: 'absolute', left: 150, top: 281, opacity: fade(frame, 12, 32)}}>
    <div style={{fontFamily: SANS, fontSize: 20, color: '#bebcae', letterSpacing: 7}}>LU XUN / 1918</div>
    <div style={{fontFamily: SERIF, fontSize: 158, fontWeight: 700, lineHeight: 1.15, letterSpacing: 17, color: PAPER, marginTop: 34, textShadow: '0 5px 26px #080a0a'}}>狂人日记</div>
    <div style={{display: 'flex', alignItems: 'center', gap: 24, marginTop: 40, fontFamily: SERIF, fontSize: 29, color: '#cac4b4', letterSpacing: 10}}>
      <span style={{background: RED, width: 42, height: 3}}/>鲁迅
    </div>
    <div style={{fontFamily: SANS, fontSize: 18, color: '#979c96', letterSpacing: 5, marginTop: 78}}>原文节选 · 木刻意象短片</div>
  </div>
</>;

const Moon: React.FC<{shot: Shot;frame: number;voiced: boolean}> = ({shot, frame, voiced}) => <>
  <Art name="moon" frame={144 + frame} duration={408}/>
  <SceneLabel shot={shot} frame={frame}/>
  <div style={{position: 'absolute', left: 168, top: 384, width: 780, fontFamily: SERIF, fontSize: 78, letterSpacing: 8, lineHeight: 1.7, color: PAPER, opacity: fade(frame, voiced ? shot.cues[0].from - 12 : 35, voiced ? 18 : 38), transform: `translateY(${(1 - fade(frame, voiced ? shot.cues[0].from - 12 : 35, 80)) * 14}px)`}}>
    <div>今天晚上，</div><div>很好的月光。</div>
  </div>
</>;

const Watch: React.FC<{shot: Shot;frame: number}> = ({shot, frame}) => <>
  <Art name="crowd" frame={frame} duration={shot.duration} darken={0.12}/>
  <SceneLabel shot={shot} frame={frame}/>
  <div style={{position: 'absolute', right: 120, top: 760, width: 250, height: 2, background: RED, transformOrigin: 'right', transform: `scaleX(${fade(frame, 80, 80)})`, opacity: 0.8}}/>
</>;

const History: React.FC<{shot: Shot;frame: number}> = ({shot, frame}) => {
  const p = clamp(frame / shot.duration);
  const reveal = fade(frame, shot.cues[2].from - 10, 52);
  const gap = 8 + reveal * 56;
  const rows = Array.from({length: 11}, (_, i) => i < 5 ? 242 + i * 49 : 242 + i * 49 + gap);
  return <>
    <AbsoluteFill style={{background: PAPER}}/>
    <svg width={W} height={H} style={{position: 'absolute', inset: 0}}>
      <defs><linearGradient id="book-light"><stop stopColor="#b6aa93"/><stop offset=".48" stopColor="#e6deca"/><stop offset=".505" stopColor="#a29883"/><stop offset=".54" stopColor="#ddd4bd"/><stop offset="1" stopColor="#c8bca5"/></linearGradient></defs>
      <path d="M 282 227 Q 635 168 957 218 Q 1270 155 1636 227 L 1710 851 Q 1285 774 958 834 Q 615 781 208 851 Z" fill="#0e1516" opacity=".13" transform="translate(0 15)"/>
      <path d="M 282 208 Q 635 149 957 199 Q 1270 136 1636 208 L 1710 832 Q 1285 755 958 815 Q 615 762 208 832 Z" fill="url(#book-light)"/>
      <path d="M 957 199 Q 947 456 958 815" stroke="#7d7564" strokeWidth="2" opacity=".55"/>
      <path d="M 282 208 Q 635 149 957 199 M 957 199 Q 1270 136 1636 208" stroke="#524d42" strokeWidth="2" opacity=".45" fill="none"/>
    </svg>
    <SceneLabel shot={shot} frame={frame} light={false}/>
    <div style={{position: 'absolute', left: 124, top: 765, fontFamily: SERIF, fontSize: 20, letterSpacing: 5, color: '#6a6459', writingMode: 'vertical-rl', opacity: fade(frame, 20)}}>字缝之间</div>
    <div style={{position: 'absolute', left: 300, top: 215, width: 1300, height: 600, overflow: 'hidden', transform: `perspective(1600px) rotateX(5deg) scale(${1 + p * .035})`, transformOrigin: '50% 60%'}}>
      {rows.map((y, i) => <div key={i} style={{position: 'absolute', top: y - 215, left: i % 2 * -18, fontFamily: SERIF, fontWeight: 600, fontSize: 32, letterSpacing: 14, color: '#24251f', opacity: (0.22 + (i % 4) * 0.09) * (1 - reveal * .48), whiteSpace: 'nowrap', transform: `rotate(${i % 2 ? -.8 : .6}deg)`}}>{'仁义道德'.repeat(8)}</div>)}
      <div style={{position: 'absolute', top: 247, left: 140, right: 100, height: 90, background: `rgba(230,222,202,${reveal * .92})`, opacity: reveal}}/>
      <div style={{position: 'absolute', top: 232, left: 360, fontFamily: SERIF, fontWeight: 900, fontSize: 130, lineHeight: 1, letterSpacing: 64, color: RED, opacity: reveal, clipPath: `inset(0 ${100 - reveal * 100}% 0 0)`, transform: `scale(${.95 + reveal * .05})`}}>吃人</div>
    </div>
    <AbsoluteFill style={{background: 'radial-gradient(ellipse at 50% 50%, transparent 40%, rgba(49,41,28,.13))'}}/>
  </>;
};

const Question: React.FC<{shot: Shot;frame: number;voiced: boolean}> = ({shot, frame, voiced}) => <>
  <Art name="crowd" frame={shot.duration - frame} duration={shot.duration} darken={0.74} reverse/>
  <SceneLabel shot={shot} frame={frame}/>
  <div style={{position: 'absolute', top: 311, left: 210, right: 210, textAlign: 'center', fontFamily: SERIF, fontSize: 114, lineHeight: 1.55, letterSpacing: 13, fontWeight: 600, color: PAPER}}>
    <div style={{opacity: fade(frame, voiced ? shot.cues[0].from - 12 : 32, voiced ? 18 : 32)}}>从来如此，</div>
    <div style={{opacity: fade(frame, voiced ? shot.cues[0].from + 20 : 84, voiced ? 18 : 32)}}>便<span style={{color: '#cb5147'}}>对</span>么？</div>
    <div style={{height: 2, width: 110, background: RED, margin: '42px auto 0', transform: `scaleX(${fade(frame, 115, 40)})`}}/>
  </div>
</>;

const Complicity: React.FC<{shot: Shot;frame: number;voiced: boolean}> = ({shot, frame, voiced}) => {
  const pressure = fade(frame, 20, 180);
  return <>
    <AbsoluteFill style={{background: '#151817'}}/>
    <Img src={staticFile('madman/moon.png')} style={{position: 'absolute', width: W, height: H, objectFit: 'cover', transform: `scale(${2.15 + pressure * .035}) translateX(-175px)`, transformOrigin: '78% 65%', opacity: .72}}/>
    <AbsoluteFill style={{background: 'linear-gradient(90deg, #101413 9%, rgba(16,20,19,.94) 27%, rgba(16,20,19,.6) 51%, rgba(16,20,19,.08) 75%, rgba(16,20,19,.44))'}}/>
    <svg width={W} height={H} style={{position: 'absolute', inset: 0}}>
      {Array.from({length: 16}, (_, i) => <line key={i} x1={50 + i * 132} y1={80} x2={50 + i * 132 + (i < 8 ? 90 : -90) * pressure} y2={910} stroke="#727065" opacity={.1} strokeWidth={1}/>) }
    </svg>
    <SceneLabel shot={shot} frame={frame}/>
    <div style={{position: 'absolute', left: 146, top: 284, fontFamily: SERIF, fontSize: 62, letterSpacing: 10, color: PAPER, opacity: fade(frame, voiced ? shot.cues[1].from - 12 : 34, voiced ? 18 : 36)}}>今天才明白，</div>
    <div style={{position: 'absolute', left: 146, top: 534, fontFamily: SERIF, fontSize: 67, lineHeight: 1.6, letterSpacing: 8, color: '#d9d1be', opacity: fade(frame, shot.cues[1].from, voiced ? 24 : 40)}}><div><span style={{color: '#b84c42'}}>我</span>也在其中</div><div>混了多年；</div></div>
    <div style={{position: 'absolute', left: 118, top: 826, height: 2, width: 330, background: RED, opacity: .55 * pressure}}/>
  </>;
};

const Children: React.FC<{shot: Shot;frame: number;voiced: boolean}> = ({shot, frame, voiced}) => <>
  <Art name="child" frame={frame} duration={432} darken={0.06}/>
  <SceneLabel shot={shot} frame={frame}/>
  <div style={{position: 'absolute', left: 145, top: 343, fontFamily: SERIF, fontSize: 63, lineHeight: 1.75, letterSpacing: 7, color: PAPER, opacity: fade(frame, voiced ? shot.cues[0].from - 12 : 40, voiced ? 18 : 40)}}><div>没有吃过人的孩子，</div><div>或者还有？</div></div>
</>;

const Plea: React.FC<{shot: Shot;frame: number;voiced: boolean}> = ({shot, frame, voiced}) => <>
  <Art name="child" frame={264 + frame} duration={432} darken={.65}/>
  <div style={{position: 'absolute', top: 413, left: 150, right: 150, color: PAPER, fontFamily: SERIF, fontSize: 138, fontWeight: 600, letterSpacing: 16, textAlign: 'center', opacity: fade(frame, voiced ? shot.cues[0].from - 12 : 5, voiced ? 12 : 22)}}>救救孩子<span style={{fontSize: 66, letterSpacing: 2}}>……</span></div>
  <div style={{position: 'absolute', left: 0, right: 0, top: 764, textAlign: 'center', fontFamily: SANS, fontSize: 23, color: '#aaa99a', letterSpacing: 6, opacity: fade(frame, 76, 28)}}>鲁迅 ·《狂人日记》· 一九一八年四月</div>
</>;

const Scene: React.FC<{shot: Shot;frame: number;voiced: boolean}> = ({shot, frame, voiced}) => <AbsoluteFill>
  {shot.id === 'title' ? <Title frame={frame}/> : null}
  {shot.id === 'moon' ? <Moon shot={shot} frame={frame} voiced={voiced}/> : null}
  {shot.id === 'watch' ? <Watch shot={shot} frame={frame}/> : null}
  {shot.id === 'history' ? <History shot={shot} frame={frame}/> : null}
  {shot.id === 'question' ? <Question shot={shot} frame={frame} voiced={voiced}/> : null}
  {shot.id === 'complicity' ? <Complicity shot={shot} frame={frame} voiced={voiced}/> : null}
  {shot.id === 'children' ? <Children shot={shot} frame={frame} voiced={voiced}/> : null}
  {shot.id === 'plea' ? <Plea shot={shot} frame={frame} voiced={voiced}/> : null}
</AbsoluteFill>;

export const MadmanFilm: React.FC<FilmProps> = ({timelineData = timeline, audioSrc = 'madman/audio/atmosphere.wav', voiced = false}) => {
  const frame = useCurrentFrame();
  const active = timelineData.shots.filter(s => frame >= s.from && frame < s.from + s.duration + 18);
  const current = timelineData.shots.find(s => frame >= s.from && frame < s.from + s.duration)!;
  return <AbsoluteFill style={{background: INK, width: W, height: H, overflow: 'hidden'}}>
    {active.map((shot, i) => <AbsoluteFill key={shot.id} style={{opacity: shot.from === 0 || i === 0 ? 1 : fade(frame, shot.from, 18)}}><Scene shot={shot} frame={frame - shot.from} voiced={voiced}/></AbsoluteFill>)}
    <Dust frame={frame}/><PrintTexture/>
    <div style={{position: 'absolute', inset: '0 0 auto', height: 84, background: '#0a0c0d'}}/>
    <div style={{position: 'absolute', inset: '914px 0 0', background: '#0a0c0d'}}/>
    <Caption shot={current} frame={frame - current.from}/>
    <div style={{position: 'absolute', left: 112, top: 31, fontFamily: SANS, fontSize: 17, letterSpacing: 5, color: '#9a9e95', opacity: fade(frame, 26)}}>狂人日记 <span style={{fontSize: 12, marginLeft: 17, color: '#616862'}}>DIARY OF A MADMAN</span></div>
    <div style={{position: 'absolute', right: 112, top: 32, fontFamily: SANS, fontSize: 15, letterSpacing: 4, color: '#737a72', opacity: fade(frame, 26)}}>鲁迅 / 原文节选</div>
    <Audio src={staticFile(audioSrc)}/>
    <AbsoluteFill style={{background: '#0a0c0d', opacity: 1 - fade(frame, 0, 18), pointerEvents: 'none'}}/>
  </AbsoluteFill>;
};
