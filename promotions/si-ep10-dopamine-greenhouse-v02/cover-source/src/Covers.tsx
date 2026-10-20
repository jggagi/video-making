import React from 'react';
import {Img, staticFile} from 'remotion';

const W = 1536;
const H = 2048;
const BG = '#050811';
const WHITE = '#F4F0E8';
const AMBER = '#E8B14B';
const MAGENTA = '#E85CD7';
const CHINESE = '"Hiragino Sans GB", sans-serif';
const METADATA = 'Menlo, "Hiragino Sans GB", monospace';

type CropFrameProps = {
  file: string;
  crop: {x: number; y: number; width: number; height: number};
  box: {x: number; y: number; width: number; height: number};
};

const CropFrame: React.FC<CropFrameProps> = ({file, crop, box}) => {
  const scale = box.width / crop.width;
  const sourceWidth = 2160 * scale;
  const sourceHeight = 3840 * scale;
  return (
    <div
      style={{
        position: 'absolute',
        left: box.x,
        top: box.y,
        width: box.width,
        height: box.height,
        overflow: 'hidden',
        backgroundColor: BG,
      }}
    >
      <Img
        src={staticFile(file)}
        style={{
          position: 'absolute',
          left: -crop.x * scale,
          top: -crop.y * scale,
          width: sourceWidth,
          height: sourceHeight,
          maxWidth: 'none',
        }}
      />
    </div>
  );
};

const Poster = ({children}: {children: React.ReactNode}) => (
  <div
    style={{
      width: W,
      height: H,
      position: 'relative',
      overflow: 'hidden',
      backgroundColor: BG,
    }}
  >
    {children}
  </div>
);

const Footer = ({firstY = 1977, secondY = 2012}: {firstY?: number; secondY?: number}) => (
  <svg
    width={W}
    height={H}
    viewBox={`0 0 ${W} ${H}`}
    style={{position: 'absolute', inset: 0, overflow: 'visible'}}
    aria-label="一眼万年 第二季 · EP.10｜多巴胺温室；未来 SI 思想实验"
  >
    <text
      x={W / 2}
      y={firstY}
      textAnchor="middle"
      dominantBaseline="middle"
      fontFamily={METADATA}
      fontSize={22}
      fontWeight={400}
      letterSpacing={1.4}
      fill={WHITE}
    >
      一眼万年 第二季 · EP.10｜多巴胺温室
    </text>
    <text
      x={W / 2}
      y={secondY}
      textAnchor="middle"
      dominantBaseline="middle"
      fontFamily={METADATA}
      fontSize={19}
      fontWeight={400}
      letterSpacing={2.2}
      fill="#AEB9C8"
    >
      未来 SI 思想实验
    </text>
  </svg>
);

const ATitle = () => (
  <svg
    width={W}
    height={H}
    viewBox={`0 0 ${W} ${H}`}
    style={{position: 'absolute', inset: 0, overflow: 'visible'}}
    aria-label="明明坐在一起只有10厘米，却活在两个永不相交的宇宙"
  >
    <g
      fontFamily={CHINESE}
      fontSize={116}
      fontWeight={700}
      letterSpacing={1.4}
      dominantBaseline="hanging"
    >
      <text x={82} y={180} fill={WHITE}>明明坐在一起</text>
      <text x={82} y={312} fill={AMBER}>只有10厘米，</text>
      <text x={82} y={444} fill={WHITE}>却活在两个</text>
      <text x={82} y={576} fill={WHITE}>永不相交的宇宙</text>
    </g>
  </svg>
);

const BTitle = () => (
  <svg
    width={W}
    height={H}
    viewBox={`0 0 ${W} ${H}`}
    style={{position: 'absolute', inset: 0, overflow: 'visible'}}
    aria-label="当AI为你定制“完美楚门世界”，你还想醒来吗？"
  >
    <g
      fontFamily={CHINESE}
      fontSize={116}
      fontWeight={700}
      letterSpacing={1.1}
      dominantBaseline="hanging"
    >
      <text x={78} y={200} fill={WHITE}>
        <tspan>当</tspan><tspan fill={AMBER}>AI</tspan><tspan>为你定制</tspan>
      </text>
      <text x={78} y={350} fill={MAGENTA}>“完美楚门世界”，</text>
      <text x={78} y={500} fill={WHITE}>
        <tspan>你还想</tspan><tspan fill={AMBER}>醒来</tspan><tspan>吗？</tspan>
      </text>
    </g>
  </svg>
);

export const CoverA: React.FC = () => (
  <Poster>
    <CropFrame
      file="frame-02.png"
      crop={{x: 240, y: 1150, width: 1500, height: 1120}}
      box={{x: 83, y: 865, width: 1370, height: 1023}}
    />
    <ATitle />
    <Footer />
  </Poster>
);

export const CoverB: React.FC = () => (
  <Poster>
    <CropFrame
      file="frame-01.png"
      crop={{x: 128, y: 1020, width: 1688, height: 1300}}
      box={{x: 50, y: 850, width: 1436, height: 1106}}
    />
    <BTitle />
    <Footer firstY={1982} secondY={2014} />
  </Poster>
);
