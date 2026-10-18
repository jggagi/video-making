import React from 'react';
import {useCurrentFrame} from 'remotion';
import {C, FONT, TOTAL_FRAMES} from '../lib/theme';
import {anchorState, SUBTITLES} from '../lib/timeline';
import {VOICED_SUBTITLES} from '../lib/voiced-subtitles';
import {ease, fmt} from '../lib/math';

export const GlobalHUD: React.FC<{withAudio?: boolean}> = ({withAudio = false}) => {
  const frame = useCurrentFrame();
  const state = anchorState(frame);
  const cue = (withAudio ? VOICED_SUBTITLES : SUBTITLES).find((s) => frame >= s.from && frame < s.to);
  const opacity = 1 - ease(frame, 10470, 10500);
  const cueOpacity = cue ? Math.min(ease(frame, cue.from, cue.from + 20), 1 - ease(frame, cue.to - 16, cue.to)) : 0;
  return <div style={{position: 'absolute', inset: 0, fontFamily: FONT, zIndex: 30, opacity, pointerEvents: 'none'}}>
    <div style={{position: 'absolute', left: 90, top: 48}}>
      <div style={{fontSize: 12, letterSpacing: 3, color: C.amber, marginBottom: 14}}>ATOMS / PHYSICAL TIME</div>
      <div style={{fontSize: 24, color: C.white, fontVariantNumeric: 'tabular-nums'}}>T + {state.milliseconds.toFixed(4).padStart(8, '0')} <span style={{fontSize: 15, color: C.amber}}>ms</span></div>
      <div style={{fontSize: 15, color: C.muted, marginTop: 12, fontVariantNumeric: 'tabular-nums'}}>DROPLET ALTITUDE: <span style={{color: C.amber}}>{state.altitudeMm.toFixed(2)} mm</span></div>
      <div style={{fontSize: 10, letterSpacing: 1.1, color: C.muted, marginTop: 10}}>NORMALIZED REFERENCE TRAJECTORY</div>
    </div>
    <div style={{position: 'absolute', left: 700, top: 55, width: 520, textAlign: 'center'}}>
      <div style={{fontSize: 12, letterSpacing: 4, color: C.muted, marginBottom: 13}}>A SPECULATIVE VISUAL ESSAY</div>
      <div style={{fontSize: 24, letterSpacing: 1.5, fontWeight: 300}}>一眼万年</div>
      <div style={{fontSize: 11, letterSpacing: 2, color: C.cyan, marginTop: 10}}>ONE BLINK, TEN MILLENNIA</div>
      <div style={{fontSize: 10, letterSpacing: 1, color: C.muted, marginTop: 10}}>500 ms  /  10,000 SUBJECTIVE YEARS</div>
    </div>
    <div style={{position: 'absolute', right: 90, top: 48, textAlign: 'right'}}>
      <div style={{fontSize: 12, letterSpacing: 3, color: C.cyan, marginBottom: 14}}>BITS / SI COGNITIVE STEP</div>
      <div style={{fontSize: 24, fontVariantNumeric: 'tabular-nums'}}>#{fmt(state.step)}</div>
      <div style={{fontSize: 14, color: C.muted, marginTop: 12}}>SUBJECTIVE EQUIVALENT: <span style={{color: C.cyan}}>{state.years.toLocaleString('en-US', {minimumFractionDigits: 1, maximumFractionDigits: 1})} YEARS</span></div>
    </div>
    <div style={{position: 'absolute', top: 190, left: 90, right: 90, height: 1, backgroundColor: C.line}}/>
    <div style={{position: 'absolute', left: 90, right: 90, bottom: 0, height: 143, background: 'linear-gradient(transparent,rgba(5,8,17,.97) 22%)', textAlign: 'center'}}>
      {cue ? <div style={{paddingTop: 20, opacity: cueOpacity}}>
        <div style={{fontSize: 29, lineHeight: 1.45, fontWeight: 500, letterSpacing: 1}}>{cue.zh}</div>
        <div style={{fontSize: 18, lineHeight: 1.6, marginTop: 8, color: '#9eafc1'}}>{cue.en}</div>
      </div> : null}
      <div style={{position: 'absolute', bottom: 20, left: 0, right: 0, height: 2, backgroundColor: C.line}}>
        <div style={{width: `${100 * frame / (TOTAL_FRAMES - 1)}%`, height: '100%', backgroundColor: frame < 1100 || frame >= 7200 ? C.amber : C.cyan}}/>
        {[1 / 6, 5 / 12, 2 / 3].map((p) => <div key={p} style={{position: 'absolute', left: `${p * 100}%`, top: -3, width: 1, height: 8, backgroundColor: C.muted}}/>)}
      </div>
    </div>
  </div>;
};
