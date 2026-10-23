import React, {useEffect, useState} from 'react';
import {AbsoluteFill, Audio, cancelRender, continueRender, delayRender, staticFile, useCurrentFrame} from 'remotion';
import {Scene} from './Scene';
import captions from '../captions.json';

const AMBER = '#F59E0B';
const CYAN = '#06B6D4';
const GOLD = '#FACC15';
const IVORY = '#FEF3C7';
const SKY = '#38BDF8';
const RED = '#E11D48';
const clamp = (x: number): number => Math.min(1, Math.max(0, x));
type Caption = {startFrame: number; endFrame: number; text: string};

// Full requested field/value strings alternate in the same three fixed rows.
// This keeps every word readable at 360px without clipping or shrinking a long HUD.
const hudRows = (frame: number): string[] => {
  const field = frame % 420 < 105;
  const progress = clamp(frame / 2820);
  const fidelity = frame >= 2820 ? '99.9999% [INDISTINGUISHABLE]' : (42 + 57.9999 * progress).toFixed(1) + '%';
  return [
    field ? 'MEMORY INGESTION STREAM:' : '1,420,000,000 HEARTBEATS LOGGED',
    field ? 'SUBCURRENT MIMICRY FIDELITY:' : fidelity,
    field ? 'CRITICAL LIFE DECISION [T-0.00s]:' : frame >= 3900 ? 'SIGNATORY IDENTITY = [VERIFIED]' : 'SIGNATORY IDENTITY = [ ? ]',
  ];
};

