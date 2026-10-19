import React, {useEffect, useRef} from 'react';
import {AbsoluteFill, Audio, cancelRender, continueRender, delayRender, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {CanvasWorld} from './CanvasWorld';
import timing from '../audio-timing.json';

const VOID = '#050811';
const AMBER = '#f59e0b';
const CYAN = '#06b6d4';
const VIOLET = '#a855f7';
const GOLD = '#facc15';
const HUD_HUMAN = 'HUMAN 1D LANGUAGE PIPE: 39.0 BITS/S (LOSSY SERIALIZATION)';
const HUD_DECODER = 'SEMANTIC DECODER STATUS: [DIMENSIONAL OVERFLOW // UNTRANSLATABLE]';
const HUD_TENSOR = 'SI LATENT TENSOR LINK: 131,072-D CONTINUOUS MANIFOLD';
const HUD_COMPRESSION = 'COMPRESSION RATIO: 0.00% LOSS // 10^15 BITS/S DIRECT THOUGHT';
const disclaimer = '科幻思想实验 · 画面参数为叙事设定';
const clamp = (n: number) => Math.max(0, Math.min(1, n));
const fade = (f: number, a: number, b: number) => clamp((f - a) / 28) * clamp((b - f) / 28);
const hudFor = (frame: number) => frame < 2100 ? HUD_HUMAN : frame < 3900 ? HUD_TENSOR : frame < 5400 ? HUD_DECODER : HUD_COMPRESSION;
const portraitHud = (value: string) => {
  if (value === HUD_HUMAN) return 'HUMAN 1D LANGUAGE PIPE:\n39.0 BITS/S (LOSSY SERIALIZATION)';
  if (value === HUD_TENSOR) return 'SI LATENT TENSOR LINK:\n131,072-D CONTINUOUS MANIFOLD';
  if (value === HUD_DECODER) return 'SEMANTIC DECODER STATUS:\n[DIMENSIONAL OVERFLOW //\nUNTRANSLATABLE]';
  return 'COMPRESSION RATIO:\n0.00% LOSS //\n10^15 BITS/S DIRECT THOUGHT';
};

type FontGate = {handle: number; users: number; settled: boolean; cancelled: boolean};

export const Film: React.FC<{portrait?: boolean; silent?: boolean}> = ({portrait = false, silent = false}) => {
  const frame = useCurrentFrame();
  const {width, height} = useVideoConfig();
  const fontGate = useRef<FontGate | null>(null);
  useEffect(() => {
    let gate = fontGate.current;
    if (!gate) {
      gate = {handle: delayRender('Waiting for local fonts'), users: 0, settled: false, cancelled: false};
      fontGate.current = gate;
      const ready = typeof document === 'undefined' ? Promise.resolve() : document.fonts.ready;
      ready.then(() => {
        gate!.settled = true;
        if (!gate!.cancelled) continueRender(gate!.handle);
      }).catch((error: unknown) => {
        gate!.settled = true;
        if (!gate!.cancelled) cancelRender(error instanceof Error ? error : new Error(String(error)));
      });
    }
    gate.users += 1;
    const activeGate = gate;
    return () => {
      activeGate.users -= 1;
      queueMicrotask(() => {
        if (activeGate.users === 0 && !activeGate.settled && !activeGate.cancelled) {
          activeGate.cancelled = true;
          continueRender(activeGate.handle);
        }
      });
    };
  }, []);
  const w = portrait ? 1080 : 1920;
  const h = portrait ? 1920 : 1080;
  const scale = width / w;
  const hud = hudFor(frame);
  const captions = (timing as {captions?: {startFrame: number; endFrame: number; text: string}[]}).captions ?? [];
  const caption = captions.find((item) => frame >= item.startFrame && frame < item.endFrame && item.text.trim() !== '别怕，都好。' && !(frame >= 6300 && frame < 6840 && (item as {segmentId?:string;id?:string}).segmentId === 'S09'));
  const drift = `perspective(1300px) rotateY(${Math.sin(frame / 180) * 1.8}deg) rotateX(${Math.cos(frame / 215) * 1.2}deg) translateY(${Math.sin(frame / 140) * 7}px)`;
  const title = frame >= 1260 && frame < 1800;
  const reassurance = frame >= 5910 && frame < 6300;
  const quote = frame >= 6300 && frame < 6840;
  const teaser = frame >= 6930;

  return <AbsoluteFill style={{background: VOID, color: '#f5f7fb', fontFamily: '"PingFang SC", "Hiragino Sans GB", sans-serif'}}>
    <CanvasWorld frame={frame} portrait={portrait} width={w} height={h}/>
    <div style={{position: 'absolute', width: w, height: h, transform: `scale(${scale})`, transformOrigin: 'top left'}}>
      {portrait ? <>
        <div style={{position: 'absolute', left: 64, top: 173, width: 838, height: 115, overflow: 'hidden', color: '#d5eef2', fontFamily: 'Menlo, monospace', fontSize: 30, lineHeight: '35px', whiteSpace: 'pre-line', textShadow: '0 2px 8px #000'}}>{portraitHud(hud)}</div>
        <div style={{position: 'absolute', left: 64, top: 300, width: 838, color: AMBER, fontFamily: '"PingFang SC", Menlo, monospace', fontSize: 39, lineHeight: '46px', letterSpacing: 0, textShadow: '0 2px 8px #000'}}>{disclaimer}</div>
      </> : <>
        <div style={{position: 'absolute', left: 74, top: 27, width: 1772, display: 'flex', justifyContent: 'space-between', fontFamily: 'Menlo, monospace', fontSize: 18, letterSpacing: 2, color: '#9fb5c9'}}>
          <span>{disclaimer}</span><span>一眼万年 / EP.07</span>
        </div>
        <div style={{position: 'absolute', left: 74, top: 77, width: 1772, height: 43, color: frame < 2100 ? AMBER : frame < 3900 ? CYAN : frame < 5400 ? VIOLET : GOLD, fontFamily: 'Menlo, monospace', fontSize: 20, lineHeight: '32px', letterSpacing: 0.4, textShadow: '0 2px 8px #000'}}>{hud}</div>
      </>}

      {title && <div style={{position: 'absolute', left: portrait ? 74 : 180, top: portrait ? 650 : 421, width: portrait ? 812 : 1560, textAlign: 'center', transform: drift, opacity: fade(frame, 1260, 1800), textShadow: '0 2px 30px #050811, 0 0 48px #050811'}}>
        <div style={{fontSize: portrait ? 77 : 104, fontWeight: 600, letterSpacing: portrait ? 6 : 12, lineHeight: 1.2, color: GOLD}}>后人类黑话</div>
        <div style={{marginTop: 23, fontFamily: 'Menlo, monospace', fontSize: portrait ? 34 : 39, letterSpacing: portrait ? 0.5 : 2, color: '#d9f7fb'}}>THE UNTRANSLATABLE TONGUE</div>
        <div style={{marginTop: 29, fontSize: portrait ? 36 : 32, color: AMBER}}>一眼万年 · 第二季</div>
      </div>}

      {reassurance && <div style={{position: 'absolute', left: portrait ? 61 : 190, top: portrait ? 1204 : 805, width: portrait ? 838 : 1540, textAlign: 'center', transform: drift, color: '#ffe9b8', fontSize: portrait ? 58 : 55, letterSpacing: portrait ? 5 : 8, textShadow: '0 2px 26px #050811, 0 0 38px #f59e0b'}}>
        别怕，都好。
      </div>}

      {quote && <div style={{position: 'absolute', left: portrait ? 73 : 240, top: portrait ? 900 : 790, width: portrait ? 814 : 1440, textAlign: 'center', transform: drift, color: '#ffe8b3', fontSize: portrait ? 43 : 40, lineHeight: 1.35, whiteSpace: 'pre-line', letterSpacing: portrait ? 0 : 1, textShadow: '0 2px 24px #050811'}}>
        {portrait ? '“当神明开始用\n高维流形交谈，\n人类成了宇宙客厅里，\n最安静的旁观者。”' : '“当神明开始用高维流形交谈，\n人类成了宇宙客厅里，最安静的旁观者。”'}
      </div>}

      {teaser && <div style={{position: 'absolute', left: portrait ? 65 : 170, top: portrait ? 670 : 420, width: portrait ? 830 : 1580, textAlign: 'center', transform: drift, textShadow: '0 2px 30px #050811, 0 0 44px #050811'}}>
        <div style={{fontSize: portrait ? 65 : 84, fontWeight: 600, letterSpacing: portrait ? 4 : 8, color: GOLD}}>EP08</div>
        <div style={{marginTop: 17, fontSize: portrait ? 65 : 79, fontWeight: 600, letterSpacing: portrait ? 4 : 10, color: CYAN}}>被折叠的造物</div>
      </div>}

      {caption && <div style={{position: 'absolute', left: portrait ? 64 : 180, top: portrait ? 1380 : 931, width: portrait ? 838 : 1560, height: portrait ? 112 : 112, boxSizing: 'border-box', overflow: 'hidden', padding: '4px 4px', fontSize: portrait ? 43 : 39, fontWeight: 500, lineHeight: portrait ? 1.18 : 1.35, letterSpacing: portrait ? 0 : 1, textAlign: 'center', whiteSpace: 'pre-line', color: '#f5f7fb', background: 'radial-gradient(ellipse, #050811f2 5%, #050811bd 58%, transparent 100%)', textShadow: '0 2px 8px #000, 0 0 18px #000'}}>{caption.text}</div>}
    </div>
    {!silent && <Audio src={staticFile('audio/master.wav')} volume={(f) => f >= 5880 && f < 5910 ? 0 : 1}/>}
  </AbsoluteFill>;
};
