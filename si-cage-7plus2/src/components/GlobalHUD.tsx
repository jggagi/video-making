import React from 'react';
import {useCurrentFrame} from 'remotion';
import {C, CN, FONT, GLOW} from '../lib/theme';
import {clamp, smooth} from '../lib/math';
import {captions} from '../lib/captions';
import timeline from '../../timeline.json';

export const humanChunks = (frame: number) => frame >= timeline.overloadFrame ? 7 : timeline.chunkFrames.filter((n) => frame >= n).length;
export const activeVariables = (frame: number) => Math.round(7 * Math.pow(128490 / 7, clamp((frame - 2700) / 2450)));
export const reasoningDepth = (frame: number) => {
  const local = frame - 5400;
  const markers = [[154, 4], [260, 10000], [510, 500000], [760, 5000000]];
  if (local <= 154) return 4;
  for (let i = 1; i < markers.length; i++) {
    const [end, value] = markers[i];
    const [start, previous] = markers[i - 1];
    if (local <= end) return Math.round(previous * Math.pow(value / previous, (local - start) / (end - start)));
  }
  return 5000000;
};

export const GlobalHUD: React.FC = () => {
  const frame = useCurrentFrame();
  const chunks = humanChunks(frame);
  const critical = frame >= 1200 && frame < 1800;
  const color = critical ? C.red : C.amber;
  const cue = captions.find((c) => frame >= c.from && frame < c.to);
  const cueAlpha = cue ? Math.min(smooth((frame - cue.from) / 14), smooth((cue.to - frame) / 14)) : 0;
  const act = frame < 2700 ? 1 : frame < 5400 ? 2 : frame < 8400 ? 3 : 4;
  const sec = Math.floor(frame / 60);
  return <div style={{position: 'absolute', inset: 0, pointerEvents: 'none', zIndex: 20, fontFamily: FONT}}>
    <div style={{position: 'absolute', inset: '0 0 auto', height: 195, background: 'linear-gradient(#050811 78%, transparent)'}}/>
    <div style={{position: 'absolute', top: 38, left: 64, right: 64, display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: C.muted, fontSize: 12, letterSpacing: 3}}>
      <span>SUPERINTELLIGENCE / OBSERVATION 02</span><span>COGNITIVE CONTAINMENT STUDY</span><span>{String(sec / 60 | 0).padStart(2, '0')}:{String(sec % 60).padStart(2, '0')} / 03:00</span>
    </div>
    <div style={{position: 'absolute', left: 64, right: 64, top: 72, height: 1, background: C.line}}/>
    <div style={{position: 'absolute', left: 64, top: 92, width: 835}}>
      <div style={{fontSize: 12, color, letterSpacing: 1.7, marginBottom: 13}}>BIOLOGICAL WORKING MEMORY</div>
      <div style={{display: 'flex', alignItems: 'center', gap: 22}}>
        <div style={{display: 'flex', gap: 6}}>{Array.from({length: 9}, (_, i) => <div key={i} style={{width: 28, height: 17, border: `1px solid ${color}`, background: i < chunks || critical ? color : 'transparent', opacity: critical ? 0.5 + 0.5 * Math.abs(Math.sin(frame * 0.28)) : 1, boxShadow: i < chunks ? `0 0 14px ${color}33` : undefined}}/>)}</div>
        <div style={{fontSize: 23, color, fontWeight: 600}}>{critical ? '10 / 9' : `${chunks} / 9`} <span style={{fontSize: 12, fontWeight: 400}}>CHUNKS</span></div>
      </div>
      <div style={{fontSize: 12, color: critical ? C.red : C.muted, marginTop: 12, letterSpacing: 1}}>{critical ? '[CRITICAL OVERFLOW - SYNAPSE SNAP]' : frame >= 1800 ? '7 CHUNKS | CAUSAL DEPTH: 4 STEPS' : 'CAPACITY 7±2 / BIOLOGICAL CONSTRAINT'}</div>
    </div>
    <div style={{position: 'absolute', right: 64, top: 92, textAlign: 'right'}}>
      <div style={{fontSize: 12, color: C.cyan, letterSpacing: 1.7, marginBottom: 10}}>ACTIVE CONTEXT MANIFOLD</div>
      <div style={{fontSize: 30, color: C.white, letterSpacing: -1, filter: GLOW.cyan}}>{activeVariables(frame).toLocaleString('en-US')} <span style={{fontSize: 12, color: C.cyan, letterSpacing: 1}}>VARIABLES</span></div>
      <div style={{fontSize: 12, color: C.cyan, marginTop: 8}}>COT REASONING DEPTH: STEP #{reasoningDepth(frame).toLocaleString('en-US')} <span style={{color: C.muted}}>(PRECISION: 100.00%)</span></div>
    </div>
    <div style={{position: 'absolute', left: 64, right: 64, top: 188, height: 1, background: C.line}}/>
    <div style={{position: 'absolute', bottom: 0, left: 0, right: 0, height: 157, background: 'linear-gradient(transparent, #050811 22%)'}}/>
    <div data-narrative-language="zh-CN" style={{position: 'absolute', left: 110, right: 110, top: 947, textAlign: 'center', opacity: cueAlpha}}>
      <div style={{fontFamily: CN, fontSize: 29, lineHeight: 1.5, fontWeight: 500, letterSpacing: 1, color: '#edf4fa'}}>{cue?.zh}</div>
    </div>
    <div style={{position: 'absolute', bottom: 28, left: 64, fontSize: 11, color: C.muted, letterSpacing: 1.5}}>ACT 0{act} / 04</div>
    <div style={{position: 'absolute', bottom: 28, right: 64, fontFamily: CN, fontSize: 11, color: C.muted, letterSpacing: 1.5}}>7±2 的囚笼</div>
    <div style={{position: 'absolute', bottom: 0, left: 0, height: 2, width: `${frame / 10799 * 100}%`, background: frame < 1800 ? color : C.cyan, filter: frame >= 1800 ? GLOW.cyan : undefined}}/>
  </div>;
};
