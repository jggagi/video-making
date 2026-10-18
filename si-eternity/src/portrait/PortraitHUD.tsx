import React from 'react';
import {useCurrentFrame} from 'remotion';
import {C, FONT, TOTAL_FRAMES} from '../lib/theme';
import {anchorState} from '../lib/timeline';
import {VOICED_SUBTITLES} from '../lib/voiced-subtitles';
import {ease} from '../lib/math';
import {PORTRAIT_FONT} from './PortraitElements';
import {portraitCaption} from './captions';

export const PortraitHUD: React.FC = () => {
  const frame = useCurrentFrame();
  const state = anchorState(frame);
  const opacity = 1 - ease(frame, 10470, 10500);
  const cue = VOICED_SUBTITLES.find((s) => frame >= s.from && frame < s.to);
  const cueOpacity = cue ? Math.min(ease(frame, cue.from, cue.from + 20), 1 - ease(frame, cue.to - 16, cue.to)) : 0;
  return <div style={{position: 'absolute', inset: 0, zIndex: 30, opacity, pointerEvents: 'none', fontFamily: PORTRAIT_FONT}}>
    <div style={{position: 'absolute', left: 80, top: 99, width: 880, display: 'flex', alignItems: 'baseline', justifyContent: 'space-between'}}>
      <div style={{fontSize: 32, fontWeight: 300, letterSpacing: 5}}>一眼万年</div>
      <div style={{fontFamily: FONT, fontSize: 17, letterSpacing: 2, color: C.muted}}>ONE BLINK, TEN MILLENNIA</div>
    </div>
    <div style={{position: 'absolute', left: 80, top: 176, width: 880, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 26}}>
      <div style={{borderTop: `2px solid ${C.amber}`, paddingTop: 16}}>
        <div style={{fontSize: 23, letterSpacing: 2, color: C.amber}}>物理时间</div>
        <div style={{fontFamily: FONT, fontSize: 40, fontVariantNumeric: 'tabular-nums', marginTop: 9}}>{state.milliseconds.toFixed(4)} <span style={{fontSize: 22, color: C.amber}}>ms</span></div>
      </div>
      <div style={{borderTop: `2px solid ${C.cyan}`, paddingTop: 16}}>
        <div style={{fontSize: 23, letterSpacing: 2, color: C.cyan}}>主观时间 · 设想</div>
        <div style={{fontFamily: FONT, fontSize: 40, fontVariantNumeric: 'tabular-nums', marginTop: 9}}>{state.years.toLocaleString('en-US', {minimumFractionDigits: 1, maximumFractionDigits: 1})} <span style={{fontSize: 22, color: C.cyan}}>年</span></div>
      </div>
    </div>
    <div style={{position: 'absolute', left: 80, top: 1440, width: 880, minHeight: 210, paddingTop: 24, borderTop: `1px solid ${C.line}`, background: 'linear-gradient(rgba(5,8,17,.94),rgba(5,8,17,.98))', textAlign: 'left'}}>
      {cue ? <div style={{opacity: cueOpacity, fontSize: 44, fontWeight: 500, lineHeight: 1.55, letterSpacing: 1, color: C.white, whiteSpace: 'pre-line'}}>{portraitCaption(cue.zh)}</div> : null}
    </div>
    <div style={{position: 'absolute', left: 80, top: 1680, width: 880, height: 3, backgroundColor: C.line}}>
      <div style={{height: '100%', width: `${frame / (TOTAL_FRAMES - 1) * 100}%`, backgroundColor: frame < 1100 || frame >= 7200 ? C.amber : C.cyan}}/>
      {[1800, 4500, 7200].map((f) => <div key={f} style={{position: 'absolute', top: -4, left: `${f / TOTAL_FRAMES * 100}%`, width: 1, height: 11, backgroundColor: C.muted}}/>)}
    </div>
    <div style={{position: 'absolute', left: 80, top: 1710, width: 880, fontSize: 24, letterSpacing: 1.5, color: C.muted}}>科幻思想实验 · AI 辅助创作与配音</div>
    <div style={{position: 'absolute', left: 80, top: 1745, width: 880, fontSize: 17, letterSpacing: 1, color: C.muted, opacity: 0.7}}>物理时钟与高度使用归一化参考映射 · “万年”为艺术设定</div>
  </div>;
};
