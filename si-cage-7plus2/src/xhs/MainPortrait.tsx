import React from 'react';
import {AbsoluteFill, Audio, staticFile, useCurrentFrame} from 'remotion';
import plan from '../../xhs-timeline.json';
import {C, CN, FONT, GLOW} from '../lib/theme';
import {clamp, smooth} from '../lib/math';
import {PortraitScene, type PortraitStage} from './PortraitScenes';

const keywords = /(第十个变量|逻辑链瞬间熔断|十万个变量|高维几何流形|全部因果|十万维|7±2|十万亿个分身|二维直线|“巧合”)/g;
const captionLines = plan.cues.flatMap((cue) => {
  if ('captionParts' in cue && cue.captionParts) return cue.captionParts.map((part) => ({
    from: cue.startFrame + part.from, to: cue.startFrame + part.to, lines: part.lines,
  }));
  return [{from: cue.startFrame, to: cue.endFrame, lines: cue.displayLines}];
});

export const PortraitBackdrop: React.FC = () => <>
  <AbsoluteFill style={{background: C.bg}}/>
  <svg width="1080" height="1920" viewBox="0 0 1080 1920" style={{position: 'absolute', inset: 0}}>
    <defs>
      <pattern id="portrait-grid" width="60" height="60" patternUnits="userSpaceOnUse"><path d="M60 0H0V60" fill="none" stroke="#88a9bc" strokeOpacity="0.055" strokeWidth="1"/></pattern>
      <radialGradient id="portrait-halo"><stop stopColor={C.cyan} stopOpacity="0.08"/><stop offset="1" stopColor={C.cyan} stopOpacity="0"/></radialGradient>
    </defs>
    <rect width="1080" height="1920" fill="url(#portrait-grid)"/>
    <ellipse cx="510" cy="870" rx="620" ry="720" fill="url(#portrait-halo)"/>
    <path d="M72 160H936M72 1640H936" stroke={C.line}/>
    <path d="M72 500V520H92M936 500V520H916M72 1250V1230H92M936 1250V1230H916" stroke="#7892a3" strokeOpacity="0.28" fill="none"/>
  </svg>
</>;

export const MainPortrait: React.FC<{withAudio: boolean}> = ({withAudio}) => {
  const frame = useCurrentFrame();
  const scene = plan.scenes.find((s) => frame >= s.from && frame < s.to) ?? plan.scenes[plan.scenes.length - 1];
  const local = frame - scene.from;
  const gold = ['overload', 'oracle', 'ending'].includes(scene.id);
  const color = gold ? C.gold : C.cyan;
  const sceneIndex = plan.scenes.indexOf(scene);
  const act = sceneIndex === 0 ? 0 : sceneIndex < 3 ? 1 : sceneIndex === 3 ? 2 : 3;
  const caption = captionLines.find((c) => frame >= c.from && frame < c.to);
  const titleAlpha = smooth(clamp((local + 6) / 18));
  const captionAlpha = caption ? Math.min(smooth((frame - caption.from + 3) / 9), smooth((caption.to - frame) / 6)) : 0;
  const seconds = Math.floor(frame / 60);
  return <AbsoluteFill style={{background: C.bg, overflow: 'hidden'}}>
    <div lang="zh-CN" data-format="xhs-portrait" style={{position: 'absolute', width: plan.logicalWidth, height: plan.logicalHeight, transform: `scale(${plan.renderScale})`, transformOrigin: '0 0', color: C.white, fontFamily: CN}}>
      <PortraitBackdrop/>
      <div style={{position: 'absolute', left: 72, top: 112, fontFamily: FONT, fontSize: 18, color: C.muted, letterSpacing: 2}}>COGNITION / EP.02</div>
      <div style={{position: 'absolute', right: 144, top: 112, fontFamily: FONT, fontSize: 18, color: C.muted}}>00:{String(seconds).padStart(2, '0')} / 01:00</div>
      <div style={{position: 'absolute', left: 72, top: 185, fontSize: 22, color, letterSpacing: 2}}>{plan.conceptLabel}</div>
      <div style={{position: 'absolute', left: 70, right: 150, top: 242, opacity: titleAlpha, transform: `translateY(${(1 - titleAlpha) * 10}px)`}}>
        <div style={{fontSize: scene.id === 'ending' ? 82 : 72, fontWeight: 650, lineHeight: 1.28, letterSpacing: -1.5, filter: gold ? GLOW.gold : GLOW.cyan}}>{scene.title}</div>
        <div style={{fontSize: scene.id === 'ending' ? 42 : 62, fontWeight: 500, lineHeight: 1.4, marginTop: 6, color: '#e6eff4', letterSpacing: -1}}>{scene.subtitle}</div>
      </div>
      <div style={{position: 'absolute', left: 72, right: 144, top: 451, display: 'flex', gap: 12}}>
        {['过载', '降维', '秩序', '答案'].map((label, i) => <div key={label} style={{flex: 1}}>
          <div style={{height: 3, background: i <= act ? color : '#273444', opacity: i === act ? 1 : 0.5}}/>
          <div style={{fontSize: 18, color: i === act ? color : C.muted, marginTop: 13, letterSpacing: 2}}>{String(i + 1).padStart(2, '0')} / {label}</div>
        </div>)}
      </div>
      <PortraitScene stage={scene.id as PortraitStage} frame={local}/>
      <div style={{position: 'absolute', left: 72, right: 144, top: 1281, fontFamily: FONT, fontSize: 18, letterSpacing: 1.2, color, opacity: 0.75}}>{scene.telemetry}</div>
      <div data-caption-language="zh-CN" style={{position: 'absolute', left: 72, width: 828, top: 1360, opacity: captionAlpha}}>
        {caption?.lines.map((line, i) => <div key={`${caption.from}-${i}`} style={{fontSize: line.length > 18 ? 42 : 48, fontWeight: 600, lineHeight: 1.55, letterSpacing: 0.2, whiteSpace: 'nowrap', textShadow: '0 2px 6px #000'}}>
          {line.split(keywords).map((part, j) => <span key={j} style={{color: j % 2 ? color : '#f3f5f7'}}>{part}</span>)}
        </div>)}
      </div>
      {!caption && frame >= 3325 && frame < 3400 && <div style={{position: 'absolute', left: 72, top: 1360, fontSize: 40, lineHeight: 1.6, color: C.gold}}>你会相信一个<br/>无法解释的答案吗？</div>}
      <div style={{position: 'absolute', left: 72, top: 1575, fontSize: 20, color: C.muted, letterSpacing: 1}}>超级智能可视化系列 · 7±2 的囚笼</div>
      <div style={{position: 'absolute', left: 72, top: 1668, fontSize: 19, color: '#627286'}}>程序化动画 · 百炼 AI 合成旁白</div>
      <div style={{position: 'absolute', left: 0, top: 1740, width: 1080 * frame / (plan.durationInFrames - 1), height: 4, background: color, filter: gold ? GLOW.gold : GLOW.cyan}}/>
    </div>
    {withAudio && <Audio src={staticFile('audio-xhs-v1/soundtrack.wav')}/>}
  </AbsoluteFill>;
};
