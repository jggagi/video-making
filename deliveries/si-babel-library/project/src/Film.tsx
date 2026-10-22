import React, {useEffect, useState} from 'react';
import {AbsoluteFill, Audio, staticFile, useCurrentFrame, useVideoConfig, delayRender, continueRender} from 'remotion';
import timing from '../audio-timing.json';
import {Geometry} from './Geometry';

const PAPER = '#EFECE6';
const INK = '#1D3557';
const RED = '#E63946';
const SLATE = '#6C7780';

type FilmProps = {silent?: boolean; cover?: false | 'A'};
type Caption = {startFrame: number; endFrame: number; text: string};

const headlineFor = (frame: number) => {
  if (frame < 1380) return '你一生的灵感，\n已被提前编号';
  if (frame < 2040) return '早在某一页，\n等你以为是新作';
  if (frame < 2880) return '所有杰作，\n混在无尽乱码里';
  if (frame < 3540) return '有限的组合';
  if (frame < 4260) return '有限，\n不等于算得完';
  if (frame < 5040) return '0.5 秒，\n一万年的旋律';
  if (frame < 5520) return '十万亿册，\n只是一个目录';
  return '最后一笔，\n也已收录';
};

export const Film: React.FC<FilmProps> = ({silent = false, cover = false}) => {
  const [fontHandle] = useState(() => delayRender("Local fonts ready"));
  useEffect(() => {document.fonts.ready.then(() => continueRender(fontHandle));}, [fontHandle]);
  const frame = useCurrentFrame();
  const {width} = useVideoConfig();
  const isCover = cover === 'A';
  const sceneFrame = isCover ? 240 : frame;
  const captions = timing.captions as unknown as Caption[];
  const caption = !isCover ? captions.find((item) => sceneFrame >= item.startFrame && sceneFrame < item.endFrame) : undefined;
  const scale = width / 1080;

  return (
    <AbsoluteFill style={{backgroundColor: PAPER, color: INK, fontFamily: '"PingFang SC", "Noto Sans CJK SC", sans-serif'}}>
      <div style={{position: 'absolute', left: 0, top: 0, width: 1080, height: 1920, transform: `scale(${scale})`, transformOrigin: 'top left'}}>
        <svg width="1080" height="1920" viewBox="0 0 1080 1920" style={{position: 'absolute', inset: 0}}>
          <defs>
            <pattern id="paper-speckle" width="34" height="34" patternUnits="userSpaceOnUse">
              <circle cx="5" cy="8" r="0.7" fill="#CFC6B8" opacity="0.33" />
              <circle cx="26" cy="21" r="0.55" fill="#B8B1A7" opacity="0.27" />
              <path d="M14 30h5" stroke="#D6C8B7" strokeWidth="0.55" opacity="0.3" />
            </pattern>
          </defs>
          <rect width="1080" height="1920" fill={PAPER} />
          <rect width="1080" height="1920" fill="url(#paper-speckle)" />
          <Geometry frame={sceneFrame} cover={isCover} />
          <path d="M64 178H920" stroke="#A8ADA0" strokeWidth="1.2" />
        </svg>

        <div style={{position: 'absolute', left: 64, top: 91, width: 250, fontSize: 28, lineHeight: '38px', fontWeight: 600, letterSpacing: 1, whiteSpace: 'nowrap'}}>
          感受 SI · 审美暴击
        </div>
        <div style={{position: 'absolute', left: 385, top: 93, width: 290, textAlign: 'center', fontSize: 25, lineHeight: '36px', color: SLATE, whiteSpace: 'nowrap'}}>
          巴别图书馆的尽头
        </div>
        <div style={{position: 'absolute', left: 735, top: 87, width: 185, height: 43, display: 'flex', alignItems: 'center', justifyContent: 'center', border: `1px solid ${INK}`, color: INK, fontSize: 28, lineHeight: '34px', letterSpacing: 1, whiteSpace: 'nowrap'}}>
          科幻思想实验
        </div>

        {!isCover && sceneFrame >= 6780 ? (
          <div style={{position: 'absolute', left: 110, top: 658, width: 800, minHeight: 208, boxSizing: 'border-box', padding: '30px 26px', backgroundColor: 'rgba(239,236,230,0.96)', color: INK, textAlign: 'center', fontFamily: '"Songti SC", "Noto Serif CJK SC", serif', fontSize: 68, lineHeight: '78px', fontWeight: 600, letterSpacing: 2}}>
            所有美都被写完后，<br />你还愿意创造吗？
          </div>
        ) : (
          <div style={{position: 'absolute', left: 64, top: isCover ? 248 : 238, width: 856, minHeight: 162, fontSize: isCover ? 74 : 70, lineHeight: isCover ? '92px' : '84px', fontWeight: 700, letterSpacing: 1.5, whiteSpace: 'pre-line', color: INK}}>
            {isCover ? '你一生的灵感，\n已被提前编号' : headlineFor(sceneFrame)}
          </div>
        )}

        {!isCover && sceneFrame >= 2880 && sceneFrame < 3540 && (
          <div style={{position: 'absolute', left: 130, top: 1340, width: 820, textAlign: 'center', color: INK, fontSize: 31, lineHeight: '40px', letterSpacing: 2}}>
            固定长度 · 固定精度
          </div>
        )}

        {!isCover && sceneFrame >= 6780 && <div style={{position:"absolute",left:110,top:1350,width:800,textAlign:"center",fontSize:34,letterSpacing:3,color:INK}}>巴别图书馆的尽头</div>}

        {!isCover && caption && (
          <div data-caption style={{position: 'absolute', left: 70, top: 1442, width: 840, minHeight: 210, boxSizing: 'border-box', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '2px 10px', color: INK, fontSize: 50, lineHeight: '54px', fontWeight: 600, textAlign: 'center', whiteSpace: 'pre-line'}}>
            {caption.text}
          </div>
        )}
      </div>
      {!silent && !isCover && <Audio src={staticFile('audio/master.wav')} />}
    </AbsoluteFill>
  );
};