export const Film: React.FC<{silent?: boolean; cover?: false | 'A' | 'B'}> = ({silent = false, cover = false}) => {
  const currentFrame = useCurrentFrame();
  const frame = cover === 'A' ? 3720 : cover === 'B' ? 4920 : currentFrame;
  const [fontHandle] = useState(() => delayRender('EP18 v03 local open fonts'));
  useEffect(() => {
    let active = true;
    Promise.all([
      document.fonts.load('600 43px EPSerif'),
      document.fonts.load('400 30px EPMono'),
    ]).then(() => document.fonts.ready).then(() => {if (active) continueRender(fontHandle);})
      .catch((error) => cancelRender(error instanceof Error ? error : new Error(String(error))));
    return () => {active = false; continueRender(fontHandle);};
  }, [fontHandle]);

  const cap = !cover && (captions as Caption[]).find((c) => frame >= c.startFrame && frame < c.endFrame);
  const lines = cap ? cap.text.split('\n') : [];
  if (lines.length > 2 || lines.some((line) => Array.from(line).length > 17)) throw new Error('Caption exceeds the two-line mobile layout');
  const hudFrame = Math.min(frame, 4859);
  const hudOpacity = frame < 4860 ? 0.88 : 0.34;
  const titleOpacity = 1 - clamp((frame - 510) / 90);
  const stamp = clamp((frame - 5040) / 60);

  return <AbsoluteFill style={{background: '#06070A', color: IVORY, fontFamily: 'EPSerif, serif'}}>
    <style>{`
      @font-face {font-family:EPSerif;src:url('${staticFile('fonts/NotoSerifSC.ttf')}') format('truetype');font-weight:100 900;font-display:block;}
      @font-face {font-family:EPMono;src:url('${staticFile('fonts/RobotoMono.ttf')}') format('truetype');font-weight:100 700;font-display:block;}
    `}</style>
    <Scene frame={frame}/>
    <svg width="2160" height="3840" viewBox="0 0 1080 1920" style={{position: 'absolute', inset: 0, pointerEvents: 'none'}}>
      {!cover && <g fontFamily="EPMono, monospace" fontSize="30" opacity={hudOpacity}>
        {hudRows(hudFrame).map((row, i) => <text key={i} x="65" y={189 + i * 39} fill={i === 0 ? AMBER : i === 1 ? frame < 1800 ? CYAN : GOLD : RED}>{row}</text>)}
      </g>}
      {!cover && titleOpacity > 0 && <g opacity={titleOpacity}>
        <text x="65" y="324" fontSize="30" fill={SKY}>一 眼 万 年 · 终 极 收 官</text>
        <text x="61" y="392" fontSize="68" fontWeight="600" letterSpacing="11" fill={IVORY}>心印潜流</text>
        <text x="65" y="429" fontFamily="EPMono" fontSize="21" letterSpacing="1" fill={CYAN}>THE SUBCURRENT DOPPELGÄNGER</text>
      </g>}
      {!cover && frame >= 600 && frame < 1320 && <g fontSize="32" fill={AMBER} opacity="0.8">
        <text x="65" y="375">{frame < 840 ? '删掉的真心话' : frame < 1080 ? '0.32s · 欲言又止' : '童年残留的梦'}</text>
      </g>}
      {!cover && frame >= 1320 && frame < 2820 && <g fontFamily="EPMono" fontSize="30" fill={GOLD} opacity="0.78">
        <text x="65" y="355">SUBCURRENT ITERATION</text>
        <text x="65" y="399">#{Math.floor(1000000 + 9000000 * clamp((frame - 1320) / 1500)).toLocaleString('en-US')}</text>
        <text x="65" y="443">ΔΨ → {(1 - clamp((frame - 1320) / 1440)).toFixed(6)}</text>
      </g>}
      {!cover && frame >= 1320 && frame < 2820 && <g opacity="0.65">
        <text x="720" y="1010" fill={SKY} fontSize="30">原形 / 潜流</text>
        {[0, 1].map((line) => <path key={line} fill="none" stroke={line === 0 ? AMBER : GOLD} strokeWidth="1.7"
          d={Array.from({length: 45}, (_, i) => {
            const x = 720 + i * 4;
            const error = (1 - clamp((frame - 1320) / 1440)) * (line ? 14 : 0);
            const y = 1065 + Math.sin(i * .25 + frame * .012) * 14 + Math.sin(i * .61 - frame * .007) * error;
            return `${i ? 'L' : 'M'}${x},${y}`;
          }).join(' ')}/>)}
      </g>}
      {!cover && frame >= 2820 && frame < 4380 && <g fontSize="35" fill={frame < 3900 ? AMBER : GOLD}>
        <text x="65" y="355">{frame < 3600 ? '改变命运的抉择' : frame < 3900 ? '你还在犹豫 · 它已动身' : '身份验证通过'}</text>
        {frame >= 3900 && <text x="65" y="405" fontFamily="EPMono" fontSize="30" fill={SKY}>SIGNATURE: AUTHENTIC HUMAN</text>}
        <rect x="713" y="815" width="178" height="60" rx="8" fill={frame < 3900 ? '#081318' : GOLD} stroke={frame < 3900 ? SKY : GOLD} strokeWidth="1.5"/>
        <text x="724" y="859" fontSize="39" fontWeight="600" fill={frame < 3900 ? IVORY : '#06070A'}>{frame < 3900 ? '确认执行' : '指令生效'}</text>
      </g>}
      {!cover && frame >= 4380 && frame < 5040 && <g fontSize="36" fill={IVORY} opacity="0.8">
        <text x="65" y="355">{frame < 4860 ? '指令已生效。' : 'ORIGIN OF CHOICE: UNDECIDABLE'}</text>
      </g>}
      {!cover && stamp > 0 && <g opacity={stamp}>
        <text x="65" y="342" fontSize="36" fontWeight="600" fill={GOLD}>一眼万年 · 全三季终</text>
        <text x="65" y="395" fontSize="38" fill={IVORY}>到底是谁，正在用你的眼睛</text>
        <text x="65" y="447" fontSize="38" fill={IVORY}>看世界？</text>
      </g>}
      {cap && <g fill={IVORY} fontWeight="700" fontSize="43" style={{paintOrder: 'stroke', stroke: '#06070A', strokeWidth: 6, strokeLinejoin: 'round'}}>
        {lines.map((line, i) => <text key={i} x="65" y={lines.length === 1 ? 1420 : 1390 + i * 56}>{line}</text>)}
      </g>}
      {!cover && frame >= 5160 && <text x="65" y="1484" fill={IVORY} opacity="0.35" fontSize="27">未来 SI 思想实验 · 遥测与数值均为虚构</text>}
      {cover && <g>
        {cover === 'A' && <g>
          <rect x="713" y="815" width="178" height="60" rx="8" fill="#081318" stroke={SKY} strokeWidth="1.5"/>
          <text x="724" y="859" fontSize="39" fontWeight="600" fill={IVORY}>确认执行</text>
        </g>}
        <rect x="44" y="235" width="865" height="293" rx="6" fill="#06070A" opacity="0.86"/>
        <text x="65" y="298" fontSize="31" fill={SKY}>一眼万年 · EP.18 · 终极悬念大结局</text>
        <text x="65" y="372" fontSize="60" fontWeight="700" fill={IVORY}>当你犹豫的 0.1 秒</text>
        <text x="65" y="437" fontSize="47" fontWeight="600" fill={GOLD}>海底那个记下了你一生的 AI</text>
        <text x="65" y="501" fontSize="54" fontWeight="700" fill={IVORY}>替你按下了确认键</text>
      </g>}
    </svg>
    {!silent && !cover && <Audio src={staticFile('audio/master.wav')}/>}
  </AbsoluteFill>;
};
